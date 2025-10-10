import gc
import logging
from pathlib import Path
import time
from typing import Any, Dict, List, Optional, Tuple, Union

from armoor.base.io import setup_dask_client, create_fast_encoding
from armoor.base.misc import optimize_for_low_swap
from armoor.data.open_decode import open_decode, register_cf


logger = logging.getLogger(__name__)

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
            'minimum': mz_param.get('tbound')[0],
            'maximum': mz_param.get('tbound')[1]
        }
        
    if 'tide' in mz_param:
        filters_config['tide'] = mz_param.get("tide")
    
    if 'bathy' in mz_param:
        # Assuming quality variable name based on data_name or a specific field
        filters_config['bathy'] = {
            'path': mz_param.get('bathy')[0],
            'fmt': mz_param.get('bathy')[1],
            'min': float(mz_param.get('bathy')[2]),
            'max': float(mz_param.get('bathy')[3])
            }
        
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

def process_single_combination(ds, mz_name, mz_param):
    """
    Optimized version using combined filters to reduce memory usage and dask operations.
    
    Parameters
    ----------
    ds : xarray.Dataset
        Input dataset
    mz_name : str
        Name of the processing zone
    mz_param : dict
        Parameters for the processing zone
        
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
    data_name = ds.attrs["data_name"]
    data_ref = ds.attrs["data_ref"]
    
    # Build filters configuration
    filters_config = build_filters_config(mz_param, data_name)
    logger.info(f"Filters config for {combination_id}: {filters_config}")
    
    # Apply combined filters if any filters are configured
    if filters_config:
        # try:
        logger.info(f"Applying combined filters for {combination_id}")
        dsout = ds.armoorfilters.apply_combined_filters(filters_config)
        if dsout is None:
            logger.warning(f"No data left after filtering for {combination_id}")
            return None
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
    #encoding = get_zarr_encoding(dsout)
    logger.info(nc)
    #Sauvegarde avec optimisations
    dsout.to_zarr(
        store=nc,
        mode="w",
        encoding=encoding,
        )
    dsout.close()
    del dsout
    logger.debug(f"💾 Sauvegardé: {nc}")
    return str(nc)

def process_single_task(task_data: Tuple[Any, Dict, str, Any, Any]) -> str:
    """Process a single dataset×metazone combination."""
    ds, mz_name, mz_param, dirout = task_data

    dsout = process_single_combination(
        ds,
        mz_name,
        mz_param,
    )
    if dsout:
        dsout = optimize_for_low_swap(dsout)
        ncout = save_result(dsout, mz_name, dirout)
        return ncout
    return None

    if 'ds' in locals():
        ds.close()
    gc.collect()

def prepare_tasks(dataset, metazones: Dict, dirout: Any) -> List[Tuple]:
    """Prepare all tasks for parallel processing."""
    tasks = []
    
    for mz_name, mz_param in metazones.items():
        dss = dataset
        if not isinstance(dss, list):
            dss = [dss]
        
        for ds in dss:
            task = (ds, mz_name, mz_param, dirout)
            tasks.append(task)
    
    return tasks

def process_all_combinations(dataset, metazones, dirout, max_workers=1):
    """Process all combinations using ThreadPoolExecutor."""
    tasks = prepare_tasks(dataset, metazones, dirout)
    ncouts = []
    for task in tasks:
        ncout = process_single_task(task)
        ncouts.append(ncout)
    if isinstance(dataset, list):
        for ds in dataset:
            ds.close()
    else:
        dataset.close()
    return ncouts

def load_datasets(data_cfg, metazones, dirout):
    """Charge les datasets de manière séquentielle (< 10s chacun)."""
    register_cf()
    ncouts = []
    for data_key, cfg_data in data_cfg.items():
        dataset_name = cfg_data["name"]
        logger.info(f"Load {dataset_name}...")
        
        start_time = time.time()
        
        dss = open_decode(
            cfg_data["path"],
            fmt=cfg_data["fmt"],
            platform=cfg_data.get("platform")
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
        ncs = process_all_combinations(dataset, metazones, dirout)
        ncouts += ncs
        if isinstance(dataset, list):
            for ds in dataset:
                ds.close()
        else:
            dataset.close()
        gc.collect()

    return ncouts
