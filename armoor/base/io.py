"""Input/output."""
import re, os
import logging
from typing import Dict, List, Tuple
from argparse import ArgumentDefaultsHelpFormatter, RawDescriptionHelpFormatter

import cftime
import zarr
import dask
import numpy as np
import pandas as pd
import xarray as xr
from dask.distributed import Client
from numcodecs import Blosc

logger = logging.getLogger(__name__)


class ArmoorArgumentHelpFormatter(RawDescriptionHelpFormatter,
                                 ArgumentDefaultsHelpFormatter):
    pass

def find_valid_chunk_size(dim_size: int, current_first_chunk: int) -> int:
    """
    Trouve une taille de chunk valide qui divise exactement la dimension
    ou dont le dernier chunk est plus petit que le premier.

    Parameters
    ----------
    dim_size : int
        Taille totale de la dimension
    current_first_chunk : int
        Taille actuelle du premier chunk

    Returns
    -------
    int
        Taille de chunk optimale
    """
    # Option 1: Divise exactement
    for chunk_size in range(current_first_chunk, 0, -1):
        if dim_size % chunk_size == 0:
            return chunk_size
    
    # Option 2: Le reste est plus petit
    chunk_size = current_first_chunk
    while chunk_size <= dim_size:
        remainder = dim_size % chunk_size
        if remainder == 0 or remainder < chunk_size:
            return chunk_size
        chunk_size -= 1
    
    # Fallback: chunk unique
    return dim_size


def auto_fix_zarr_encoding(ds: xr.Dataset, verbose: bool = True) -> xr.Dataset:
    """
    Corrige automatiquement TOUS les problèmes d'encodage Zarr.
    
    Cette fonction:
    1. Analyse tous les chunks actuels
    2. Détecte les problèmes (dernier chunk > premier chunk)
    3. Recalcule des chunks optimaux
    4. Nettoie tous les encodages problématiques
    
    Parameters:
    -----------
    ds : xr.Dataset
        Dataset à corriger
    verbose : bool
        Afficher les détails (défaut: True)
        
    Returns
    -------
    --------
    xr.Dataset : Dataset corrigé, prêt pour to_zarr()
    """
    if verbose:
        logger.debug("=" * 70)
        logger.debug("AUTO-FIX ZARR CHUNKS")
        logger.debug("=" * 70)
    
    ds_fixed = ds.copy()   
    
    encoding = {}
    # Traiter toutes les variables (data + coords)
    all_vars = list(ds_fixed.data_vars) + list(ds_fixed.coords)
    for var_name in all_vars:
        var = ds_fixed[var_name]
        
        # Skip si pas de chunks
        if var.chunks is None:
            if verbose:
                logger.debug(f"\n {var_name}: No chunks chunks (small array)")
            # continue
        else:
            if verbose:
                logger.debug(f"\n{'─' * 70}")
                logger.debug(f"Variable: {var_name}")
                logger.debug(f"  Shape: {var.shape}")
                logger.debug(f"  Dims: {var.dims}")
                logger.debug(f"  Actual chunks: {var.chunks}")
            
            # Analyser chaque dimension
            needs_rechunk = False
            new_chunks = {}
            
            for dim_name, dim_size, dim_chunks in zip(var.dims, var.shape, var.chunks):
                n_chunks = len(dim_chunks)
                
                if n_chunks <= 1:
                    # Un seul chunk - OK
                    new_chunks[dim_name] = dim_size
                    if verbose:
                        logger.debug(f"  {dim_name}: 1 chunk ({dim_size}) - OK")
                    continue
                
                first_chunk = dim_chunks[0]
                last_chunk = dim_chunks[-1]
                
                if last_chunk > first_chunk:
                    # PROBLÈME DÉTECTÉ
                    needs_rechunk = True
                    optimal_size = find_valid_chunk_size(dim_size, first_chunk)
                    new_chunks[dim_name] = optimal_size
                    
                    if verbose:
                        logger.debug(f" {dim_name}: Detected problem!")
                        logger.debug(f"    - Dimension size: {dim_size}")
                        logger.debug(f"    - Actual chunks: {dim_chunks}")
                        logger.debug(f"    - First chunk: {first_chunk}, Last: {last_chunk}")
                        logger.debug(f"    - New chunk: {optimal_size}")
                        
                        # Calculer la nouvelle distribution
                        n_full = dim_size // optimal_size
                        remainder = dim_size % optimal_size
                        if remainder > 0:
                            logger.debug(f"    - Result: {n_full} chunks of {optimal_size} + 1 chunk of {remainder}")
                        else:
                            logger.debug(f"    - Result: {n_full} chunks of {optimal_size} (division exacte)")
                else:
                    # Chunks OK - garder la taille du premier
                    new_chunks[dim_name] = first_chunk
                    if verbose:
                        logger.debug(f"  {dim_name}: Chunks OK ({n_chunks} chunks: {first_chunk}...{last_chunk})")
            
            # Rechunker si nécessaire
            if needs_rechunk:
                if verbose:
                    logger.debug(f"  → Rechunking with: {new_chunks}")
                ds_fixed[var_name] = var.chunk(new_chunks)
        da_fixed = ds_fixed[var_name]
        safe_encoding = {}
        for encod in ["units", "calendar"]:
            if encod in da_fixed.encoding:
                e = da_fixed.encoding[encod]
                safe_encoding[encod] = e
        if var_name == "time":
            safe_encoding["dtype"] = np.float64
        safe_encoding["_FillValue"] = -99999
        encoding[var_name] = safe_encoding
        da_fixed.encoding = safe_encoding
        for key, val in list(da_fixed.attrs.items()):
            if isinstance(val, (np.integer, int)):
                da_fixed.attrs[key] = float(val)
            elif isinstance(val, str):
                da_fixed.attrs[key] = str(val)
        if np.issubdtype(da_fixed.dtype, np.number):
            vmin = da_fixed.min().values
            vmax = da_fixed.max().values
            if var_name == "time":
                if "units" in da_fixed.encoding:
                    units = da_fixed.encoding['units']
                    calendar = da_fixed.encoding.get('calendar', 'standard')
                    dtvmin = pd.to_datetime(vmin).to_pydatetime()
                    dtvmax = pd.to_datetime(vmax).to_pydatetime()
                    vmin = cftime.date2num(dtvmin, units, calendar)
                    vmax = cftime.date2num(dtvmax, units, calendar)
            
            da_fixed.attrs["valid_min"] = float(vmin)
            da_fixed.attrs["valid_max"] = float(vmax)
        if var_name in ("lon", "lat", "depth"):
            if "axis" in da_fixed.attrs:
                da_fixed.attrs.pop("axis")
            if "step" in da_fixed.attrs:
                da_fixed.attrs.pop("step")
        da_fixed.attrs["coordinates"] = ','.join(list(da_fixed.dims))
        ds_fixed[var_name] = da_fixed
        if verbose:
            logger.debug(f"  Encoding cleaned (kept: {list(safe_encoding.keys())})")
    if verbose:
        logger.debug("\n" + "=" * 70)
        logger.debug("Every problem corrected?")
        logger.debug("=" * 70)
        
        # Résumé
        logger.debug("\nFinal chunks:")
        for var_name in ds_fixed.data_vars:
            var = ds_fixed[var_name]
            if var.chunks is not None:
                logger.debug(f"  {var_name}: {var.chunks}")

    return ds_fixed, encoding

def write_dataset_to_netcdf(ds: xr.Dataset, path: str, compute: bool = True):
    """
    Sauvegarde Netcdf avec attrs et encoding.
    
    Parameters:
    -----------
    ds : xr.Dataset
        Dataset à sauvegarder
    path : str
        Chemin de sortie Zarr
    compute : bool
        Calculer immédiatement (True) ou retourner delayed (False)
    """
    ds, encoding = auto_fix_zarr_encoding(ds)
    res = ds.to_netcdf(path, compute=compute, encoding=encoding, format="NETCDF4")
    return res

def write_dataset_to_zarr(
    ds: xr.Dataset,
    path: str,
    mode: str = 'w',
    consolidated: bool = True,
    compute: bool = True,
    **kwargs
):
    """
    Sauvegarde sécurisée vers Zarr avec correction automatique.
    
    Parameters:
    -----------
    ds : xr.Dataset
        Dataset à sauvegarder
    path : str
        Chemin de sortie Zarr
    mode : str
        Mode d'écriture ('w', 'a', 'w-')
    consolidated : bool
        Consolider les métadonnées (recommandé)
    compute : bool
        Calculer immédiatement (True) ou retourner delayed (False)
    **kwargs : arguments supplémentaires pour to_zarr()
    """
    # Correction automatique
    ds, encoding = auto_fix_zarr_encoding(ds)

    logger.info(f"\n Write: {path}")
    logger.debug(f"   Mode: {mode}")
    logger.debug(f"   Consolidated metadata: {consolidated}")
    
    # Écriture
    result = ds.to_zarr(
        path,
        mode=mode,
        consolidated=consolidated,
        compute=compute,
        encoding=encoding,
        **kwargs
    )
    
    if compute:
        logger.info("Successfully written.")
    else:
        logger.info("Delayed writting.")
    
    return result

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
    
    Parameters
    ----------
    ds
        xarray dataset
    rechunk
        if True, rechunk dataset to avoid conflicts
        
    Returns
    -------
    encoding dict for .to_zarr()
    """
    encoding = {}
    
    for var_name, var in ds.data_vars.items():
        encoding[var_name] = {
            # 'compressors': Blosc(cname='zstd', clevel=5),
            # 'dtype': np.float32 if var.dtype == np.float64 else var.dtype,
            # 'chunks': var.chunks
        }
        # Don't specify chunks - let zarr handle it
    return create_fast_encoding(ds)


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

def setup_dask_client(n_workers, processes, memory_limit, dashboardaddress, localdirectory):
    """Configure le client Dask de manière robuste."""
    # Configuration optimale
    dask.config.set({
        "distributed.worker.profile.enabled": False,
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
        #'array.shuffle.method': 'tasks',
        # 'array.chunk-size': '128MB',
        # 'optimization.cull': True
        'array.slicing.split_large_chunks': True,
        'optimization.fuse.active': True,
    })
    
    kw_client = dict(
        n_workers=n_workers,#os.cpu_count() - 2,  # Réduire le nombre de workers
        threads_per_worker=2,
        memory_limit=memory_limit,#'750MB',#'4GB',
        silence_logs=True,
        dashboard_address=dashboardaddress,#:8082,
        local_directory=localdirectory,
        processes=processes
    )
    
    return kw_client

def extract_suffix_from_filename(filename):
    """
    Extracts 'time' and 'z' values from a filename in the format ref_[time]_[z].nc
    
    Parameters
    ----------
    filename : str
        Filename to analyze
        
    Returns
    -------
    dict
        Dictionary with 'time' and 'z' keys (values None if not found)
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
