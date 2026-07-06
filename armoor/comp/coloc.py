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
from armoor.base.dispatch import SubclassingMethodRegistry
from armoor.base.interp import coarsen as _coarsen, grid2loc, interp_time, regrid, vinterp
from armoor.base.io import (create_fast_encoding, get_zarr_encoding,
                            setup_dask_client)
from armoor.comp import COMP_VARS
from armoor.comp.comparison import get_comparison
from armoor.comp.misc import get_colocation_params, validate_colocation

logger = logging.getLogger(__name__)


class AbstractColocation(SubclassingMethodRegistry):
    """Abstract class for coloction."""

    _dispatch_label = "Colocation"


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
    
    def tmonth(self) -> Tuple[xr.Dataset, xr.Dataset]:
        """Monthly climatological colocation.

        Groups model data by calendar month, computes monthly means,
        then aligns with the reference climatology on a shared month index (1–12).
        """
        ds_prod_monthly = (
            self.dsprod
            .sel(time=slice(self.start, self.end))
            .groupby("time.month")
            .mean("time")
            .rename({"month": "time"})
        )
        common_months = np.intersect1d(
            ds_prod_monthly.time.values,
            self.dsref.time.values,
        )
        ds_prod_monthly = ds_prod_monthly.sel(time=common_months)
        ds_ref_monthly = self.dsref.sel(time=common_months)
        # Align time dtype and strip CF encoding attrs: WOA18 stores month
        # indices as floats with 'units'/'calendar' in attrs, while the
        # product has plain int months from groupby. Make both consistent
        # (int, no CF attrs) so zarr encoding doesn't conflict.
        ds_ref_monthly = ds_ref_monthly.assign_coords(
            time=("time", common_months.astype(int), {})
        )
        return ds_ref_monthly, ds_prod_monthly

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

    def coarsen(self, factor: int, on: str = "product", boundary: str = "trim", method: str = "mean") -> Tuple[xr.Dataset, xr.Dataset]:
        """Coarsen one or both datasets by aggregating spatial blocks.

        Useful for degrading model resolution before computing comparison
        scores, e.g. to study score sensitivity to grid resolution.

        Parameters
        ----------
        factor : int
            Coarsening factor applied to both ``x`` and ``y`` dimensions.
        on : str
            Which dataset to coarsen: ``"product"`` (default), ``"reference"``,
            or ``"both"``.
        boundary : str
            How to handle non-divisible sizes: ``"trim"`` (default) or ``"pad"``.
        method : str
            Aggregation method: ``"mean"`` (default), ``"median"``, ``"min"``, ``"max"``.

        Returns
        -------
        tuple[xr.Dataset, xr.Dataset]
            Reference and product datasets (the coarsened one(s) replaced).
        """
        if on in ("product", "both"):
            self.dsprod = _coarsen(self.dsprod, factor=factor, boundary=boundary, method=method)
        if on in ("reference", "both"):
            self.dsref = _coarsen(self.dsref, factor=factor, boundary=boundary, method=method)
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

        # Drop members outside radius at ALL timesteps (compaction)
        any_valid = mask.any(dim="time")
        if not any_valid.any():
            logger.warning(
                "No product member is ever within the radius; "
                "skipping where(mask) to avoid an all-NaN dataset."
            )
            return
        if not any_valid.all():
            n_before = self.dsprod.sizes["member"]
            valid_idx = np.where(any_valid.values)[0]
            self.dsprod = self.dsprod.isel(member=valid_idx)
            mask = mask.isel(member=valid_idx)
            logger.info(
                f"Compacted members: {n_before} -> {self.dsprod.sizes['member']}"
            )

        # Drop members whose ocean data are all-NaN at every (time, z) point.
        # These are land/masked cells in the model that passed the geographic
        # distance filter but carry no usable data (e.g. coastal or shelf cells).
        _geo = {"lon", "lat", "depth"}
        _ocean_vars = [v for v in self.dsprod.data_vars if v not in _geo]
        if _ocean_vars:
            # A member is valid if at least one ocean variable has at least one
            # non-NaN value across all times (and depths if 3-D).
            sample_var = _ocean_vars[0]
            reduce_dims = [d for d in self.dsprod[sample_var].dims if d != "member"]
            valid_member = (~self.dsprod[sample_var].isnull()).any(dim=reduce_dims)
            if not valid_member.all():
                n_before = self.dsprod.sizes["member"]
                ocean_valid_idx = np.where(valid_member.values)[0]
                if len(ocean_valid_idx) == 0:
                    logger.warning(
                        f"All {n_before} compacted members have NaN ocean data "
                        f"(lon [{float(self.dsprod.lon.min()):.2f}, "
                        f"{float(self.dsprod.lon.max()):.2f}], "
                        f"lat [{float(self.dsprod.lat.min()):.2f}, "
                        f"{float(self.dsprod.lat.max()):.2f}]). "
                        "Skipping colocation for this reference."
                    )
                    return
                self.dsprod = self.dsprod.isel(member=ocean_valid_idx)
                mask = mask.isel(member=ocean_valid_idx)
                logger.warning(
                    f"Dropped {n_before - len(ocean_valid_idx)} members with "
                    f"all-NaN ocean data; {len(ocean_valid_idx)} remain."
                )

        for coord in ["lon", "lat"]:
            self.dsprod[coord] = self.dsprod[coord].expand_dims({"time": self.dsprod.time})
        self.dsprod = self.dsprod.reset_coords(["lon", "lat"])

        # Promote depth to coordinate before masking so where(mask) does not
        # NaN-fill it. A NaN source coordinate in vinterp causes regrid1d to
        # produce all-NaN output for every affected profile.
        if "depth" in self.dsprod.data_vars:
            self.dsprod = self.dsprod.set_coords("depth")

        coords = [coord for coord in mask.coords]
        mask = mask.drop_vars(coords)
        self.dsprod = self.dsprod.where(mask)
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
        if "member" not in self.dsprod.dims:
            self.dsprod = xcoords.geo_stack(self.dsprod, "member")
        if "time" not in self.dsref.lon.dims:
            # Cas time-independent (unchanged)
            dist_prod2ref = self._calculate_distances_vectorized(self.dsprod, self.dsref)
            filtered_ds = self.dsprod.where(dist_prod2ref < radius_meters)#, drop=True)
            self.dsprod = self._clean_coordinates(filtered_ds)
        else:
            logger.info("time dependent")
            self._handle_time_dependent(radius_meters)
        # Set depth coordinate if needed (unchanged)
        #if "depth" not in self.dsprod.coords and "depth" in self.dsprod.data_vars:
        #    self.dsprod = self.dsprod.set_coords("depth")
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
    comparison = get_comparison(comp_func)
    metazones = validate_colocation(metazones, comparison.colocation_params_user)
    coloc_params = get_colocation_params(
        metazones,
        comparison.colocation_params_user,
        comparison.colocation_params_default
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

def _drop_time_cf_attrs_if_not_datetime(ds):
    """Remove CF time encoding attrs from the time coordinate before zarr write.

    When a dataset is opened with ``decode_times=False`` (e.g. climatologies
    with 'months since ...' units), the time coordinate carries CF attrs
    (``units``, ``calendar``) and possibly encoding inherited from the zarr
    store.  Newer xarray versions try to re-encode such variables as CF time,
    which fails with ``ValueError: failed to prevent overwriting existing key
    units in attrs``.

    For non-datetime time, rebuild the coordinate from scratch (forcing values
    to a plain numpy array) so that all CF baggage — attrs, encoding, and any
    lazy zarr references — is stripped away.

    For datetime64 time that has CF units already in ``.attrs`` (which can
    happen when xarray's ``merge`` decodes float CF time internally without
    going through the normal decode→encode cycle), strip ``units`` and
    ``calendar`` from attrs so the CF encoder can re-encode correctly.
    """
    if "time" not in ds.coords:
        return ds
    time_var = ds["time"]
    if np.issubdtype(time_var.dtype, np.datetime64):
        # CF encoder will add "units" to attrs; if they're already there the
        # write fails.  Strip them so the encoder can set them properly.
        if any(k in time_var.attrs for k in ("units", "calendar")):
            clean_attrs = {k: v for k, v in time_var.attrs.items()
                           if k not in ("units", "calendar")}
            clean_time = xr.Variable(
                "time",
                time_var.values,
                attrs=clean_attrs,
                encoding=dict(time_var.encoding),
            )
            return ds.assign_coords(time=clean_time)
        return ds
    # Rebuild from scratch: force to numpy, empty attrs, empty encoding.
    clean_time = xr.Variable("time", np.asarray(time_var.values), attrs={})
    return ds.assign_coords(time=clean_time)


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

    logger.info(f"Save {ncout_ref} and {ncout_prod}")
    if "mask" in dsref.data_vars:
        dsref = dsref.drop_vars("mask")
    dsref = _drop_time_cf_attrs_if_not_datetime(dsref)
    dsref = dsref.chunk("auto")
    encoding_ref = get_zarr_encoding(dsref)
    # For non-datetime time (e.g. WOA18 month indices), provide explicit zarr
    # encoding so xarray's CF time encoder does not attempt to re-encode it.
    if "time" in dsref.coords and not np.issubdtype(dsref["time"].dtype, np.datetime64):
        encoding_ref["time"] = {"dtype": str(dsref["time"].dtype)}
    if "time" in dsref.coords:
        logger.debug(
            "dsref time before zarr write — dtype=%s attrs=%s encoding=%s enc_ref=%s",
            dsref["time"].dtype,
            dict(dsref["time"].attrs),
            dict(dsref["time"].encoding),
            encoding_ref.get("time"),
        )
    job_ref = dsref.to_zarr(store=ncout_ref, mode="w", encoding=encoding_ref, compute=False)

    if "mask" in dsprod.data_vars:
        dsprod = dsprod.drop_vars("mask")
    dsprod = _drop_time_cf_attrs_if_not_datetime(dsprod)
    dsprod = dsprod.chunk("auto")
    encoding_prod = get_zarr_encoding(dsprod)
    if "time" in dsprod.coords and not np.issubdtype(dsprod["time"].dtype, np.datetime64):
        encoding_prod["time"] = {"dtype": str(dsprod["time"].dtype)}
    job_prod = dsprod.to_zarr(store=ncout_prod, mode="w", encoding=encoding_prod, compute=False)

    dask.compute(job_ref, job_prod)
    dsref.close()
    dsprod.close()

    return ncout_ref, ncout_prod


def _prepare_dataset(ds, comp_func, is_reference=False):
    """Prepare a dataset for colocation.

    Only loads the raw source variables that already exist in the dataset.
    Derived oceanographic variables (pdens, sndspeed, temp-from-ptemp, …)
    are computed later in ``main_output`` when the colocated data is
    re-opened — at that point the data is sparse and tiny.

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
    if "depth" in ds.data_vars:
        ds = ds.set_coords("depth")
    if "pres" in ds.data_vars:
        ds = ds.set_coords("pres")

    # Keep only raw variables already present that are needed (directly or
    # as inputs for derived variables computed later in output).
    # Map each derived variable to its required raw inputs.
    _OCEANVAR_INPUTS = {
        "ptemp": {"temp", "sal", "pres"},
        "temp":  {"ptemp", "sal", "pres"},
        "pdens": {"ptemp", "temp", "sal", "pres"},
        "sndspeed": {"ptemp", "temp", "sal", "pres"},
        "u":     {"cdir", "cspeed"},
        "v":     {"cdir", "cspeed"},
        "cdir":  {"u", "v"},
        "cspeed": {"u", "v"},
    }
    needed = set(COMP_VARS[comp_func])
    vars_to_keep = needed & set(ds.data_vars)
    # Add raw inputs required to derive any missing requested variable.
    for var in needed:
        if var not in ds.data_vars:
            for inp in _OCEANVAR_INPUTS.get(var, ()):
                if inp in ds.data_vars:
                    vars_to_keep.add(inp)
    if is_reference:
        if "mask" in ds.data_vars:
            vars_to_keep.add("mask")

    for var in list(ds.data_vars):
        if var not in vars_to_keep:
            ds = ds.drop_vars(var)

    if "depth" in ds.coords and "time" in ds.depth.dims:
        ds = ds.reset_coords("depth")
    if "pres" in ds.data_vars and "time" not in ds.pres.dims:
        ds = ds.set_coords("pres")

    ds = ds.load()
    # Ensure time coordinate is in nanosecond precision to avoid xarray warnings
    # when the zarr stores times as datetime64[s] or datetime64[ms].
    if "time" in ds.coords and ds["time"].dtype != np.dtype("datetime64[ns]"):
        ds["time"] = ds["time"].astype("datetime64[ns]")
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
    if params.get("vertical") is None:
        return dsref_list, dsprod_list

    return get_comparison(comp_func).apply_vertical_ranges(dsref_list, dsprod_list, params)


def _save_colocation_results(dssref, dssprod, comp_func, metazone, ref_name, prod_name):
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
    ref_name: str
        Reference dataset name.
    prod_name: str
        Product dataset name.

    Returns
    -------
    list
        List of output file paths.
    """
    logger.info("Save coloc data in zarr")
    paths = []

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

        paths.append(ncout_ref)
        paths.append(ncout_prod)

        dsref.close()
        dsprod.close()

    return paths


def _process_single_product(dsrefin, ncin, params, tbound, comp_func, metazone):
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

    Returns
    -------
    tuple
        (ref_name, prod_name, paths) where paths is a list of output file paths.
    """
    logger.info(f"-- Process {ncin}")

    dsprodin = xr.open_dataset(ncin, chunks={})
    if "depth" in dsprodin and "depth" not in dsprodin.coords:
        dsprodin = dsprodin.set_coords("depth")
    dsprodin = _prepare_dataset(dsprodin, comp_func, is_reference=False)
    logger.info(dsprodin.sizes)

    dsref = dsrefin.copy()
    prod_name = dsprodin.attrs['data_name']
    ref_name = dsrefin.attrs['data_name']
    gattrs_prod = dsprodin.attrs.copy()
    # Move instead of copy: avoids holding two full datasets in memory.
    dsprod = dsprodin
    del dsprodin

    gattrs_ref = dsref.attrs

    # Apply colocations
    dsref, dsprod = _apply_colocations(dsref, dsprod, params, tbound)

    # Set depth/pres as coordinate if needed
    for vcoord in ["depth", "pres"]:
        if vcoord in dsref.data_vars:
            dsref = dsref.set_coords(vcoord)
        if vcoord in dsprod.data_vars:
            dsprod = dsprod.set_coords(vcoord)
    
    dsref = dsref.assign_attrs(gattrs_ref)
    dsprod = dsprod.assign_attrs(gattrs_prod)

    # # Ensure results are numpy-backed (some colocation ops may create dask arrays).
    # # Limit threads to avoid OOM from too many concurrent allocations.
    # logger.info("Compute coloc ref and prod")
    # with dask.config.set(num_workers=4):
    #     dsref = dsref.load()
    #     dsprod = dsprod.load()

    # Apply ranges
    dssref, dssprod = _apply_time_ranges(dsref, dsprod, params, tbound)
    dssref, dssprod = _apply_vertical_ranges(dssref, dssprod, params, comp_func)

    # Save results and return paths
    paths = _save_colocation_results(
        dssref, dssprod, comp_func, metazone, ref_name, prod_name
    )
    return ref_name, prod_name, paths


def _process_reference(ncref, ncins, params, tbound, comp_func, metazone, ncouts):
    """Process all products for a single reference.

    Parameters
    ----------
    ncref: Path
        Path to reference file.
    ncins: list
        Pre-filtered list of product file paths for this metazone.
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

    _climato_names = {"woa18", "bobyclim"}
    _ds_meta = xr.open_dataset(ncref, engine="zarr", chunks={}, decode_times=False)
    _is_climato = any(n in _ds_meta.attrs.get("data_name", "") for n in _climato_names)
    _ds_meta.close()
    dsrefin = xr.open_dataset(ncref, engine="zarr", chunks={},
                               decode_times=not _is_climato)
    dsrefin = _prepare_dataset(dsrefin, comp_func, is_reference=True)

    results = []
    for ncin in ncins:
        result = _process_single_product(
            dsrefin, ncin, params, tbound, comp_func, metazone
        )
        results.append(result)
 
    # Merge results into ncouts
    for ref_name, prod_name, paths in results:
        if ref_name not in ncouts[metazone]:
            ncouts[metazone][ref_name] = {}
        if prod_name not in ncouts[metazone][ref_name]:
            ncouts[metazone][ref_name][prod_name] = []
        ncouts[metazone][ref_name][prod_name].extend(paths)

    dsrefin.close()
    gc.collect()


def _process_metazone(metazone, params, mz_files, metazones, comp_func, ncouts):
    """Process colocation for a single metazone.

    Parameters
    ----------
    metazone: str
        Metazone name.
    params: dict
        Colocation parameters for this metazone.
    mz_files: dict
        Pre-filtered file index with keys "ref" and "prod".
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

    ncrefs = mz_files["ref"]
    ncins = mz_files["prod"]

    for ncref in ncrefs:
        _process_reference(ncref, ncins, params, tbound, comp_func, metazone, ncouts)

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

    # Build file index once (avoid repeated list scans)
    ncs_index = {}
    for nc in ncs:
        nc_str = str(nc)
        for metazone in coloc_params:
            if metazone in nc_str:
                if metazone not in ncs_index:
                    ncs_index[metazone] = {"ref": [], "prod": []}
                if "ref" in nc_str:
                    ncs_index[metazone]["ref"].append(nc)
                else:
                    ncs_index[metazone]["prod"].append(nc)

    ncouts = {}
    for metazone, params in coloc_params.items():
        mz_files = ncs_index.get(metazone, {"ref": [], "prod": []})
        _process_metazone(metazone, params, mz_files, metazones, comp_func, ncouts)

    return ncouts
