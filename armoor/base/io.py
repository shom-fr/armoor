"""Input/output."""
from argparse import (
    ArgumentDefaultsHelpFormatter,
    RawDescriptionHelpFormatter,
)
import dask
from dask.distributed import Client
import numpy as np
from numcodecs import Blosc
import xarray as xr

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

def setup_dask_client():
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
        'array.shuffle.method': 'tasks',
        # 'array.chunk-size': '128MB',
        'array.slicing.split_large_chunks': False,
        'optimization.cull': True
    })

    client = Client(
        n_workers=16,  # Réduire le nombre de workers
        threads_per_worker=1,
        memory_limit='4GB',
        silence_logs=True,
        dashboard_address=':8787',
        local_directory='/tmp',
        processes=True
    )
    
    return client
