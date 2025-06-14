"""Input/output."""
from argparse import (
    ArgumentDefaultsHelpFormatter,
    RawDescriptionHelpFormatter,
)


class ArmoorArgumentHelpFormatter(RawDescriptionHelpFormatter,
                                 ArgumentDefaultsHelpFormatter):
    pass

def create_fast_encoding(ds):
    """Crée un encoding optimisé pour la vitesse de sauvegarde."""
    encoding = {}
    
    for var_name, var in ds.data_vars.items():
        encoding[var_name] = {
            'zlib': True,           # Compression légère
            'complevel': 1,         # Niveau minimal pour vitesse
            'shuffle': False,       # Pas de shuffle pour la vitesse
            'fletcher32': False,    # Pas de checksum
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
            
            encoding[var_name]['chunksizes'] = tuple(chunksizes)
    
    return encoding