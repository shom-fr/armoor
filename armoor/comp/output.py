import gc
import itertools
import logging
import re
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple

import dask
import numpy as np
import pandas as pd
import xarray as xr

from armoor import ArmoorError
from armoor.base.io import (
    get_zarr_encoding,
    setup_dask_client,
    sort_ncs_by_suffix
    )
from armoor.comp import COMP_VARS, OUTPUTS_PARAMS
from armoor.comp.plot import PlotComp
from armoor.comp.stats import StatsComp

logger = logging.getLogger(__name__)


def check_output(func_name, outputs):
    for output in outputs.values():
        if output.get('otype') not in OUTPUTS_PARAMS[func_name].keys():
            raise ArmoorError(
                f"Not implemented output for {func_name}: {output}"
                )

class OutputProcessor:
    """
    A class to handle output processing with statistical comparisons between 
    production and reference datasets.
    """
    
    def __init__(self):
        """Initialize the OutputProcessor."""
        pass
    
    def process_output(self, ocfg: List[Dict[str, Any]], func_comp: str) -> Dict[str, Dict[str, List[str]]]:
        """
        Process output configurations to generate statistical comparisons.
        
        This function processes production and reference datasets to generate
        statistical comparisons and save them in various output formats.
        
        Args:
            ocfg: List containing [metazone_config, output_config] dictionaries
            func_comp: Function component identifier used for output directory structure
            
        Returns:
            Dictionary mapping output types to metazones to list of output file paths.
            Structure: {output_name: {metazone_name: [file_path1, file_path2, ...]}}
            
        Raises:
            ArmoorError: When processing fails due to configuration or data issues
        
        Example:
            >>> ocfg = [
            ...     {'atlantic': {'ncins': {'ref1': {'prod1': ['file1.nc']}}}},
            ...     {'comparison': {'otype': 'stats_comp'}}
            ... ]
            >>> processor = OutputProcessor()
            >>> result = processor.process_output(ocfg, 'validation')
            >>> print(result)
            {'stats_comp': {'atlantic': ['validation/output/atlantic/ref1/stats_comp/all.zarr']}}
        """
        # Extract configuration components
        config = self._parse_configuration(ocfg)
        metazone, output, mparams, oparams = config
        
        logger.info(f"{metazone} -- {output}")
        
        # Validate output compatibility
        if not self._validate_output_compatibility(oparams, mparams, metazone, output, func_comp):
            return {output: {metazone: []}}
        
        # Get output parameters and initialize result structure
        output_params = OUTPUTS_PARAMS[func_comp][output]
        ncouts = {output: {metazone: []}}
        ref_ncins = mparams.get("ncins")
        
        # Process each reference dataset
        for ref_name, prods in ref_ncins.items():
            logger.info(f"Process {output} for {ref_name}")
            
            # Sort and organize input files
            sorted_prods = self._sort_products(prods, output_params)
            
            # Generate statistics and comparisons
            processed_datasets = self._generate_statistics_and_comparisons(
                sorted_prods, mparams, output_params
            )
            
            # Save outputs
            output_files = self._save_outputs(
                processed_datasets, sorted_prods, func_comp, metazone, 
                ref_name, output, output_params
            )
            
            ncouts[output][metazone].extend(output_files)
            
            # Cleanup
            del processed_datasets
            gc.collect()
        
        return ncouts
    
    def _parse_configuration(self, ocfg: List[Dict[str, Any]]) -> Tuple[str, str, Dict[str, Any], Dict[str, Any]]:
        """
        Parse and extract configuration components.
        
        Args:
            ocfg: Configuration list containing metazone and output configs
            
        Returns:
            Tuple of (metazone_name, output_name, metazone_params, output_params)
        """
        metazone = ''.join(ocfg[0].keys())
        output_key = ''.join(ocfg[1].keys())
        
        mparams = ocfg[0][metazone]
        oparams = ocfg[1][output_key]
        output = oparams.get("otype")
        
        return metazone, output, mparams, oparams
    
    def _validate_output_compatibility(self, oparams: Dict[str, Any], mparams: Dict[str, Any], 
                                     metazone: str, output: str, func_comp: str) -> bool:
        """
        Validate if output type is compatible with metazone parameters.
        
        Args:
            oparams: Output parameters
            mparams: Metazone parameters  
            metazone: Metazone name
            output: Output type name
            func_comp: Function component identifier
            
        Returns:
            True if compatible, False otherwise
        """
        try:
            output_config = OUTPUTS_PARAMS[func_comp][output]
        except KeyError:
            logger.warning(f"Output type '{output}' not found in OUTPUTS_PARAMS for {func_comp}")
            return False
        
        # Check required parameters
        if output_config.get("mparams_pro"):
            for dim, required_params in output_config.get("mparams_pro").items():
                if not bool(set(required_params) & set(mparams.keys())):
                    logger.info(
                        f"{output} cannot be processed for {metazone} "
                        f"caused by missing {required_params}"
                    )
                    return False
        
        # Check conflicting parameters
        if output_config.get("mparams_con"):
            for dim, conflicting_params in output_config.get("mparams_con").items():
                if bool(set(conflicting_params) & set(mparams.keys())):
                    logger.info(
                        f"{output} cannot be processed for {metazone} "
                        f"caused by conflicting {conflicting_params}"
                    )
                    return False
        
        return True
    
    def _sort_products(self, prods: Dict[str, Dict[str, List]], 
                      output_params: Dict[str, Any]) -> Dict[str, Dict[str, Dict]]:
        """
        Sort and organize product files by type (prod/ref) and sorting criteria.
        
        Args:
            prods: Dictionary mapping product names to their file lists
            output_params: Output configuration parameters
            
        Returns:
            Dictionary with sorted products organized by type
        """
        logger.info("Sorting products")
        sorted_prods = {}
        sort_dim = output_params.get("sort")
        
        for prod_name, ncins in prods.items():
            logger.info(f"Sorting {prod_name}")
            sorted_prods[prod_name] = {}
            
            for file_type in ["prod", "ref"]:
                # Filter files by type (prod or ref)
                type_files = [nc for nc in ncins if file_type in str(nc)]
                
                # Sort files by the specified dimension
                sorted_files = sort_ncs_by_suffix(type_files, sort_dim=sort_dim)
                sorted_prods[prod_name][file_type] = sorted_files
        
        return sorted_prods
    
    def _generate_statistics_and_comparisons(self, sorted_prods: Dict[str, Dict], 
                                           mparams: Dict[str, Any],
                                           output_params: Dict[str, Any]) -> Dict[str, Dict]:
        """
        Generate statistics and comparisons for all products.
        
        Args:
            sorted_prods: Sorted product files organized by type
            mparams: Metazone parameters
            output_params: Output configuration parameters
            
        Returns:
            Dictionary containing processed datasets organized by product and data type
        """
        logger.info("Computing statistics & concatenations")
        
        dss = {}
        concat_dim = output_params.get("concat")
        
        for prod_name in sorted_prods.keys():
            logger.info(f"Processing {prod_name}")
            dss[prod_name] = {"prod": {}, "ref": {}, "comp": {}}
            
            # Process each sorting group
            sort_keys = sorted_prods[prod_name]["prod"].keys()
            
            for sort_key in sort_keys:
                # Generate statistics for this sorting group
                stats_data = self._compute_statistics_for_sort_group(
                    sorted_prods[prod_name], sort_key, mparams, output_params
                )
                
                # Concatenate datasets for each data type
                for data_type in ["prod", "ref", "comp"]:
                    concatenated_data = self._concatenate_datasets(
                        stats_data[data_type], concat_dim
                    )
                    dss[prod_name][data_type][sort_key] = concatenated_data
        
        return dss
    
    def _compute_statistics_for_sort_group(self, prod_files: Dict[str, Dict], 
                                         sort_key: str, mparams: Dict[str, Any],
                                         output_params: Dict[str, Any]) -> Dict[str, List]:
        """
        Compute statistics for a specific sorting group.
        
        Args:
            prod_files: Product files organized by type (prod/ref)
            sort_key: Sorting key identifier
            mparams: Metazone parameters
            output_params: Output parameters
            
        Returns:
            Dictionary containing lists of computed statistics for each data type
        """
        prod_files_list = prod_files["prod"][sort_key]
        ref_files_list = prod_files["ref"][sort_key]
        num_files = len(prod_files_list)
        
        # Initialize storage for computed data trees
        computed_data = {
            "prod": [],
            "ref": [],
            "comp": []
        }
        
        # Process each file pair
        for file_idx in range(num_files):
            ds_prod = xr.open_dataset(prod_files_list[file_idx])
            ds_ref = xr.open_dataset(ref_files_list[file_idx])
            
            try:
                # Prepare statistics configuration
                stats = output_params.get("stat").copy() if output_params.get("stat") else None
                
                # Compute statistics and comparisons
                dt_prod, dt_ref, dt_comps = StatsComp(
                    mparams, ds_prod, ds_ref, stats
                ).compute()
                
                # Store results
                computed_data["prod"].append(dt_prod)
                computed_data["ref"].append(dt_ref)
                computed_data["comp"].append(dt_comps)
                
            finally:
                # Cleanup datasets
                ds_prod.close()
                ds_ref.close()
        
        return computed_data
    
    def _concatenate_datasets(self, data_trees: List[Any], 
                            concat_dim: List[str]) -> Dict[str, xr.Dataset]:
        """
        Concatenate datasets from data trees along specified dimensions.
        
        Args:
            data_trees: List of data trees to concatenate
            concat_dim: Dimensions to concatenate along
            
        Returns:
            Dictionary of concatenated datasets
        """
        concatenated_data = {}
        
        if not data_trees or not data_trees[0]:
            return concatenated_data
        
        # Process each dataset in the data trees
        for ds_name in data_trees[0].keys():
            datasets = [dt[ds_name].to_dataset() for dt in data_trees]
            
            if concat_dim == ["time"]:
                concatenated_dataset = self._concatenate_time_datasets(datasets)
            elif len(datasets) == 1:
                concatenated_dataset = datasets[0]
            else:
                raise ArmoorError("Multi-dataset concatenation not implemented")
            
            concatenated_data[ds_name] = concatenated_dataset
        
        return concatenated_data
    
    def _concatenate_time_datasets(self, datasets: List[xr.Dataset]) -> xr.Dataset:
        """
        Concatenate datasets along the time dimension.
        
        Args:
            datasets: List of datasets to concatenate
            
        Returns:
            Concatenated dataset
        """
        # Handle multi-time datasets by splitting into individual time slices
        if datasets[0].sizes["time"] > 1:
            time_slices = []
            for ds in datasets:
                time_slices.extend([
                    ds.isel(time=time_idx) 
                    for time_idx in range(ds.sizes["time"])
                ])
            datasets = time_slices
        
        # Concatenate along time dimension
        concatenated = xr.concat(datasets, "time")
        
        # Preserve vrange attributes if present
        if datasets[0].attrs.get("vrange"):
            vrange_attrs = [ds.attrs.get("vrange") for ds in datasets]
            concatenated.attrs["vrange"] = vrange_attrs
        
        return concatenated
    
    def _save_outputs(self, processed_datasets: Dict[str, Dict], 
                     sorted_prods: Dict[str, Dict], func_comp: str,
                     metazone: str, ref_name: str, output: str,
                     output_params: Dict[str, Any]) -> List[str]:
        """
        Save processed datasets to output files.
        
        Args:
            processed_datasets: Processed datasets organized by product and type
            sorted_prods: Sorted product information
            func_comp: Function component identifier
            metazone: Metazone name
            ref_name: Reference dataset name
            output: Output type name
            output_params: Output configuration parameters
            
        Returns:
            List of saved output file paths
        """
        output_files = []
        
        # Create base output directory
        dirout = Path(f"{func_comp}/output/{metazone}/{ref_name}/{output}")
        
        # Get all sorting keys
        sort_keys = list(sorted_prods[list(sorted_prods.keys())[0]]["prod"].keys())
        
        # Save outputs for each sorting group
        for sort_key in sort_keys:
            sort_dir = dirout / sort_key
            sort_dir.mkdir(parents=True, exist_ok=True)
            
            if output_params.get("output"):
                # Save all products in a single file
                output_file = self._save_combined_output(
                    processed_datasets, sort_key, sort_dir, sorted_prods
                )
                output_files.append(str(output_file))
            else:
                # Save each product separately
                separate_files = self._save_separate_outputs(
                    processed_datasets, sort_key, sort_dir, sorted_prods
                )
                output_files.extend([str(f) for f in separate_files])
        
        return output_files
    
    def _save_combined_output(self, processed_datasets: Dict[str, Dict], 
                            sort_key: str, sort_dir: Path,
                            sorted_prods: Dict[str, Dict]) -> Path:
        """
        Save all products in a combined output file.
        
        Args:
            processed_datasets: Processed datasets
            sort_key: Sorting key
            sort_dir: Output directory for this sort group
            sorted_prods: Sorted product information
            
        Returns:
            Path to saved combined file
        """
        dt = xr.DataTree()
        
        for prod_name in sorted_prods.keys():
            # Create product node in data tree
            dt.update(xr.DataTree.from_dict({prod_name: xr.DataTree()}))
            
            # Add data for each type (prod, ref, comp)
            for data_type in ["prod", "ref", "comp"]:
                datasets = processed_datasets[prod_name][data_type][sort_key]
                data_tree = xr.DataTree.from_dict(datasets)
                dt[prod_name].update(xr.DataTree.from_dict({data_type: data_tree}))
        
        # Save combined file
        output_file = sort_dir / "all.zarr"
        encoding = get_zarr_encoding(dt)
        dt.to_zarr(output_file, mode="w", encoding=encoding)
        
        return output_file
    
    def _save_separate_outputs(self, processed_datasets: Dict[str, Dict], 
                             sort_key: str, sort_dir: Path,
                             sorted_prods: Dict[str, Dict]) -> List[Path]:
        """
        Save each product in a separate output file.
        
        Args:
            processed_datasets: Processed datasets
            sort_key: Sorting key
            sort_dir: Output directory for this sort group
            sorted_prods: Sorted product information
            
        Returns:
            List of paths to saved files
        """
        output_files = []
        
        for prod_name in sorted_prods.keys():
            dt = xr.DataTree()
            
            # Create product node in data tree
            dt.update(xr.DataTree.from_dict({prod_name: xr.DataTree()}))
            
            # Add data for each type (prod, ref, comp)
            for data_type in ["prod", "ref", "comp"]:
                datasets = processed_datasets[prod_name][data_type][sort_key]
                data_tree = xr.DataTree.from_dict(datasets)
                dt[prod_name].update(xr.DataTree.from_dict({data_type: data_tree}))
            
            # Save product file
            output_file = sort_dir / f"{prod_name}.zarr"
            encoding = get_zarr_encoding(dt)
            dt.to_zarr(output_file, mode="w", encoding=encoding)
            output_files.append(output_file)
        
        return output_files


class OutputPipelineManager:
    """
    Manager class for handling the complete output processing pipeline with parallelization.
    """
    
    def __init__(self):
        """Initialize the OutputPipelineManager."""
        self.processor = OutputProcessor()
    
    def process_and_extract(self, output_config: List[Dict[str, Any]], 
                          func_comp: str) -> Dict[str, Dict[str, List[str]]]:
        """
        Process output configuration and extract non-empty results.
        
        This method is designed to be used with Dask for parallel processing.
        
        Args:
            output_config: Output configuration
            func_comp: Function component identifier
            
        Returns:
            Dictionary with only non-empty results
        """
        # Process the output
        results = self.processor.process_output(output_config, func_comp)
        
        # Filter out empty results
        filtered_results = {}
        for output_name, metazones in results.items():
            for metazone_name, file_paths in metazones.items():
                if len(file_paths) > 0:
                    if output_name not in filtered_results:
                        filtered_results[output_name] = {}
                    filtered_results[output_name][metazone_name] = file_paths
        
        return filtered_results
    
    def process_all_outputs(self, ncs: Dict[str, Any], metazones_in: Dict[str, Any],
                          outputs: Dict[str, Any], func_comp: str) -> Dict[str, Dict[str, List[str]]]:
        """
        Process all output configurations with parallel execution.
        
        Args:
            ncs: NetCDF files organized by metazone
            metazones_in: Input metazone configurations
            outputs: Output configurations
            func_comp: Function component identifier
            
        Returns:
            Dictionary mapping output types to metazones to file paths
            
        Example:
            >>> manager = OutputPipelineManager()
            >>> ncs = {'atlantic': {'ref1': {'prod1': ['file1.nc']}}}
            >>> metazones = {'atlantic': {'param1': 'value1'}}
            >>> outputs = {'comparison': {'otype': 'stats_comp'}}
            >>> result = manager.process_all_outputs(ncs, metazones, outputs, 'validation')
        """
        # Prepare configurations
        output_configs = self._prepare_output_configurations(
            ncs, metazones_in, outputs, func_comp
        )
        
        # Create delayed tasks for parallel processing
        delayed_tasks = [
            dask.delayed(self.process_and_extract)(config, func_comp)
            for config in output_configs
        ]
        
        # Execute all tasks in parallel
        results = dask.compute(*delayed_tasks)
        
        # Merge all results
        return self._merge_results(results)
    
    def _prepare_output_configurations(self, ncs: Dict[str, Any], 
                                     metazones_in: Dict[str, Any],
                                     outputs: Dict[str, Any], 
                                     func_comp: str) -> List[List[Dict[str, Any]]]:
        """
        Prepare output configurations for processing.
        
        Args:
            ncs: NetCDF files organized by metazone
            metazones_in: Input metazone configurations
            outputs: Output configurations
            func_comp: Function component identifier
            
        Returns:
            List of output configurations ready for processing
        """
        # Remove format specification and validate outputs
        output_configs = outputs.copy()
        output_configs.pop("fmt", None)
        check_output(func_comp, output_configs)
        
        # Prepare metazone configurations
        prepared_metazones = {}
        for metazone_name, metazone_config in metazones_in.items():
            if metazone_config:
                prepared_metazones[metazone_name] = {
                    "ncins": ncs.get(metazone_name),
                    "vars": COMP_VARS[func_comp],
                    **metazone_config.copy()
                }
        
        # Convert to list format expected by the processor
        metazone_list = [{key: value} for key, value in prepared_metazones.items()]
        output_list = [{key: value} for key, value in output_configs.items()]
        
        # Create all combinations of metazones and outputs
        output_combinations = list(itertools.product(metazone_list, output_list))
        
        return output_combinations
    
    def _merge_results(self, results: List[Dict[str, Dict[str, List[str]]]]) -> Dict[str, Dict[str, List[str]]]:
        """
        Merge results from parallel processing.
        
        Args:
            results: List of result dictionaries from parallel tasks
            
        Returns:
            Merged results dictionary
        """
        merged_results = {}
        
        for result in results:
            for output_name, metazones in result.items():
                if output_name not in merged_results:
                    merged_results[output_name] = {}
                merged_results[output_name].update(metazones)
        
        return merged_results


# Convenience functions for backward compatibility
def process_output(ocfg: List[Dict[str, Any]], func_comp: str) -> Dict[str, Dict[str, List[str]]]:
    """
    Process a single output configuration.
    
    This function maintains backward compatibility with the original function signature.
    
    Args:
        ocfg: Output configuration list containing [metazone_config, output_config]
        func_comp: Function component identifier
        
    Returns:
        Dictionary mapping output types to metazones to list of output file paths
        
    Example:
        >>> ocfg = [
        ...     {'atlantic': {'ncins': {'ref1': {'prod1': ['file1.nc']}}}},
        ...     {'comparison': {'otype': 'stats_comp'}}
        ... ]
        >>> result = process_output(ocfg, 'validation')
    """
    processor = OutputProcessor()
    return processor.process_output(ocfg, func_comp)


@dask.delayed
def process_and_extract(output_config: List[Dict[str, Any]], func_comp: str) -> Dict[str, Dict[str, List[str]]]:
    """
    Dask delayed wrapper for process_and_extract.
    
    Args:
        output_config: Output configuration
        func_comp: Function component identifier
        
    Returns:
        Dictionary with filtered results
    """
    manager = OutputPipelineManager()
    return manager.process_and_extract(output_config, func_comp)


def main_output(ncs: Dict[str, Any], metazones_in: Dict[str, Any],
               outputs: Dict[str, Any], func_comp: str) -> Dict[str, Dict[str, List[str]]]:
    """
    Main function for processing all output configurations with parallel execution.
    
    This function maintains backward compatibility while providing improved structure
    and parallel processing capabilities.
    
    Args:
        ncs: Dictionary mapping metazone names to their NetCDF files
        metazones_in: Dictionary of metazone configurations
        outputs: Dictionary of output configurations (fmt key will be removed)
        func_comp: Function component identifier for directory structure
        
    Returns:
        Dictionary mapping output names to metazones to lists of output file paths.
        Structure: {output_name: {metazone_name: [file_path1, file_path2, ...]}}
        
    Example:
        >>> ncs = {'atlantic': {'ref1': {'prod1': ['file1.nc', 'file2.nc']}}}
        >>> metazones = {'atlantic': {'param1': 'value1'}}
        >>> outputs = {'monthly_stats': {'otype': 'statistics'}, 'fmt': 'zarr'}
        >>> result = main_output(ncs, metazones, outputs, 'validation')
        >>> print(result)
        {'statistics': {'atlantic': ['validation/output/atlantic/ref1/statistics/file1.zarr']}}
    """
    manager = OutputPipelineManager()
    return manager.process_all_outputs(ncs, metazones_in, outputs, func_comp)

# def process_output(ocfg, func_comp):
    
#     metazone = ''.join(ocfg[0].keys())
#     output = ''.join(ocfg[1].keys())
#     mparams, oparams = ocfg[0][metazone], ocfg[1][output]
#     output = oparams.get("otype")
    
#     logger.info(f"{metazone} -- {output}")
#     oparams = OUTPUTS_PARAMS[func_comp][output]
#     ref_ncins = mparams.get("ncins")
#     concat_dim = oparams.get("concat")
#     ncouts =  {output: {metazone: []}}
    
#     if oparams.get("mparams_pro"):
#         for dim, param in oparams.get("mparams_pro").items():
#             if not bool(set(param) & set(mparams.keys())):
#                 logger.info(f"{output} cannot be processed for {metazone} caused by missing {param}")
#                 return ncouts
#     if oparams.get("mparams_con"):
#         for dim, param in oparams.get("mparams_con").items():
#             if bool(set(param) & set(mparams.keys())):
#                 logger.info(f"{output} cannot be processed for {metazone} caused by {param}")
#                 return ncouts
#     for ref_name, prods in ref_ncins.items():
#         logger.info(f"Process {output} for {ref_name}")
#         sorted_prods = {}
#         logger.info("Sorting")
#         for prod, ncins in prods.items():
#             logger.info(f"{prod}")
#             sorted_prods[prod] = {}
#             for prefix in ["prod", "ref"]:
#                 ncs = [nc for nc in ncins if prefix in str(nc)]
#                 ncs = sort_ncs_by_suffix(
#                     ncs,
#                     sort_dim=oparams.get("sort")
#                     )
#                 sorted_prods[prod].update({f"{prefix}": ncs})

#         logger.info("Stats & concat")
#         dts = {}
#         dss = {}
#         for prod in sorted_prods.keys():
#             logger.info(f"{prod}")
#             dss[prod] = {
#                 "prod": {},
#                 "ref": {},
#                 "comp": {}
#                 }
#             dts.update({
#                 "prod": {},
#                 "ref": {},
#                 "comp": {}
#                 })
#             sorts = sorted_prods[prod]["prod"].keys()
#             for sort in sorts:
#                 nncs = len(sorted_prods[prod]["prod"][sort])
#                 dts["prod"].update({sort: []})
#                 dts["ref"].update({sort: []})
#                 dts["comp"].update({sort: []})
#                 for inc in range(nncs):
#                     ds_prod = xr.open_dataset(
#                         sorted_prods[prod]["prod"][sort][inc]
#                         )
#                     ds_ref = xr.open_dataset(
#                         sorted_prods[prod]["ref"][sort][inc]
#                         )
#                     if oparams.get("stat"):
#                         stats =  oparams.get("stat").copy()
#                     else:
#                         stats =  None
#                     dt_prod, dt_ref, dt_comps = StatsComp(
#                         mparams, ds_prod, ds_ref, stats
#                         ).compute()
#                     dts["prod"][sort].append(dt_prod)
#                     dts["ref"][sort].append(dt_ref)
#                     dts["comp"][sort].append(dt_comps)
#                     del dt_prod
#                     del dt_ref
#                     del dt_comps
#                 for data in ["prod", "ref", "comp"]:
#                     dts0 = dts[data][sort]
#                     dts_data = {}
#                     if len(dts0) > 0:
#                         if dts0[0]:
#                             for ds_name in dts0[0].keys():
#                                 dss0 = []
#                                 for dt in dts0:
#                                     dss0.append(dt[ds_name].to_dataset())
#                                 if concat_dim == ["time"]:
#                                     if dss0[0].sizes["time"] > 1:
#                                         dss1 = []
#                                         for ids, ds0 in enumerate(dss0):
#                                             dss1 += [
#                                                 ds0.isel(time=itime) 
#                                                 for itime in range(
#                                                     ds0.sizes["time"]
#                                                     )
#                                                 ]
#                                         dss0 = dss1
#                                         del dss1
#                                     ds = xr.concat(dss0, "time")
#                                     if dss0[0].attrs.get("vrange"):
#                                         xattrs = [
#                                             ds0.attrs.get("vrange") for ds0 in dss0
#                                             ]
#                                         ds.attrs["vrange"] = xattrs
#                                 elif len(dss0) == 1:
#                                     ds = dss0[0]
#                                 else:
#                                     raise ArmoorError(
#                                         "Not implemented."
#                                         )
#                                 del dss0
#                                 dts_data.update({ds_name: ds})
#                                 del ds
#                     dss[prod][data].update({sort: dts_data})
#                     del dts_data

#         dirout = Path(
#             f"{func_comp}/output/{metazone}/"
#             f"{ref_name}/{output}"
#             )
        
#         for sort in sorts:
#             dirout_sort = dirout / sort
#             dirout_sort.mkdir(parents=True, exist_ok=True)
#             if oparams.get("output"):
#                 dt = xr.DataTree()
#                 for prod in sorted_prods.keys():
#                     dt.update(xr.DataTree.from_dict({
#                         prod: xr.DataTree()
#                         }))
#                     for data in ["prod", "ref", "comp"]:
#                         dss0 = dss[prod][data][sort]
#                         dss0 = xr.DataTree.from_dict(dss0)
#                         dt[prod].update(xr.DataTree.from_dict({
#                             data: dss0
#                             }))
#                 ncout = dirout_sort / "all.zarr"
#                 encoding = get_zarr_encoding(dt)
#                 dt.to_zarr(ncout, mode="w", encoding=encoding)
#                 ncouts[output][metazone].append(str(ncout))
#             else:
#                 for prod in sorted_prods.keys():
#                     dt = xr.DataTree()
#                     dt.update(xr.DataTree.from_dict({
#                         prod: xr.DataTree()
#                         }))
#                     for data in ["prod", "ref", "comp"]:
#                         dss0 = dss[prod][data][sort]
#                         dss0 = xr.DataTree.from_dict(dss0)
#                         dt[prod].update(xr.DataTree.from_dict({
#                             data: dss0
#                             }))
#                     ncout = dirout_sort / f"{prod}.zarr"
#                     encoding = get_zarr_encoding(dt)
#                     dt.to_zarr(ncout, mode="w", encoding=encoding)
#                     ncouts[output][metazone].append(str(ncout))
#             del dt
#         del dss
#         gc.collect()
#     return ncouts

# @dask.delayed
# def process_and_extract(output, func_comp):
#     """Process output and extract non-empty results"""
#     ncs = process_output(output, func_comp)
    
#     # Extract only non-empty results
#     filtered_results = {}
#     for o, ms in ncs.items():
#         for m, ns in ms.items():
#             if len(ns) > 0:
#                 if o not in filtered_results:
#                     filtered_results[o] = {}
#                 filtered_results[o][m] = ns
    
#     return filtered_results

# def main_output(ncs, metazones_in, outputs, func_comp):
    
#     output_ins = outputs.copy()
#     output_ins.pop("fmt")
#     check_output(func_comp, output_ins)
#     metazones = {}
#     for metazone in metazones_in.keys():
#         if metazones_in.get(metazone):
#             metazones.update({metazone: {
#                 "ncins": ncs.get(metazone),
#                 "vars": COMP_VARS[func_comp],
#                 **metazones_in[metazone].copy()
#                 }})
#     metazones = [{key: value} for key, value in metazones.items()]
#     output_ins = [{key: value} for key, value in output_ins.items()]
#     outputs = list(itertools.product(metazones, output_ins))
#     ncouts = {}

#     delayed_tasks = [
#         process_and_extract(output, func_comp)
#         for output in outputs
#     ]

#     results = dask.compute(*delayed_tasks)
    
#     # Merge all filtered results
#     ncouts = {}
#     for result in results:
#         for o, ms in result.items():
#             if o not in ncouts:
#                 ncouts[o] = {}
#             ncouts[o].update(ms) 

#     return ncouts

