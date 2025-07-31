import gc
import itertools
import logging
import re
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Optional

import dask
import numpy as np
import pandas as pd
import xarray as xr

from armoor.__init__ import ArmoorError
from armoor.base.interp import grid2loc, interp_time, vinterp
from armoor.base.io import (
    setup_dask_client,
    get_zarr_encoding,
    sort_ncs_by_suffix
    )
from armoor.base.misc import optimize_for_low_swap
import armoor.base.ranges as ranges
from armoor.data import INTERP_PARAMS_USER, OUTPUTS_PARAMS

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
    if "time" in ds.dims:
        ds = ds.drop_dims("time")
    if "time" in ds.coords:
        ds = ds.drop_vars("time")
    ds = ds.expand_dims(dim="time")
    ds["time"] = xr.DataArray(
        data=[pd.to_datetime(time)],
        dims="time"
        )
    ds = ds.set_coords("time")
    return ds

def get_datatrees(dsins, dim, mparams):
    
    dts = []
    for ds in dsins:
        if "depth" in ds.coords:
            if "time" in ds["depth"].dims:
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
                if data_name != "data":
                    if ("time" in dim) and (k == "time"):
                        ds0 = set_time_range(ds0, v)
                    dt.update(xr.DataTree.from_dict({
                        data_name: ds0
                        }))
        dts.append(dt)
        del dt
        del ds
    return dts
    
    
class AbstractInterpolation:
    """Abstract class for interpolation."""
    
    def __init__(self):
        """Initialize the AbstractInterpolation instance with an empty dictionary to store methods."""
        self.methods = {}

    def register_method(self, func):
        """Register a method in the methods dictionary.

        Parameters
        ----------
        func
            The method to be registered.

        Returns
        -------
            The registered method.
        """
        self.methods[func.__name__] = func
        return func

    def __post_init__(self):
        """Register all callable methods of the class after initialization.
        
        This method is called after the instance is initialized.
        """
        for name, method in vars(self.__class__).items():
            if callable(method) and not name.startswith("__"):
                self.register_method(method)

    def call(self, method_name, *args, **kwargs):
        """Call a method by its name.

        Parameters
        ----------
        method_name: str
            The name of the method to call.

        Returns
        -------
            The result of the called method.

        Raises
        ------
            AttributeError: If the method is not found.
        """
        method = self.methods.get(method_name)
        if method:
            return method(self, *args, **kwargs)
        raise ArmoorError(f"Interpolation '{method_name}' not found")

    def __init_subclass__(cls):
        """Initialize the subclass by adding the __post_init__ method to the class.
        
        This method is called after the class is defined.
        """
        def __post_init__(self):
            for name, method in vars(cls).items():
                if callable(method) and not name.startswith("__"):
                    self.register_method(method)
        cls.__post_init__ = __post_init__


class TimeInterpolation(AbstractInterpolation):
    """Interpolate in time a dataset.

    Parameters
    ----------
    xarray_obj : xarray.Dataset
        Product dataset to subset.
    """
    
    def __init__(self, ds, tbound):
        self.ds = ds
        self.methods = {}
        self.start = tbound[0]
        self.end = tbound[1]

    def tfreq(self, tfreq: str) -> xr.Dataset:
        """Subset dataset selecting elements at specific terms.
    
        Parameters
        ----------
        freq : str
            See :ref:`here <timeseries.offset_aliases>` for a list of
            frequency aliases.
            
        Returns
        -------
        xarray.Dataset, xarray.Dataset
        """
        time = pd.date_range(start=self.start, end=self.end, freq=tfreq)
        self.ds = interp_time(self.ds, time)
        return self.ds


class HorizontalInterpolation(AbstractInterpolation):
    """Interpolate horizontaly a dataset.

    Parameters
    ----------
    xarray_obj : xarray.Dataset
        Product dataset to subset.
    """
    
    def __init__(self, ds):
        self.ds = ds
        self.methods = {}

    def cloud(self, coords: [(float, float)]):
        """Interpolate datasets at specific coordinates.

        Parameters
        ----------
        coordinates : list of tuples
            Set of points coordinates (lon, lat) defining the coordinates to select.

        Returns
        -------
        xarray.Dataset, xarray.Dataset
            Dataset with elements located at specific coordinates.
        """
        return grid2loc(self.ds, coords)
    
    def _clean_coordinates(self, dataset: xr.Dataset) -> xr.Dataset:
        """Remove temporary coordinates and rename primary ones."""
        coords_to_drop = ["lon", "lat", "lon_1", "lat_1"]
        existing_coords = [coord for coord in coords_to_drop if coord in dataset.coords]
        
        cleaned_ds = dataset.drop_vars(existing_coords)
        return cleaned_ds.rename({"lon_0": "lon", "lat_0": "lat"})


class VerticalInterpolation(AbstractInterpolation):
    """Interpolate verticaly a dataset.

    Parameters
    ----------
    xarray_obj : xarray.Dataset
        Product dataset to interpolate.
    """
    
    def __init__(self, ds):
        self.ds = ds
        self.methods = {}
        self.logger = logging.getLogger(__name__)
        
    def vlevel(self, args: (str, list)):
        """Interpolate datasets to specified vertical levels.
        
        Parameters
        ----------
        args: dict
            A dictionary with a single key-value pair where the key is the vertical coordinate name
            and the value is a list of vertical levels to interpolate to.
        
        Returns
        -------
        xarray.Dataset, xarray.Dataset
            A tuple containing the verticaly interpolated reference dataset and product dataset.
        """
        vname = args[0]
        vlevels = args[1]
        vlevels = xr.DataArray(vlevels, dims="z", name=vname)
        attrs = self.ds.attrs
        if "z" in self.ds.dims:
            self.ds = vinterp(self.ds, vname, vlevels)
            self.ds.attrs.update(attrs)
            return self.ds
        else:
            logger.warning("No 'z' dim in product")
            return None


def process_time_interpolation(ds, param, tbound):
    """Process interpolation for time dimension.
    
    Parameters
    ----------
    ds: xr.Dataset
        Product dataset.
    param: list
        Parameters for time colocation.
    tbound: list
        Time bounds for colocation.
    
    Returns
    -------
    tuple
        Interpolated product dataset.
    """
    logger.info("---- Time interpolation")
    coloc = TimeInterpolation(ds, tbound)
    coloc.__post_init__()
    ds = coloc.call(*param)
    return ds
    
def process_horizontal_interpolation(ds, param):
    """Process interpolation for horizontal dimensions.
    
    Parameters
    ----------
    ds: xr.Dataset
        Product dataset.
    param: list
        Parameters for horizontal colocation.
    
    Returns
    -------
    tuple
        Interpolated product dataset.
    """
    logger.info("---- Horizontal interpolation")
    coloc = HorizontalInterpolation(ds)
    coloc.__post_init__()
    ds = coloc.call(*param)
    return ds

def process_vertical_interpolation(ds, param):
    """Process interpolation for vertical dimensions.
    
    Parameters
    ----------
    ds: xr.Dataset
        Product dataset.
    param: list
        Parameters for vertical colocation.
    
    Returns
    -------
    tuple
        Interpolated product datasets.
    """
    logger.info("---- Vertical colocation")    
    coloc = VerticalInterpolation(ds)
    coloc.__post_init__()
    ds = coloc.call(*param)
    return ds

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
        ncname += f"_{attrs['trange']}"
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

def main_output(ncs, metazones, outputs):
    interp_check = validate_and_get_params(metazones)
    interp_params = {}
    ncouts = {}
    for metazone, params in interp_check.items():
        if not params:
            logger.info(f"{metazone}: no interpolation required.")
            interp_params[metazone] = None
        else:
            interp_params[metazone] = params

    for nc in ncs:
        dsin = xr.open_dataset(nc)
        if "depth" in dsin.coords:
            if "time" in dsin["depth"].dims:
                dsin = dsin.reset_coords("depth")
        attrs_in = dsin.attrs
        prod_name = attrs_in.get("data_name")
        dsin = optimize_for_low_swap(dsin, target_chunk_mb=512)
        logger.info(f"Process {nc}")
        for metazone, params in interp_params.items():
            mparams = metazones[metazone]
            ds = dsin.copy()
            if params:
                logger.info("Start interpolation")
                if params.get("time"):
                    ds = process_time_interpolation(
                        ds,
                        params.get("time"),
                        metazones[metazone].get("tbound")
                        )
                    gc.collect()
                if params.get("horizontal"):
                    ds = process_horizontal_interpolation(
                        ds,
                        params.get("horizontal"),
                        )
                    gc.collect()
                if params.get("vertical"):
                    ds = process_vertical_interpolation(
                        ds,
                        params.get("vertical"),
                        )
                if not isinstance(ds, xr.Dataset):
                    ds.close()
                    continue
                gc.collect()
            else:
                logger.info("No interpolation required")
            ds.attrs.update(attrs_in)
            vars2drop = []
            for varname in ("bathy", "mask"):
                if varname in ds:
                    vars2drop.append(varname)
            ds = ds.drop_vars(vars2drop, errors='raise')
            logger.info("Compute prod")
            with setup_dask_client():
                ds = ds.compute()
                if  "tfreq" in metazones[metazone]:
                    ds = ranges.tfreq(ds)
                elif "trange_seq" in metazones[metazone]:
                    ds = ranges.trange_seq(
                        ds,
                        *metazones[metazone].get("tbound"),
                        metazones[metazone]["trange_seq"][0]
                        )
                else:
                    ds = [ds]
                if "vlevel" in metazones[metazone]:
                    vname  = metazones[metazone]["vlevel"][0]
                    ds = ranges.vlevels(ds, vname)
                elif "vrange" in metazones[metazone]:
                    vname = metazones[metazone]["vrange"][1]
                    vbins = metazones[metazone]["vrange"][2]
                    ds = ranges.vrange(ds, vname, vbins)
                dss = ds
                del ds
            dsin.close()
            logger.info("Save interp data")
            fouts = []
            for ids in range(len(dss)):
                dsprod = dss[ids]
                dirout = Path(
                    f"data/interp/{metazone}/"
                    f"{dsprod.attrs['data_name']}"
                    )
                dirout.mkdir(parents=True, exist_ok=True)
                fout_prod = save_datasets(
                    dsprod,
                    dirout,
                    dsprod.attrs['data_name']
                    )
                fouts.append(fout_prod)
                dsprod.close()
            del dss
            
            for oname, output in outputs.items():
                logger.info(oname)
                oparams =  OUTPUTS_PARAMS.get(output.get("otype"))
                if not oparams:
                    logger.warning(f"Skip {output.get('otype')}: forbidden")
                    continue
                should_continue = False
                if oparams.get("mparams_pro"):
                    for dim, param in oparams.get("mparams_pro").items():
                        if not bool(set(param) & set(mparams.keys())):
                            logger.info(f"{output} cannot be processed for {metazone} caused by missing {param}")
                            should_continue = True
                if oparams.get("mparams_con"):
                    for dim, param in oparams.get("mparams_con").items():
                        if bool(set(param) & set(mparams.keys())):
                            logger.info(f"{output} cannot be processed for {metazone} caused by {param}")
                            should_continue = True
                if should_continue:
                    continue
                logger.info(oparams)
                sort_dim = oparams.get("sort")
                concat_dim = oparams.get("concat")
                fins_dict_sorted = sort_ncs_by_suffix(fouts, sort_dim=sort_dim)
                for name_sort, fins_sorted in fins_dict_sorted.items():
                    logger.info(name_sort)
                    dss = [xr.open_dataset(fin) for fin in fins_sorted]
                    dts0 = get_datatrees(
                        dss,
                        oparams.get("stat"),
                        metazones[metazone]
                        )
                    del dss
                    dsouts = {}
                    for ds_name in dts0[0].keys():
                        dss0 = []
                        for dt in dts0:
                            dss0.append(dt[ds_name].to_dataset())
                        if concat_dim == ["time"]:
                            if dss0[0].sizes["time"] > 1:
                                dss1 = []
                                for ids, ds0 in enumerate(dss0):
                                    dss1 += [
                                        ds0.isel(time=itime) 
                                        for itime in range(
                                            ds0.sizes["time"]
                                            )
                                        ]
                                dss0 = dss1
                                del dss1
                            ds = xr.concat(dss0, "time")
                            if dss0[0].attrs.get("vrange"):
                                xattrs = [
                                    ds0.attrs.get("vrange") for ds0 in dss0
                                    ]
                                ds.attrs["vrange"] = xattrs
                        elif len(dss0) == 1:
                            ds = dss0[0]
                        else:
                            raise ArmoorError(
                                "Not implemented."
                                )
                        del dss0
                        dsouts.update({ds_name: ds})
                        del ds
                    del dts0
                    dirout = Path(
                        f"data/output/{metazone}/{oname}/{name_sort}/"
                        )
                    dirout.mkdir(parents=True, exist_ok=True)
                    dt = xr.DataTree()
                    dt.update(xr.DataTree.from_dict(
                        dsouts
                        ))
                    del dsouts
                    ncout = dirout / f"{prod_name}.zarr"
                    encoding = get_zarr_encoding(dt)
                    logger.info(f"Save {ncout}")
                    dt.to_zarr(ncout, mode="w", encoding=encoding)
                    if not ncouts.get(oname):
                        ncouts.update({oname: {}})
                    if not ncouts[oname].get(metazone):
                        ncouts[oname] = {metazone: []}
                    ncouts[oname][metazone].append(ncout)
                    del dt
                    
    return ncouts 
 
            
            
            
            
            
            
            