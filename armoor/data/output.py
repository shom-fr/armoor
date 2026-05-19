import gc
import logging
import re
import sys
from pathlib import Path
from typing import Dict, List, Optional, Any

import pandas as pd
import xarray as xr

from armoor.__init__ import ArmoorError
from armoor.base.io import (
    setup_dask_client,
    get_zarr_encoding,
    sort_ncs_by_suffix
    )
from armoor.base.misc import optimize_for_low_swap
import armoor.base.ranges as ranges
from armoor.data import INTERP_PARAMS_USER, OUTPUTS_PARAMS
from armoor.data.interp import (
    process_time_interpolation,
    process_horizontal_interpolation,
    process_vertical_interpolation
    )

logger = logging.getLogger(__name__)
   
def get_dim_stats(dsin, dim, mparams):
    if dim:
        dim_stats = dim.copy()
        if ("time" in dim) and ("trange_seq" not in mparams):
            dim_stats.remove("time")
        if ("z" in dim) and ("vrange" not in mparams):
            dim_stats.remove("z")
        if ("x" in dim) and ("x" not in dsin.dims):
            dim_stats.remove("x")
            dim_stats.remove("y")
        return dim_stats
    else:
        return None
    
def set_time_range(ds, time):
    if "time" not in ds.dims: # mean/std groups
        if "time" in ds.coords:
            ds = ds.drop_vars("time")
        ds = ds.expand_dims(dim="time")
        
        t1, t2 = [pd.to_datetime(t).strftime('%Y%m%d') for t in time.strip('[').split('_')]
        med_time = t1+0.5*(t2-t1)
        
        ds["time"] = xr.DataArray(
            data=[med_time],
            dims="time"
            )    
        del t1,t2,med_time
        
        ds = ds.set_coords("time")
    return ds

def get_datatrees(dsins, dim, mparams):
    dts = []
    for ds in dsins:
        for coord in ["lon", "lat", "depth"]:
            if coord in ds.coords:
                if "time" in ds[coord].dims:
                    ds = ds.reset_coords("depth")
        dt = xr.DataTree(name=ds.attrs["data_name"])
        dt.update(xr.DataTree.from_dict({
            "data": ds
            }))
        dim = get_dim_stats(ds, dim, mparams)
        if dim:
            dt.update(xr.DataTree.from_dict({
                "mean": ds.mean(dim=dim)
                }))
            dt.update(xr.DataTree.from_dict({
                "std": ds.std(dim=dim)
                }))
        xdim = {}
        if "trange_seq" in mparams:
            xdim.update({"time": ds.attrs["trange"]})
        for k, v in xdim.items():
            for data_name, dt0 in dt.items():
                ds0 = dt0.to_dataset()
                ds0 = ds0.assign_attrs({"trange_seq": mparams['trange_seq'][0]})
                if dim:
                    if ("time" in dim) and (k == "time"):
                        ds0 = set_time_range(ds0, v)
                dt.update(xr.DataTree.from_dict({
                    data_name: ds0
                    }))
        dts.append(dt)
        del dt,ds
    return dts

def validate_interpolation(metazones):
    """Validate that only one of the two parameters is defined for each metazone.

    This function checks if either param1 or param2 is defined, but not both,
    for each metazone in the metazones dictionary.

    Parameters
    ----------
    metazones (dict): A dictionary of metazones with their parameters.
    param1: str
        The first parameter to check.
    param2: str
        The second parameter to check.
        
    Raises
    ------
    ArmoorError: If both parameters are defined or neither is defined.
    """
    for mz_name, mz_param in metazones.items():
        for k, v in INTERP_PARAMS_USER.items():
            if len(v) == 2:
                param1, param2 = v[0], v[1]
                val1 = mz_param.get(param1)
                val2 = mz_param.get(param2)
                if val1 is not None and val2 is not None:
                    raise ArmoorError(
                        f"Both '{param1}' and '{param2}' are defined for {mz_name}. "
                        f"Please choose either '{param1}' or '{param2}' colocation."
                    )
                    
                if val1 is None and val2 is None:
                    logger.info(
                        f"Neither '{param1}' nor '{param2}' is defined for {mz_name}. "
                        f"Please choose either '{param1}' or '{param2}' colocation."
                    )
                    metazones[mz_name] = None
                    continue
    return metazones

def get_interpolation_params(metazones):
    """
    Retrieve colocation parameters for each metazone based on given parameters.

    This function takes two dictionaries as input: `metazones` and `params`. It
    returns a dictionary where each key is a metazone and each value is a
    dictionary containing the colocation parameters ("time", "horizontal",
    "vertical") that were found in `metazones` using the parameter candidates
    specified in `params`.

    Parameters
    ----------
    metazones: dict
        A dictionary where each key is the name of a metazone
        and each value is a dictionary containing the
        parameters of that metazone.
    params_user: dict
        A dictionary defined by users where each key is a type of interpolation
        ("time", "horizontal", "vertical") and each value is a
        list of parameter candidates to search for in `metazones`.
    params_default: dict
        A dictionary where each key is a type of colocation
        ("time", "horizontal", "vertical") and each value is a
        list of default parameters.

    Returns
    -------
    dict 
        A dictionary where each key is a metazone and each value is a
        dictionary containing the colocation parameters found for that
        metazone.
    """
    interp_params = {}
    for mz_name, mz_params in metazones.items():
        if mz_params:            
            interp_params[mz_name] = {
                interp: (param_candidate, mz_params.get(param_candidate))
                for interp in ("time", "horizontal", "vertical") 
                for param_candidate in INTERP_PARAMS_USER.get(interp, [])
                if (mz_params.get(param_candidate) is not None)
                }
        else:
            interp_params[mz_name] = None
    return interp_params

def validate_and_get_params(metazones):
    """Validate and get colocation parameters.
    
    Parameters
    ----------
    metazones: dict
        Dictionary containing metazone information.
    
    Returns
    -------
    dict
        Colocation parameters.
    """
    metazones = validate_interpolation(metazones)
    interp_params = get_interpolation_params(metazones)
    return interp_params

def save_datasets(dsprod, dirout, prod_name):
    """Save dataset to NetCDF files.

    Parameters
    ----------
    dsprod: xr.Dataset
        Product dataset to save.
    dirout: Path
        Directory to save the datasets.
    prod_name: str
        Name for the product dataset file.
    
    Returns
    -------
    tuple
        Paths to the saved reference and product NetCDF files.
    """
    attrs = dsprod.attrs
    ncname = ""
    if "time" in attrs:
        ncname += f"_{attrs['time']}"
    elif "trange" in attrs:
        trange = attrs['trange']
        trange = re.sub('[\[\]]', '', trange)
        ncname += f"_{trange}"
    else:
        pass
    
    if "vlevel" in attrs:
        ncname += f"_{attrs['vlevel']}"
    elif "vrange" in attrs:
        ncname += f"_{attrs['vrange']}"
    else:
        pass
    ncout_prod = dirout / f"prod{ncname}.zarr"
    #logger.info(f"Save {ncout_prod}")
    dsprod = dsprod.chunk("auto")
    encoding = get_zarr_encoding(dsprod)
    # dsprod.to_netcdf(
    #     ncout_prod,
    #     encoding=encoding,
    #     format='NETCDF4',
    #     engine='netcdf4',
    #     compute=True  # Forcer le compute immédiat
    #     )
    dsprod.to_zarr(
        store=ncout_prod,
        mode="w",
        encoding=encoding,
        )
    dsprod.close()
    return ncout_prod


class OutputProcessor:
    """
    A class to handle NetCDF data processing including interpolation and output generation.
    """
    
    def __init__(self, target_chunk_mb: int = 512):
        """
        Initialize the DataProcessor.

        Parameters
        ----------
        target_chunk_mb
            Target chunk size in MB for memory optimization
        """
        self.target_chunk_mb = target_chunk_mb
    
    def process_datasets(self, ncs: List[str], metazones: Dict[str, Any], 
                        outputs: Dict[str, Any]) -> Dict[str, Dict[str, List[Path]]]:
        """
        Main processing function for NetCDF datasets.
        
        Parameters
        ----------
        ncs
            List of NetCDF file paths to process
        metazones
            Dictionary containing metazone configurations
        outputs
            Dictionary containing output configurations (will be modified)
            
        Returns
        -------
        Dictionary mapping output names to metazones to list of output files
            
        Raises
        ------
        ArmoorError
            When processing fails
        """
        # Remove 'fmt' from outputs as it's not needed
        outputs.pop("fmt", None)
        
        # Validate and prepare interpolation parameters
        interp_params = self._prepare_interpolation_params(metazones)
        ncouts = {}
        
        # Process each NetCDF file
        for nc_file in ncs:
            logger.info(f"Processing {nc_file}")
            ncouts = self._process_single_netcdf(
                nc_file, metazones, interp_params, outputs, ncouts
            )
            
        return ncouts
    
    def _prepare_interpolation_params(self, metazones: Dict[str, Any]) -> Dict[str, Optional[Dict]]:
        """
        Validate metazones and prepare interpolation parameters.
        
        Parameters
        ----------
        metazones
            Dictionary containing metazone configurations
            
        Returns
        -------
        Dictionary mapping metazone names to interpolation parameters
        """
        interp_check = validate_and_get_params(metazones)
        interp_params = {}
        
        for metazone, params in interp_check.items():
            if not params:
                logger.info(f"{metazone}: no interpolation required.")
                interp_params[metazone] = None
            else:
                interp_params[metazone] = params
                
        return interp_params
    
    def _process_single_netcdf(self, nc_file: str, metazones: Dict[str, Any],
                              interp_params: Dict[str, Optional[Dict]], 
                              outputs: Dict[str, Any],
                              ncouts: Dict[str, Dict[str, List[Path]]]) -> Dict[str, Dict[str, List[Path]]]:
        """
        Process a single NetCDF file for all metazones.
        
        Parameters
        ----------
        nc_file
            Path to NetCDF file
        metazones
            Metazone configurations
        interp_params
            Interpolation parameters for each metazone
        outputs
            Output configurations
        ncouts
            Accumulator for output file paths
            
        Returns
        -------
        Updated ncouts dictionary
        """
        # Load and prepare dataset
        dsin = self._load_and_prepare_dataset(nc_file)
        attrs_in = dsin.attrs
        prod_name = attrs_in.get("data_name")
        
        try:
            # Process each metazone
            for metazone, params in interp_params.items():
                fouts = self._process_metazone(
                    dsin, metazone, metazones[metazone], params, attrs_in
                )
                
                # Generate outputs for this metazone
                ncouts = self._generate_outputs(
                    fouts, metazone, metazones[metazone], outputs, 
                    prod_name, ncouts
                )
                
        finally:
            dsin.close()
            
        return ncouts
    
    def _load_and_prepare_dataset(self, nc_file: str) -> xr.Dataset:
        """
        Load and prepare a NetCDF dataset for processing.
        
        Parameters
        ----------
        nc_file
            Path to NetCDF file
            
        Returns
        -------
        Loaded and prepared xarray Dataset
        """
        dsin = xr.open_dataset(nc_file)
        
        # Handle depth coordinate if it has time dimension
        if "depth" in dsin.coords and "time" in dsin["depth"].dims:
            dsin = dsin.reset_coords("depth")
            
        # Optimize chunking for memory efficiency
        dsin = optimize_for_low_swap(dsin, target_chunk_mb=self.target_chunk_mb)
        
        return dsin
    
    def _process_metazone(self, dsin: xr.Dataset, metazone: str, 
                         mparams: Dict[str, Any], params: Optional[Dict],
                         attrs_in: Dict[str, Any]) -> List[Path]:
        """
        Process a dataset for a specific metazone.
        
        Parameters
        ----------
        dsin
            Input dataset
        metazone
            Name of the metazone
        mparams
            Metazone parameters
        params
            Interpolation parameters
        attrs_in
            Original dataset attributes
            
        Returns
        -------
        List of output file paths
        """
        ds = dsin.copy()
        
        # Apply interpolations if needed
        if params:
            ds = self._apply_interpolations(ds, params, mparams)
            if not isinstance(ds, xr.Dataset):
                ds.close()
                return []
        else:
            logger.info("No interpolation required")
        
        # Restore attributes and clean up dataset
        ds.attrs.update(attrs_in)
        ds = self._cleanup_dataset(ds)
        
        # Compute and process ranges
        # with setup_dask_client():
        ds = ds.compute()
        dss = self._apply_range_processing(ds, mparams)
        
        # Save processed datasets
        fouts = self._save_processed_datasets(dss, metazone)
        
        return fouts
    
    def _apply_interpolations(self, ds: xr.Dataset, params: Dict[str, Any],
                             mparams: Dict[str, Any]) -> xr.Dataset:
        """
        Apply various interpolations to the dataset.
        
        Parameters
        ----------
        ds
            Dataset to interpolate
        params
            Interpolation parameters
        mparams
            Metazone parameters
            
        Returns
        -------
        Interpolated dataset
        """
        logger.info("Start interpolation")
        
        # Time interpolation
        if params.get("time"):
            ds = process_time_interpolation(
                ds, params.get("time"), mparams.get("tbound")
            )
            gc.collect()
        
        # Horizontal interpolation
        if params.get("horizontal"):
            ds = process_horizontal_interpolation(ds, params.get("horizontal"))
            gc.collect()
        
        # Vertical interpolation
        if params.get("vertical"):
            ds = process_vertical_interpolation(ds, params.get("vertical"))
            gc.collect()
        
        return ds
    
    def _cleanup_dataset(self, ds: xr.Dataset) -> xr.Dataset:
        """
        Remove unnecessary variables from dataset.
        
        Parameters
        ----------
        ds
            Dataset to clean up
            
        Returns
        -------
        Cleaned dataset
        """
        vars_to_drop = []
        for varname in ("bathy", "mask"):
            if varname in ds:
                vars_to_drop.append(varname)
        
        return ds.drop_vars(vars_to_drop, errors='ignore')
    
    def _apply_range_processing(self, ds: xr.Dataset, 
                               mparams: Dict[str, Any]) -> List[xr.Dataset]:
        """
        Apply time and vertical range processing to dataset.
        
        Parameters
        ----------
        ds
            Dataset to process
        mparams
            Metazone parameters
            
        Returns
        -------
        List of processed datasets
        """
        # Time range processing
        if "tfreq" in mparams:
            dss = ranges.tfreq(ds)
        elif "trange_seq" in mparams:
            logger.info('Applying trange_seq...')
            try:
                dss = ranges.trange_seq(
                    ds, *mparams.get("tbound"), mparams["trange_seq"][0]
                    )
            except:
                logger.info('Error for trange_seq. Maybe tbound was not defined in metazones.')
                sys.exit(1)
        else:
            dss = [ds]
        
        # Vertical level processing
        if "vlevel" in mparams:
            vname = mparams["vlevel"][0]
            dss = ranges.vlevels(dss, vname)
        elif "vrange" in mparams:
            vname = mparams["vrange"][1]
            vbins = mparams["vrange"][2]
            dss = ranges.vrange(dss, vname, vbins)
        
        return dss
    
    def _save_processed_datasets(self, dss: List[xr.Dataset], 
                                metazone: str) -> List[Path]:
        """
        Save processed datasets to disk.
        
        Parameters
        ----------
        dss
            List of datasets to save
        metazone
            Metazone name for directory structure
            
        Returns
        -------
        List of saved file paths
        """
        logger.info("Save interpolated data")
        fouts = []
        
        try:
            for ids, dsprod in enumerate(dss):
                dirout = Path(f"data/interp/{metazone}/{dsprod.attrs['data_name']}")
                dirout.mkdir(parents=True, exist_ok=True)
                
                fout_prod = save_datasets(
                    dsprod, dirout, dsprod.attrs['data_name']
                )
                fouts.append(fout_prod)
                dsprod.close()
        finally:
            del dss
            
        return fouts
    
    def _generate_outputs(self, fouts: List[Path], metazone: str,
                         mparams: Dict[str, Any], outputs: Dict[str, Any],
                         prod_name: str, 
                         ncouts: Dict[str, Dict[str, List[Path]]]) -> Dict[str, Dict[str, List[Path]]]:
        """
        Generate output files for a metazone.
        
        Parameters
        ----------
        fouts
            List of intermediate file paths
        metazone
            Metazone name
        mparams
            Metazone parameters
        outputs
            Output configurations
        prod_name
            Product name
        ncouts
            Accumulator for output paths
            
        Returns
        -------
        Updated ncouts dictionary
        """
        for oname, output in outputs.items():
            logger.info(f"Processing output: {oname}")
            
            # Check if output type is allowed and compatible
            if not self._validate_output_compatibility(output, mparams, metazone):
                continue
            
            # Process this output type
            output_files = self._process_output_type(
                fouts, output, metazone, mparams, prod_name, oname
            )
            
            # Add to results
            if output_files:
                if oname not in ncouts:
                    ncouts[oname] = {}
                if metazone not in ncouts[oname]:
                    ncouts[oname][metazone] = []
                ncouts[oname][metazone].extend(output_files)
        
        return ncouts
    
    def _validate_output_compatibility(self, output: Dict[str, Any],
                                     mparams: Dict[str, Any], 
                                     metazone: str) -> bool:
        """
        Validate if an output type is compatible with the metazone parameters.
        
        Parameters
        ----------
        output
            Output configuration
        mparams
            Metazone parameters
        metazone
            Metazone name
            
        Returns
        -------
        True if compatible, False otherwise
        """
        oparams = OUTPUTS_PARAMS.get(output.get("otype"))
        if not oparams:
            logger.warning(f"Skip {output.get('otype')}: forbidden")
            return False
        
        # Check required parameters
        if oparams.get("mparams_pro"):
            for dim, param in oparams.get("mparams_pro").items():
                if not bool(set(param) & set(mparams.keys())):
                    logger.info(
                        f"{output} cannot be processed for {metazone} "
                        f"due to missing {param}"
                    )
                    return False
        
        # Check conflicting parameters
        if oparams.get("mparams_con"):
            for dim, param in oparams.get("mparams_con").items():
                if bool(set(param) & set(mparams.keys())):
                    logger.info(
                        f"{output} cannot be processed for {metazone} "
                        f"due to conflicting {param}"
                    )
                    return False
        
        return True
    
    def _process_output_type(self, fouts: List[Path], output: Dict[str, Any],
                           metazone: str, mparams: Dict[str, Any],
                           prod_name: str, oname: str) -> List[Path]:
        """
        Process a specific output type.
        
        Parameters
        ----------
        fouts
            Input file paths
        output
            Output configuration
        metazone
            Metazone name
        mparams
            Metazone parameters
        prod_name
            Product name
        oname
            Output name
            
        Returns
        -------
        List of generated output files
        """
        oparams = OUTPUTS_PARAMS.get(output.get("otype"))
        logger.info(f"Output parameters: {oparams}")
        
        sort_dim = oparams.get("sort")
        concat_dim = oparams.get("concat")
        
        fins_dict_sorted = sort_ncs_by_suffix(fouts, sort_dim=sort_dim)
        output_files = []
        
        for name_sort, fins_sorted in fins_dict_sorted.items():
            logger.info(f"Processing sorted group: {name_sort}")
            
            output_file = self._process_sorted_group(
                fins_sorted, oparams, mparams, metazone, oname,
                name_sort, prod_name, concat_dim
            )
            
            if output_file:
                output_files.append(output_file)
        
        return output_files
    
    def _process_sorted_group(self, fins_sorted: List[Path], 
                             oparams: Dict[str, Any], mparams: Dict[str, Any],
                             metazone: str, oname: str, name_sort: str,
                             prod_name: str, concat_dim: List[str]) -> Optional[Path]:
        """
        Process a sorted group of files to create a single output.
        
        Parameters
        ----------
        fins_sorted
            Sorted list of input files
        oparams
            Output parameters
        mparams
            Metazone parameters
        metazone
            Metazone name
        oname
            Output name
        name_sort
            Sorted group name
        prod_name
            Product name
        concat_dim
            Concatenation dimensions
            
        Returns
        -------
        Path to generated output file, or None if failed
        """
        # Load datasets
        dss = [xr.open_dataset(fin) for fin in fins_sorted]
        
        try:
            # Get data trees with statistics
            dts0 = get_datatrees(dss, oparams.get("stat"), mparams)
            del dss
            
            # Process each dataset in the tree
            dsouts = {}
            for ds_name in dts0[0].keys():
                ds = self._process_tree_dataset(
                    dts0, ds_name, concat_dim
                )
                dsouts[ds_name] = ds
            
            del dts0
            
            # Save as zarr
            return self._save_datatree_output(
                dsouts, metazone, oname, name_sort, prod_name
            )
            
        except Exception as e:
            logger.error(f"Failed to process sorted group {name_sort}: {e}")
            return None
    
    def _process_tree_dataset(self, dts0: List[Any], ds_name: str,
                             concat_dim: List[str]) -> xr.Dataset:
        """
        Process a single dataset from the data tree.
        
        Parameters
        ----------
        dts0
            List of data trees
        ds_name
            Name of dataset to extract
        concat_dim
            Concatenation dimensions
            
        Returns
        -------
        Processed dataset
        """
        dss0 = [dt[ds_name].to_dataset() for dt in dts0]
        
        if concat_dim == ["time"]:
            # Handle time concatenation
            if dss0[0].sizes["time"] > 1:
                # Split multi-time datasets into individual time slices
                dss1 = []
                for ds0 in dss0:
                    dss1.extend([
                        ds0.isel(time=itime) 
                        for itime in range(ds0.sizes["time"])
                    ])
                dss0 = dss1
            
            ds = xr.concat(dss0, "time")
            
            # Handle vrange attributes specifically
            if dss0[0].attrs.get("vrange"):
                vrange_attrs = [ds0.attrs.get("vrange") for ds0 in dss0]
                ds.attrs["vrange"] = vrange_attrs
                
        elif len(dss0) == 1:
            ds = dss0[0]
        else:
            raise ArmoorError("Multi-dataset concatenation not implemented")
        
        return ds
    
    def _save_datatree_output(self, dsouts: Dict[str, xr.Dataset],
                             metazone: str, oname: str, name_sort: str,
                             prod_name: str) -> Path:
        """
        Save processed datasets as a DataTree zarr file.
        
        Parameters
        ----------
        dsouts
            Dictionary of datasets to save
        metazone
            Metazone name
        oname
            Output name
        name_sort
            Sorted group name
        prod_name
            Product name
            
        Returns
        -------
        Path to saved file
        """
        dirout = Path(f"data/output/{metazone}/{oname}/{name_sort}/")
        dirout.mkdir(parents=True, exist_ok=True)
        
        # Create DataTree and save
        dt = xr.DataTree()
        dt.update(xr.DataTree.from_dict(dsouts))
        
        ncout = dirout / f"{prod_name}.zarr"
        encoding = get_zarr_encoding(dt)
        
        logger.info(f"Saving output: {ncout}")
        dt.to_zarr(ncout, mode="w", encoding=encoding)
        
        return ncout


# Convenience function for backward compatibility
def main_output(ncs: List[str], metazones: Dict[str, Any], 
               outputs: Dict[str, Any]) -> Dict[str, Dict[str, List[Path]]]:
    """
    Main function for processing NetCDF datasets with interpolation and output generation.
    
    This function processes a list of NetCDF files according to specified metazone
    configurations and generates various output formats.
    
    Parameters
    ----------
    ncs
        List of paths to NetCDF files to process
    metazones
        Dictionary containing metazone configurations with parameters
              for interpolation, time/vertical ranges, etc.
    outputs
        Dictionary containing output configurations. The 'fmt' key will
            be removed if present.
    
    Returns
    -------
    Dictionary mapping output names to metazones to lists of output file paths.
    Structure
        {output_name: {metazone_name: [file_path1, file_path2, ...]}}
    
    Raises
    ------
    ArmoorError
        When processing fails due to configuration or data issues
    
    Examples
    --------
    >>> ncs = ['data1.nc', 'data2.nc']
    >>> metazones = {
    ...     'zone1': {'tbound': ['2020-01-01', '2020-12-31']},
    ...     'zone2': {'vlevel': ['surface']}
    ... }
    >>> outputs = {'monthly': {'otype': 'timeseries'}}
    >>> result = main_output(ncs, metazones, outputs)
    >>> print(result)
    {'monthly': {'zone1': [Path('data/output/zone1/monthly/...')], ...}}
    """
    processor = OutputProcessor()
    return processor.process_datasets(ncs, metazones, outputs)
