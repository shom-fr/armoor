import gc
import logging
import os
import shutil
import sys
from pathlib import Path
import time
from typing import Any, Dict, List, Optional, Tuple, Union

import dask
import dask.array as da
from collections import Counter
import numpy as np
import xarray as xr

import armoor  # noqa: F401 — registers all xarray accessors (ds.filters, …)
from armoor.base.io import (setup_dask_client, create_fast_encoding,
                            write_dataset_to_zarr, compute_bundled_zarr_writes)
from armoor.base.misc import optimize_for_low_swap
from armoor.data.datatype import get_data_type
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
    data_type = ds.attrs.get("data_type")

    # Build filters configuration
    filters_config = build_filters_config(mz_param, data_name)
    logger.info(f"Filters config for {combination_id}: {filters_config}")

    # Apply combined filters if any filters are configured
    if filters_config:
        logger.info(f"Applying combined filters for {combination_id}")
        dsout = ds.filters.combined(filters_config)
        if dsout is None:
            logger.info(f"No data left after filtering for {combination_id}")
            return None
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
            "data_type": data_type,
        }

    elapsed = time.time() - start_time
    logger.info(f"Processing {combination_id} completed in {elapsed:.1f}s")
        
    return dsout

class StagedDataset(str):
    """A zarr output path that also carries the metazone it was written for.

    Behaves identically to a plain str/path everywhere (isinstance str is
    True, json.dumps serializes it as a plain string, Path(x) works, string
    matching in main_coloc's file-index scan works) -- this is purely
    additive metadata riding along on the same object, not a new on-disk
    shape. Lets callers recover the metazone without parsing it back out of
    the path.
    """

    def __new__(cls, path, metazone):
        obj = super().__new__(cls, path)
        obj.metazone = metazone
        return obj


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
        compute=False,
        compressor=_OUTPUT_COMPRESSOR,
        )
    compute_bundled_zarr_writes([write_job])
    dsout.close()
    del dsout
    logger.info(f"Saved: {nc}")
    return StagedDataset(str(nc), metazone=mz_name)

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
            tc = _compute_output_time_chunk(dsout)
            dsout = dsout.chunk({'time': tc}) if tc else dsout.chunk('auto')
        except Exception:
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
    # Open with native zarr chunks (chunks={}) so xarray never materialises a
    # single array larger than one stored chunk.  The staging phase ensures
    # time is chunked to _STAGING_TIME_CHUNK and spatial dims to
    # _STAGING_SPATIAL_CHUNK, so each chunk stays well below 1 GB.
    ds = xr.open_dataset(str(zfile), chunks={})
    task = (ds, mz_name, mz_param, dirout)
    ncout = process_single_task(task)
    ds.close()
    return ncout


def _process_metazone_from_union_zarr(zfile, mz_name, mz_param, dirout):
    """Apply per-metazone spatial prefilter on the union staging zarr, then process.

    Used when Phase 1 staged ONE union zarr (covering all metazones) rather
    than one zarr per metazone.  Re-reading the zarr multiple times in parallel
    is free when it lives in /dev/shm (~20 GB/s RAM bandwidth).
    """
    ds = xr.open_dataset(str(zfile), chunks={})
    mz_bounds = _extract_prefilter_bounds({mz_name: mz_param})
    if mz_bounds is not None:
        ds_mz = _apply_prefilter(ds, mz_bounds)
        if any(s == 0 for s in ds_mz.sizes.values()):
            logger.warning(f"Skipping {mz_name}: empty after per-metazone prefilter")
            ds.close()
            return None
    else:
        ds_mz = ds
    task = (ds_mz, mz_name, mz_param, dirout)
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
_TARGET_CHUNK_BYTES = 2 * 1024**3          # target uncompressed size per output zarr chunk
_BLOSC_MAX_CHUNK_BYTES = 2_000_000_000     # Blosc per-variable per-chunk limit


def _compute_output_time_chunk(dsout):
    """Return the optimal time chunk size for a zarr output dataset.

    The previous formula divided _TARGET_CHUNK_BYTES by *total* dataset
    bytes/tstep.  Because zarr stores each variable in its own array, the
    Blosc 2 GB limit applies *per variable*, not across the whole dataset.
    Dividing by the total deflated chunk sizes by N_vars (typically 3–7×),
    producing unnecessarily small time chunks and proportionally more NFS
    chunk files — each costing ~1–2 s of metadata latency on HPC NFS.

    This function uses the largest per-variable bytes/tstep so every variable
    chunk stays just under the Blosc 2 GB limit, minimising NFS file count.
    """
    if 'time' not in dsout.dims or dsout.sizes.get('time', 1) <= 1:
        return None
    n_time = dsout.sizes['time']
    timed_vars = [v for v in dsout.data_vars if 'time' in dsout[v].dims]
    if not timed_vars:
        return None
    max_bytes_per_var_per_tstep = max(
        dsout[v].nbytes / n_time for v in timed_vars
    )
    if max_bytes_per_var_per_tstep <= 0:
        return None
    tc = max(1, int(_BLOSC_MAX_CHUNK_BYTES / max_bytes_per_var_per_tstep))
    logger.debug(
        f"_compute_output_time_chunk: {len(timed_vars)} timed vars, "
        f"max {max_bytes_per_var_per_tstep/1e6:.1f} MB/var/tstep → time_chunk={tc}"
    )
    return tc


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
_RAM_LOAD_FRACTION = 0.50      # load into RAM if filtered data < 50 % of available RAM
_STAGING_SPATIAL_CHUNK = 64  # rechunk non-time dims to this size before staging
_STAGING_TIME_CHUNK = 10       # rechunk time to this size to reduce task count

def _make_staging_compressor():
    """Fast lz4 compressor for temporary staging zarrs."""
    try:
        from numcodecs import Blosc
        return Blosc(cname='lz4', clevel=1, shuffle=Blosc.BITSHUFFLE)
    except ImportError:
        return None

def _make_output_compressor():
    """zstd+BITSHUFFLE compressor for final output zarrs.

    clevel=1 gives lz4-like compression speed while still achieving ~4-5×
    ratio (vs lz4 ~3×), keeping Phase 2 CPU-bound time similar to lz4 but
    reducing NFS copy volume by ~30-40%.
    """
    try:
        from numcodecs import Blosc
        return Blosc(cname='zstd', clevel=1, shuffle=Blosc.BITSHUFFLE)
    except ImportError:
        return None

_STAGING_COMPRESSOR = _make_staging_compressor()
_OUTPUT_COMPRESSOR  = _make_output_compressor()

_STAGING_COMPRESS_RATIO = 4.0  # lz4 cl1 on ocean data: typically 3-5×
_OUTPUT_COMPRESS_RATIO  = 6.0  # zstd+BITSHUFFLE on ocean data: typically 5-8×
_OUTPUT_SHM_MARGIN      = 1.2  # require 20 % safety margin when staging output to /dev/shm


def _get_zarr_tmp_dir(needed_bytes=0):
    """Return best directory for temporary zarr files.

    Preference order:
    1. /dev/shm (tmpfs RAM disk) — eliminates all temporary disk I/O.
    2. $TMPDIR — per-job local SSD on HPC nodes (much faster than NFS).
    3. Current working directory (fallback).

    Parameters
    ----------
    needed_bytes : int
        Estimated UNCOMPRESSED bytes; the actual disk usage is divided by
        _STAGING_COMPRESS_RATIO before checking free space.
    """
    # Use compressed size estimate: lz4 reduces ocean data by ~4×.
    # Using raw ds.nbytes (uncompressed) would over-estimate disk usage and
    # incorrectly reject fast /dev/shm in favour of slower $TMPDIR.
    disk_bytes = max(int(needed_bytes / _STAGING_COMPRESS_RATIO), 1)

    candidates = [_SHM_DIR]
    tmpdir_env = os.environ.get("TMPDIR")
    if tmpdir_env:
        candidates.append(Path(tmpdir_env))

    for candidate in candidates:
        if candidate.exists():
            try:
                free = shutil.disk_usage(candidate).free
                if free > max(_SHM_MIN_FREE, disk_bytes * 1.1):
                    logger.info(
                        f"{candidate} available ({free / 1e9:.1f} GB free, "
                        f"estimated need {disk_bytes / 1e9:.1f} GB compressed) "
                        f"-- using it for zarr staging"
                    )
                    return candidate
            except OSError:
                pass

    logger.warning(
        "No fast local storage available for zarr staging "
        "(neither /dev/shm nor $TMPDIR have enough free space) "
        "-- falling back to current directory (may be slow NFS)"
    )
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

    For both 1-D and 2-D lat/lon coordinates an ``isel`` with integer slices
    is applied first so that only the bounding-box region is read from disk
    via HDF5/NetCDF4 hyperslab selection.  For 2-D coordinates a fine
    ``where(mask, drop=True)`` is then applied on the much smaller sub-region.
    """
    if not bounds:
        return ds

    # --- Temporal pre-filter ---
    # Skip for climatologies: time is not decoded as datetime64 (e.g. WOA18
    # opened with decode_times=False stores month indices as floats).
    if ('time_min' in bounds and 'time' in ds.dims
            and np.issubdtype(ds['time'].dtype, np.datetime64)):
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

    if lat.ndim == 1 and lon.ndim == 1:
        # Structured grid: use integer-slice isel → HDF5 hyperslab → actual IO reduction.
        lat_vals = lat.compute().values
        lon_vals = lon.compute().values

        lat_mask = (lat_vals >= lat_min) & (lat_vals <= lat_max)
        if not lat_mask.any():
            logger.warning("_apply_prefilter: no lat points inside bbox — returning full lat range")
            return ds
        lat_idx = np.where(lat_mask)[0]
        lat_slice = slice(int(lat_idx[0]), int(lat_idx[-1]) + 1)

        # Handle 0-360 vs -180-180 longitude convention
        if lon_vals.min() >= 0 and lon_min < 0:
            lon_min_360 = lon_min % 360
            lon_max_360 = lon_max % 360
            if lon_min_360 > lon_max_360:
                # Wraps across 0°: e.g. lon ∈ [346°, 360°] ∪ [0°, 5°]
                lon_mask = (lon_vals >= lon_min_360) | (lon_vals <= lon_max_360)
            else:
                lon_mask = (lon_vals >= lon_min_360) & (lon_vals <= lon_max_360)
        else:
            lon_mask = (lon_vals >= lon_min) & (lon_vals <= lon_max)

        if not lon_mask.any():
            logger.warning("_apply_prefilter: no lon points inside bbox — returning full lon range")
            return ds
        lon_idx = np.where(lon_mask)[0]
        lon_slice = slice(int(lon_idx[0]), int(lon_idx[-1]) + 1)

        dim_lat = lat.dims[0]
        dim_lon = lon.dims[0]
        logger.info(
            f"_apply_prefilter: 1-D isel [{dim_lat}={lat_slice}, {dim_lon}={lon_slice}] "
            f"({lat_slice.stop - lat_slice.start} × {lon_slice.stop - lon_slice.start} pts) "
            f"— HDF5 hyperslab: only bbox read from disk"
        )
        return ds.isel({dim_lat: lat_slice, dim_lon: lon_slice})

    # --- 2-D lat/lon (curvilinear or pseudo-curvilinear grids) ---
    # lat_vals = lat.compute().values  # shape (y, x) or (lat, lon)
    # lon_vals = lon.compute().values
    # mask_sub = ((lat_vals >= lat_min) & (lat_vals <= lat_max)) & ((lon_vals >= lon_min) & (lon_vals <= lon_max))
    # return ds.where(mask_sub)
    
    mask_2d = ((lat >= lat_min) & (lat <= lat_max) & (lon >= lon_min) & (lon <= lon_max)).compute()
    arg_where = np.argwhere(mask_2d.values)
    if arg_where.size == 0:
        logger.warning("_apply_prefilter: no points inside bbox for 2-D grid")
        return ds

    # Use lat.dims to get the actual dimension names (never assume 'y'/'x')
    dim_y, dim_x = lat.dims[0], lat.dims[1]
    # arg_where columns follow lat.dims order: col 0 = dim_y index, col 1 = dim_x index
    y_min_idx, x_min_idx = arg_where.min(axis=0)
    y_max_idx, x_max_idx = arg_where.max(axis=0)
    y_slice = slice(int(y_min_idx), int(y_max_idx) + 1)
    x_slice = slice(int(x_min_idx), int(x_max_idx) + 1)
    logger.info(
        f"_apply_prefilter: 2-D isel [{dim_y}={y_slice}, {dim_x}={x_slice}] "
        f"({y_slice.stop - y_slice.start} × {x_slice.stop - x_slice.start} pts)"
    )
    ds = ds.isel({dim_y: y_slice, dim_x: x_slice})
    return ds.where(mask_2d.isel({dim_y: y_slice, dim_x: x_slice}))


def _process_large_dataset_pipelined(dss, data_key, metazones, dirout):
    """Stage union-prefiltered datasets to one temporary zarr per source, then process.

    The union prefilter has already been applied by load_datasets(), so dss
    covers only the bounding box of all metazones combined.

    Phase 1: rechunk (on already-reduced data) → stage ONE zarr per source.
    Phase 2: for each (staging zarr × metazone), apply the per-metazone fine
             prefilter, process, and write the final zarr.  All phase-2 writes
             are fused into a single dask.compute() call.
    """
    logger.info(f"_process_large_dataset_pipelined: data_key={data_key!r} "
                f"n_datasets={len(dss)} n_metazones={len(metazones)}")

    # Rechunk AFTER the union prefilter (on reduced data).
    # HDF5 sources often have small internal chunks (e.g. 100×100) that produce
    # tens of thousands of dask tasks; merging non-time dims to
    # _STAGING_SPATIAL_CHUNK reduces task count by ~100×.
    #
    # Use the output time_chunk (Blosc 2 GB per-variable limit) rather than
    # _STAGING_TIME_CHUNK=10.  This means Phase 2 inherits the right chunk size
    # directly from the staging zarr and never needs to rechunk, eliminating
    # the main source of excess tasks in Phase 2 (~4× task reduction).
    dss_rechunked = []
    for ds in dss:
        non_time_dims = [d for d in ds.dims if d != 'time']
        rechunk_spec = {d: _STAGING_SPATIAL_CHUNK for d in non_time_dims}
        if 'time' in ds.dims:
            # _compute_output_time_chunk on the full union-prefiltered domain gives
            # a conservative lower bound: every per-metazone subset has a smaller
            # or equal bytes/tstep → its optimal tc is >= this value → no rechunk needed.
            staging_tc = _compute_output_time_chunk(ds) or _STAGING_TIME_CHUNK
            rechunk_spec['time'] = staging_tc
            logger.info(f"Staging time_chunk={staging_tc} (output-aligned, avoids Phase 2 rechunk)")
        if rechunk_spec and any(isinstance(v.data, da.Array) for v in ds.variables.values()):
            ds = ds.chunk(rechunk_spec)
        dss_rechunked.append(ds)
    del dss

    # ONE staging zarr per source dataset (not one per metazone).
    total_nbytes = sum(ds.nbytes for ds in dss_rechunked)
    zarr_dir = _get_zarr_tmp_dir(needed_bytes=total_nbytes)

    zfiles = []
    ncs = []
    try:
        # --- Phase 1: rechunk + stage to temporary zarr ---
        write_jobs = []
        for ids, ds in enumerate(dss_rechunked):
            if any(isinstance(v.data, da.Array) for v in ds.variables.values()):
                ds = ds.unify_chunks()
            if 'time' in ds.dims and 'time' in ds.chunks:
                t_chunks = ds.chunks['time']
                interior = t_chunks[:-1] if len(t_chunks) > 1 else t_chunks
                if len(set(interior)) > 1:
                    uniform_t = max(set(interior), key=interior.count)
                    ds = ds.chunk({'time': uniform_t})
            zfile = zarr_dir / f"tmp_{data_key}_{ids}.zarr"
            logger.info(f"Staging {data_key} ({ids + 1}/{len(dss_rechunked)}) -> {zfile}")
            write_jobs.append(write_dataset_to_zarr(
                ds, str(zfile), mode="w", consolidated=True,
                compute=False, minmax=False,
                compressor=_STAGING_COMPRESSOR,
            ))
            zfiles.append(zfile)

        t0 = time.time()
        compute_bundled_zarr_writes(write_jobs)
        logger.info(f"Staging done ({len(write_jobs)} zarr(s)) in {time.time() - t0:.1f}s")
        del write_jobs, dss_rechunked
        gc.collect()

        # --- Phase 2: one output zarr per (source × metazone), all in parallel ---
        #
        # Each metazone runs as an independent dask.delayed task.  Re-reading the
        # union staging zarr N times is free when it lives in /dev/shm (~20 GB/s).
        # Each task applies its own per-metazone spatial prefilter before processing.
        delayed_tasks = []
        for zfile in zfiles:
            for mz_name, mz_param in metazones.items():
                delayed_tasks.append(
                    dask.delayed(_process_metazone_from_union_zarr)(
                        str(zfile), mz_name, mz_param, dirout
                    )
                )

        nc_paths_p2 = []
        if delayed_tasks:
            nc_paths_p2 = list(dask.compute(*delayed_tasks, scheduler="threads"))
        for nc in nc_paths_p2:
            if nc:
                logger.info(f"Saved: {nc}")
        ncs = nc_paths_p2

    finally:
        for zfile in zfiles:
            if zfile.exists():
                shutil.rmtree(zfile)

    return ncs


def load_datasets(data_cfg, metazones, dirout):
    """Load datasets and process all metazone combinations.

    The union bounding-box prefilter is applied immediately after opening,
    before the small/large decision, so the threshold is compared against
    the data volume that will actually be processed (not the full global domain).

    Small datasets (< threshold after prefilter) are passed directly to
    processing.  Large datasets use the two-phase pipelined zarr path.
    """
    register_cf()
    ncouts = []

    # Compute union bounds once — shared by all datasets
    union_bounds = _extract_prefilter_bounds(metazones)

    for data_key, cfg_data in data_cfg.items():
        dataset_name = cfg_data["name"]
        logger.info(f"Load {dataset_name}...")
        start_time = time.time()

        data_type = get_data_type(cfg_data["fmt"])
        data_type.validate_load_params(cfg_data["fmt"], metazones)

        try:
            dss = open_decode(
                cfg_data["path"],
                fmt=cfg_data["fmt"],
                platform=cfg_data.get("platform")
            )
        except armoor.ArmoorError as e:
            logger.warning(f"{dataset_name}: {e} — skipping")
            continue
        if not isinstance(dss, list):
            dss = [dss]
        logger.debug(dss)

        # Attach metadata before any filtering
        for ids, ds in enumerate(dss):
            if len(dss) == 1:
                ds.attrs["data_name"] = cfg_data["name"]
            else:
                ds.attrs["data_name"] = f"{cfg_data['name']}_{ds.attrs['name']}"
            ds.attrs["data_ref"] = str(cfg_data.get("ref"))
            ds.attrs["data_type"] = data_type.name

        # Apply union prefilter FIRST so the size decision is made on
        # the actual data volume, not the full global domain.
        if union_bounds is not None:
            original_nbytes = sum(ds.nbytes for ds in dss)
            dss_filtered = []
            for ds in dss:
                ds_f = _apply_prefilter(ds, union_bounds)
                if any(s == 0 for s in ds_f.sizes.values()):
                    logger.warning(
                        f"{dataset_name}: empty after union prefilter, skipping this sub-dataset"
                    )
                    continue
                dss_filtered.append(ds_f)
            if not dss_filtered:
                logger.warning(f"{dataset_name}: all sub-datasets empty after union prefilter — skipping")
                continue
            filtered_nbytes = sum(ds.nbytes for ds in dss_filtered)
            logger.info(
                f"Union prefilter: {original_nbytes / 1e9:.1f} GB "
                f"-> {filtered_nbytes / 1e9:.1f} GB "
                f"({(1 - filtered_nbytes / max(1, original_nbytes)) * 100:.0f}% reduction)"
            )
            dss = dss_filtered

        # Size decision on filtered data
        total_nbytes = sum(ds.nbytes for ds in dss)
        zarr_threshold = _get_zarr_size_threshold()
        if total_nbytes > zarr_threshold:
            logger.info("Large dataset -- using pipelined zarr processing")
            ncs = _process_large_dataset_pipelined(dss, data_key, metazones, dirout)
        else:
            logger.info("Small dataset -- processing directly in memory")
            ncs = process_all_combinations(dss, metazones, dirout)
            for ds in dss:
                ds.close()
            del dss

        elapsed = time.time() - start_time
        logger.info(f"{dataset_name} load in {elapsed:.1f}s")
        ncouts += ncs

    return ncouts
