"""Input/output."""
import re, os
import logging
import time
from typing import Dict, List, Tuple
from argparse import ArgumentDefaultsHelpFormatter, RawDescriptionHelpFormatter

import zarr
import dask
import numpy as np
import xarray as xr
from dask.diagnostics import ProgressBar
# dask.distributed is imported lazily in setup_dask_client to avoid the
# heavy import cost at module load time on NFS HPC filesystems.
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
    lazy_minmax = []
    minmax_vars = []

    _CF_GEO_ATTRS = {
        "lon":   {"axis": "X", "standard_name": "longitude", "units": "degrees_east"},
        "lat":   {"axis": "Y", "standard_name": "latitude",  "units": "degrees_north"},
        "depth": {"axis": "Z", "standard_name": "depth",     "positive": "down"},
    }
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

                non_uniform = not all(c == first_chunk for c in dim_chunks[:-1])
                if last_chunk > first_chunk or non_uniform:
                    # PROBLÈME DÉTECTÉ
                    needs_rechunk = True
                    optimal_size = find_valid_chunk_size(dim_size, max(dim_chunks[:-1]))
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

            # Cap chunks to stay under the Blosc 2 GB per-buffer limit
            _BLOSC_MAX_CHUNK_BYTES = 2_000_000_000
            if new_chunks:
                chunk_bytes = int(np.prod(list(new_chunks.values()))) * var.dtype.itemsize
                if chunk_bytes > _BLOSC_MAX_CHUNK_BYTES:
                    while chunk_bytes > _BLOSC_MAX_CHUNK_BYTES:
                        spatial = {d: new_chunks[d] for d in new_chunks if d != 'time'}
                        dim_to_reduce = max(
                            spatial if spatial else new_chunks,
                            key=(spatial if spatial else new_chunks).__getitem__
                        )
                        new_chunks[dim_to_reduce] = max(1, new_chunks[dim_to_reduce] // 2)
                        chunk_bytes = int(np.prod(list(new_chunks.values()))) * var.dtype.itemsize
                    needs_rechunk = True
                    if verbose:
                        logger.debug(f"  → Capped chunks for Blosc 2 GB limit: {new_chunks}")

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
        if np.issubdtype(da_fixed.dtype, np.number) and da_fixed.size > 0 and da_fixed.chunks is not None:
            lazy_minmax.append(da_fixed.min())
            lazy_minmax.append(da_fixed.max())
            minmax_vars.append(var_name)
        if "step" in da_fixed.attrs:
            da_fixed.attrs.pop("step")
        if var_name in _CF_GEO_ATTRS:
            da_fixed.attrs.update(_CF_GEO_ATTRS[var_name])
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

    return ds_fixed, encoding, (lazy_minmax, minmax_vars)

def _apply_minmax_to_zarr(path, minmax_vars, computed_minmax, ds):
    """Update zarr store attrs with computed valid_min/valid_max."""
    import cftime
    import pandas as pd

    store = zarr.open(str(path), mode='r+')
    for idx, var_name in enumerate(minmax_vars):
        result_vmin = computed_minmax[2 * idx]
        result_vmax = computed_minmax[2 * idx + 1]
        if result_vmin is None or result_vmax is None:
            logger.warning(
                f"_apply_minmax_to_zarr: min/max for '{var_name}' is None "
                f"— skipping valid_min/valid_max attrs for this variable"
            )
            continue
        vmin = result_vmin.values
        vmax = result_vmax.values
        if var_name == "time":
            da_t = ds[var_name]
            if "units" in da_t.encoding:
                units = da_t.encoding['units']
                calendar = da_t.encoding.get('calendar', 'standard')
                vmin = float(cftime.date2num(
                    pd.to_datetime(vmin).to_pydatetime(), units, calendar))
                vmax = float(cftime.date2num(
                    pd.to_datetime(vmax).to_pydatetime(), units, calendar))
        store[var_name].attrs['valid_min'] = float(vmin)
        store[var_name].attrs['valid_max'] = float(vmax)
    zarr.consolidate_metadata(str(path))


class _BundledNetcdfWrite:
    """Bundles netcdf write + min/max computation into a single dask pass."""

    def __init__(self, write_delayed, lazy_minmax, minmax_vars, path, ds):
        self._write_delayed = write_delayed
        self._lazy_minmax = lazy_minmax
        self._minmax_vars = minmax_vars
        self._path = path
        self._ds = ds

    def compute(self):
        results = dask.compute(self._write_delayed, *self._lazy_minmax)
        if self._lazy_minmax:
            _apply_minmax_to_netcdf(
                self._path, self._minmax_vars, results[1:], self._ds)
        return results[0]


class _BundledZarrWrite:
    """Bundles zarr write + min/max computation into a single dask pass.

    When .compute() is called, both the zarr write and the min/max
    reductions share the same task graph, so each data chunk is read
    only once instead of twice.
    """

    def __init__(self, write_delayed, lazy_minmax, minmax_vars, path, ds):
        self._write_delayed = write_delayed
        self._lazy_minmax = lazy_minmax
        self._minmax_vars = minmax_vars
        self._path = path
        self._ds = ds

    def compute(self):
        results = dask.compute(self._write_delayed, *self._lazy_minmax)
        if self._lazy_minmax:
            _apply_minmax_to_zarr(
                self._path, self._minmax_vars, results[1:], self._ds)
        return results[0]


def compute_bundled_zarr_writes(write_jobs):
    """Compute multiple _BundledZarrWrite objects in a single dask pass.

    All write jobs are submitted together so the dask thread scheduler can
    run them in parallel — in practice N zarr writes proceed concurrently
    without waiting for each other.

    Note: optimize_graph=False is intentional.  Dask's graph optimizer can
    reorder or fuse zarr write tasks in ways that corrupt the store, so we
    disable it.  As a result there is no read deduplication across jobs; the
    parallelism benefit is write concurrency only.

    The scheduler used can be overridden via the ARMOOR_DASK_SCHEDULER env
    var ('threads', 'synchronous', 'processes') for benchmarking purposes.

    Parameters
    ----------
    write_jobs : list of _BundledZarrWrite
        Write jobs returned by ``write_dataset_to_zarr(..., compute=False)``.
    """
    import os
    scheduler = os.environ.get("ARMOOR_DASK_SCHEDULER", "threads")

    all_delayed = []
    for job in write_jobs:
        if job._write_delayed is not None:
            all_delayed.append(job._write_delayed)
        all_delayed.extend(job._lazy_minmax)

    def _task_count(d):
        """Return dask task count for d; 0 for non-dask or empty graphs."""
        try:
            g = d.__dask_graph__()
            return len(g) if g is not None else 0
        except (AttributeError, TypeError):
            return 0

    n_jobs = len(write_jobs)
    total_tasks = sum(_task_count(d) for d in all_delayed)
    logger.info(
        f"compute_bundled_zarr_writes: {total_tasks} tasks, {n_jobs} zarr(s), "
        f"scheduler={scheduler!r}"
    )

    t0 = time.time()
    kw = dict(optimize_graph=False)
    if scheduler == "threads":
        # Use at least os.cpu_count() threads so a single-zarr staging write
        # (n_jobs=1 → formula gives 4) still saturates all available CPUs.
        # n_cpus = os.cpu_count() or 8
        #kw["num_workers"] = min(, max(n_jobs * 4, n_cpus))
        ncpus = os.cpu_count()
        if ncpus >= n_jobs * 4:
            num_workers = ncpus
        elif ncpus <= 2:
            num_workers = 1
        else:
            num_workers = ncpus - 2
        kw["num_workers"] = min(num_workers, max(n_jobs * 4, ncpus // 4))

    with ProgressBar(dt=30.0):
        results = dask.compute(*all_delayed, scheduler=scheduler, **kw)

    logger.info(f"compute_bundled_zarr_writes: done in {time.time() - t0:.1f}s")

    offset = 0
    for job in write_jobs:
        n = len(job._lazy_minmax)
        if job._lazy_minmax:
            _apply_minmax_to_zarr(
                job._path, job._minmax_vars, results[offset + 1: offset + 1 + n], job._ds)
        else:
            # No min/max to compute, but still consolidate metadata so that
            # subsequent xr.open_zarr() calls read a single .zmetadata file
            # instead of stat-ing every chunk directory on (potentially slow) NFS.
            zarr.consolidate_metadata(str(job._path))
        offset += 1 + n


def _apply_minmax_to_netcdf(path, minmax_vars, computed_minmax, ds):
    """Update netcdf file attrs with computed valid_min/valid_max."""
    import cftime
    import pandas as pd
    import netCDF4

    with netCDF4.Dataset(str(path), mode='a') as nc:
        for idx, var_name in enumerate(minmax_vars):
            vmin = computed_minmax[2 * idx].values
            vmax = computed_minmax[2 * idx + 1].values
            if var_name == "time":
                da_t = ds[var_name]
                if "units" in da_t.encoding:
                    units = da_t.encoding['units']
                    calendar = da_t.encoding.get('calendar', 'standard')
                    vmin = float(cftime.date2num(
                        pd.to_datetime(vmin).to_pydatetime(), units, calendar))
                    vmax = float(cftime.date2num(
                        pd.to_datetime(vmax).to_pydatetime(), units, calendar))
            if var_name in nc.variables:
                nc.variables[var_name].setncattr('valid_min', float(vmin))
                nc.variables[var_name].setncattr('valid_max', float(vmax))


def write_dataset_to_netcdf(ds: xr.Dataset, path: str, compute: bool = True):
    """
    Sauvegarde Netcdf avec attrs et encoding.

    Computes the netcdf write and valid_min/valid_max in a single dask pass
    so that data chunks are read only once.

    Parameters:
    -----------
    ds : xr.Dataset
        Dataset à sauvegarder
    path : str
        Chemin de sortie NetCDF
    compute : bool
        Calculer immédiatement (True) ou retourner delayed (False)
    """
    ds, encoding, (lazy_minmax, minmax_vars) = auto_fix_zarr_encoding(ds)
    write_delayed = ds.to_netcdf(path, compute=False, encoding=encoding, format="NETCDF4")

    if compute:
        results = dask.compute(write_delayed, *lazy_minmax)
        if lazy_minmax:
            _apply_minmax_to_netcdf(path, minmax_vars, results[1:], ds)
        return results[0]
    else:
        return _BundledNetcdfWrite(
            write_delayed, lazy_minmax, minmax_vars, path, ds)

def write_dataset_to_zarr(
    ds: xr.Dataset,
    path: str,
    mode: str = 'w',
    consolidated: bool = True,
    compute: bool = True,
    minmax: bool = True,
    compressor=None,
    **kwargs
    ):
    """
    Sauvegarde sécurisée vers Zarr avec correction automatique.

    Computes the zarr write and valid_min/valid_max in a single dask pass
    so that data chunks are read only once.

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
    compressor : numcodecs compressor or None
        Override the zarr compressor for all variables.  Pass a fast
        compressor (e.g. ``Blosc(cname='lz4', clevel=1)``) for temporary
        staging writes, or ``None`` to keep the default.
    **kwargs : arguments supplémentaires pour to_zarr()
    """
    # Correction automatique
    ds, encoding, (lazy_minmax, minmax_vars) = auto_fix_zarr_encoding(ds)
    if not minmax:
        lazy_minmax = []
        minmax_vars = []

    if compressor is not None:
        for var_name in encoding:
            encoding[var_name]['compressor'] = compressor

    logger.info(f"\n Write: {path}")
    logger.debug(f"   Mode: {mode}")
    logger.debug(f"   Consolidated metadata: {consolidated}")

    # Create delayed write job
    write_delayed = ds.to_zarr(
        path,
        mode=mode,
        consolidated=consolidated,
        compute=False,
        encoding=encoding,
        **kwargs
        )

    if write_delayed is None:
        # Older xarray (< 2022.06) writes synchronously for non-dask datasets
        # and returns None instead of a Delayed.  Wrap in a no-op so that
        # compute_bundled_zarr_writes can handle this job uniformly.
        write_delayed = dask.delayed(lambda: None)()

    if compute:
        # Compute write + min/max in a single dask pass
        results = dask.compute(write_delayed, *lazy_minmax)
        if lazy_minmax:
            _apply_minmax_to_zarr(path, minmax_vars, results[1:], ds)
        logger.info("Successfully written.")
        return results[0]
    else:
        logger.info("Delayed writting.")
        return _BundledZarrWrite(
            write_delayed, lazy_minmax, minmax_vars, path, ds)

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

    def _convert_single(fin):
        fout = str(fin).replace(extin, extout)
        xr.open_zarr(fin).to_netcdf(fout)
        return fout

    delayed_results = [dask.delayed(_convert_single)(fin) for fin in fins if fin]
    if delayed_results:
        fouts = list(dask.compute(*delayed_results))
    else:
        fouts = []
    return fouts

def setup_dask_client(n_workers, processes, memory_limit, dashboardaddress, localdirectory):  # noqa: E501
    """Configure le client Dask de manière robuste."""
    from dask.distributed import Client  # noqa: F401 — lazy import, heavy on NFS HPC
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

def output_suffix(attrs):
    """Build the ``_<time-or-trange>_<vlevel-or-vrange>`` output filename suffix.

    Inverse of `extract_suffix_from_filename` below: reads the
    ``time``/``trange``/``vlevel``/``vrange`` attrs set by
    `armoor.base.ranges.tfreq`/`trange_seq`/`vlevels`/`vrange`; time-like
    attrs take priority over the range-like ones when both happen to be set.
    `trange` is a bracketed range (e.g. ``"[2020-01-01T00:00:00_2020-01-31T00:00:00["``)
    -- the brackets aren't filename-safe, so they're stripped here.

    Parameters
    ----------
    attrs : dict
        A dataset's ``.attrs``.

    Returns
    -------
    str
        Empty string if none of the four attrs is present.
    """
    parts = []
    if "time" in attrs:
        parts.append(attrs["time"])
    elif "trange" in attrs:
        parts.append(re.sub(r"[\[\]]", "", attrs["trange"]))
    if "vlevel" in attrs:
        parts.append(attrs["vlevel"])
    elif "vrange" in attrs:
        parts.append(attrs["vrange"])
    return "".join(f"_{p}" for p in parts)


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
    
    sub_pattern_time = r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}'
    pattern_time = rf'(_(?P<dates>{sub_pattern_time}(?:_{sub_pattern_time})?))'

    pattern_z = r'_([0-9.-]+)'

    # Main pattern: ref_[time]_[z].nc
    pattern_full = rf'(?P<prefix>[^_]+){pattern_time}{pattern_z}\.zarr'
    match_full = re.search(pattern_full, filename)
    if match_full:
        result['time'] = match_full.group(2)
        result['z'] = match_full.group(4)

    # Partial pattern: ref_[time]_*.nc (time without z)
    pattern_time_only = rf'(?P<prefix>[^_]+){pattern_time}\.zarr'
    match_time = re.search(pattern_time_only, filename)

    if match_time:
        result['time'] = match_time.groups()[-1]

    # Partial pattern: ref_*_[z].nc (z without valid time)
    pattern_z_only = rf'(?P<prefix>[^_]+){pattern_z}\.zarr'
    match_z = re.search(pattern_z_only, filename)
    if match_z and not result['time']:  # Only if time not already found
        result['z'] = match_z.group(2)
        
    return result

def _range_info_from_staged(nc):
    """Read time/vlevel-like info directly off a StagedDataset, if present.

    Returns None when `nc` carries none of these attrs (e.g. a plain str,
    or a StagedDataset from a stage that never set them), signalling the
    caller should fall back to `extract_suffix_from_filename`.

    Parameters
    ----------
    nc : str or armoor.data.load.StagedDataset
        A path, possibly carrying `.time`/`.trange`/`.vlevel`/`.vrange`.

    Returns
    -------
    dict or None
        ``{"time": ..., "z": ...}`` (matching `extract_suffix_from_filename`'s
        shape) if any of the four attrs is set, else None.
    """
    time_val = getattr(nc, "time", None)
    if time_val is None:
        trange_val = getattr(nc, "trange", None)
        # trange is bracketed (e.g. "[t1_t2["); strip to match the
        # filename-derived form output_suffix() already produces on disk.
        time_val = re.sub(r"[\[\]]", "", trange_val) if trange_val else None
    z_val = getattr(nc, "vlevel", None) or getattr(nc, "vrange", None)
    if time_val is None and z_val is None:
        return None
    return {"time": time_val, "z": z_val}


def sort_ncs_by_suffix(ncs: List[str], sort_dim=["time", "z"]) -> Dict[str, List[str]]:
    """Sort a list of NetCDF files by their suffix.
    """
    ncouts = {}
    for nc in ncs:
        res = _range_info_from_staged(nc)
        if res is None:
            res = extract_suffix_from_filename(str(nc))

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
