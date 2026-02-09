import gc
import logging
import warnings
from pathlib import Path
from typing import List, Optional, Tuple

import dask
import numpy as np
import pandas as pd
import xarray as xr
import xoa.coords as xcoords
import xoa.geo as xgeo

import armoor.base.ranges as ranges
from armoor.__init__ import ArmoorError
from armoor.base.interp import grid2loc, interp_time, regrid, vinterp
from armoor.base.io import (create_fast_encoding, get_zarr_encoding,
                            setup_dask_client)
from armoor.base.misc import optimize_for_low_swap
from armoor.comp import (COLOCATION_PARAMS_DEFAULT, COLOCATION_PARAMS_USER,
                         COMP_VARS)
from armoor.comp.misc import get_colocation_params, validate_colocation

logger = logging.getLogger(__name__)

class AbstractColocation:
    """Abstract class for coloction."""
    
    def __init__(self):
        """Initialize the AbstractColocation instance with an empty dictionary to store methods."""
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
        raise ArmoorError(f"Colocation '{method_name}' not found")

    def __init_subclass__(cls):
        """Initialize the subclass by adding the __post_init__ method to the class.
        
        This method is called after the class is defined.
        """
        def __post_init__(self):
            for name, method in vars(cls).items():
                if callable(method) and not name.startswith("__"):
                    self.register_method(method)
        cls.__post_init__ = __post_init__


class TimeColocation(AbstractColocation):
    """Colocate timely two datasets.

    Parameters
    ----------
    xarray_obj : xarray.Dataset
        Observation dataset to subset.
    """
    
    def __init__(self, dsref, dsprod, tbound):
        self.dsref = dsref
        self.dsprod = dsprod
        self.methods = {}
        self.start = tbound[0]
        self.end = tbound[1]

    def tfreq(self, tfreq: str) -> xr.Dataset:
        """Subset dataset selecting elements at specific terms.
    
        Parameters
        ----------
        freq : str
            Frequency aliases.
            
        Returns
        -------
        xarray.Dataset, xarray.Dataset
        """
        time = pd.date_range(start=self.start, end=self.end, freq=tfreq)
        self.dsref = interp_time(self.dsref, time)
        self.dsprod = interp_time(self.dsprod, time)
        return self.dsref, self.dsprod
    
    def trange_seq(self, args: [str, str]) -> xr.Dataset:
        """
        Colocate reference and product on the same time axis before ranging.

        Parameters
        ----------
        args: list
            List of two elements, the first one is the bin period, 
            the second one is the reference time axis (reference or product).

        Returns
        -------
        xarray.Dataset, xarray.Dataset
        """
        tfreq = args[0]
        ref = args[1]
        if len(args) > 2:
            method = args[2]
        else:
            method = "linear"
        if ref == "reference":
            self.dsprod = interp_time(self.dsprod, self.dsref.time, method=method)
            self.dsprod["time"].encoding = self.dsref.time.encoding
            self.dsprod["time"].attrs = self.dsref.time.attrs
        elif ref == "product":
            self.dsref = interp_time(self.dsref, self.dsprod.time, method=method)
            self.dsref["time"].encoding = self.dsprod.time.encoding
            self.dsref["time"].attrs = self.dsprod.time.attrs
        else:
            raise ArmoorError(
                "Use 'reference' or 'product' to specify the reference time"
                "for ranging then."
                )
        return self.dsref, self.dsprod
    

class HorizontalColocation(AbstractColocation):
    """Colocate horizontaly two datasets.

    Parameters
    ----------
    xarray_obj : xarray.Dataset
        Observation dataset to subset.
    """
    
    def __init__(self, dsref, dsprod):
        self.dsref = dsref
        self.dsprod = dsprod
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
        if not set(("x", "y")).issubset(self.dsref.lon.dims):
            return None, grid2loc(self.dsprod, coords)
        else:
            return grid2loc(self.dsref, coords), grid2loc(self.dsprod, coords)
        
    def href(self, ref: str):
        """Regrid dataset on 'ref' grid.

        Parameters
        ----------
        ref : str
            'reference' or 'product'.

        Returns
        -------
        xarray.Dataset, xarray.Dataset
            Datasets with elements located at specific coordinates.
        """
        if ref == "reference":
            if "mask" in self.dsref:
                mask = self.dsref.mask.compute()
                self.dsref = self.dsref.where(mask, drop=True)
            self.dsprod = regrid(self.dsprod, self.dsref)
        else:
            if "mask" in self.dsprod:
                self.dsprod = self.dsprod.where(self.dsprod.mask, drop=True)
            self.dsref = regrid(self.dsref, self.dsprod)
        if "mask" in self.dsprod:
            self.dsprod = self.dsprod.drop_vars("mask")
        if "mask" in self.dsref:
            self.dsref= self.dsref.drop_vars("mask")
        return self.dsref, self.dsprod
    
    def _clean_coordinates(self, dataset: xr.Dataset) -> xr.Dataset:
        """Remove temporary coordinates and rename primary ones."""
        coords_to_drop = ["lon", "lat", "lon_1", "lat_1"]
        existing_coords = [coord for coord in coords_to_drop if coord in dataset.coords]
        
        cleaned_ds = dataset.drop_vars(existing_coords)
        return cleaned_ds.rename({"lon_0": "lon", "lat_0": "lat"})
    
    def _calculate_distances_vectorized(self, prod_data: xr.Dataset, ref_data: xr.Dataset) -> xr.DataArray:
        """
        Calculate distances using vectorized operations for all timesteps at once.
        OPTIMISATION 1: Calcul vectorisé pour tous les timesteps simultanément
        """
        rename_dims = {"npts0": "member"}
        if "time" in ref_data.lon.dims:
            rename_dims["npts1"] = "time"
        dist = (xgeo.get_distances(prod_data, ref_data)
                #.squeeze()
                .rename(rename_dims)
                .assign_coords(member=prod_data.member)
            )
        return dist
    
    def _handle_time_dependent(self, radius_meters: float) -> None:
        """
        OPTIMISATION MAJEURE: Traite tous les timesteps simultanément au lieu d'une boucle.
        """
        dist_prod2ref = self._calculate_distances_vectorized(self.dsprod, self.dsref)
        mask = dist_prod2ref < radius_meters
        mask = mask.transpose("time", "member")
        for coord in ["lon", "lat"]:
            self.dsprod[coord] = self.dsprod[coord].expand_dims({"time": self.dsprod.time})
        self.dsprod = self.dsprod.reset_coords(["lon", "lat"])
        
        coords = [coord for coord in mask.coords]
        mask = mask.drop_vars(coords)
        self.dsprod = self.dsprod.where(mask)#, drop=True)
        self.dsprod = self.dsprod.set_coords(["lon", "lat"])
 
    def radius(self, radius: float) -> Tuple[xr.Dataset, xr.Dataset]:
        """
        Version optimisée de la méthode radius.
        
        Parameters
        ----------
        radius : float
            Radius (in km) of the disk around an observation.
        Returns
        -------
        tuple[xarray.Dataset, xarray.Dataset]
            Tuple containing (reference dataset, product dataset)
        """
        if radius <= 0:
            raise ValueError("Radius must be positive")
        
        radius_meters = radius * 1e3
        
        # Préparation des données (unchanged)
        self.dsprod = xcoords.geo_stack(self.dsprod, "member")
        # OPTIMISATION: Choix de la méthode selon le cas
        if "time" not in self.dsref.lon.dims:
            # Cas time-independent (unchanged)
            dist_prod2ref = self._calculate_distances_vectorized(self.dsprod, self.dsref)
            filtered_ds = self.dsprod.where(dist_prod2ref < radius_meters)#, drop=True)
            self.dsprod = self._clean_coordinates(filtered_ds)
        else:
            self._handle_time_dependent(radius_meters)
        
        # Set depth coordinate if needed (unchanged)
        if "depth" not in self.dsprod.coords and "depth" in self.dsprod.data_vars:
            self.dsprod = self.dsprod.set_coords("depth")
        return self.dsref, self.dsprod
    

class VerticalColocation(AbstractColocation):
    """Colocate horizontaly two datasets.

    Parameters
    ----------
    xarray_obj : xarray.Dataset
        Observation dataset to subset.
    """
    
    def __init__(self, dsref, dsprod):
        self.dsref = dsref
        self.dsprod = dsprod
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
        prod_attrs = self.dsprod.attrs
        ref_attrs = self.dsref.attrs
        if "z" in self.dsref.dims:
            self.dsref = vinterp(self.dsref, vname, vlevels)
        else:
            logger.warning("No 'z' dim in reference")
        if "z" in self.dsprod.dims:
            self.dsprod = vinterp(self.dsprod, vname, vlevels)
        else:
            self.logger.warning("no 'z' dim in product")
        self.dsref.attrs.update(ref_attrs)
        self.dsprod.attrs.update(prod_attrs)
        return self.dsref, self.dsprod
    
    def vrange(self, args: [str, str, list]) -> xr.Dataset:
        """
        Colocate reference and product on the same vertical axis before ranging.

        Parameters
        ----------
        args: list
            List of three elements, the first one is the vertical reference (reference or product),
            the second one is the vertical coodinate,
            the third one is the list of bounds of the vertical bins.

        Returns
        -------
        xarray.Dataset, xarray.Dataset
        """
        vref = args[0]
        vcoord = args[1]
        if vref == "reference":
            attrs = self.dsprod.attrs
            self.dsprod = vinterp(
                self.dsprod.chunk(dict(z=-1)), vcoord, self.dsref[vcoord].chunk(dict(z=-1))
                )
            self.dsprod.attrs.update(attrs)
        elif vref == "product":
            attrs = self.dsref.attrs
            self.dsref = vinterp(
                self.dsref.chunk(dict(z=-1)), vcoord, self.dsprod[vcoord].chunk(dict(z=-1))
                )
            self.dsref.attrs.update(attrs)
        else:
            raise ArmoorError(
                "Use 'reference' or 'product' to specify the vertical "
                "reference for ranging then."
                )
        return self.dsref, self.dsprod


def validate_and_get_params(metazones, comp_func):
    """Validate and get colocation parameters.
    
    Parameters
    ----------
    metazones: dict
        Dictionary containing metazone information.
    comp_func: str
        Comparison function identifier.
    
    Returns
    -------
    dict
        Colocation parameters.
    """
    metazones = validate_colocation(metazones, COLOCATION_PARAMS_USER[comp_func])
    coloc_params = get_colocation_params(
        metazones,
        COLOCATION_PARAMS_USER[comp_func],
        COLOCATION_PARAMS_DEFAULT.get(comp_func)
        )
    return coloc_params


def process_time_colocation(dsref, dsprod, param, tbound):
    """Process colocation for time dimension.
    
    Parameters
    ----------
    dsref: xr.Dataset
        Reference dataset.
    dsprod: xr.Dataset
        Product dataset.
    param: list
        Parameters for time colocation.
    tbound: list
        Time bounds for colocation.
    
    Returns
    -------
    tuple
        Colocated reference and product datasets.
    """
    logger.info("---- Time colocation")
    coloc = TimeColocation(dsref, dsprod, tbound)
    coloc.__post_init__()
    dsref, dsprod = coloc.call(*param)
    return dsref, dsprod
    
def process_horizontal_colocation(dsref, dsprod, param):
    """Process colocation for horizontal dimensions.
    
    Parameters
    ----------
    dsref: xr.Dataset
        Reference dataset.
    dsprod: xr.Dataset
        Product dataset.
    param: list
        Parameters for horizontal colocation.
    
    Returns
    -------
    tuple
        Colocated reference and product datasets.
    """
    logger.info("---- Horizontal colocation")
    coloc = HorizontalColocation(dsref, dsprod)
    coloc.__post_init__()
    dsref, dsprod = coloc.call(*param)
    return dsref, dsprod

def process_vertical_colocation(dsref, dsprod, param):
    """Process colocation for vertical dimensions.
    
    Parameters
    ----------
    dsref: xr.Dataset
        Reference dataset.
    dsprod: xr.Dataset
        Product dataset.
    param: list
        Parameters for vertical colocation.
    
    Returns
    -------
    tuple
        Colocated reference and product datasets.
    """
    logger.info("---- Vertical colocation")    
    coloc = VerticalColocation(dsref, dsprod)
    coloc.__post_init__()
    dsref, dsprod = coloc.call(*param)
    return dsref, dsprod

def save_datasets(dsref, dsprod, dirout, ref_name, prod_name):
    """Save datasets to NetCDF files.

    Parameters
    ----------
    dsref: xr.Dataset
        Reference dataset to save.
    dsprod: xr.Dataset
        Product dataset to save.
    dirout: Path
        Directory to save the datasets.
    ref_name: str
        Name for the reference dataset file.
    prod_name: str
        Name for the product dataset file.

    Returns
    -------
    tuple
        Paths to the saved reference and product NetCDF files.
    """
    attrs = dsref.attrs
    ncname = ""
    if "time" in attrs:
        ncname += f"_{attrs['time']}"
    elif "trange" in attrs:
        ncname += f"_{attrs['trange']}"

    if "vlevel" in attrs:
        ncname += f"_{attrs['vlevel']}"
    elif "vrange" in attrs:
        ncname += f"_{attrs['vrange']}"

    ncout_ref = dirout / f"ref{ncname}.zarr"
    ncout_prod = dirout / f"prod{ncname}.zarr"

    logger.info(f"Save {ncout_ref}")
    if "mask" in dsref.data_vars:
        dsref = dsref.drop_vars("mask")
    dsref = dsref.chunk("auto")
    encoding = get_zarr_encoding(dsref)
    dsref.to_zarr(store=ncout_ref, mode="w", encoding=encoding)
    dsref.close()

    logger.info(f"Save {ncout_prod}")
    if "mask" in dsprod.data_vars:
        dsprod = dsprod.drop_vars("mask")
    dsprod = dsprod.chunk("auto")
    encoding = get_zarr_encoding(dsprod)
    dsprod.to_zarr(store=ncout_prod, mode="w", encoding=encoding)
    dsprod.close()

    return ncout_ref, ncout_prod


def _prepare_dataset(ds, comp_func, is_reference=False):
    """Prepare a dataset for colocation.

    Parameters
    ----------
    ds: xr.Dataset
        Dataset to prepare.
    comp_func: str
        Comparison function identifier.
    is_reference: bool
        Whether this is a reference dataset.

    Returns
    -------
    xr.Dataset
        Prepared dataset.
    """
    ds = optimize_for_low_swap(ds, target_chunk_mb=512)

    if "depth" in ds.data_vars:
        ds = ds.set_coords("depth")

    for var in COMP_VARS[comp_func]:
        da = ds.oceanvars.sel(var)
        if isinstance(da, xr.DataArray):
            ds[var] = da

    vars_to_keep = set(COMP_VARS[comp_func])
    if is_reference:
        vars_to_keep.add("mask")

    for var in list(ds.data_vars):
        if var not in vars_to_keep:
            ds = ds.drop_vars(var)

    if "depth" in ds.coords and "time" in ds.depth.dims:
        ds = ds.reset_coords("depth")

    return ds


def _apply_colocations(dsref, dsprod, params, tbound):
    """Apply time, horizontal, and vertical colocations.

    Parameters
    ----------
    dsref: xr.Dataset
        Reference dataset.
    dsprod: xr.Dataset
        Product dataset.
    params: dict
        Colocation parameters.
    tbound: tuple
        Time bounds.

    Returns
    -------
    tuple
        Colocated (dsref, dsprod).
    """
    if params.get("time"):
        dsref, dsprod = process_time_colocation(
            dsref, dsprod, params["time"], tbound
        )
        gc.collect()

    if params.get("horizontal"):
        dsref, dsprod = process_horizontal_colocation(
            dsref, dsprod, params["horizontal"]
        )
        gc.collect()

    if params.get("vertical"):
        dsref, dsprod = process_vertical_colocation(
            dsref, dsprod, params["vertical"]
        )
        gc.collect()

    return dsref, dsprod


def _apply_time_ranges(dsref, dsprod, params, tbound):
    """Apply time ranging to datasets.

    Parameters
    ----------
    dsref: xr.Dataset
        Reference dataset.
    dsprod: xr.Dataset
        Product dataset.
    params: dict
        Colocation parameters containing time settings.
    tbound: tuple
        Time bounds.

    Returns
    -------
    tuple
        Lists of (dsref_list, dsprod_list) after ranging.
    """
    time_coloc = params.get("time")

    if time_coloc is None:
        return [dsref], [dsprod]

    if "tfreq" in time_coloc[0]:
        return ranges.tfreq(dsref), ranges.tfreq(dsprod)

    if "trange_seq" in time_coloc[0]:
        if time_coloc[1][0] != "*":
            return (
                ranges.trange_seq(dsref, *tbound, time_coloc[1][0]),
                ranges.trange_seq(dsprod, *tbound, time_coloc[1][0])
            )

    return [dsref], [dsprod]


def _apply_vertical_ranges(dsref_list, dsprod_list, params, comp_func):
    """Apply vertical ranging to dataset lists.

    Parameters
    ----------
    dsref_list: list
        List of reference datasets.
    dsprod_list: list
        List of product datasets.
    params: dict
        Colocation parameters containing vertical settings.
    comp_func: str
        Comparison function identifier.

    Returns
    -------
    tuple
        Lists of (dsref_list, dsprod_list) after vertical ranging.
    """
    vertical_coloc = params.get("vertical")

    if vertical_coloc is None:
        return dsref_list, dsprod_list

    if "vlevel" in vertical_coloc[0] or comp_func in ("comp_mooring", "comp_drifter"):
        if comp_func in ("comp_mooring", "comp_drifter"):
            vname = "depth"
        else:
            vname = vertical_coloc[1][0]

        if comp_func != "comp_sst":
            return (
                ranges.vlevels(dsref_list, vname),
                ranges.vlevels(dsprod_list, vname)
            )

    elif "vrange" in vertical_coloc[0]:
        vname = vertical_coloc[1][1]
        vbins = vertical_coloc[1][2]
        return (
            ranges.vrange(dsref_list, vname, vbins),
            ranges.vrange(dsprod_list, vname, vbins)
        )

    return dsref_list, dsprod_list


def _save_colocation_results(dssref, dssprod, comp_func, metazone, ncouts, ref_name, prod_name):
    """Save colocation results to files.

    Parameters
    ----------
    dssref: list
        List of reference datasets.
    dssprod: list
        List of product datasets.
    comp_func: str
        Comparison function identifier.
    metazone: str
        Metazone name.
    ncouts: dict
        Dictionary to store output paths.
    ref_name: str
        Reference dataset name.
    prod_name: str
        Product dataset name.
    """
    logger.info("Save coloc data in zarr")

    for ids in range(len(dssref)):
        dsref = dssref[ids]
        dsprod = dssprod[ids]

        dirout = Path(
            f"{comp_func}/coloc/{metazone}/"
            f"{dsref.attrs['data_name']}/{dsprod.attrs['data_name']}"
        )
        dirout.mkdir(parents=True, exist_ok=True)

        ncout_ref, ncout_prod = save_datasets(
            dsref, dsprod, dirout,
            dsref.attrs['data_name'],
            dsprod.attrs['data_name']
        )

        ncouts[metazone][ref_name][prod_name].append(ncout_ref)
        ncouts[metazone][ref_name][prod_name].append(ncout_prod)

        dsref.close()
        dsprod.close()


def _process_single_product(dsrefin, ncin, params, tbound, comp_func, metazone, ncouts):
    """Process colocation for a single product against a reference.

    Parameters
    ----------
    dsrefin: xr.Dataset
        Reference dataset (already prepared).
    ncin: Path
        Path to product file.
    params: dict
        Colocation parameters.
    tbound: tuple
        Time bounds.
    comp_func: str
        Comparison function identifier.
    metazone: str
        Metazone name.
    ncouts: dict
        Dictionary to store output paths.
    """
    logger.info(f"-- Process {ncin}")

    dsprodin = xr.open_dataset(ncin)
    if "depth" in dsprodin and "depth" not in dsprodin.coords:
        dsprodin = dsprodin.set_coords("depth")
    dsprodin = _prepare_dataset(dsprodin, comp_func, is_reference=False)
    logger.info(dsprodin.sizes)

    dsref = dsrefin.copy()
    dsprod = dsprodin.copy()
    gattrs_ref = dsref.attrs
    gattrs_prod = dsprod.attrs

    prod_name = dsprodin.attrs['data_name']
    ref_name = dsrefin.attrs['data_name']

    # Initialize output structure
    if ref_name not in ncouts[metazone]:
        ncouts[metazone][ref_name] = {}
    if prod_name not in ncouts[metazone][ref_name]:
        ncouts[metazone][ref_name][prod_name] = []

    # Apply colocations
    dsref, dsprod = _apply_colocations(dsref, dsprod, params, tbound)

    # Set depth as coordinate if needed
    if "depth" in dsref.data_vars:
        dsref = dsref.set_coords("depth")
    if "depth" in dsprod.data_vars:
        dsprod = dsprod.set_coords("depth")

    dsref = dsref.assign_attrs(gattrs_ref)
    dsprod = dsprod.assign_attrs(gattrs_prod)

    # Compute
    logger.info("Compute coloc ref")
    dsref = dsref.compute()
    logger.info("Compute coloc prod")
    dsprod = dsprod.compute()

    # Apply ranges
    dssref, dssprod = _apply_time_ranges(dsref, dsprod, params, tbound)
    dssref, dssprod = _apply_vertical_ranges(dssref, dssprod, params, comp_func)

    # Save results
    _save_colocation_results(
        dssref, dssprod, comp_func, metazone, ncouts, ref_name, prod_name
    )


def _process_reference(ncref, ncs, params, tbound, comp_func, metazone, ncouts):
    """Process all products for a single reference.

    Parameters
    ----------
    ncref: Path
        Path to reference file.
    ncs: list
        List of all NetCDF file paths.
    params: dict
        Colocation parameters.
    tbound: tuple
        Time bounds.
    comp_func: str
        Comparison function identifier.
    metazone: str
        Metazone name.
    ncouts: dict
        Dictionary to store output paths.
    """
    logger.info(f"Use reference {ncref}")

    dsrefin = xr.open_dataset(ncref, engine="zarr")
    dsrefin = _prepare_dataset(dsrefin, comp_func, is_reference=True)

    ncins = [nc for nc in ncs if metazone in str(nc) and "ref" not in str(nc)]

    for ncin in ncins:
        _process_single_product(
            dsrefin, ncin, params, tbound, comp_func, metazone, ncouts
        )

    dsrefin.close()
    gc.collect()


def _process_metazone(metazone, params, ncs, metazones, comp_func, ncouts):
    """Process colocation for a single metazone.

    Parameters
    ----------
    metazone: str
        Metazone name.
    params: dict
        Colocation parameters for this metazone.
    ncs: list
        List of all NetCDF file paths.
    metazones: dict
        Dictionary containing all metazone information.
    comp_func: str
        Comparison function identifier.
    ncouts: dict
        Dictionary to store output paths.
    """
    logger.info(f"Start colocation for {metazone}.")
    logger.info(f"Colocation parameters are: {params}")

    tbound = metazones[metazone].get("tbound")
    ncouts[metazone] = {}

    ncrefs = [nc for nc in ncs if (metazone in str(nc)) and ("ref" in str(nc))]

    for ncref in ncrefs:
        _process_reference(ncref, ncs, params, tbound, comp_func, metazone, ncouts)

    logger.info(f"End colocation for {metazone}.")


def main_coloc(ncs, metazones, comp_func):
    """Colocate reference and products.

    Parameters
    ----------
    ncs: list
        List of NetCDF file paths.
    metazones: dict
        Dictionary containing metazone information.
    comp_func: str
        Comparison function identifier.

    Returns
    -------
    dict
        Dict of paths to the saved reference and product NetCDF files.
    """
    coloc_check = validate_and_get_params(metazones, comp_func)

    # Filter valid metazones
    coloc_params = {}
    for metazone, params in coloc_check.items():
        if not params:
            logger.info(f"Skip {metazone}: colocation is not possible for this functionnality.")
        else:
            coloc_params[metazone] = params

    ncouts = {}
    for metazone, params in coloc_params.items():
        _process_metazone(metazone, params, ncs, metazones, comp_func, ncouts)

    return ncouts
