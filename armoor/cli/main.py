"""Command-line interface for armoor."""
import gc
import json
import logging
import time
from argparse import ArgumentParser
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

from xoa.cfgm import ConfigManager, register_validation_functions

import armoor.base.oceanvars
from armoor import ArmoorError
from armoor.base.io import (ArmoorArgumentHelpFormatter, create_fast_encoding,
                            setup_dask_client, zarrs2netcdfs)
from armoor.base.log import add_logging_parser_arguments, main_setup_logging
from armoor.base.misc import (comma_separated, dict_to_list,
                              optimize_for_low_swap, parse_coords,
                              parse_mixed_param, parse_qc_tuple)
from armoor.cli import COMP_INI, DATA_INI, METAZONES_INI
from armoor.comp import METAZONE_PARAMS
from armoor.comp.coloc import main_coloc
from armoor.comp.misc import add_comp_parser_arguments
from armoor.comp.output import main_output as output_comp
from armoor.comp.plot import main_plot as plot_comp
from armoor.data.load import load_datasets
from armoor.data.output import main_output as output_data
from armoor.data.plot import main_plot as plot_data

logger = logging.getLogger(__name__)

logging.getLogger('distributed').setLevel(logging.ERROR)

register_validation_functions(coordinates=parse_coords)
register_validation_functions(mlist=parse_mixed_param)


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

def get_parser_filters():
    """Get parser for filtering."""
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
        default='ncs_filter.json'
        )
    
    return parser

def main_filters():
    """Apply filters over metazones."""
    # Get parser
    parser = get_parser_filters()

    # Parse
    args = parser.parse_args()
    
    # Setup logging
    main_setup_logging(args)

    # Load configuration
    if not args.cfgfile.exists():
        raise ArmoorError(
            f"File not found: {args.cfgfile}."
            )
    
    cfg = ConfigManager(DATA_INI).load(str(args.cfgfile))
    metazones = ConfigManager(METAZONES_INI).load(str(args.metazonesfile))
    
    metazones = check_metazones_in(
       args. metazones,
       metazones
       )

    logger.info(f"🚀 Processing {len(cfg['data'])} datasets × {len(metazones)} metazones")
    
    zarrs = load_datasets(cfg["data"], metazones, None)

    ncs = zarrs2netcdfs(zarrs)

    with open(args.jsonfile, 'w') as f:
        json.dump(ncs, f, indent=4)
        
    logger.info(f"Find the list of NetCDF files in: {args.jsonfile}")

def get_parser_data():
    """Get parser for data."""
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
        default='ncs_filter.json'
        )
    parser.add_argument(
        '--filters-only',
        action='store_true',
        help="Use for exiting after filters processes.",
        )
    
    return parser

def main_data():
    """Process data over metazones."""
    # Get parser
    parser = get_parser_data()

    # Parse
    args = parser.parse_args()
    
    # Setup logging
    main_setup_logging(args)

    # Load configuration
    if not args.cfgfile.exists():
        raise ArmoorError(
            f"File not found: {args.cfgfile}."
            )
    
    cfg = ConfigManager(DATA_INI).load(str(args.cfgfile))
    metazones = ConfigManager(METAZONES_INI).load(str(args.metazonesfile))
    
    metazones = check_metazones_in(
       args. metazones,
       metazones
       )

    logger.info(f"🚀 Processing {len(cfg['data'])} datasets × {len(metazones)} metazones")
    
    zarrs = load_datasets(cfg["data"], metazones, "data")

    if args.filters_only:

        ncs = zarrs2netcdfs(zarrs)
    
        with open(args.jsonfile, 'w') as f:
            json.dump(ncs, f, indent=4)
            
        logger.info(f"Find the list of NetCDF files in: {args.jsonfile}")
    
    else:
        
        zarr_outputs = output_data(zarrs, metazones, cfg.get("outputs").copy())

        ofmt = cfg["outputs"].get("fmt")
        
        if "png" in ofmt:
            plot_data(zarr_outputs, metazones)
    
        zarr_outputs = dict_to_list(zarr_outputs)
        
        if "zarr" in ofmt:
            with open(args.jsonfile, 'w') as f:
                json.dump(zarr_outputs, f, indent=4)
                
        if "netcdf" in ofmt:
            ncs_outputs = zarrs2netcdfs(zarr_outputs)
            with open(args.jsonfile, 'w') as f:
                json.dump(ncs_outputs, f, indent=4)

def main_comp(cfgfile, metafile, metazones, func_comp, jsonfile, ofilter, ocoloc, comp_args):
    
    logger.info("Initial diagnostic:")
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

    logger.info(f"Processing {len(cfg['data'])} datasets × {len(metazones)} metazones")
        
    zarr = load_datasets(cfg["data"], metazones, func_comp)
    
    if ofilter:
        zarr = [str(z) for z in zarr]
        ncs_outputs = zarrs2netcdfs(zarr)
        with open(jsonfile, 'w') as f:
            json.dump(ncs_outputs, f, indent=4)
        
    else:
    
        zarr_coloc = main_coloc(zarr, metazones, func_comp)
        
        if ocoloc:
            zarr_coloc = dict_to_list(zarr_coloc)
            zarr_coloc = [str(z) for z in zarr_coloc]
            ncs_outputs = zarrs2netcdfs(zarr_coloc)
            with open(jsonfile, 'w') as f:
                json.dump(ncs_outputs, f, indent=4)
        
        else:
            
            zarr_outputs = output_comp(zarr_coloc, metazones, cfg.get("outputs"), func_comp)
            
            ofmt = cfg["outputs"].get("fmt")
            
            if "png" in ofmt:
                plot_comp(zarr_outputs, metazones, func_comp)
        
            zarr_outputs = dict_to_list(zarr_outputs)
            
            if "zarr" in ofmt:
                with open(jsonfile, 'w') as f:
                    json.dump(zarr_outputs, f, indent=4)
                    
            if "netcdf" in ofmt:
                ncs_outputs = zarrs2netcdfs(zarr_outputs)
                with open(jsonfile, 'w') as f:
                    json.dump(ncs_outputs, f, indent=4)
    
    logger.info(f"Find the list of generated files in: {jsonfile}")
    
    elapsed = time.time() - start_time
    logger.info(f"Execution time: {elapsed:.1f} seconds")    
    
    logger.info("Final diagnostic:")
    monitor_performance()


def get_parser_comp_models():
    """Get parser for models comparison."""
    # Setup argument parser
    parser = ArgumentParser(
        description="Compare models ouputs.",
        formatter_class=ArmoorArgumentHelpFormatter,
        )
    add_logging_parser_arguments(parser)
    add_comp_parser_arguments(parser)
    
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
    main_comp(
        args.cfgfile,
        args.metazonesfile,
        args.metazones,
        func_comp,
        args.jsonfile,
        args.filters_only,
        args.coloc_only,
        )

def get_parser_comp_sst():
    """Get parser for sst comparison."""
    # Setup argument parser
    parser = ArgumentParser(
        description="Compare sst satellite with model ouputs.",
        formatter_class=ArmoorArgumentHelpFormatter,
        )
    add_logging_parser_arguments(parser)
    add_comp_parser_arguments(parser)
    parser.add_argument(
        '--qc',
        type=parse_qc_tuple,
        default=None,
        help="Tuple specifying quality tresholds, ex: ptemp,1,7"
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

    main_comp(
        args.cfgfile,
        args.metazonesfile,
        args.metazones,
        func_comp,
        args.jsonfile,
        args.filters_only,
        args.coloc_only,
        kw_comp
        )
    
def get_parser_comp_argo():
    """Get parser for argo comparison."""
    # Setup argument parser
    parser = ArgumentParser(
        description="Compare argo data with model ouputs.",
        formatter_class=ArmoorArgumentHelpFormatter,
        )
    add_logging_parser_arguments(parser)
    add_comp_parser_arguments(parser)
    parser.add_argument(
        'radius',
        type=float,
        help="Radius of disk to filter model point around observation."
        )
    parser.add_argument(
        '--qc',
        type=parse_qc_tuple,
        default=None,
        help="Tuple specifying quality tresholds, ex: ptemp,1,7"
        )
    
    return parser

def main_comp_argo():
    """Compare argo with other products."""
        
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
    
    main_comp(
        args.cfgfile,
        args.metazonesfile,
        args.metazones,
        func_comp,
        args.jsonfile,
        args.filters_only,
        args.coloc_only,
        kw_comp
        )

def get_parser_comp_mooring():
    """Get parser for mooring comparison."""
    # Setup argument parser
    parser = ArgumentParser(
        description="Compare mooring data with model ouputs.",
        formatter_class=ArmoorArgumentHelpFormatter,
        )
    add_logging_parser_arguments(parser)
    add_comp_parser_arguments(parser)
    parser.add_argument(
        'radius',
        type=float,
        help="Radius of disk to filter model point around observation."
        )
    parser.add_argument(
        '--qc',
        type=dict,
        default=None,
        help="Dictionnary specifying quality tresholds, ex: ptemp:1,7"
        )
    
    return parser

def main_comp_mooring():
    """Compare argo with other products."""
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
    
    main_comp(
        args.cfgfile,
        args.metazonesfile,
        args.metazones,
        func_comp,
        args.jsonfile,
        args.filters_only,
        args.coloc_only,
        kw_comp
        )

# def apply_time_filters(dsout, mz_param, data_name):
#     """Applique les filtres temporels."""
#     time_meta = ["tbound", "terms", "trange_cut"]
    
#     for k in time_meta:
#         if k in mz_param:
#             if "climatology" not in dsout.time.attrs:
#                 dsout = FILTERS[k](dsout)(*mz_param[k])
#             if dsout is None:
#                 logger.warning(f"⚠️ Filtre {k} returns None for {data_name}")
#                 return None
    
#     return dsout

# def apply_horizontal_filters(dsout, mz_param, data_name):
#     """Applique les filtres horizontaux."""
#     horizontal_meta = ["bathy", "polygon"]#, "polygon_dilat"]
    
#     for k in horizontal_meta:
#         if k in mz_param:
#             if k == "polygon":
#                 args = mz_param[k]
#                 if set(["x", "y"]).issubset(set(dsout.lon.dims)):
#                     k = "polygon_dilat"
#             else:
#                 args = (*mz_param[k],)
            
#             dsout = FILTERS[k](dsout)(args)
#             if dsout is None:
#                 logger.warning(f"⚠️ Filtre {k} returns None for {data_name}")
#                 return None
#     return dsout


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
