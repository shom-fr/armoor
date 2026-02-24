import gc
import logging
import os
import shutil
import sys
from pathlib import Path
import time
from typing import Any, Dict, List, Optional, Tuple, Union

import dask
from dask.diagnostics import ProgressBar
import numpy as np
import xarray as xr

from armoor.base.io import (setup_dask_client, create_fast_encoding,
                            write_dataset_to_zarr, compute_bundled_zarr_writes)
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
    if 'thours' in mz_param:
        filters_config['hours_selection'] = {
            'minimum': mz_param.get('thours')[0],
            'maximum': mz_param.get('thours')[1]
        }
    if 'tide' in mz_param:
        filters_config['tide'] = mz_param.get("tide")
    
    if 'tresample' in mz_param:
        filters_config['tresample'] = mz_param.get("tresample")
        
    if 'tsmooth' in mz_param:
        filters_config['tsmooth'] = mz_param.get("tsmooth")
    
    if 'bathy' in mz_param:
        # Assuming quality variable name based on data_name or a specific field
        bathy_min = mz_param.get('bathy')[2]
        bathy_max = mz_param.get('bathy')[3]
        filters_config['bathy'] = {
            'path': mz_param.get('bathy')[0],
            'fmt': mz_param.get('bathy')[1],
            'min': None if bathy_min == "None" else float(bathy_min),
            'max': None if bathy_max == "None" else float(bathy_max)
            }
    
    if 'oceanvars' in mz_param:
        filters_config["oceanvars"] = mz_param.get('oceanvars')
        
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
    
    data_name = ds.attrs["data_name"]
    data_ref = ds.attrs["data_ref"]

    # Build filters configuration
    filters_config = build_filters_config(mz_param, data_name)
    logger.info(f"Filters config for {combination_id}: {filters_config}")

    # Apply combined filters if any filters are configured
    if filters_config:
        logger.info(f"Applying combined filters for {combination_id}")
        all_nan = bool(ds[list(ds.data_vars)].to_array().isnull().all().values)
        logger.info(all_nan)
        dsout = ds.armoorfilters.apply_combined_filters(filters_config)
        if dsout is None:
            logger.info(f"No data left after filtering for {combination_id}")
            sys.exit()
        all_nan = bool(ds[list(ds.data_vars)].to_array().isnull().all().values)
        logger.info(all_nan)
    else:
        logger.info(f"No filters to apply for {combination_id}")
        dsout = ds.copy()
    
    # Check if dataset is not empty after filtering
    if dsout is not None:
        # Check if dataset has any data left
        if any(dsout.sizes[dim] == 0 for dim in dsout.dims):
            logger.warning(f"Dataset empty after filtering for {combination_id}")
            return None
        elif dsout.sizes["time"] == 1:
            logger.warning(f"One time step in the filtered dataset for {combination_id}, this may cause troubleshooting.")
        elif "time" not in dsout.dims:
            logger.warning(f"no index found for coordinate 'time' for {combination_id}")
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
    # encoding = create_fast_encoding(dsout)
    #encoding = get_zarr_encoding(dsout)
    # logger.info(nc)
    #Sauvegarde avec optimisations
    # write_job = ds_clean.chunk("auto").to_zarr(
    #     store=nc,
    #     mode="w",
    #     compute=False,
    #     consolidated=True,
    #     # encoding=encoding
    #     )
    write_job = write_dataset_to_zarr(
        dsout,
        nc,
        mode="w",
        consolidated=True,
        compute=False
        )
    with ProgressBar():
        write_job.compute()
    dsout.close()
    del dsout
    logger.info(f"Saved: {nc}")
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
        # dsout = optimize_for_low_swap(dsout)
        try:
            dsout = dsout.chunk('auto')
        except:
            logger.info("No chunks")
        ncout = save_result(dsout, mz_name, dirout)
        del dsout
        return ncout
    return None

    # if 'ds' in locals():
    #     ds.close()
    # gc.collect()

def _process_single_task_from_zarr(zfile, mz_name, mz_param, dirout):
    """Open zarr, process one combination, close. Thread-safe for parallel use."""
    ds = xr.open_dataset(str(zfile), chunks="auto")
    task = (ds, mz_name, mz_param, dirout)
    ncout = process_single_task(task)
    ds.close()
    return ncout


def process_all_combinations(inputs, metazones, dirout, max_workers=1):
    """Process all combinations with dask.delayed parallelism.

    Parameters
    ----------
    inputs : list
        List of zarr file paths (str/Path) or xr.Dataset objects.
    metazones : dict
        Metazone configurations.
    dirout : str
        Output directory identifier.
    max_workers : int
        Unused, kept for API compatibility.

    Returns
    -------
    list
        List of output file paths.
    """
    from pathlib import Path

    if not isinstance(inputs, list):
        inputs = [inputs]

    delayed_results = []
    for inp in inputs:
        if isinstance(inp, (str, Path)):
            # Each task opens its own zarr file (thread-safe for parallel)
            for mz_name, mz_param in metazones.items():
                delayed_results.append(
                    dask.delayed(_process_single_task_from_zarr)(
                        inp, mz_name, mz_param, dirout
                    )
                )
        else:
            # Dataset passed directly -- process sequentially to avoid sharing issues
            for mz_name, mz_param in metazones.items():
                task = (inp, mz_name, mz_param, dirout)
                delayed_results.append(dask.delayed(process_single_task)(task))

    if delayed_results:
        ncouts = list(dask.compute(*delayed_results))
    else:
        ncouts = []
    return ncouts

_ZARR_SIZE_THRESHOLD_DEFAULT = 2 * 1024**3  # 2 GB fallback
_ZARR_SIZE_THRESHOLD_MAX = 4 * 1024**3     # 4 GB cap (avoids Dask graph serialization overhead)
_ZARR_RAM_FRACTION = 0.6


def _get_available_ram():
    """Return available RAM in bytes, or None if detection fails."""
    try:
        import psutil
        return psutil.virtual_memory().available
    except ImportError:
        pass
    try:
        return os.sysconf('SC_AVPHYS_PAGES') * os.sysconf('SC_PAGE_SIZE')
    except (ValueError, OSError, AttributeError):
        return None


_SHM_DIR = Path("/dev/shm")
_SHM_MIN_FREE = 2 * 1024**3   # require at least 2 GB free in /dev/shm
_RAM_LOAD_FRACTION = 0.40      # load into RAM if filtered data < 40 % of available RAM


def _get_zarr_tmp_dir(needed_bytes=0):
    """Return best directory for temporary zarr files.

    Preference order:
    1. /dev/shm (tmpfs RAM disk) — eliminates all temporary disk I/O.
    2. Current working directory (local disk, existing behaviour).

    Parameters
    ----------
    needed_bytes : int
        Estimated bytes required; used to verify /dev/shm has enough room.
    """
    if _SHM_DIR.exists():
        try:
            free = shutil.disk_usage(_SHM_DIR).free
            if free > max(_SHM_MIN_FREE, needed_bytes * 1.1):
                logger.info(
                    f"/dev/shm available ({free / 1e9:.1f} GB free) "
                    f"-- using RAM disk for zarr staging"
                )
                return _SHM_DIR
        except OSError:
            pass
    return Path(".")


def _get_zarr_size_threshold():
    """Adaptive threshold based on available RAM.

    On low-RAM machines the threshold drops below the default to prevent OOM.
    On high-RAM machines the threshold is capped at _ZARR_SIZE_THRESHOLD_MAX
    because the bottleneck shifts to Dask graph serialization, not RAM.
    """
    available = _get_available_ram()
    if available and available > 0:
        threshold = min(int(available * _ZARR_RAM_FRACTION), _ZARR_SIZE_THRESHOLD_MAX)
        logger.info(f"Available RAM: {available / 1024**3:.1f} GB -- zarr threshold: {threshold / 1024**3:.1f} GB")
        return threshold
    logger.info(f"Cannot detect available RAM -- using default {_ZARR_SIZE_THRESHOLD_DEFAULT / 1024**3:.0f} GB threshold")
    return _ZARR_SIZE_THRESHOLD_DEFAULT


def _extract_prefilter_bounds(metazones):
    """Extract union bounding box and time range from all metazones.

    Returns a dict with spatial ('lat_min', 'lat_max', 'lon_min', 'lon_max')
    and/or temporal ('time_min', 'time_max') keys, or None.
    """
    lats, lons = [], []
    time_mins, time_maxs = [], []
    for mz_param in metazones.values():
        if 'polygon' in mz_param:
            for lat, lon in mz_param['polygon']:
                lats.append(lat)
                lons.append(lon)
        if 'tbound' in mz_param:
            time_mins.append(str(mz_param['tbound'][0]))
            time_maxs.append(str(mz_param['tbound'][1]))
    bounds = {}
    if lats:
        margin = 2.0  # degrees
        bounds['lat_min'] = min(lats) - margin
        bounds['lat_max'] = max(lats) + margin
        bounds['lon_min'] = min(lons) - margin
        bounds['lon_max'] = max(lons) + margin
    if time_mins:
        bounds['time_min'] = min(time_mins)
        bounds['time_max'] = max(time_maxs)
    return bounds if bounds else None


def _apply_prefilter(ds, bounds):
    """Apply coarse spatial and temporal pre-filter lazily.

    This dramatically reduces the data volume for gridded products that cover
    a much larger domain than the metazones of interest, cutting zarr staging
    time proportionally.  Works with 1-D or 2-D lat(y,x)/lon(y,x) coordinates.
    """
    if not bounds:
        return ds

    # --- Temporal pre-filter ---
    if 'time_min' in bounds and 'time' in ds.dims:
        ds = ds.sel(time=slice(bounds['time_min'], bounds['time_max']))

    # --- Spatial pre-filter ---
    if 'lat_min' not in bounds:
        return ds
    if 'lat' not in ds or 'lon' not in ds:
        return ds

    lat_min, lat_max = bounds['lat_min'], bounds['lat_max']
    lon_min, lon_max = bounds['lon_min'], bounds['lon_max']

    lat = ds['lat']
    lon = ds['lon']
    lat_cond = (lat >= lat_min) & (lat <= lat_max)
    lon_cond = (lon >= lon_min) & (lon <= lon_max)

    # Handle 0-360 vs -180-180 longitude convention
    # if float(lon.min()) >= 0 and lon_min < 0:
    #     lon_min_360 = lon_min % 360
    #     lon_max_360 = lon_max % 360
    #     if lon_min_360 > lon_max_360:
    #         # Wraps across 0°: e.g. lon ∈ [346°, 360°] ∪ [0°, 5°]
    #         lon_cond = (lon >= lon_min_360) | (lon <= lon_max_360)
    #     else:
    #         lon_cond = (lon >= lon_min_360) & (lon <= lon_max_360)
    # else:
    #     lon_cond = (lon >= lon_min) & (lon <= lon_max)
    mask = lat_cond & lon_cond
    mask = mask.compute()
    return ds.where(mask, drop=True)


def _process_large_dataset_pipelined(dss, data_key, metazones, dirout):
    """Process large datasets with the best available staging strategy.

    Strategy selection (in order of preference):

    1. **RAM-first** — if the union-filtered data fits in 40 % of available RAM,
       load it into memory once and run ``process_all_combinations`` directly.
       No zarr staging, no disk I/O; all per-metazone work is pure numpy.

    2. **/dev/shm (RAM-disk)** — write one per-metazone temporary zarr to
       ``/dev/shm`` (tmpfs).  Eliminates all rotational/SSD I/O for staging;
       Stage-2 reads are at RAM speed.  All metazone writes for a given source
       dataset are fused into a single ``dask.compute`` call so shared source
       chunks are read from the network exactly once.

    3. **Local-disk fallback** — same per-metazone approach but zarr files land
       on the local filesystem (original behaviour).
    """
    union_bounds = _extract_prefilter_bounds(metazones)

    # ── Apply union pre-filter to all source datasets (lazy) ──────────────────
    dss_filtered = []
    for ds in dss:
        if union_bounds is not None:
            original_nbytes = ds.nbytes
            ds_f = _apply_prefilter(ds, union_bounds)
            filtered_nbytes = ds_f.nbytes
            if original_nbytes > 0:
                reduction = (1 - filtered_nbytes / original_nbytes) * 100
                logger.info(
                    f"Union pre-filter: {original_nbytes / 1e9:.1f} GB "
                    f"-> {filtered_nbytes / 1e9:.1f} GB "
                    f"({reduction:.0f}% reduction)"
                )
        else:
            ds_f = ds
        dss_filtered.append(ds_f)

    total_filtered = sum(ds.nbytes for ds in dss_filtered)

    # ── Strategy 1: RAM-first ──────────────────────────────────────────────────
    available_ram = _get_available_ram()
    if available_ram and total_filtered < available_ram * _RAM_LOAD_FRACTION:
        logger.info(
            f"RAM-first: loading {total_filtered / 1e9:.1f} GB into RAM "
            f"({total_filtered / available_ram * 100:.0f}% of "
            f"{available_ram / 1e9:.1f} GB available) -- no zarr staging"
        )
        dss_loaded = [ds.load() for ds in dss_filtered]
        for ds in dss:
            ds.close()
        del dss, dss_filtered
        ncs = process_all_combinations(dss_loaded, metazones, dirout)
        for ds in dss_loaded:
            ds.close()
        return ncs

    # ── Strategies 2 & 3: per-metazone zarr staging ───────────────────────────
    # Pick staging directory: /dev/shm (RAM disk) when possible.
    zarr_dir = _get_zarr_tmp_dir(needed_bytes=total_filtered)

    # zfiles: list of (path, mz_name, mz_param)
    zfiles = []
    ncs = []
    try:
        for ids, ds in enumerate(dss_filtered):
            original_nbytes = ds.nbytes
            write_jobs = []
            for mz_name, mz_param in metazones.items():
                # Tight per-metazone filter: only read what this metazone needs.
                mz_bounds = _extract_prefilter_bounds({mz_name: mz_param})
                if mz_bounds is not None:
                    ds_mz = _apply_prefilter(ds, mz_bounds)
                    filtered_nbytes = ds_mz.nbytes
                    if original_nbytes > 0:
                        reduction = (1 - filtered_nbytes / original_nbytes) * 100
                        logger.info(
                            f"Pre-filter {mz_name}: {original_nbytes / 1e9:.1f} GB "
                            f"-> {filtered_nbytes / 1e9:.1f} GB "
                            f"({reduction:.0f}% reduction)"
                        )
                else:
                    ds_mz = ds
                zfile = zarr_dir / f"tmp_{data_key}_{ids}_{mz_name}.zarr"
                logger.info(f"Staging {mz_name} ({ids + 1}/{len(dss_filtered)}) -> {zfile}")
                write_job = write_dataset_to_zarr(
                    ds_mz,
                    str(zfile),
                    mode="w",
                    consolidated=True,
                    compute=False,
                )
                write_jobs.append(write_job)
                zfiles.append((zfile, mz_name, mz_param))
            # Single dask pass: all metazone writes share the same upstream
            # task graph so each source chunk is read from the network once.
            compute_bundled_zarr_writes(write_jobs)
            ds.close()
        del dss, dss_filtered
        logger.info("All datasets staged to zarr")

        # Stage 2: process per-metazone zarrs in parallel.
        delayed_tasks = [
            dask.delayed(_process_single_task_from_zarr)(
                str(zfile), mz_name, mz_param, dirout
            )
            for zfile, mz_name, mz_param in zfiles
        ]
        if delayed_tasks:
            ncs = list(dask.compute(*delayed_tasks))

    finally:
        for zfile, _, _ in zfiles:
            if zfile.exists():
                shutil.rmtree(zfile)

    return ncs


def load_datasets(data_cfg, metazones, dirout):
    """Load datasets and process all metazone combinations.

    Small datasets (< 2 GB) are passed directly to processing,
    skipping the intermediate zarr round-trip.  Large datasets
    fall back to a temporary zarr to avoid memory pressure.
    """
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
        logger.debug(dss)

        # Add metadata
        for ids, ds in enumerate(dss):
            if len(dss) == 1:
                ds.attrs["data_name"] = cfg_data["name"]
            else:
                ds.attrs["data_name"] = f"{cfg_data['name']}_{ds.attrs['name']}"
            ds.attrs["data_ref"] = str(cfg_data.get("ref"))

        # Choose direct or zarr-backed processing based on dataset size
        total_nbytes = sum(ds.nbytes for ds in dss)
        zarr_threshold = _get_zarr_size_threshold()
        if total_nbytes > zarr_threshold:
            # Large datasets: pipelined write + processing
            logger.info("Large dataset -- using pipelined zarr processing")
            ncs = _process_large_dataset_pipelined(dss, data_key, metazones, dirout)
        else:
            # Small datasets: pass directly, skip zarr round-trip
            logger.info("Small dataset -- processing directly in memory")
            ncs = process_all_combinations(dss, metazones, dirout)
            for ds in dss:
                ds.close()
            del dss

        elapsed = time.time() - start_time
        logger.info(f"{dataset_name} load in {elapsed:.1f}s")

        ncouts += ncs

    return ncouts
