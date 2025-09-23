"""Input/output."""
import re, os
from typing import Dict, List
from argparse import ArgumentDefaultsHelpFormatter, RawDescriptionHelpFormatter

import dask
import numpy as np
import xarray as xr
from dask.distributed import Client
from numcodecs import Blosc


class ArmoorArgumentHelpFormatter(RawDescriptionHelpFormatter,
                                 ArgumentDefaultsHelpFormatter):
    pass

def create_fast_encoding(ds):
    """Crée un encoding optimisé pour la vitesse de sauvegarde."""
    encoding = {}
    
    for var_name, var in ds.data_vars.items():
        # encoding[var_name] = {
        #     #'zlib': True,           # Compression légère
        #     #'complevel': 1,         # Niveau minimal pour vitesse
        #     #'shuffle': False,       # Pas de shuffle pour la vitesse
        #     #'fletcher32': False,    # Pas de checksum
        # }
        encoding[var_name] = {
            'compressor': Blosc(cname='zstd', clevel=1),
            'dtype': np.float32 if var.dtype == np.float64 else var.dtype
        }
        # Chunks NetCDF optimisés
        if hasattr(var.data, 'chunks') and var.data.chunks:
            # Utiliser les chunks Dask existants
            chunksizes = []
            for i, dim_chunks in enumerate(var.data.chunks):
                if isinstance(dim_chunks, (tuple, list)):
                    chunk_size = min(dim_chunks[0], var.shape[i])
                else:
                    chunk_size = min(dim_chunks, var.shape[i])
                chunksizes.append(int(chunk_size))
            
            encoding[var_name]['chunks'] = tuple(chunksizes)
    
    return encoding

def get_zarr_encoding(ds: xr.Dataset, rechunk: bool = True) -> dict:
    """
    Create encoding dict for fast zarr save/load of large datasets.
    
    Args:
        ds: xarray dataset
        rechunk: if True, rechunk dataset to avoid conflicts
        
    Returns:
        encoding dict for .to_zarr()
    """
    encoding = {}
    
    for var_name, var in ds.data_vars.items():
        encoding[var_name] = {
            'compressor': Blosc(cname='zstd', clevel=5),
            'dtype': np.float32 if var.dtype == np.float64 else var.dtype
        }
        # Don't specify chunks - let zarr handle it
    
    return encoding


def zarrs2netcdfs(fins):
    """
    Convert multiple Zarr files to NetCDF format.
    
    This function takes a list of Zarr file paths and converts each one to NetCDF format
    by replacing the file extension from 'zarr' to 'nc'. The conversion is performed
    using xarray's open_zarr() and to_netcdf() methods.
    
    Parameters
    ----------
    fins : list of str
        List of input Zarr file paths to be converted. Empty or None values in the
        list will be skipped.
    
    Returns
    -------
    list of str
        List of output NetCDF file paths that were successfully created.
        
    Notes
    -----
    - Requires xarray to be imported as 'xr'
    - Input files must have 'zarr' extension
    - Output files will have 'nc' extension
    - Empty or None input paths are automatically skipped
    
    Examples
    --------
    >>> import xarray as xr
    >>> zarr_files = ['data1.zarr', 'data2.zarr', None, 'data3.zarr']
    >>> nc_files = zarrs2netcdfs(zarr_files)
    >>> print(nc_files)
    ['data1.nc', 'data2.nc', 'data3.nc']
    """
    extin = "zarr"
    extout = "nc"
    fouts = []
    for fin in fins:
        if fin:
            fout = str(fin).replace(extin, extout)
            xr.open_zarr(fin).to_netcdf(fout)
            fouts.append(fout)
    return fouts

def setup_dask_client():
    """Configure le client Dask de manière robuste."""
    # Configuration optimale
    # dask.config.set({
    #     "distributed.worker.profile.enabled": False,
    #     'distributed.worker.daemon': False,
    #     'distributed.comm.timeouts.connect': '120s',
    #     'distributed.comm.timeouts.tcp': '120s',
    #     'distributed.worker.memory.target': 0.9,
    #     'distributed.worker.memory.spill': 0.8,
    #     'distributed.worker.memory.pause': 0.9,
    #     'distributed.worker.memory.terminate': 0.95,
    #     'distributed.worker.memory.monitor-interval': '100ms',
    #     'distributed.scheduler.allowed-failures': 2,
    #     'distributed.scheduler.work-stealing': True,
    #     'array.shuffle.method': 'tasks',
    #     # 'array.chunk-size': '128MB',
    #     'array.slicing.split_large_chunks': False,
    #     'optimization.cull': True
    # })
    
    kw_client = dict(
       n_workers=os.cpu_count() - 2,  # Réduire le nombre de workers
       threads_per_worker=2,
       #memory_limit='8GB',#'4GB',
       silence_logs=True,
       dashboard_address=':8787',
       local_directory='/tmp',
       processes=True   
    )
    
    return kw_client

def extract_suffix_from_filename(filename):
    """
    Extracts 'time' and 'z' values from a filename in the format ref_[time]_[z].nc
    
    Args:
        filename (str): Filename to analyze
        
    Returns:
        dict: Dictionary with 'time' and 'z' keys (values None if not found)
    """
    result = {'time': None, 'z': None}
    
    # Main pattern: ref_[time]_[z].nc
    pattern_full = r'([^/]+)_(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})_([0-9.-]+)\.zarr'
    match_full = re.search(pattern_full, filename)
    if match_full:
        result['time'] = match_full.group(2)
        result['z'] = match_full.group(3)
        return result
    
    # Partial pattern: ref_[time]_*.nc (time without z)
    pattern_time_only = r'([^/]+)_(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})\.zarr'
    match_time = re.search(pattern_time_only, filename)
    
    if match_time:
        result['time'] = match_time.group(2)
    
    # Partial pattern: ref_*_[z].nc (z without valid time)
    pattern_z_only = r'([^/]+)_([0-9.-]+)\.zarr'
    match_z = re.search(pattern_z_only, filename)
    
    if match_z and not result['time']:  # Only if time not already found
        result['z'] = match_z.group(2)
    return result

def sort_ncs_by_suffix(ncs: List[str], sort_dim=["time", "z"]) -> Dict[str, List[str]]:
    """Sort a list of NetCDF files by their suffix.
    """
    ncouts = {}
    for nc in ncs:
        if not isinstance(nc, str):
            nc = str(nc)
        res = extract_suffix_from_filename(nc)
        if sort_dim == ["time", "z"]:
            if res.get("time") and res.get("z"):
                suff = f"{res['time']}_{res['z']}"
            elif not res.get("time") and res.get("z"):
                suff =  f"{res['z']}"
            elif res.get("time") and not res.get("z"):
                suff =  f"{res['time']}"
            else:
                suff = "None"
        elif sort_dim == ["z"]:
            if res.get("z"):
                suff = f"{res['z']}"
            else:
                suff = "None"
        elif sort_dim == ["time"]:
            if res.get("time"):
                suff = f"{res['time']}"
            else:
                suff = "None"
        else:
            suff = "None"
        if not ncouts.get(suff):
            ncouts[suff] = []
        
        ncouts[suff].append(nc)

    return ncouts
