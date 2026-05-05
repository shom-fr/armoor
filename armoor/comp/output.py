import gc
import itertools
import logging
import shutil
from pathlib import Path
from typing import Dict, List, Any, Tuple

import dask
import numpy as np
import pandas as pd
import xarray as xr
from xoa.geo import haversine, bearing

from armoor import ArmoorError
from armoor.base.io import (
    get_zarr_encoding,
    sort_ncs_by_suffix,
    write_dataset_to_zarr
    )
from armoor.comp import COMP_VARS, OUTPUTS_PARAMS
from armoor.comp.stats import StatsComp
import armoor  # noqa: F401 — registers all xarray accessors
from armoor.diags.parcels import Parcels

logger = logging.getLogger(__name__)

DATA_TYPES = ("prod", "ref", "comp")
EPOCH = "1950-01-01"

_DRIFTER_OTYPE_REMAP = {
    "timeseries": "timeseries_drifter",
    "maps_current": "maps_current_drifter",
    "maps_trajectory": "maps_trajectory_drifter",
}


def _compute_oceanvars(ds, func_comp):
    """Compute derived oceanographic variables on a colocated dataset.

    Derived variables (pdens, sndspeed, temp-from-ptemp, …) are computed
    here rather than during colocation so that the expensive gsw calls
    run on the small colocated data, not the full product grid.
    """
    for var in COMP_VARS[func_comp]:
        if var not in ds.data_vars:
            da = ds.oceanvars.sel(var)
            if isinstance(da, xr.DataArray):
                ds[var] = da
    return ds


def check_output(func_name, outputs):
    for oname, output in outputs.items():
        if func_name == "comp_drifter":
            otype = output.get('otype')
            if otype in _DRIFTER_OTYPE_REMAP:
                output["otype"] = _DRIFTER_OTYPE_REMAP[otype]
        if output.get('otype') not in OUTPUTS_PARAMS[func_name].keys():
            raise ArmoorError(
                f"Not implemented output for {func_name}: {output}"
                )
    return outputs
        
def _convert_time_to_epoch_seconds(ds, epoch=EPOCH):
    """Convert dataset time coordinates to seconds since epoch."""
    return [
        (pd.to_datetime(time) - pd.to_datetime(epoch))
        / pd.to_timedelta("1s")
        for time in ds.time.values
        ]


def _prepare_prod_for_parcels(zprod):
    """Read production zarr, convert time to epoch seconds, write as netcdf."""
    ncprod = str(zprod).replace(".zarr", ".nc")
    with xr.open_dataset(zprod) as dsprod:
        if "z" in dsprod.sizes:
            dsprod = dsprod.squeeze(dim="z")
        dsprod = dsprod.drop("depth")
        dsprod = dsprod[["u", "v"]]
        timeprod = _convert_time_to_epoch_seconds(dsprod)
        dsprod["time"] = xr.DataArray(
            timeprod,
            dims=dsprod.time.dims,
            attrs={
                'dtype': 'float64',
                'units': f'seconds since {EPOCH} 00:00:00',
                }
            )
        dsprod.to_netcdf(ncprod)
    return ncprod, timeprod


def _interpolate_ref_and_run_parcels(zref, odt, timeprod, ncprod, runtime):
    """Interpolate reference dataset and execute Parcels simulation."""
    with xr.open_dataset(zref) as dsref:
        dsref_update = (
            dsref.reset_coords(["lon", "lat"]).drop("depth")
            .interp.tfreq(odt)
        )
    zref = str(zref)
    dsref_update = dsref_update.compute()
    write_dataset_to_zarr(
        dsref_update,
        zref.replace(".zarr", "_tmp.zarr"),
        mode="w",
        consolidated=True,
        compute=True
        )
    timeref = [
        float((pd.to_datetime(time) - pd.to_datetime(EPOCH))
              / pd.to_timedelta("1s")) - timeprod[0]
        for time in dsref_update.time.values
        ]
    ptc_coords_start = {
        "time": timeref,
        "lon": dsref_update.lon.values,
        "lat": dsref_update.lat.values
        }
    if runtime:
        rruntime = pd.to_timedelta(runtime) / pd.to_timedelta("1s")
    else:
        rruntime = (
            dsref_update.time.max() - dsref_update.time.min()
            ) / pd.to_timedelta("1s")
    rruntime = float(rruntime)
    del dsref_update
    Parcels(
        ncprod,
        ptc_coords_start,
        rruntime,
        outputdt=odt,
        ).execute()
    return zref


def _rewrite_prod_as_zarr(ncprod, zprod):
    """Remove old prod zarr, rewrite from parcels netcdf output."""
    shutil.rmtree(zprod)
    with xr.open_dataset(ncprod) as dsprod:
        write_dataset_to_zarr(
            dsprod,
            zprod,
            mode="w",
            consolidated=True,
            compute=True
            )


def preproc_comp_drifter(zins, odt, runtime=None):
    logger.info("Preproc comp_drifter")
    for drifter, prods in zins.items():
        logger.info(drifter)
        for prod, zs in prods.items():
            logger.info(f"Prod: {prod}")
            zref = [z for z in zs if "ref_" in str(z)][0]
            zprod = [z for z in zs if "prod_" in str(z)][0]
            ncprod, timeprod = _prepare_prod_for_parcels(zprod)
            zref = _interpolate_ref_and_run_parcels(
                zref, odt, timeprod, ncprod, runtime
                )
            _rewrite_prod_as_zarr(ncprod, zprod)
            zins[drifter].update({
                prod: [zref, zprod]
                })
    return zins

def preproc_comp(func_comp, ncs, **kwargs):
    if func_comp == "comp_drifter":
        return preproc_comp_drifter(
            ncs,
            kwargs.get("freq_drift"),
            runtime=kwargs.get("period_drift")
            )
        
class OutputProcessor:
    """
    A class to handle output processing with statistical comparisons between 
    production and reference datasets.
    """
    
    def __init__(self, func_comp=None):
        """Initialize the OutputProcessor."""
        self.func_comp = func_comp
    
    def process_output(self, ocfg: List[Dict[str, Any]]) -> Dict[str, Dict[str, List[str]]]:
        """
        Process output configurations to generate statistical comparisons.
        
        This function processes production and reference datasets to generate
        statistical comparisons and save them in various output formats.
        
        Parameters
        ----------
        ocfg
            List containing [metazone_config, output_config] dictionaries

        Returns
        -------
        dict
            Dictionary mapping output types to metazones to list of output file paths.
            Structure: {output_name: {metazone_name: [file_path1, file_path2, ...]}}

        Raises
        ------
        ArmoorError
            When processing fails due to configuration or data issues

        Examples
        --------
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
        if not self._validate_output_compatibility(oparams, mparams, metazone, output):
            return {output: {metazone: []}}
        
        # Get output parameters and initialize result structure
        output_params = OUTPUTS_PARAMS[self.func_comp][output]
        ncouts = {output: {metazone: []}}
        ref_ncins = mparams.get("ncins")
        
        # Process each reference dataset
        for ref_name, prods in ref_ncins.items():
            logger.info(f"Process {output} for {ref_name}")
            
            # Sort and organize input files
            sorted_prods = self._sort_products(prods, output_params)
 
            # Generate statistics and comparisons
            processed_datasets = self._generate_statistics_and_comparisons(
                sorted_prods, mparams, output_params, output
                )
            # Save outputs
            output_files = self._save_outputs(
                processed_datasets, sorted_prods, metazone, 
                ref_name, output, output_params
                )
            
            ncouts[output][metazone].extend(output_files)
            
            # Cleanup
            del processed_datasets
            gc.collect()
        return ncouts
    
    def _drifter(self, dsref, dsprod, output):
        """Compute drifter-specific comparison metrics.

        For timeseries_drifter: computes haversine distance and bearing angle
        differences between reference drifter trajectories and parcels-simulated
        trajectories, averaged across all particles per time step.

        For maps_current_drifter / maps_trajectory_drifter: no comparison is
        computed (returns None); these outputs only need prod/ref data.

        Parameters
        ----------
        dsref
            Reference dataset with drifter positions.
        dsprod
            Production dataset with parcels simulation output.
        output
            Output type string.

        Returns
        -------
        xr.DataTree with 'diff' node containing distance/direction, or None.
        """
        if output in ("maps_current_drifter", "maps_trajectory_drifter"):
            return None

        coords = ["time", "lon", "lat"]
        suff = "_parcels"
        dsref = dsref[coords].set_coords(["time", "lat", "lon"]).squeeze()
        vrenames = {f"{vname}{suff}": vname for vname in coords}
        dsprod = dsprod[[f"{vname}{suff}" for vname in coords]]
        dsprod = dsprod.rename_vars(vrenames)

        data_list = []
        for iptc in range(dsprod.sizes["trajectory_parcels"]):
            dsparti = dsprod.isel(trajectory_parcels=iptc)
            dsparti = dsparti.where(dsparti.time.notnull(), drop=True)
            dsparti = dsparti.swap_dims({"obs_parcels": "time"})
            dsdrift = dsref.sel(time=slice(dsparti.time.min(), dsparti.time.max()))
            dsparti = dsparti.sel(time=slice(dsdrift.time.min(), dsdrift.time.max()))
            dist = haversine(dsdrift.lon, dsdrift.lat, dsparti.lon, dsparti.lat)
            bear_drift = bearing(
                dsdrift.lon.isel(time=slice(1, None)),
                dsdrift.lat.isel(time=slice(1, None)),
                dsdrift.lon.isel(time=slice(None, -1)),
                dsdrift.lat.isel(time=slice(None, -1))
                )
            bear_parti = bearing(
                dsparti.lon.isel(time=slice(1, None)),
                dsparti.lat.isel(time=slice(1, None)),
                dsparti.lon.isel(time=slice(None, -1)),
                dsparti.lat.isel(time=slice(None, -1))
                )
            angle = (((bear_drift - bear_parti) + 180) % 360) - 180
            if isinstance(angle, np.float64):
                angle = [angle]
            angle = np.concatenate([[0], angle])
            data_list.append(pd.DataFrame({
                'time': (dsparti.time - dsparti.time.min()).values / pd.to_timedelta("1d"),
                'dist': dist.values if hasattr(dist, 'values') else dist,
                'angle': angle.values if hasattr(angle, 'values') else angle
            }))

        df_all = pd.concat(data_list, ignore_index=True)
        grouped = df_all.groupby('time').agg({
            'dist': 'mean',
            'angle': 'mean'
        })
        dtcomps = xr.DataTree(name="comps")
        dtcomps.update(xr.DataTree.from_dict({
            "diff": xr.Dataset(
                data_vars=dict(
                    distance=(["time"], grouped['dist'].values),
                    direction=(["time"], grouped['angle'].values)
                    ),
                coords=dict(
                    time=grouped.index.values
                    )
                )
            }))
        return dtcomps
                
    
    def _parse_configuration(self, ocfg: List[Dict[str, Any]]) -> Tuple[str, str, Dict[str, Any], Dict[str, Any]]:
        """
        Parse and extract configuration components.
        
        Parameters
        ----------
        ocfg
            Configuration list containing metazone and output configs
            
        Returns
        -------
        Tuple of (metazone_name, output_name, metazone_params, output_params)
        """
        metazone = next(iter(ocfg[0]))
        output_key = next(iter(ocfg[1]))

        mparams = ocfg[0][metazone]
        oparams = ocfg[1][output_key]
        output = oparams.get("otype")
        
        return metazone, output, mparams, oparams
    
    def _validate_output_compatibility(self, oparams: Dict[str, Any], mparams: Dict[str, Any], 
                                     metazone: str, output: str) -> bool:
        """
        Validate if output type is compatible with metazone parameters.
        
        Parameters
        ----------
        oparams
            Output parameters
        mparams
            Metazone parameters
        metazone
            Metazone name
        output
            Output type name
            
        Returns
        -------
        True if compatible, False otherwise
        """
        try:
            if self.func_comp == "comp_drifter" and output in _DRIFTER_OTYPE_REMAP:
                output = _DRIFTER_OTYPE_REMAP[output]
            output_config = OUTPUTS_PARAMS[self.func_comp][output]
        except KeyError:
            logger.warning(f"Output type '{output}' not found in OUTPUTS_PARAMS for {self.func_comp}")
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
        
        Parameters
        ----------
        prods
            Dictionary mapping product names to their file lists
        output_params
            Output configuration parameters
            
        Returns
        -------
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
                                           output_params: Dict[str, Any], output) -> Dict[str, Dict]:
        """
        Generate statistics and comparisons for all products.
        
        Parameters
        ----------
        sorted_prods
            Sorted product files organized by type
        mparams
            Metazone parameters
        output_params
            Output configuration parameters
            
        Returns
        -------
        Dictionary containing processed datasets organized by product and data type
        """
        logger.info("Computing statistics & concatenations")
        
        dss = {}
        concat_dim = output_params.get("concat")
        
        for prod_name in sorted_prods.keys():
            logger.info(f"Processing {prod_name}")
            dss[prod_name] = {dt: {} for dt in DATA_TYPES}

            # Process each sorting group
            sort_keys = sorted_prods[prod_name]["prod"].keys()
            for sort_key in sort_keys:

                # Generate statistics for this sorting group
                stats_data = self._compute_statistics_for_sort_group(
                    sorted_prods[prod_name], sort_key, mparams, output_params, output
                )
                # Concatenate datasets for each data type
                for data_type in DATA_TYPES:
                    concatenated_data = self._concatenate_datasets(
                        stats_data[data_type], concat_dim
                    )
                    dss[prod_name][data_type][sort_key] = concatenated_data
        
        return dss
    
    def _compute_statistics_for_sort_group(self, prod_files: Dict[str, Dict], 
                                         sort_key: str, mparams: Dict[str, Any],
                                         output_params: Dict[str, Any], output) -> Dict[str, List]:
        """
        Compute statistics for a specific sorting group.
        
        Parameters
        ----------
        prod_files
            Product files organized by type (prod/ref)
        sort_key
            Sorting key identifier
        mparams
            Metazone parameters
        output_params
            Output parameters
            
        Returns
        -------
        Dictionary containing lists of computed statistics for each data type
        """
        prod_files_list = prod_files["prod"][sort_key]
        ref_files_list = prod_files["ref"][sort_key]
        num_files = len(prod_files_list)

        # Initialize storage for computed data trees
        computed_data = {data_type: [] for data_type in DATA_TYPES}

        # Open all files upfront to avoid repeated open/close overhead
        prod_datasets = []
        ref_datasets = []
        try:
            prod_datasets = [
                _compute_oceanvars(xr.open_dataset(f), self.func_comp)
                for f in prod_files_list
            ]
            ref_datasets = [
                _compute_oceanvars(xr.open_dataset(f), self.func_comp)
                for f in ref_files_list
            ]
            # Process each file pair
            for file_idx in range(num_files):
                ds_prod = prod_datasets[file_idx]
                ds_ref = ref_datasets[file_idx]
                # Set depth/pres as coordinate if needed
                for vcoord in ["depth", "pres"]:
                    if vcoord in ds_ref.data_vars:
                        ds_ref = ds_ref.set_coords(vcoord)
                    if vcoord in ds_prod.data_vars:
                        ds_prod = ds_prod.set_coords(vcoord)
                # Prepare statistics configuration
                stats = output_params.get("stat").copy() if output_params.get("stat") else None
                # Compute statistics and comparisons
                dt_prod, dt_ref, dt_comps = StatsComp(
                    mparams, ds_prod, ds_ref, stats
                ).compute()
                if self.func_comp == "comp_drifter":
                    dt_comps = self._drifter(ds_ref, ds_prod, output)

                # Store results
                computed_data["prod"].append(dt_prod)
                computed_data["ref"].append(dt_ref)
                computed_data["comp"].append(dt_comps)
        finally:
            # Close all files at end
            for ds in prod_datasets + ref_datasets:
                ds.close()

        return computed_data
    
    def _concatenate_datasets(self, data_trees: List[Any], 
                            concat_dim: List[str]) -> Dict[str, xr.Dataset]:
        """
        Concatenate datasets from data trees along specified dimensions.
        
        Parameters
        ----------
        data_trees
            List of data trees to concatenate
        concat_dim
            Dimensions to concatenate along
            
        Returns
        -------
        Dictionary of concatenated datasets
        """
        concatenated_data = {}
        
        # Filter out None entries (e.g. from _drifter for map outputs)
        data_trees = [dt for dt in data_trees if dt is not None]
        if not data_trees:
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
        
        Parameters
        ----------
        datasets
            List of datasets to concatenate
            
        Returns
        -------
        Concatenated dataset
        """
        # Handle multi-time datasets by splitting into individual time slices
        if any(ds.sizes["time"] > 1 for ds in datasets):
            time_slices = []
            for ds in datasets:
                time_slices.extend([
                    ds.isel(time=[time_idx])
                    for time_idx in range(ds.sizes["time"])
                ])
            datasets = time_slices

        # Concatenate along time dimension
        concatenated = xr.concat(datasets, "time")

        # Preserve vrange attributes if present in any dataset
        vrange_attrs = [ds.attrs.get("vrange") for ds in datasets if ds.attrs.get("vrange")]
        if vrange_attrs:
            concatenated.attrs["vrange"] = vrange_attrs
        
        return concatenated
    
    def _save_outputs(self, processed_datasets: Dict[str, Dict], 
                     sorted_prods: Dict[str, Dict],
                     metazone: str, ref_name: str, output: str,
                     output_params: Dict[str, Any]) -> List[str]:
        """
        Save processed datasets to output files.
        
        Parameters
        ----------
        processed_datasets
            Processed datasets organized by product and type
        sorted_prods
            Sorted product information
        metazone
            Metazone name
        ref_name
            Reference dataset name
        output
            Output type name
        output_params
            Output configuration parameters
            
        Returns
        -------
        List of saved output file paths
        """
        output_files = []
        
        # Create base output directory
        dirout = Path(f"{self.func_comp}/output/{metazone}/{ref_name}/{output}")
        
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
        
        Parameters
        ----------
        processed_datasets
            Processed datasets
        sort_key
            Sorting key
        sort_dir
            Output directory for this sort group
        sorted_prods
            Sorted product information
            
        Returns
        -------
        Path to saved combined file
        """
        dt = xr.DataTree()
        
        for prod_name in sorted_prods.keys():
            # Create product node in data tree
            dt.update(xr.DataTree.from_dict({prod_name: xr.DataTree()}))
            
            # Add data for each type (prod, ref, comp)
            for data_type in DATA_TYPES:
                datasets = processed_datasets[prod_name][data_type][sort_key]
                data_tree = xr.DataTree.from_dict(datasets)
                dt[prod_name].update(xr.DataTree.from_dict({data_type: data_tree}))

        # Save combined file
        output_file = sort_dir / "all.zarr"
        encoding = get_zarr_encoding(dt)
        dt.to_zarr(output_file, mode="w", encoding=encoding)
        logger.info(f"{output_file} saved")
        return output_file
    
    def _save_separate_outputs(self, processed_datasets: Dict[str, Dict], 
                             sort_key: str, sort_dir: Path,
                             sorted_prods: Dict[str, Dict]) -> List[Path]:
        """
        Save each product in a separate output file.
        
        Parameters
        ----------
        processed_datasets
            Processed datasets
        sort_key
            Sorting key
        sort_dir
            Output directory for this sort group
        sorted_prods
            Sorted product information
            
        Returns
        -------
        List of paths to saved files
        """
        output_files = []
        
        for prod_name in sorted_prods.keys():
            dt = xr.DataTree()
            
            # Create product node in data tree
            dt.update(xr.DataTree.from_dict({prod_name: xr.DataTree()}))
            
            # Add data for each type (prod, ref, comp)
            for data_type in DATA_TYPES:
                datasets = processed_datasets[prod_name][data_type][sort_key]
                if datasets:
                    data_tree = xr.DataTree.from_dict(datasets)
                    dt[prod_name].update(xr.DataTree.from_dict({data_type: data_tree}))

            # Save product file
            output_file = sort_dir / f"{prod_name}.zarr"
            encoding = get_zarr_encoding(dt)
            dt.to_zarr(output_file, mode="w", encoding=encoding)
            output_files.append(output_file)
            logger.info(f"{output_file} saved")
        
        return output_files


class OutputPipelineManager:
    """
    Manager class for handling the complete output processing pipeline with parallelization.
    """
    
    def __init__(self, func_comp=None):
        """Initialize the OutputPipelineManager."""
        self.processor = OutputProcessor(func_comp=func_comp)
        self.func_comp = func_comp
    
    def process_and_extract(self, output_config: List[Dict[str, Any]]) -> Dict[str, Dict[str, List[str]]]:
        """
        Process output configuration and extract non-empty results.
        
        This method is designed to be used with Dask for parallel processing.
        
        Parameters
        ----------
        output_config
            Output configuration
            
        Returns
        -------
        Dictionary with only non-empty results
        """
        # Process the output
        results = self.processor.process_output(output_config)
        
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
                          outputs: Dict[str, Any], **kwargs) -> Dict[str, Dict[str, List[str]]]:
        """
        Process all output configurations with parallel execution.
        
        Parameters
        ----------
        ncs
            NetCDF files organized by metazone
        metazones_in
            Input metazone configurations
        outputs
            Output configurations
            
        Returns
        -------
        Dictionary mapping output types to metazones to file paths
            
        Examples
        --------
        >>> manager = OutputPipelineManager()
        >>> ncs = {'atlantic': {'ref1': {'prod1': ['file1.nc']}}}
        >>> metazones = {'atlantic': {'param1': 'value1'}}
        >>> outputs = {'comparison': {'otype': 'stats_comp'}}
        >>> result = manager.process_all_outputs(ncs, metazones, outputs, 'validation')
        """
        # Prepare configurations
        output_configs = self._prepare_output_configurations(
            ncs, metazones_in, outputs, **kwargs
        )
        # Create delayed tasks for parallel processing
        delayed_tasks = [
            dask.delayed(self.process_and_extract)(config)
            for config in output_configs
        ]
        
        # Execute all tasks in parallel
        results = dask.compute(*delayed_tasks)
        
        # Merge all results
        results = self._merge_results(results)
        return results
    
    def _prepare_output_configurations(self, ncs: Dict[str, Any], 
                                     metazones_in: Dict[str, Any],
                                     outputs: Dict[str, Any],
                                     **kwargs
                                     ) -> List[List[Dict[str, Any]]]:
        """
        Prepare output configurations for processing.
        
        Parameters
        ----------
        ncs
            NetCDF files organized by metazone
        metazones_in
            Input metazone configurations
        outputs
            Output configurations
            
        Returns
        -------
        List of output configurations ready for processing
        """
        # Remove format specification and validate outputs
        output_configs = outputs.copy()
        output_configs.pop("fmt", None)
        output_configs = check_output(self.func_comp, output_configs)
        preproc = OUTPUTS_PARAMS[self.func_comp].get("preproc")
        # Prepare metazone configurations
        prepared_metazones = {}
        for metazone_name, metazone_config in metazones_in.items():
            if metazone_config:
                ncins = ncs.get(metazone_name)
                if preproc:
                    preproc_comp(self.func_comp, ncins, **kwargs)
                prepared_metazones[metazone_name] = {
                    "ncins": ncins,
                    "vars": COMP_VARS[self.func_comp],
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

        Parameters
        ----------
        results
            List of result dictionaries from parallel tasks

        Returns
        -------
        Merged results dictionary
        """
        merged_results = {}

        for result in results:
            for output_name, metazones in result.items():
                if output_name not in merged_results:
                    merged_results[output_name] = {}
                for mz_name, file_paths in metazones.items():
                    if mz_name in merged_results[output_name]:
                        merged_results[output_name][mz_name].extend(file_paths)
                    else:
                        merged_results[output_name][mz_name] = file_paths
        
        return merged_results


def main_output(ncs: Dict[str, Any], metazones_in: Dict[str, Any],
               outputs: Dict[str, Any], func_comp: str, **kwargs) -> Dict[str, Dict[str, List[str]]]:
    """
    Main function for processing all output configurations with parallel execution.
    
    This function maintains backward compatibility while providing improved structure
    and parallel processing capabilities.
    
    Parameters
    ----------
    ncs
        Dictionary mapping metazone names to their NetCDF files
    metazones_in
        Dictionary of metazone configurations
    outputs
        Dictionary of output configurations (fmt key will be removed)
    func_comp
        Function component identifier for directory structure
        
    Returns
    -------
    Dictionary mapping output names to metazones to lists of output file paths.
    Structure
        {output_name: {metazone_name: [file_path1, file_path2, ...]}}
        
    Examples
    --------
    >>> ncs = {'atlantic': {'ref1': {'prod1': ['file1.nc', 'file2.nc']}}}
    >>> metazones = {'atlantic': {'param1': 'value1'}}
    >>> outputs = {'monthly_stats': {'otype': 'statistics'}, 'fmt': 'zarr'}
    >>> result = main_output(ncs, metazones, outputs, 'validation')
    >>> print(result)
    {'statistics': {'atlantic': ['validation/output/atlantic/ref1/statistics/file1.zarr']}}
    """
    manager = OutputPipelineManager(func_comp=func_comp)
    fouts = manager.process_all_outputs(ncs, metazones_in, outputs, **kwargs)
    return fouts
