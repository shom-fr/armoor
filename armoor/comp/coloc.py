import gc
import logging
from pathlib import Path
from typing import Tuple

import dask
import numpy as np
import pandas as pd
import xarray as xr
import xoa.coords as xcoords
import xoa.geo as xgeo

import armoor.ranges as ranges
from armoor.__init__ import ArmoorError
from armoor.dispatch import SubclassingMethodRegistry
from armoor.interp import coarsen as _coarsen, grid2loc, grid2track, interp_time, regrid, vinterp
from armoor.io import get_zarr_encoding
from armoor.comp import COMP_VARS
from armoor.comp.comparison import get_comparison
from armoor.comp.misc import get_colocation_params, validate_colocation
from armoor.data.datatype import get_data_type_by_name
from armoor.data.load import StagedDataset

logger = logging.getLogger(__name__)


class AbstractColocation(SubclassingMethodRegistry):
    """Abstract base for colocation strategies (time/horizontal/vertical).

    Subclasses register their own methods for dispatch via `call`; see
    `armoor.dispatch.SubclassingMethodRegistry`.
    """

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
            self.dsprod.sel(time=slice(self.start, self.end))
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
        ds_ref_monthly = ds_ref_monthly.assign_coords(time=("time", common_months.astype(int), {}))
        return ds_ref_monthly, ds_prod_monthly

    def trange_seq(self, args: dict) -> xr.Dataset:
        """
        Colocate reference and product on the same time axis before ranging.

        Parameters
        ----------
        args: dict
            Dict with a ``tref`` key (the reference time axis, "reference" or
            "product") and an optional ``method`` key (interpolation method,
            defaults to "linear").

        Returns
        -------
        xarray.Dataset, xarray.Dataset
        """
        ref = args["tref"]
        method = args.get("method") or "linear"
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
                "Use 'reference' or 'product' to specify the reference timefor ranging then."
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

    def track(self) -> Tuple[xr.Dataset, xr.Dataset]:
        """Interpolate the product onto the reference's own moving track.

        Unlike `cloud` (a fixed list of points), this pairs each product
        interpolation with the reference's own (time, lon, lat) -- e.g. one
        point per profile along a glider mission -- so the product keeps a
        single "time" dim matching the reference's, instead of a
        "time" x "npts" cross product. Relies on `dsprod`'s "time" already
        being aligned (same values/order) with `dsref`'s, which the time
        colocation step (run first, see `_apply_colocations`) guarantees.

        Returns
        -------
        tuple[xarray.Dataset, xarray.Dataset]
            The reference dataset (unchanged) and the product dataset
            interpolated onto its track.
        """
        return self.dsref, grid2track(self.dsprod, self.dsref)

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
            self.dsref = self.dsref.drop_vars("mask")
        return self.dsref, self.dsprod

    def coarsen(
        self, factor: int, on: str = "product", boundary: str = "trim", method: str = "mean"
    ) -> Tuple[xr.Dataset, xr.Dataset]:
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

    def _calculate_distances_vectorized(
        self, prod_data: xr.Dataset, ref_data: xr.Dataset
    ) -> xr.DataArray:
        """
        Calculate distances using vectorized operations for all timesteps at once.
        """
        rename_dims = {"npts0": "member"}
        if "time" in ref_data.lon.dims:
            rename_dims["npts1"] = "time"
        dist = (
            xgeo.get_distances(prod_data, ref_data)
            # .squeeze()
            .rename(rename_dims)
            .assign_coords(member=prod_data.member)
        )
        if "npts1" in dist.dims:
            # A time-independent reference (e.g. a single fixed mooring) has
            # exactly one point here -- squeeze it out, otherwise it leaks
            # as a spurious size-1 dim into dsprod via the caller's
            # `.where(dist < radius)`, breaking the dims-signature match in
            # `select_vars_by_dims` and silently dropping the whole group.
            dist = dist.squeeze("npts1", drop=True)
        return dist

    def _handle_time_dependent(self, radius_meters: float) -> None:
        """Process every timestep at once instead of looping over them."""
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
            logger.info(f"Compacted members: {n_before} -> {self.dsprod.sizes['member']}")

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
        Radius-based colocation: keep every product point within `radius`
        of the reference.

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
            # Time-independent case
            dist_prod2ref = self._calculate_distances_vectorized(self.dsprod, self.dsref)
            filtered_ds = self.dsprod.where(dist_prod2ref < radius_meters)
            self.dsprod = self._clean_coordinates(filtered_ds)
        else:
            logger.info("time dependent")
            self._handle_time_dependent(radius_meters)
        # Set depth coordinate if needed (unchanged)
        # if "depth" not in self.dsprod.coords and "depth" in self.dsprod.data_vars:
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

    def vlevel(self, args: dict):
        """Interpolate datasets to specified vertical levels.

        Parameters
        ----------
        args: dict
            Dict with a ``vname`` key (the vertical coordinate name) and a
            ``levels`` key (the list of vertical levels to interpolate to).

        Returns
        -------
        xarray.Dataset, xarray.Dataset
            A tuple containing the verticaly interpolated reference dataset and product dataset.
        """
        vname = args["vname"]
        vlevels = args["levels"]
        vlevels = xr.DataArray(vlevels, dims="z", name=vname)
        prod_attrs = self.dsprod.attrs
        ref_attrs = self.dsref.attrs
        ref_has_z = "z" in self.dsref.dims
        prod_has_z = "z" in self.dsprod.dims
        if ref_has_z:
            self.dsref = vinterp(self.dsref, vname, vlevels)
        else:
            logger.warning("No 'z' dim in reference")
        if prod_has_z:
            self.dsprod = vinterp(self.dsprod, vname, vlevels)
        else:
            self.logger.warning("no 'z' dim in product")
        # A single selected level with "z" on only one side (e.g. a
        # full-depth model compared to a surface-only satellite reference)
        # otherwise leaves a singleton "z" dim there alone, which breaks
        # select_vars_by_dims's signature match against the other side.
        if len(vlevels) == 1:
            if prod_has_z and not ref_has_z and "z" in self.dsprod.dims:
                self.dsprod = self.dsprod.squeeze("z", drop=True)
            if ref_has_z and not prod_has_z and "z" in self.dsref.dims:
                self.dsref = self.dsref.squeeze("z", drop=True)
        self.dsref.attrs.update(ref_attrs)
        self.dsprod.attrs.update(prod_attrs)
        return self.dsref, self.dsprod

    def vrange(self, args: dict) -> xr.Dataset:
        """
        Colocate reference and product on the same vertical axis before ranging.

        Parameters
        ----------
        args: dict
            Dict with a ``vref`` key (the vertical reference, "reference" or
            "product") and a ``vname`` key (the vertical coordinate name).
            The bin bounds (``bins_min``/``bins_max``) aren't used here — they
            only matter for the later output-side range splitting.

        Returns
        -------
        xarray.Dataset, xarray.Dataset
        """
        vref = args["vref"]
        vcoord = args["vname"]
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
                "Use 'reference' or 'product' to specify the vertical reference for ranging then."
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
        metazones, comparison.colocation_params_user, comparison.colocation_params_default
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
            clean_attrs = {
                k: v for k, v in time_var.attrs.items() if k not in ("units", "calendar")
            }
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


def save_datasets(dsref, dsprod, dirout, staged=None):
    """Save datasets to NetCDF files.

    Parameters
    ----------
    dsref: xr.Dataset
        Reference dataset to save.
    dsprod: xr.Dataset
        Product dataset to save.
    dirout: Path
        Directory to save the datasets.
    staged: StagedDataset, optional
        Pipeline context (metazone/comp_func) to carry onto the returned
        paths. When None, plain Path objects are returned (metazone/
        comp_func-less, e.g. for callers outside the comp_func pipeline).

    Returns
    -------
    tuple
        Paths to the saved reference and product NetCDF files, as
        StagedDataset instances carrying `staged`'s metazone/comp_func
        (or plain Path if `staged` is None).
    """
    ncname = dsref.range.suffix
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

    if staged is None:
        result = ncout_ref, ncout_prod
    else:
        result = (
            staged.with_range(dsref, path=str(ncout_ref), stage="coloc"),
            staged.with_range(dsprod, path=str(ncout_prod), stage="coloc"),
        )

    dsref.close()
    dsprod.close()
    return result


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
        "temp": {"ptemp", "sal", "pres"},
        "sal": {"conduct", "temp", "pres"},
        "pdens": {"ptemp", "temp", "sal", "pres"},
        "sndspeed": {"ptemp", "temp", "sal", "pres"},
        "u": {"cdir", "cspeed"},
        "v": {"cdir", "cspeed"},
        "cdir": {"u", "v"},
        "cspeed": {"u", "v"},
        "mld": {"ptemp", "temp", "sal", "pres"},
        "sla": {"sla", "ssh"},
        "eke": {"sla"},
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
    # when the zarr stores times as datetime64[s] or datetime64[ms]. Only
    # applies to datasets whose time is already a real datetime -- for
    # climatologies opened with decode_times=False (e.g. WOA18's raw month
    # index 1-12), "time" isn't a datetime at all, and astype("datetime64[ns]")
    # would silently reinterpret the month index as a bogus timestamp.
    if (
        "time" in ds.coords
        and np.issubdtype(ds["time"].dtype, np.datetime64)
        and ds["time"].dtype != np.dtype("datetime64[ns]")
    ):
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
        dsref, dsprod = process_time_colocation(dsref, dsprod, params["time"], tbound)
        gc.collect()

    if params.get("horizontal"):
        dsref, dsprod = process_horizontal_colocation(dsref, dsprod, params["horizontal"])
        gc.collect()

    if params.get("vertical"):
        dsref, dsprod = process_vertical_colocation(dsref, dsprod, params["vertical"])
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
        tfreq = time_coloc[1]["tfreq"]
        if tfreq != "*":
            return (
                ranges.trange_seq(dsref, *tbound, tfreq),
                ranges.trange_seq(dsprod, *tbound, tfreq),
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


def _split_by_dims(ds):
    """Split a dataset into sub-datasets grouped by variable dimension signature."""
    groups = {}
    for var in ds.data_vars:
        key = frozenset(ds[var].dims)
        if key not in groups:
            groups[key] = []
        groups[key].append(var)
    return {key: ds[vars_list] for key, vars_list in groups.items()}


def select_vars_by_dims(prod_groups, sig):
    """Extract all the variables from a dataset
    depending at least on dimensions in sig.

    Returns None, like a plain dict .get(), when no product group matches
    -- callers already skip that ref group in that case (e.g. a comp_func
    whose product simply has no counterpart for this signature).
    """
    sig = set(sig)

    for group, ds in prod_groups.items():
        group = set(group)

        if sig == group.intersection(sig) and len(sig) == len(group) - ("member" in group):
            return ds

    return None


def _save_colocation_results(dssref, dssprod, staged):
    """Save colocation results to files.

    Parameters
    ----------
    dssref: list
        List of reference datasets.
    dssprod: list
        List of product datasets.
    staged: StagedDataset
        Pipeline context (comp_func/metazone) for this colocation run.

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

        dirout = staged.output_dir(
            "coloc",
            ref_name=dsref.attrs['data_name'],
            prod_name=dsprod.attrs['data_name'],
        )
        dirout.mkdir(parents=True, exist_ok=True)

        ncout_ref, ncout_prod = save_datasets(dsref, dsprod, dirout, staged=staged)

        paths.append(ncout_ref)
        paths.append(ncout_prod)

        dsref.close()
        dsprod.close()

    return paths


def _process_single_product(dsrefin, ncin, params, tbound, staged, mparams=None):
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
    staged: StagedDataset
        Pipeline context (comp_func/metazone) for this colocation run.
    mparams: dict, optional
        Full metazone parameter dict (e.g. carrying a CLI-supplied
        ``cgeo_ref``), forwarded to `Comparison.compute_oceanvars`.

    Returns
    -------
    tuple
        (ref_name, prod_name, paths) where paths is a list of output file paths.
    """
    comp_func = staged.comp_func
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

    comparison = get_comparison(comp_func)
    dsref = comparison.compute_oceanvars(dsref, mparams)
    dsprod = comparison.compute_oceanvars(dsprod, mparams)

    # Set depth/pres as coordinate if needed
    for vcoord in ["depth", "pres"]:
        if vcoord in dsref.data_vars:
            dsref = dsref.set_coords(vcoord)
        if vcoord in dsprod.data_vars:
            dsprod = dsprod.set_coords(vcoord)

    if comp_func == "comp_drifter" and not params.get("horizontal"):
        # No horizontal colocation step is configured for this comp func
        # (comp_drifter: spatial matching happens later, via OceanParcels in
        # preproc_comp_drifter). The product legitimately keeps its full
        # (y, x) grid here, so a dims-signature match against the point-like
        # reference would always fail -- skip the split/match and range the
        # whole pair directly instead.
        dssref, dssprod = [dsref], [dsprod]
        if "time" in dsref.dims:
            dssref, dssprod = _apply_time_ranges(dsref, dsprod, params, tbound)
        if "z" in dsref.dims:
            dssref, dssprod = _apply_vertical_ranges(dssref, dssprod, params, comp_func)
    else:
        # Split by dimension signature, then apply ranges per group conditionally
        ref_groups = _split_by_dims(dsref)
        prod_groups = _split_by_dims(dsprod)

        dssref = []
        dssprod = []
        for sig, sub_ref in ref_groups.items():
            sub_prod = select_vars_by_dims(prod_groups, sig)

            if sub_ref is None or sub_prod is None:
                continue

            if "time" in sub_ref.dims:
                sub_ref_list, sub_prod_list = _apply_time_ranges(sub_ref, sub_prod, params, tbound)
            else:
                sub_ref_list, sub_prod_list = [sub_ref], [sub_prod]

            if "z" in sub_ref.dims:
                sub_ref_list, sub_prod_list = _apply_vertical_ranges(
                    sub_ref_list, sub_prod_list, params, comp_func
                )

            dssref.extend(sub_ref_list)
            dssprod.extend(sub_prod_list)

    # Save results and return paths
    paths = _save_colocation_results(dssref, dssprod, staged)
    return ref_name, prod_name, paths


def _process_reference(ncref, ncins, params, tbound, staged, ncouts, mparams=None):
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
    staged: StagedDataset
        Pipeline context (comp_func/metazone) for this colocation run.
    ncouts: dict
        Dictionary to store output paths.
    mparams: dict, optional
        Full metazone parameter dict, forwarded to `_process_single_product`.
    """
    metazone = staged.metazone
    logger.info(f"Use reference {ncref}")

    _ds_meta = xr.open_dataset(ncref, engine="zarr", chunks={}, decode_times=False)
    _is_climato = get_data_type_by_name(_ds_meta.attrs.get("data_type")).is_climatology
    _ds_meta.close()
    dsrefin = xr.open_dataset(ncref, engine="zarr", chunks={}, decode_times=not _is_climato)
    dsrefin = _prepare_dataset(dsrefin, staged.comp_func, is_reference=True)

    results = []
    for ncin in ncins:
        result = _process_single_product(dsrefin, ncin, params, tbound, staged, mparams=mparams)
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


def _process_metazone(staged, params, mz_files, metazones, ncouts):
    """Process colocation for a single metazone.

    Parameters
    ----------
    staged: StagedDataset
        Pipeline context (comp_func/metazone) for this colocation run.
    params: dict
        Colocation parameters for this metazone.
    mz_files: dict
        Pre-filtered file index with keys "ref" and "prod".
    metazones: dict
        Dictionary containing all metazone information.
    ncouts: dict
        Dictionary to store output paths.
    """
    metazone = staged.metazone
    logger.info(f"Start colocation for {metazone}.")
    logger.info(f"Colocation parameters are: {params}")

    tbound = metazones[metazone].get("tbound")
    mparams = metazones[metazone]
    ncouts[metazone] = {}

    ncrefs = mz_files["ref"]
    ncins = mz_files["prod"]

    for ncref in ncrefs:
        _process_reference(ncref, ncins, params, tbound, staged, ncouts, mparams=mparams)

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
        # Match the "ref_<name>.zarr"/"prod_<name>.zarr" filename convention
        # itself, not a substring check anywhere in the path -- a metazone
        # name containing "ref" (e.g. "modelzone_href") would otherwise
        # match every file under it, misclassifying every product as a
        # second reference.
        basename = Path(nc_str).name
        for metazone in coloc_params:
            if metazone in nc_str:
                if metazone not in ncs_index:
                    ncs_index[metazone] = {"ref": [], "prod": []}
                if basename.startswith("ref_"):
                    ncs_index[metazone]["ref"].append(nc)
                else:
                    ncs_index[metazone]["prod"].append(nc)

    ncouts = {}
    for metazone, params in coloc_params.items():
        mz_files = ncs_index.get(metazone, {"ref": [], "prod": []})
        staged = StagedDataset("", metazone=metazone, comp_func=comp_func, stage="coloc")
        _process_metazone(staged, params, mz_files, metazones, ncouts)

    return ncouts
