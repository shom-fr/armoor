import gc
import logging
import shutil
from pathlib import Path

from dask.distributed import Client


logger = logging.getLogger(__name__)

def to_netcdf_ref_prods(dss, parent_dir, ncpat):
    """Save in netcdf files reference and products from data.

    This function separates datasets into references and products based on the
    'ref' attribute in each dataset.

    Parameters
    ----------
    dss : Dict[str, List[xr.Dataset]]
        Dictionary where keys are measurement zone names and values are lists of datasets.
        Each dataset must have 'data_name' and 'data_ref' attributes.
    parent_dir : str or Path
        Parent directory where NetCDF files will be saved.
    ncpat : str
        Filename pattern with format placeholders. Should include variables like:
        {mz_name}, {data_name}, {refprod} for proper file organization.
        Example: "{refprod}/{mz_name}/{data_name}.nc"

    Returns
    -------
        tuple: Two list, one for reference and one for products.
    """
    ncs_prod = []
    for mz_name, datasets in dss.items():
        for ds in datasets:
            data_name = ds.attrs["data_name"]
            refprod = "ref" if ds.attrs["data_ref"] == "True" else "prod"
            nc = Path(parent_dir) / ncpat.format(**locals())
            ncs_prod.append(nc)
            nc.parent.mkdir(parents=True, exist_ok=True)
            ds.to_netcdf(nc, compute=True)
            ds.close()
            gc.collect()
    return ncs_prod

# import gc
# import logging
# from pathlib import Path
# from typing import Dict, List, Union, Tuple
# import xarray as xr
# import dask 

# def to_netcdf_ref_prods(
#     dss: Dict[str, List[xr.Dataset]], 
#     parent_dir: Union[str, Path], 
#     ncpat: str,
#     compression: str = "zlib",
#     complevel: int = 5,
#     shuffle: bool = True,
#     verbose: bool = True
# ) -> Tuple[List[Path], List[Path]]:
#     """
#     Save datasets to NetCDF files, separating references and products.
    
#     This function processes a dictionary of datasets and saves them as NetCDF files,
#     automatically categorizing them as references or products based on the 'data_ref' 
#     attribute. Files are organized in separate directories and compressed for efficient storage.
    
#     Parameters
#     ----------
#     dss : Dict[str, List[xr.Dataset]]
#         Dictionary where keys are measurement zone names and values are lists of datasets.
#         Each dataset must have 'data_name' and 'data_ref' attributes.
#     parent_dir : str or Path
#         Parent directory where NetCDF files will be saved.
#     ncpat : str
#         Filename pattern with format placeholders. Should include variables like:
#         {mz_name}, {data_name}, {refprod} for proper file organization.
#         Example: "{refprod}/{mz_name}/{data_name}.nc"
#     compression : str, optional
#         Compression algorithm for NetCDF files (default: "zlib").
#         Options: "zlib", "lzf", "gzip", "szip".
#     complevel : int, optional
#         Compression level from 1 (fast) to 9 (best compression) (default: 5).
#     shuffle : bool, optional
#         Whether to use shuffle filter for better compression (default: True).
#     verbose : bool, optional
#         Whether to print progress information (default: True).
    
#     Returns
#     -------
#     Tuple[List[Path], List[Path]]
#         Two lists containing paths to saved files:
#         - First list: reference files
#         - Second list: product files
    
#     Raises
#     ------
#     KeyError
#         If required attributes ('data_name', 'data_ref') are missing from datasets.
#     ValueError
#         If 'data_ref' attribute contains invalid values (not 'True' or 'False').
#     OSError
#         If there are issues creating directories or writing files.
    
#     Notes
#     -----
#     - Datasets are automatically closed after saving to free memory
#     - Garbage collection is performed after each save operation
#     - Files are saved with compression to reduce disk usage
#     - Reference files are identified by data_ref='True', products by data_ref='False'
    
#     Examples
#     --------
#     >>> # Basic usage
#     >>> datasets = {
#     ...     'zone1': [ds1, ds2],
#     ...     'zone2': [ds3, ds4]
#     ... }
#     >>> pattern = "{refprod}/{mz_name}_{data_name}.nc"
#     >>> ref_files, prod_files = to_netcdf_ref_prods(datasets, "/output", pattern)
    
#     >>> # With custom compression
#     >>> ref_files, prod_files = to_netcdf_ref_prods(
#     ...     datasets, "/output", pattern,
#     ...     compression="gzip", complevel=9
#     ... )
    
#     >>> # Check results
#     >>> print(f"Saved {len(ref_files)} reference files")
#     >>> print(f"Saved {len(prod_files)} product files")
#     """
#     # Initialize return lists
#     # ncs_ref = []
#     # ncs_prod = []
#     ncs_out = []
    
#     # Setup logging if verbose
#     if verbose:
#         logging.basicConfig(level=logging.INFO)
#         logger = logging.getLogger(__name__)
    
#     # Convert parent_dir to Path object
#     parent_dir = Path(parent_dir)
    
#     # Validation
#     if not dss:
#         raise ValueError("Input dictionary 'dss' is empty")
    
#     total_datasets = sum(len(datasets) for datasets in dss.values())
#     processed = 0
    
#     if verbose:
#         logger.info(f"Processing {total_datasets} datasets from {len(dss)} measurement zones")
    
#     try:
#         for mz_name, datasets in dss.items():
#             if verbose:
#                 logger.info(f"Processing measurement zone: {mz_name} ({len(datasets)} datasets)")
            
#             for i, ds in enumerate(datasets):
#                 # Validate required attributes
#                 if "data_name" not in ds.attrs:
#                     raise KeyError(f"Dataset {i} in zone '{mz_name}' missing 'data_name' attribute")
                
#                 if "data_ref" not in ds.attrs:
#                     raise KeyError(f"Dataset {i} in zone '{mz_name}' missing 'data_ref' attribute")
                
#                 # Extract attributes
#                 data_name = ds.attrs["data_name"]
#                 data_ref_str = str(ds.attrs["data_ref"])
                
#                 # Validate data_ref value
#                 if data_ref_str not in ["True", "False"]:
#                     raise ValueError(f"Invalid 'data_ref' value: {data_ref_str}. Must be 'True' or 'False'")
                
#                 # Determine reference or product
#                 refprod = "ref" if data_ref_str == "True" else "prod"
                
#                 # Create file path using format string
#                 try:
#                     nc_path = parent_dir / ncpat.format(**locals())
#                 except KeyError as e:
#                     raise ValueError(f"Pattern '{ncpat}' contains undefined placeholder: {e}")
                
#                 # Create parent directory
#                 nc_path.parent.mkdir(parents=True, exist_ok=True)
                
#                 # Configure encoding for compression
#                 encoding = {}
#                 for var in ds.data_vars:
#                     encoding[var] = {
#                         'zlib': compression == 'zlib',
#                         'complevel': complevel if compression == 'zlib' else None,
#                         'shuffle': shuffle,
#                         '_FillValue': None
#                         }
                
#                 # Save to NetCDF
#                 if verbose:
#                     logger.info(f"Saving {refprod}: {nc_path.name}")
                
#                 #ds = ds.optimize()
#                 # with dask.config.set(scheduler='threads'):
#                 #     ds = ds.compute()
#                 ds.to_netcdf(
#                     nc_path,
#                     #engine="h5netcdf",
#                     compute=True,
#                     encoding=encoding if compression else None
#                     )
                
#                 # # Add to appropriate list
#                 # if refprod == "ref":
#                 #     ncs_ref.append(nc_path)
#                 # else:
#                 #     ncs_prod.append(nc_path)
#                 ncs_out.append(nc_path)
#                 # Memory management
#                 ds.close()
#                 processed += 1
                
#                 # Periodic garbage collection for large datasets
#                 if processed % 10 == 0:
#                     gc.collect()
                
#                 if verbose and processed % 5 == 0:
#                     logger.info(f"Progress: {processed}/{total_datasets} datasets processed")
    
#     except Exception as e:
#         logger.error(f"Error during processing: {str(e)}")
#         raise
    
#     finally:
#         # Final cleanup
#         gc.collect()
    
#     if verbose:
#         logger.info(f"✅ Successfully saved {len(ncs_out)} reference and  product files")
#         logger.info(f"Total disk space used: {_calculate_total_size(ncs_out):.2f} MB")
    
#     return ncs_out


# def _calculate_total_size(file_paths: List[Path]) -> float:
#     """Calculate total size of files in MB."""
#     total_size = 0
#     for path in file_paths:
#         if path.exists():
#             total_size += path.stat().st_size
#     return total_size / (1024 * 1024)


# # Utility function for batch processing
# def batch_to_netcdf_ref_prods(
#     dss: Dict[str, List[xr.Dataset]], 
#     parent_dir: Union[str, Path], 
#     ncpat: str,
#     batch_size: int = 50,
#     **kwargs
# ) -> Tuple[List[Path], List[Path]]:
#     """
#     Process large datasets in batches to manage memory usage.
    
#     Parameters
#     ----------
#     dss : Dict[str, List[xr.Dataset]]
#         Dictionary of datasets to process
#     parent_dir : str or Path
#         Output directory
#     ncpat : str
#         Filename pattern
#     batch_size : int, optional
#         Number of datasets to process per batch (default: 50)
#     **kwargs
#         Additional arguments passed to to_netcdf_ref_prods
    
#     Returns
#     -------
#     Tuple[List[Path], List[Path]]
#         Combined lists of reference and product file paths
#     """
#     all_refs = []
#     all_prods = []
    
#     # Convert to list of (mz_name, dataset) pairs
#     all_items = []
#     for mz_name, datasets in dss.items():
#         for ds in datasets:
#             all_items.append((mz_name, ds))
    
#     # Process in batches
#     for i in range(0, len(all_items), batch_size):
#         batch_items = all_items[i:i + batch_size]
        
#         # Reconstruct dictionary for batch
#         batch_dss = {}
#         for mz_name, ds in batch_items:
#             if mz_name not in batch_dss:
#                 batch_dss[mz_name] = []
#             batch_dss[mz_name].append(ds)
        
#         # Process batch
#         batch_refs, batch_prods = to_netcdf_ref_prods(batch_dss, parent_dir, ncpat, **kwargs)
        
#         all_refs.extend(batch_refs)
#         all_prods.extend(batch_prods)
        
#         # Force garbage collection between batches
#         gc.collect()
    
#     return all_refs + all_prods

# import logging
# import gc
# from pathlib import Path
# from typing import Dict, List, Union, Tuple, Optional
# import xarray as xr
# import dask
# from concurrent.futures import ThreadPoolExecutor, as_completed
# from dataclasses import dataclass


# @dataclass
# class CompressionConfig:
#     """Configuration pour la compression NetCDF."""
#     algorithm: str = None
#     level: int = 1
#     shuffle: bool = False
    
#     def validate(self):
#         """Valide la configuration de compression."""
#         valid_algorithms = ["zlib", "lzf", "gzip", "szip", None]
#         if self.algorithm not in valid_algorithms:
#             raise ValueError(f"Algorithm '{self.algorithm}' not in {valid_algorithms}")
#         if not 1 <= self.level <= 9:
#             raise ValueError("Compression level must be between 1 and 9")


# def to_netcdf_ref_prods(
#     dss: Dict[str, List[xr.Dataset]], 
#     parent_dir: Union[str, Path], 
#     ncpat: str,
#     compression_config: Optional[CompressionConfig] = None,
#     verbose: bool = True,
#     max_workers: int = 4,
#     chunk_size: int = 10
# ) -> Tuple[List[Path], List[Path]]:
#     """
#     Sauvegarde des datasets en fichiers NetCDF, séparant références et produits.
    
#     Version améliorée avec traitement parallèle, meilleure gestion d'erreurs,
#     et configuration flexible de la compression.
    
#     Parameters
#     ----------
#     dss : Dict[str, List[xr.Dataset]]
#         Dictionnaire où les clés sont les noms de zones de mesure et les valeurs 
#         sont des listes de datasets. Chaque dataset doit avoir les attributs 
#         'data_name' et 'data_ref'.
#     parent_dir : str or Path
#         Répertoire parent où sauvegarder les fichiers NetCDF.
#     ncpat : str
#         Pattern de nom de fichier avec placeholders.
#         Exemple: "{refprod}/{mz_name}/{data_name}.nc"
#     compression_config : CompressionConfig, optional
#         Configuration de compression. Par défaut: zlib, niveau 5, shuffle activé.
#     verbose : bool, optional
#         Affichage des informations de progression (défaut: True).
#     max_workers : int, optional
#         Nombre maximum de workers pour le traitement parallèle (défaut: 4).
#     chunk_size : int, optional
#         Taille des chunks pour le traitement par batch (défaut: 10).
    
#     Returns
#     -------
#     Tuple[List[Path], List[Path]]
#         Deux listes contenant les chemins des fichiers sauvegardés:
#         - Première liste: fichiers de référence
#         - Deuxième liste: fichiers produits
    
#     Raises
#     ------
#     ValueError
#         Si les paramètres d'entrée sont invalides.
#     KeyError
#         Si les attributs requis manquent dans les datasets.
#     OSError
#         En cas de problème de création de répertoires ou d'écriture.
#     """
#     # Configuration par défaut
#     if compression_config is None:
#         compression_config = CompressionConfig()
    
#     compression_config.validate()
    
#     # Initialisation
#     ncs_ref = []
#     ncs_prod = []
#     parent_dir = Path(parent_dir)
    
#     # Configuration du logging
#     logger = _setup_logger(verbose)
    
#     # Validation des entrées
#     _validate_inputs(dss, ncpat, parent_dir)
    
#     total_datasets = sum(len(datasets) for datasets in dss.values())
    
#     if verbose:
#         logger.info(f"Traitement de {total_datasets} datasets depuis {len(dss)} zones de mesure")
#         logger.info(f"Configuration compression: {compression_config.algorithm}, niveau {compression_config.level}")
    
#     try:
#         # Préparation des tâches
#         tasks = _prepare_tasks(dss, parent_dir, ncpat)
        
#         # Traitement par chunks pour éviter la surcharge mémoire
#         for i in range(0, len(tasks), chunk_size):
#             chunk_tasks = tasks[i:i + chunk_size]
            
#             if verbose:
#                 logger.info(f"Traitement du chunk {i//chunk_size + 1}/{(len(tasks)-1)//chunk_size + 1}")
            
#             # Traitement parallèle du chunk
#             chunk_ref, chunk_prod = _process_chunk_parallel(
#                 chunk_tasks, compression_config, max_workers, logger, verbose
#             )
            
#             ncs_ref.extend(chunk_ref)
#             ncs_prod.extend(chunk_prod)
            
#             # Nettoyage mémoire entre les chunks
#             gc.collect()
    
#     except Exception as e:
#         logger.error(f"Erreur pendant le traitement: {str(e)}")
#         raise
    
#     finally:
#         gc.collect()
    
#     if verbose:
#         logger.info(f"✅ Sauvegarde réussie: {len(ncs_ref)} références, {len(ncs_prod)} produits")
#         total_size = _calculate_total_size(ncs_ref + ncs_prod)
#         logger.info(f"Espace disque total utilisé: {total_size:.2f} MB")
    
#     return ncs_ref + ncs_prod


# def _setup_logger(verbose: bool) -> logging.Logger:
#     """Configure le logger."""
#     if verbose:
#         logging.basicConfig(
#             level=logging.INFO,
#             format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
#         )
#     return logging.getLogger(__name__)


# def _validate_inputs(dss: Dict, ncpat: str, parent_dir: Path):
#     """Valide les paramètres d'entrée."""
#     if not dss:
#         raise ValueError("Le dictionnaire 'dss' est vide")
    
#     if not ncpat:
#         raise ValueError("Le pattern 'ncpat' ne peut pas être vide")
    
#     # Test du pattern avec des valeurs fictives
#     try:
#         test_vars = {'mz_name': 'test', 'data_name': 'test', 'refprod': 'ref'}
#         ncpat.format(**test_vars)
#     except KeyError as e:
#         raise ValueError(f"Pattern '{ncpat}' contient un placeholder invalide: {e}")


# @dataclass
# class ProcessingTask:
#     """Représente une tâche de traitement d'un dataset."""
#     mz_name: str
#     dataset: xr.Dataset
#     nc_path: Path
#     refprod: str
#     data_name: str


# def _prepare_tasks(dss: Dict, parent_dir: Path, ncpat: str) -> List[ProcessingTask]:
#     """Prépare les tâches de traitement."""
#     tasks = []
    
#     for mz_name, datasets in dss.items():
#         for i, ds in enumerate(datasets):
#             # Validation des attributs
#             if "data_name" not in ds.attrs:
#                 raise KeyError(f"Dataset {i} dans la zone '{mz_name}' manque l'attribut 'data_name'")
            
#             if "data_ref" not in ds.attrs:
#                 raise KeyError(f"Dataset {i} dans la zone '{mz_name}' manque l'attribut 'data_ref'")
            
#             data_name = ds.attrs["data_name"]
#             data_ref_str = str(ds.attrs["data_ref"])
            
#             if data_ref_str not in ["True", "False"]:
#                 raise ValueError(f"Valeur 'data_ref' invalide: {data_ref_str}")
            
#             refprod = "ref" if data_ref_str == "True" else "prod"
            
#             # Création du chemin
#             nc_path = parent_dir / ncpat.format(
#                 mz_name=mz_name,
#                 data_name=data_name,
#                 refprod=refprod
#             )
            
#             tasks.append(ProcessingTask(
#                 mz_name=mz_name,
#                 dataset=ds,
#                 nc_path=nc_path,
#                 refprod=refprod,
#                 data_name=data_name
#             ))
    
#     return tasks


# def _process_chunk_parallel(
#     tasks: List[ProcessingTask],
#     compression_config: CompressionConfig,
#     max_workers: int,
#     logger: logging.Logger,
#     verbose: bool
# ) -> Tuple[List[Path], List[Path]]:
#     """Traite un chunk de tâches en parallèle."""
#     chunk_ref = []
#     chunk_prod = []
    
#     with ThreadPoolExecutor(max_workers=max_workers) as executor:
#         # Soumission des tâches
#         future_to_task = {
#             executor.submit(_process_single_dataset, task, compression_config): task
#             for task in tasks
#         }
        
#         # Collection des résultats
#         for future in as_completed(future_to_task):
#             task = future_to_task[future]
#             try:
#                 nc_path = future.result()
                
#                 if task.refprod == "ref":
#                     chunk_ref.append(nc_path)
#                 else:
#                     chunk_prod.append(nc_path)
                
#                 if verbose:
#                     logger.info(f"✓ Sauvegardé: {nc_path.name}")
                    
#             except Exception as e:
#                 logger.error(f"Erreur lors du traitement de {task.data_name}: {e}")
#                 raise
    
#     return chunk_ref, chunk_prod


# def _process_single_dataset(task: ProcessingTask, compression_config: CompressionConfig) -> Path:
#     """Traite un seul dataset."""
#     # Création du répertoire parent
#     task.nc_path.parent.mkdir(parents=True, exist_ok=True)
    
#     # Configuration de l'encodage
#     encoding = _create_encoding(task.dataset, compression_config)
    
#     # Calcul et sauvegarde
#     with dask.config.set(scheduler='threads'):
#         computed_ds = task.dataset.compute()
    
#     try:
#         computed_ds.to_netcdf(
#             task.nc_path,
#             encoding=encoding,
#             compute=True
#         )
#     finally:
#         # Nettoyage
#         computed_ds.close()
#         task.dataset.close()
    
#     return task.nc_path


# def _create_encoding(ds: xr.Dataset, config: CompressionConfig) -> Dict:
#     """Crée la configuration d'encodage pour la compression."""
#     if config.algorithm is None:
#         return {}
    
#     encoding = {}
#     for var in ds.data_vars:
#         encoding[var] = {
#             'zlib': config.algorithm == 'zlib',
#             'complevel': config.level if config.algorithm == 'zlib' else None,
#             'shuffle': config.shuffle,
#             '_FillValue': None
#         }
    
#     return encoding


# def _calculate_total_size(file_paths: List[Path]) -> float:
#     """Calcule la taille totale des fichiers en MB."""
#     total_size = 0
#     for path in file_paths:
#         if path.exists():
#             total_size += path.stat().st_size
#     return total_size / (1024 * 1024)


# # Exemple d'utilisation
# if __name__ == "__main__":
#     # Configuration de compression personnalisée
#     comp_config = CompressionConfig(
#         algorithm="zlib",
#         level=7,
#         shuffle=True
#     )
    
#     # Utilisation avec configuration personnalisée
#     # ref_files, prod_files = to_netcdf_ref_prods(
#     #     datasets_dict,
#     #     "/output/path",
#     #     "{refprod}/{mz_name}_{data_name}.nc",
#     #     compression_config=comp_config,
#     #     max_workers=6,
#     #     chunk_size=15
#     # )