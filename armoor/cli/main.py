"""Command-line interface for armoor."""
import ast
import re
import gc
import os
import json
import weakref
import warnings
from contextlib import contextmanager
from typing import List, Union, Any, Tuple, Optional
from argparse import ArgumentParser
from configobj import ConfigObj
from dask.distributed import Client, as_completed, wait
from concurrent.futures import ThreadPoolExecutor
import traceback
from concurrent.futures import TimeoutError
import asyncio
import time
import dask
import logging
from pathlib import Path
from xoa.cfgm import ConfigManager, register_validation_functions

from armoor import ArmoorError
from armoor.cli import COMP_INI, METAZONES_INI
from armoor.base import FILTERS
from armoor.base.io import ArmoorArgumentHelpFormatter, create_fast_encoding
from armoor.base.log import add_logging_parser_arguments, main_setup_logging
from armoor.base.misc import string_to_tuples_float, optimize_for_low_swap
import armoor.base.oceanvars
from armoor.comp import METAZONE_PARAMS
from armoor.comp.io import to_netcdf_ref_prods
from armoor.comp.coloc import main_coloc
from armoor.comp.output import main_output
from armoor.comp.plot import main_plot
from armoor.data.open_decode import register_cf, open_decode

logger = logging.getLogger(__name__)

logging.getLogger('distributed').setLevel(logging.ERROR)

def parse_mixed_param(param_value: Union[str, List]) -> List:
    """
    Parse a ConfigObj parameter that contains strings and lists mixed together.
    Returns all elements in their original order.
    
    Handles formats like:
    - param1 = "toto", [10, 20, 100]
    - param1 = "tutu", "toto", [10, 20, 100]
    - param1 = [10, 20, 100], "toto"
    - param1 = ["toto", [10, 20, 100]]
    - param1 = "product","depth",[(0, 100), (400, 500)]
    
    Parameters
    ----------
    param_value : Union[str, List]
        ConfigObj parameter value (can be string or already parsed list)
        
    Returns
    -------
    List
        List containing all elements (strings and lists) in original order
        
    Raises
    ------
    ValueError
        If the parameter format is invalid
        
    Examples
    --------
    >>> parse_mixed_param('"toto", [10, 20, 100]')
    ['toto', [10, 20, 100]]
    
    >>> parse_mixed_param('"tutu", "toto", [10, 20, 100]')
    ['tutu', 'toto', [10, 20, 100]]
    
    >>> parse_mixed_param(['tutu', 'toto', [10, 20, 100]])
    ['tutu', 'toto', [10, 20, 100]]
    
    >>> parse_mixed_param('"product","depth",[(0, 100), (400, 500)]')
    ['product', 'depth', [(0, 100), (400, 500)]]
    """
    if isinstance(param_value, str):
        return _parse_string_format(param_value)
    elif isinstance(param_value, list):
        return _parse_list_format(param_value)
    else:
        raise ValueError(f"Unsupported parameter type: {type(param_value)}")


def _parse_string_format(param_str: str) -> List:
    """Parse string format and return all elements in order."""
    param_str = param_str.strip()
    
    result = []
    i = 0
    current_token = ""
    in_quotes = False
    quote_char = None
    
    while i < len(param_str):
        char = param_str[i]
        
        # Handle quotes
        if char in ['"', "'"] and (quote_char is None or char == quote_char):
            if not in_quotes:
                in_quotes = True
                quote_char = char
            elif char == quote_char:
                in_quotes = False
                quote_char = None
            current_token += char
        
        # Handle list start
        elif char == '[' and not in_quotes:
            # Save current token if it exists
            if current_token.strip():
                cleaned_token = _clean_string_value(current_token.strip().rstrip(','))
                if cleaned_token:
                    result.append(cleaned_token)
                current_token = ""
            
            # Find matching closing bracket
            bracket_count = 1
            list_start = i
            i += 1
            
            while i < len(param_str) and bracket_count > 0:
                if param_str[i] == '[':
                    bracket_count += 1
                elif param_str[i] == ']':
                    bracket_count -= 1
                i += 1
            
            if bracket_count > 0:
                raise ValueError(f"Unmatched opening bracket at position {list_start}")
            
            # Extract and parse the list
            list_str = param_str[list_start:i]
            try:
                list_value = ast.literal_eval(list_str)
                if isinstance(list_value, list):
                    result.append(list_value)
                else:
                    raise ValueError(f"Expected list, got {type(list_value)}")
            except (ValueError, SyntaxError) as e:
                raise ValueError(f"Invalid list format '{list_str}': {e}")
            
            # Skip any following comma and whitespace
            while i < len(param_str) and param_str[i] in ', \t':
                i += 1
            continue
        
        # Handle comma (separator)
        elif char == ',' and not in_quotes:
            if current_token.strip():
                cleaned_token = _clean_string_value(current_token.strip())
                if cleaned_token:
                    result.append(cleaned_token)
            current_token = ""
        
        # Regular character
        else:
            current_token += char
        
        i += 1
    
    # Handle last token
    if current_token.strip():
        cleaned_token = _clean_string_value(current_token.strip())
        if cleaned_token:
            result.append(cleaned_token)
    
    return result


def _parse_list_format(param_list: List) -> List:
    """Parse list format and return all elements as-is."""
    if len(param_list) < 1:
        raise ValueError(f"Parameter must contain at least 1 element, got {len(param_list)}")
    
    # Clean string elements but keep everything in order
    result = []
    for element in param_list:
        if isinstance(element, str):
            result.append(_clean_string_value(element))
        else:
            result.append(element)
    
    return result


def _clean_string_value(string_part: str) -> str:
    """Remove quotes and clean string value."""
    string_part = string_part.strip()
    
    # Remove outer quotes if present
    if ((string_part.startswith('"') and string_part.endswith('"')) or 
        (string_part.startswith("'") and string_part.endswith("'"))):
        string_part = string_part[1:-1]
    
    return string_part


def parse_multiple_params(config_dict: dict, param_names: List[str]) -> dict:
    """
    Parse multiple ConfigObj parameters that follow the mixed format.
    
    Parameters
    ----------
    config_dict : dict
        Dictionary containing configuration parameters
    param_names : List[str]
        Names of parameters to parse as mixed format
        
    Returns
    -------
    dict
        Dictionary with parsed parameters as lists
        
    Examples
    --------
    >>> config = {
    ...     'param1': '"toto", [10, 20, 100]',
    ...     'param2': '"tutu", "toto", [10, 20, 100]',
    ...     'vrange': '"product","depth",[(0, 100), (400, 500)]',
    ...     'other': 'normal_param'
    ... }
    >>> parse_multiple_params(config, ['param1', 'param2', 'vrange'])
    {'param1': ['toto', [10, 20, 100]], 'param2': ['tutu', 'toto', [10, 20, 100]], 'vrange': ['product', 'depth', [(0, 100), (400, 500)]]}
    """
    result = {}
    
    for param_name in param_names:
        if param_name in config_dict:
            try:
                result[param_name] = parse_mixed_param(config_dict[param_name])
            except ValueError as e:
                raise ValueError(f"Error parsing parameter '{param_name}': {e}")
        else:
            raise KeyError(f"Parameter '{param_name}' not found in configuration")
    
    return result


def validate_mixed_param_types(parsed_list: List, 
                             expected_string_count: Optional[int] = None,
                             expected_list_count: Optional[int] = None) -> bool:
    """
    Validate the types of parsed mixed parameter.
    
    Parameters
    ----------
    parsed_list : List
        Parsed list containing strings and lists
    expected_string_count : int, optional
        Expected number of string elements
    expected_list_count : int, optional
        Expected number of list elements
        
    Returns
    -------
    bool
        True if validation passes
        
    Raises
    ------
    TypeError
        If validation fails
    """
    if not isinstance(parsed_list, list):
        raise TypeError(f"Parsed parameter must be a list, got {type(parsed_list)}")
    
    string_count = sum(1 for item in parsed_list if isinstance(item, str))
    list_count = sum(1 for item in parsed_list if isinstance(item, list))
    
    if expected_string_count is not None and string_count != expected_string_count:
        raise TypeError(f"Expected {expected_string_count} strings, got {string_count}")
    
    if expected_list_count is not None and list_count != expected_list_count:
        raise TypeError(f"Expected {expected_list_count} lists, got {list_count}")
    
    return True

def parse_coords(s):
    """
    Parse a string into latitude and longitude coordinates.
    
    Parameters
    ----------
    s: str
        A string representing the coordinates in the format "lat,lon".
    
    Returns
    -------
    tuple: A tuple containing the latitude and longitude as floats.
    
    Raises
    ------
        ArmoorError: If the string is not in the correct format.
    """
    try:
        return string_to_tuples_float(",".join(s))
    except:
        raise ArmoorError("Coordinates must be a list of tuples (lat,lon)")

register_validation_functions(coordinates=parse_coords)
register_validation_functions(mlist=parse_mixed_param)

def comma_separated(sarg):
    """Parse a string of comma-separated list."""
    return [a.strip() for a in sarg.split(",")]

def check_metazones_in(metazones_arg, metazones_cfg, func_param=None, **kwargs):
    """Check if all metazone-names given in command-line are present in cfgfile.

    This function checks if all elements of the first list are present in the
    second list. If any element from the first list is not found in the second
    list, it raises a ValueError.

    Parameters
    ----------
    metazones_arg : list
        List of metazones given in the command-line.
    metazones_cfg:
        List of metazones given in the cfgfile.
    func_param: list
        List of parameters available regarding the current functionnality.

    Raises
    ------
        ValueError: If any element of list1 is not found in list2.
    """
    metazones_bad = []
    for metazone in metazones_arg:
        if metazone not in metazones_cfg:
            metazones_bad.append(metazone)           
    if len(metazones_bad) > 0:
        raise ArmoorError(
            f"Missing metazones in cfgfile: {metazones_bad}."
            )
    if kwargs:
        for metazone in metazones_arg:
            metazones_cfg[metazone].update(kwargs)
    metazones = {}
    for metazone in metazones_arg:
        for k, v in metazones_cfg[metazone].items():
            if v == None:
                del metazones_cfg[metazone][k]
        metazones[metazone] = metazones_cfg[metazone]
    if func_param:
        for metazone_name, metazone_param in metazones.items():
            for k, v in metazone_param.items():
                if (k != "name") and (k not in func_param):
                    logger.warning(
                        f"{k} cannot be defined to use this functionnality.\n"
                        f"{k} is removed to run this functionnality."
                    )
                    del metazones[metazone_name][k]
                # if (k == "polygon") and ("href" in metazone_param.keys()):
                #     metazones[metazone_name].update({
                #         "polygon_dilat": metazones[metazone_name].get("polygon")
                #         })
                #     del metazones[metazone_name]["polygon"]
    return metazones

def main_open_datasets(cfg: ConfigObj):
    """Open and decode list of data.
    
    Parameters
    ----------
    cfg: ConfigObj
        List of data to be opened and decoded.
    
    Return
    ------
    dss: list
        List of datasets.
    """
    if not cfg:
        raise ArmoorError(
            "Data section empty: Check [data] in your cfgfile."
            )
    register_cf()
    dss = []
    data_ref = {}
    for _, cfg_data in cfg.items():
        ds = open_decode(
            cfg_data["path"],
            fmt=cfg_data["fmt"],
            platform=cfg_data["platform"]
            )
        # ds = optimize_for_low_swap(ds, target_chunk_mb=8)
        #ds.attrs["data_name"] = cfg_data["name"]
        ds.attrs["data_ref"] = str(cfg_data["ref"])
        data_ref.update({
            cfg_data["name"]: str(cfg_data["ref"])
            })
        dss.append(ds)
        ds.close()
    return dss, data_ref


def get_parser_metazones():
    """Get parser for sst comparison."""
    # Setup argument parser
    parser = ArgumentParser(
        description="Apply filters over metazones.",
        formatter_class=ArmoorArgumentHelpFormatter,
        )
    add_logging_parser_arguments(parser)
    parser.add_argument(
        'metazones',
        type=comma_separated,
        help="List of metazone to be processed."
        )
    parser.add_argument(
        'cfgfile',
        type=Path,
        help="Path of the configuration file."
        )
    parser.add_argument(
        '-m', '--metazonesfile',
        type=Path,
        help="Path of the configuration file dedicated to the description of metazones.",
        default="metazones.cfg"
        )
    parser.add_argument(
        '--jsonfile',
        type=Path,
        help="Path of the output json file.",
        default='ncs_metazones.json'
        )
    
    return parser

def main_metazones():
    """Apply filters over metazones."""
    # Get parser
    parser = get_parser_metazones()

    # Parse
    args = parser.parse_args()
    
    # Setup logging
    main_setup_logging(args)

    # Load configuration
    if not args.cfgfile.exists():
        raise ArmoorError(
            f"File not found: {args.cfgfile}."
            )
    
    cfg = ConfigManager(COMP_INI).load(str(args.cfgfile))
    metazones = ConfigManager(METAZONES_INI).load(str(args.metazonesfile))
    
    metazones = check_metazones_in(
       args. metazones,
       metazones
       )

    logger.info(f"🚀 Processing {len(cfg['data'])} datasets × {len(metazones)} metazones")
    
    register_cf()
    
    ncs = load_datasets_sequential(cfg["data"], metazones, None)

    with open(args.jsonfile, 'w') as f:
        json.dump(ncs, f, indent=4)


def main_comp(cfgfile, metafile, metazones, func_comp, comp_args):
    
    logger.info("🔍 DIAGNOSTIC INITIAL:")
    monitor_performance()
    
    start_time = time.time()
    
    
    cfg = ConfigManager(COMP_INI).load(str(cfgfile))
    metas = ConfigManager(METAZONES_INI).load(str(metafile))

    
    if not cfg:
        raise ArmoorError("Data section empty: Check [data] in your cfgfile.")
    # Metazones
    
    metazones = check_metazones_in(
        metazones,
        metas,
        func_param=METAZONE_PARAMS[func_comp],
        **comp_args
        )

    logger.info(f"🚀 Processing {len(cfg['data'])} datasets × {len(metazones)} metazones")
    
    register_cf()
    
    ncs = load_datasets_sequential(cfg["data"], metazones, func_comp)
    
    ncs_coloc = main_coloc(ncs, metazones, func_comp)

    ncs_outputs = main_output(ncs_coloc, metazones, cfg.get("outputs"), func_comp)
    
    # with open('ncs_outputs.json', 'w') as f:
    #     json.dump(ncs_outputs, f, indent=4)
    
    # with open('ncs_outputs.json', 'r', encoding='utf-8') as file:
    #     ncs_outputs = json.load(file)
    
    main_plot(ncs_outputs, metazones, func_comp)

    elapsed = time.time() - start_time
    logger.info(f"🎯 TRAITEMENT TERMINÉ EN {elapsed:.1f} SECONDES")    
    
    logger.info("🔍 DIAGNOSTIC FINAL:")
    monitor_performance()


def get_parser_comp_models():
    """Get parser for models comparison."""
    # Setup argument parser
    parser = ArgumentParser(
        description="Compare models ouputs.",
        formatter_class=ArmoorArgumentHelpFormatter,
        )
    add_logging_parser_arguments(parser)
    parser.add_argument(
        'metazones',
        type=comma_separated,
        help="List of metazone to be processed."
        )
    parser.add_argument(
        'cfgfile',
        type=Path,
        help="Path of the configuration file."
        )
    parser.add_argument(
        '-m', '--metazonesfile',
        type=Path,
        help="Path of the configuration file dedicated to the description of metazones.",
        default="metazones.cfg"
        )
    
    return parser

def main_comp_models():
    """Compare a model reference with other products."""
    
    # Get parser
    parser = get_parser_comp_sst()
    func_comp = "comp_models"

    # Parse
    args = parser.parse_args()
    
    # Setup logging
    main_setup_logging(args)

    # Load configuration
    if not args.cfgfile.exists():
        raise ArmoorError(
            f"File not found: {args.cfgfile}."
            )
    main_comp(args.cfgfile, args.metazonesfile, args.metazones, func_comp, {})


def get_parser_comp_sst():
    """Get parser for sst comparison."""
    # Setup argument parser
    parser = ArgumentParser(
        description="Compare sst satellite with model ouputs.",
        formatter_class=ArmoorArgumentHelpFormatter,
        )
    add_logging_parser_arguments(parser)
    parser.add_argument(
        'metazones',
        type=comma_separated,
        help="List of metazone to be processed."
        )
    parser.add_argument(
        'cfgfile',
        type=Path,
        help="Path of the configuration file."
        )
    parser.add_argument(
        '--qc',
        type=dict,
        default=None,
        help="Dictionnary specifying quality tresholds, ex: ptemp:1,7"
        )
    parser.add_argument(
        '-m', '--metazonesfile',
        type=Path,
        help="Path of the configuration file dedicated to the description of metazones.",
        default="metazones.cfg"
        )
    
    return parser

def main_comp_sst():
    """Compare sst reference with other products."""
    
    # Get parser
    parser = get_parser_comp_sst()
    func_comp = "comp_sst"

    # Parse
    args = parser.parse_args()
    
    # Setup logging
    main_setup_logging(args)

    # Load configuration
    if not args.cfgfile.exists():
        raise ArmoorError(
            f"File not found: {args.cfgfile}."
            )
    kw_comp = {"qc": args.qc}    
    main_comp(args.cfgfile, args.metazonesfile, args.metazones, func_comp, kw_comp)
    
def get_parser_comp_argo():
    """Get parser for argo comparison."""
    # Setup argument parser
    parser = ArgumentParser(
        description="Compare argo data with model ouputs.",
        formatter_class=ArmoorArgumentHelpFormatter,
        )
    add_logging_parser_arguments(parser)
    parser.add_argument(
        'metazones',
        type=comma_separated,
        help="List of metazone to be processed."
        )
    parser.add_argument(
        'radius',
        type=float,
        help="Radius (in km) of the disk around an observation within which model data are taken into account"
        )
    parser.add_argument(
        'cfgfile',
        type=Path,
        help="Path of the configuration file."
        )
    parser.add_argument(
        '--qc',
        type=dict,
        default=None,
        help="Dictionnary specifying quality tresholds, ex: ptemp:1,7"
        )
    parser.add_argument(
        '-m', '--metazonesfile',
        type=Path,
        help="Path of the configuration file dedicated to the description of metazones.",
        default="metazones.cfg"
        )
    
    return parser

def main_comp_argo():
    """Compare argo with other products - Version optimisée."""
        
    # Get parser
    parser = get_parser_comp_argo()
    func_comp = "comp_argo"

    # Parse
    args = parser.parse_args()
    
    # Setup logging
    main_setup_logging(args)
    
    # Load configuration
    if not args.cfgfile.exists():
        raise ArmoorError(f"File not found: {args.cfgfile}.")
    
    kw_comp = {"radius": args.radius, "qc": args.qc}
    
    main_comp(args.cfgfile, args.metazonesfile, args.metazones, func_comp, kw_comp)

def get_parser_comp_mooring():
    """Get parser for mooring comparison."""
    # Setup argument parser
    parser = ArgumentParser(
        description="Compare mooring data with model ouputs.",
        formatter_class=ArmoorArgumentHelpFormatter,
        )
    add_logging_parser_arguments(parser)
    parser.add_argument(
        'metazones',
        type=comma_separated,
        help="List of metazone to be processed."
        )
    parser.add_argument(
        'radius',
        type=float,
        help="Radius (in km) of the disk around an observation within which model data are taken into account"
        )
    parser.add_argument(
        'cfgfile',
        type=Path,
        help="Path of the configuration file."
        )
    parser.add_argument(
        '--qc',
        type=dict,
        default=None,
        help="Dictionnary specifying quality tresholds, ex: ptemp:1,7"
        )
    parser.add_argument(
        '-m', '--metazonesfile',
        type=Path,
        help="Path of the configuration file dedicated to the description of metazones.",
        default="metazones.cfg"
        )
    
    return parser

def main_comp_mooring():
    """Compare argo with other products - Version optimisée."""
        
    # Get parser
    parser = get_parser_comp_mooring()
    func_comp = "comp_mooring"

    # Parse
    args = parser.parse_args()
    
    # Setup logging
    main_setup_logging(args)
    
    # Load configuration
    if not args.cfgfile.exists():
        raise ArmoorError(f"File not found: {args.cfgfile}.")
    
    kw_comp = {"radius": args.radius, "qc": args.qc}
    
    main_comp(args.cfgfile, args.metazonesfile, args.metazones, func_comp, kw_comp)
    
    
def load_datasets_sequential(data_cfg, metazones, func_comp):
    """Charge les datasets de manière séquentielle (< 10s chacun)."""
    ncouts = []
    for data_key, cfg_data in data_cfg.items():
        datasets = {}
        dataset_name = cfg_data["name"]
        logger.info(f"📥 Chargement {dataset_name}...")
        
        start_time = time.time()
        
        # Chargement optimisé
        #with setup_dask_client():
        
        dss = open_decode(
            cfg_data["path"],
            fmt=cfg_data["fmt"],
            platform=cfg_data["platform"]
        )

        if not isinstance(dss, list):
            dss = [dss]

        for ids, ds in enumerate(dss):
            # Chunking optimal pour dimensions (121,40,500,500)

            ds = optimize_chunks_for_dimensions(ds)
            
            # Métadonnées
            if len(dss) == 1:
                ds.attrs["data_name"] = cfg_data["name"]
            else:
                ds.attrs["data_name"] = f"{cfg_data['name']}_{ds.attrs['name']}"
            ds.attrs["data_ref"] = str(cfg_data["ref"])
            dss[ids] = ds
        
        elapsed = time.time() - start_time
        logger.info(f"✅ {dataset_name} load in {elapsed:.1f}s")
        
        datasets[dataset_name] = {
            'dataset': dss if len(dss) > 1 else dss[0],
            'config': cfg_data,
            'load_time': elapsed
        }

        ncs = process_all_combinations(datasets, metazones, func_comp)
        ncouts += ncs
        
    total_datasets = len(datasets)
    logger.info(f"📊 {total_datasets} datasets chargés avec succès")

    return ncouts

def optimize_chunks_for_dimensions(ds):
    """Optimise le chunking pour les dimensions (121,40,500,500)."""
    
    # Chunks optimaux basés sur vos dimensions
    optimal_chunks = {}
    
    for dim_name, dim_size in ds.sizes.items():
        if dim_name == 'time':
            # Time: garder entier si < 200, sinon chunker
            optimal_chunks[dim_name] = min(121, dim_size)
        elif dim_name == 'z':
            # Z: garder entier si petit
            optimal_chunks[dim_name] = min(40, dim_size)
        elif dim_name in ['y', 'lat', 'latitude']:
            # Y: chunker en 2-4 parties
            optimal_chunks[dim_name] = min(250, dim_size)
        elif dim_name in ['x', 'lon', 'longitude']:
            # X: chunker en 2-4 parties
            optimal_chunks[dim_name] = min(250, dim_size)
        else:
            # Autres dimensions: chunks adaptatifs
            optimal_chunks[dim_name] = min(100, dim_size)
    
    logger.debug(f"Chunks optimaux: {optimal_chunks}")
    
    # Appliquer le chunking
    try:
        ds = ds.chunk(optimal_chunks)
        # Optimiser pour réduire le swap
        ds = optimize_for_low_swap(ds, target_chunk_mb=128)  # 128MB par chunk
    except Exception as e:
        logger.warning(f"Erreur chunking: {e}")
        # Fallback: chunking simple
        ds = optimize_for_low_swap(ds, target_chunk_mb=256)
    
    return ds

def process_all_combinations(datasets, metazones, func_comp):
    """Traite toutes les combinaisons dataset×metazone en parallèle."""
    client = setup_dask_client()
    ncouts = []
    for dataset_name, dataset_info in datasets.items():
        for mz_name, mz_param in metazones.items():
            dss = dataset_info['dataset']
            if not isinstance(dss, list):
                dss = [dss]
            for ds in dss:
                dsout = process_single_combination(
                        ds,
                        dataset_info['config'],
                        mz_name,
                        mz_param,
                        func_comp
                    )
                if dsout:
                    ncout = save_result(dsout, mz_name, func_comp)
                    ncouts.append(ncout)
    client.close()
    return ncouts

def process_single_combination(ds, cfg_data, mz_name, mz_param, func_comp):
    """Version améliorée avec gestion d'erreurs robuste."""
    
    combination_id = f"{cfg_data['name']}_{mz_name}"
    start_time = time.time()
    dsout = None
    try:
        logger.info(f"🔄 Traitement {combination_id}")
        
        # Vérifier que les données sont disponibles
        if ds is None:
            logger.error(f"Dataset None pour {combination_id}")
            return None
        
        # Copier le dataset pour éviter les modifications
        dsout = ds.copy(deep=True)  # Deep copy pour éviter les références
        data_name = dsout.attrs["data_name"]#cfg_data["name"]
        data_ref = str(cfg_data["ref"])
        
        # Appliquer les filtres avec gestion d'erreurs
        try:
            dsout = apply_time_filters(dsout, mz_param, data_name)
            if dsout is None:
                return None
        except Exception as e:
            logger.error(f"Erreur filtre temporel {combination_id}: {e}")
            return None
        
        try:
            dsout = apply_horizontal_filters(dsout, mz_param, data_name)
            if dsout is None:
                return None
        except Exception as e:
            logger.error(f"Erreur filtre horizontal {combination_id}: {e}")
            return None
        
        # Métadonnées finales
        dsout.attrs = {
            "data_name": data_name,
            "data_ref": data_ref,
        }
        
    except Exception as e:
        elapsed = time.time() - start_time
        logger.error(f"❌ Erreur {combination_id} après {elapsed:.1f}s: {e}")
        return None
    finally:
        return dsout
        # Nettoyage mémoire robuste
        if dsout is not None:
            try:
                dsout.close()
                del dsout
            except:
                pass

def apply_time_filters(dsout, mz_param, data_name):
    """Applique les filtres temporels."""
    time_meta = ["tbound", "terms", "trange_cut"]
    
    for k in time_meta:
        if k in mz_param:
            if "climatology" not in dsout.time.attrs:
                dsout = FILTERS[k](dsout)(*mz_param[k])
            if dsout is None:
                logger.warning(f"⚠️ Filtre {k} returns None for {data_name}")
                return None
    
    return dsout

def apply_horizontal_filters(dsout, mz_param, data_name):
    """Applique les filtres horizontaux."""
    horizontal_meta = ["bathy", "polygon"]#, "polygon_dilat"]
    
    for k in horizontal_meta:
        if k in mz_param:
            if k == "polygon":
                args = mz_param[k]
                if set(["x", "y"]).issubset(set(dsout.lon.dims)):
                    k = "polygon_dilat"
            else:
                args = (*mz_param[k],)
            
            dsout = FILTERS[k](dsout)(args)
            if dsout is None:
                logger.warning(f"⚠️ Filtre {k} returns None for {data_name}")
                return None
    return dsout

def save_result(dsout, mz_name, func_comp):
    """Sauvegarde optimisée (< 30s)."""
    
    # Préparer les chemins
    refprod = "ref" if dsout.attrs["data_ref"] == "True" else "prod"
    data_name = dsout.attrs["data_name"]
    parent_dir = f"{func_comp}/metazones" if func_comp else "metazones"
    ncpat = "{mz_name}/{data_name}/{refprod}_{data_name}.nc"
    nc = Path(parent_dir) / ncpat.format(**locals())
    nc.parent.mkdir(parents=True, exist_ok=True)
    
    # Encoding optimisé pour la vitesse
    encoding = create_fast_encoding(dsout)
    
    #Sauvegarde avec optimisations
    dsout.to_netcdf(
        nc,
        encoding=encoding,
        format='NETCDF4',
        engine='netcdf4',
        compute=True  # Forcer le compute immédiat
        )
    
    logger.debug(f"💾 Sauvegardé: {nc}")
    return str(nc)

# Fonction de diagnostic pour surveiller les performances
def monitor_performance():
    """Surveille les performances du système."""
    try:
        import psutil
        
        # Mémoire
        memory = psutil.virtual_memory()
        swap = psutil.swap_memory()
        
        logger.info(f"💾 Mémoire: {memory.percent:.1f}% utilisée ({memory.available/1e9:.1f}GB libre)")
        logger.info(f"🔄 Swap: {swap.percent:.1f}% utilisé ({swap.free/1e9:.1f}GB libre)")
        
        # CPU
        cpu_percent = psutil.cpu_percent(interval=1)
        logger.info(f"⚡ CPU: {cpu_percent:.1f}% utilisé")
        
        # Alertes
        if memory.percent > 90:
            logger.warning("⚠️ Mémoire critique (>90%)")
        if swap.percent > 50:
            logger.warning("⚠️ Swap élevé (>50%)")
            
    except ImportError:
        logger.debug("psutil non disponible")
    except Exception as e:
        logger.debug(f"Erreur monitoring: {e}")


# Configuration Dask recommandée
def setup_dask_client():
    """Configure le client Dask de manière robuste."""
    
    # Configuration optimale
    dask.config.set({
        'distributed.worker.daemon': False,
        'distributed.comm.timeouts.connect': '120s',
        'distributed.comm.timeouts.tcp': '120s',
        'distributed.worker.memory.target': 0.9,
        'distributed.worker.memory.spill': 0.8,
        'distributed.worker.memory.pause': 0.9,
        'distributed.worker.memory.terminate': 0.95,
        'distributed.worker.memory.monitor-interval': '100ms',
        'distributed.scheduler.allowed-failures': 2,
        'distributed.scheduler.work-stealing': True,
    })
    
    client = Client(
        n_workers=4,  # Réduire le nombre de workers
        threads_per_worker=4,
        memory_limit='18GB',
        silence_logs=True,
        dashboard_address=':8787'
    )
    
    return client