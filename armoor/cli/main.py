"""Command-line interface for armoor."""
import gc
import json
from typing import List, Union, Any, Tuple, Optional, Dict
from argparse import ArgumentParser
import time
import logging
from pathlib import Path
from xoa.cfgm import ConfigManager, register_validation_functions

from armoor import ArmoorError
from armoor.cli import COMP_INI, DATA_INI, METAZONES_INI
from armoor.base import FILTERS
from armoor.base.io import ArmoorArgumentHelpFormatter, create_fast_encoding, setup_dask_client, zarrs2netcdfs
from armoor.base.log import add_logging_parser_arguments, main_setup_logging
from armoor.base.misc import (
    optimize_for_low_swap,
    dict_to_list,
    parse_qc_tuple,
    parse_coords,
    parse_mixed_param,
    comma_separated
    )
import armoor.base.oceanvars
from armoor.comp import METAZONE_PARAMS
from armoor.comp.coloc import main_coloc
from armoor.comp.misc import add_comp_parser_arguments
from armoor.comp.output import main_output
from armoor.comp.plot import main_plot
from armoor.data.open_decode import register_cf, open_decode

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
    
    register_cf()
    
    zarrs = load_datasets_sequential(cfg["data"], metazones, None)

    ncs = zarrs2netcdfs(zarrs)

    with open(args.jsonfile, 'w') as f:
        json.dump(ncs, f, indent=4)
        
    logger.info(f"Find the list of NetCDF files in: {args.jsonfile}")

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
    
    register_cf()
    
    zarr = load_datasets_sequential(cfg["data"], metazones, func_comp)
    
    if ofilter:
        zarr = [str(z) for z in zarr]
        ncs_outputs = zarrs2netcdfs(zarr)
        with open(jsonfile, 'w') as f:
            json.dump(ncs_outputs, f, indent=4)
        
    else:
    
        zarr_coloc = main_coloc(zarr, metazones, func_comp)
        
        if ocoloc:
            print(zarr_coloc)
            zarr_coloc = dict_to_list(zarr_coloc)
            zarr_coloc = [str(z) for z in zarr_coloc]
            ncs_outputs = zarrs2netcdfs(zarr_coloc)
            with open(jsonfile, 'w') as f:
                json.dump(ncs_outputs, f, indent=4)
        
        else:
            
            zarr_outputs = main_output(zarr_coloc, metazones, cfg.get("outputs"), func_comp)
            
            ofmt = cfg["outputs"].get("fmt")
            
            if "png" in ofmt:
                main_plot(zarr_outputs, metazones, func_comp)
        
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
    
    
def load_datasets_sequential(data_cfg, metazones, func_comp):
    """Charge les datasets de manière séquentielle (< 10s chacun)."""
    client = setup_dask_client()
    ncouts = []
    for data_key, cfg_data in data_cfg.items():
        dataset_name = cfg_data["name"]
        logger.info(f"Load {dataset_name}...")
        
        start_time = time.time()
        
        dss = open_decode(
            cfg_data["path"],
            fmt=cfg_data["fmt"],
            platform=cfg_data["platform"]
            )

        if not isinstance(dss, list):
            dss = [dss]

        for ids, ds in enumerate(dss):
            # Métadonnées
            if len(dss) == 1:
                ds.attrs["data_name"] = cfg_data["name"]
            else:
                ds.attrs["data_name"] = f"{cfg_data['name']}_{ds.attrs['name']}"
            ds.attrs["data_ref"] = str(cfg_data.get("ref"))
            dss[ids] = ds
            del ds
        
        elapsed = time.time() - start_time
        logger.info(f"{dataset_name} load in {elapsed:.1f}s")
        
        dataset = dss if len(dss) > 1 else dss[0]
        for ds in dss:
            ds.close()
        del dss
        ncs = process_all_combinations(dataset, metazones, func_comp)
        ncouts += ncs
        dataset.close()
        gc.collect()
    client.close()

    return ncouts
    
def process_single_task(task_data: Tuple[Any, Dict, str, Any, Any]) -> str:
    """Process a single dataset×metazone combination."""
    ds, mz_name, mz_param, func_comp = task_data
    
    # try:
        # Process the combination
    dsout = process_single_combination(
        ds,
        mz_name,
        mz_param,
        func_comp
    )
    dsout = optimize_for_low_swap(dsout)
    if dsout:
        ncout = save_result(dsout, mz_name, func_comp)
        return ncout
    return None
        
    # except Exception as e:
    #     print(f"Error processing {mz_name}: {e}")
    #     return None
    # finally:
        # Clean up
    if 'ds' in locals():
        ds.close()
    gc.collect()

def prepare_tasks(dataset, metazones: Dict, func_comp: Any) -> List[Tuple]:
    """Prepare all tasks for parallel processing."""
    tasks = []
    
    for mz_name, mz_param in metazones.items():
        dss = dataset
        if not isinstance(dss, list):
            dss = [dss]
        
        for ds in dss:
            task = (ds, mz_name, mz_param, func_comp)
            tasks.append(task)
    
    return tasks

def process_all_combinations(dataset, metazones, func_comp, max_workers=1):
    """Process all combinations using ThreadPoolExecutor."""
    tasks = prepare_tasks(dataset, metazones, func_comp)
    ncouts = []
    for task in tasks:
        ncout = process_single_task(task)
        ncouts.append(ncout)
    dataset.close()
    return ncouts

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

def build_filters_config(mz_param, data_name):
    """
    Build filters configuration dictionary from mz_param.
    
    Parameters
    ----------
    mz_param : dict
        Configuration parameters containing filter settings
    data_name : str
        Name of the data source
        
    Returns
    -------
    dict
        Filters configuration for apply_combined_filters
    """
    filters_config = {}
    
    # Time filters (assuming they become data_selection filters)
    if 'tbound' in mz_param:
        filters_config['time_selection'] = {
            'dim': 'time',
            'minimum': mz_param.get('tbound')[0],
            'maximum': mz_param.get('tbound')[1]
        }
        
    if 'tide' in mz_param:
        filters_config['tide'] = mz_param.get("tide")
        
    # # Depth filters
    # if 'depth_min' in mz_param or 'depth_max' in mz_param:
    #     filters_config['depth_selection'] = {
    #         'dim': 'depth',
    #         'minimum': mz_param.get('depth_min'),
    #         'maximum': mz_param.get('depth_max')
    #     }
    
    # Quality filters
    if 'qc' in mz_param:
        # Assuming quality variable name based on data_name or a specific field
        filters_config['quality'] = {
            'qname': mz_param.get('qc')[0],
            'qmin': mz_param.get('qc')[1],
            'qmax': mz_param.get('qc')[2]
            }
    
    # Horizontal/spatial filters
    if 'polygon' in mz_param:
        filters_config['polygon'] = {
            'coords': mz_param['polygon'],
            'dilate': True if mz_param.get("href") else False
        }
    # elif 'bbox' in mz_param:
    #     # Convert bounding box to polygon coordinates
    #     bbox = mz_param['polygon']  # Assuming [lon_min, lat_min, lon_max, lat_max]
    #     coords = [
    #         (bbox[1], bbox[0]),  # lat_min, lon_min
    #         (bbox[3], bbox[0]),  # lat_max, lon_min
    #         (bbox[3], bbox[2]),  # lat_max, lon_max
    #         (bbox[1], bbox[2])   # lat_min, lon_max
    #     ]
    #     filters_config['polygon'] = {
    #         'coords': coords,
    #         'dilate': True,#mz_param.get('polygon_dilate', False)
    #     }
    
    # # Geographic bounds as data selection
    # if 'lon_min' in mz_param or 'lon_max' in mz_param:
    #     filters_config['lon_selection'] = {
    #         'dim': 'lon',
    #         'minimum': mz_param.get('lon_min'),
    #         'maximum': mz_param.get('lon_max')
    #     }
    
    # if 'lat_min' in mz_param or 'lat_max' in mz_param:
    #     filters_config['lat_selection'] = {
    #         'dim': 'lat',
    #         'minimum': mz_param.get('lat_min'),
    #         'maximum': mz_param.get('lat_max')
    #     }
    
    return filters_config


def process_single_combination(ds, mz_name, mz_param, func_comp):
    """
    Optimized version using combined filters to reduce memory usage and dask operations.
    
    Parameters
    ----------
    ds : xarray.Dataset
        Input dataset
    cfg_data : dict
        Configuration data
    mz_name : str
        Name of the processing zone
    mz_param : dict
        Parameters for the processing zone
    func_comp : callable
        Comparison function
        
    Returns
    -------
    xarray.Dataset or None
        Processed dataset or None if processing failed
    """
    data_name = ds.attrs["data_name"]
    combination_id = f"{data_name}_{mz_name}"
    start_time = time.time()
    dsout = None
    
    logger.info(f"Processing {combination_id}")
    
    # Check if data is available
    if ds is None:
        logger.error(f"Dataset is None for {combination_id}")
        return None
    
    # Copy dataset to avoid modifications
    dsout = ds.copy(deep=True)  # Deep copy to avoid references
    data_name = dsout.attrs["data_name"]
    data_ref = dsout.attrs["data_ref"]
    
    # Build filters configuration
    # try:
    filters_config = build_filters_config(mz_param, data_name)
    logger.info(f"Filters config for {combination_id}: {filters_config}")
    # except Exception as e:
    #     logger.error(f"Error building filters config for {combination_id}: {e}")
    #     return None
    
    # Apply combined filters if any filters are configured
    if filters_config:
        # try:
        logger.info(f"Applying combined filters for {combination_id}")
        dsout = dsout.armoorfilters.apply_combined_filters(filters_config)
        if dsout is None:
            logger.warning(f"No data left after filtering for {combination_id}")
            return None
        # except Exception as e:
        #     logger.error(f"Error applying combined filters for {combination_id}: {e}")
        #     return None
    else:
        logger.info(f"No filters to apply for {combination_id}")
    
    # Check if dataset is not empty after filtering
    if dsout is not None:
        # Check if dataset has any data left
        if any(dsout.sizes[dim] == 0 for dim in dsout.dims):
            logger.warning(f"Dataset empty after filtering for {combination_id}")
            return None
    
    # Final metadata
    if dsout is not None:
        dsout.attrs = {
            "data_name": data_name,
            "data_ref": data_ref,
        }
    
    elapsed = time.time() - start_time
    logger.info(f"Processing {combination_id} completed in {elapsed:.1f}s")
        
    
    return dsout

def save_result(dsout, mz_name, func_comp):
    """Sauvegarde optimisée (< 30s)."""
    
    # Préparer les chemins
    refprod = "ref" if dsout.attrs["data_ref"] == "True" else "prod"
    data_name = dsout.attrs["data_name"]
    parent_dir = f"{func_comp}/metazones" if func_comp else "metazones"
    ncpat = "{mz_name}/{data_name}/{refprod}_{data_name}.zarr"
    nc = Path(parent_dir) / ncpat.format(**locals())

    nc.parent.mkdir(parents=True, exist_ok=True)
    
    # Encoding optimisé pour la vitesse
    encoding = create_fast_encoding(dsout)
    # encoding = get_zarr_encoding(dsout)
    logger.info(nc)
    #Sauvegarde avec optimisations
    dsout.to_zarr(
        store=nc,
        mode="w",
        encoding=encoding,
        #safe_chunks=False
        # format='NETCDF4',
        # engine='netcdf4',
        #compute=True  # Forcer le compute immédiat
        )
    dsout.close() 
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
