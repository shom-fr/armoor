"""Interpolation functions."""

# pyproj and xoa.regrid are imported lazily (inside the functions that need
# them) to avoid the significant NFS stat overhead on HPC cluster filesystems
# when the whole armoor package is imported at startup.
import logging
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
import re
import numpy as np
import pandas as pd
import xarray as xr

from armoor.misc import geo_vars

logger = logging.getLogger(__name__)


def interp_time(
    ds,
    dates,
    method="linear",
    preserve_encoding=False,
    keep_flag=False,
    diurnal_vars=None,
    persistency=None,
):
    """Interpolate a dataset in time.

    Vectorized: all in-range dates are interpolated in a single
    ``ds.interp()`` call, then concatenated as 2-3 bulk chunks
    instead of thousands of single-timestep datasets.

    Parameters
    ----------
    ds : xarray.Dataset
        Dataset to interpolate.
    dates : single or list of dates
        Interpolation dates.

    Returns
    -------
    xarray.Dataset
    """
    # Parse and sort target dates
    dates = pd.to_datetime(dates)
    if hasattr(dates, '__len__') and len(dates) > 1:
        dates = sorted(dates)
    elif not hasattr(dates, '__len__'):
        dates = [dates]

    varstime = [var for var in ds if "time" in ds[var].dims]
    varsnotime = [var for var in ds if "time" not in ds[var].dims]

    time_name = "time"
    time = ds.indexes[time_name]
    begindate_nc = time[0]
    enddate_nc = time[-1]

    ds_first = ds.isel({time_name: slice(0, 1)})
    ds_last = ds.isel({time_name: slice(-1, None)})

    persistency_config = None
    if persistency:
        m = re.search(r"mean_(?P<term>.*)(?P<units>.)", persistency, re.DOTALL)
        if m:
            persistency_config = {
                'timedelta': pd.to_timedelta(int(m["term"]), m["units"]),
                'term': int(m["term"]),
                'units': m["units"],
            }

    # Classify dates
    dates_before = []
    dates_after = []
    dates_main = []  # exact matches + in-range → single vectorized interp

    for date in dates:
        if date < begindate_nc:
            dates_before.append(date)
        elif date > enddate_nc:
            dates_after.append(date)
        else:
            dates_main.append(date)

    # --- Build result parts (bulk multi-timestep datasets) ---
    parts = []  # [(dataset, sort_key)]

    # 1. Exact + in-range: single vectorized interpolation
    #    (scipy returns exact values at data points, no precision issue)
    if dates_main:
        sorted_main = sorted(dates_main)
        interp_ds = ds[varstime].interp({time_name: sorted_main}, method=method, assume_sorted=True)
        parts.append(interp_ds)

    # 2. Before range (persistency / extrapolation)
    if dates_before:
        base_ds = ds_first[varstime]
        if persistency_config:
            date_target = begindate_nc + persistency_config['timedelta']
            ds_pers = ds.where(ds[time_name] <= date_target).mean(dim=time_name, keepdims=True)

        before_dss = []
        for date in sorted(dates_before):
            this_ds = base_ds.copy(deep=False)
            this_ds = this_ds.assign_coords({time_name: [date]})
            if persistency_config:
                for vname in ds_pers:
                    if vname in this_ds:
                        this_ds[vname] = this_ds[vname].copy(data=ds_pers[vname].data)
            before_dss.append(this_ds)
        parts.append(xr.concat(before_dss, time_name))

    # 3. After range (persistency / extrapolation)
    if dates_after:
        base_ds = ds_last[varstime]
        if persistency_config:
            date_target = enddate_nc - persistency_config['timedelta']
            ds_pers = ds.where(ds[time_name] >= date_target).mean(dim=time_name, keepdims=True)

        after_dss = []
        for date in sorted(dates_after):
            this_ds = base_ds.copy(deep=False)
            this_ds = this_ds.assign_coords({time_name: [date]})
            if persistency_config:
                for vname in ds_pers:
                    if vname in this_ds:
                        this_ds[vname] = this_ds[vname].copy(data=ds_pers[vname].data)
            after_dss.append(this_ds)
        parts.append(xr.concat(after_dss, time_name))

    # Diurnal correction (only affects before/after dates)
    if diurnal_vars and (dates_before or dates_after):
        # Lookup from main interp result for ±24h targets
        main_ds = parts[0] if dates_main else None
        edge_parts = parts[1:]  # before and/or after chunks
        for part in edge_parts:
            for i in range(part.sizes[time_name]):
                date = pd.Timestamp(part[time_name].values[i])
                if date < begindate_nc:
                    time_target = date + pd.to_timedelta("24h")
                elif date > enddate_nc:
                    time_target = date - pd.to_timedelta("24h")
                else:
                    continue
                target_ds = None
                if main_ds is not None and time_target in main_ds[time_name].values:
                    target_ds = main_ds.sel({time_name: time_target})
                if target_ds is not None:
                    for vname in diurnal_vars:
                        if vname in part and vname in target_ds:
                            part[vname].values[i] = target_ds[vname].values

    # Concat 2-3 bulk parts (not N single-timestep datasets)
    if len(parts) == 1:
        dso = parts[0]
    else:
        dso = xr.concat(
            parts,
            time_name,
            compat="no_conflicts",
            coords="minimal",
            data_vars="all",
        ).sortby(time_name)

    # Add non-time variables
    for var in varsnotime:
        dso[var] = ds[var]

    # Preserve attrs and encoding
    dso[time_name].attrs.update(ds[time_name].attrs)
    dso[time_name].encoding.update(ds[time_name].encoding)

    if preserve_encoding:
        for vname, var in ds.items():
            if vname in dso:
                dso[vname].encoding.update(var.encoding)

    dso = dso.transpose(time_name, ...)

    return dso


def _crop_to_bbox(ds, coords, margin_deg=1.0):
    """Crop a gridded dataset to the (lat, lon) bounding box of `coords`.

    Parameters
    ----------
    ds: xr.Dataset
        Gridded dataset with ``lat``/``lon`` coordinates.
    coords: list of (float, float)
        (lat, lon) points the crop must contain.
    margin_deg: float
        Degrees of padding added around the points' bounding box.

    Returns
    -------
    xr.Dataset
        `ds` restricted to the grid rows/columns overlapping the padded
        bounding box (unchanged if nothing overlaps).
    """
    lats = np.array([c[0] for c in coords])
    lons = np.array([c[1] for c in coords])
    mask = (
        (ds.lat >= lats.min() - margin_deg)
        & (ds.lat <= lats.max() + margin_deg)
        & (ds.lon >= lons.min() - margin_deg)
        & (ds.lon <= lons.max() + margin_deg)
    )
    if not bool(mask.any()):
        return ds

    slices = {}
    for dim in mask.dims:
        other_dims = [d for d in mask.dims if d != dim]
        touched = mask.any(dim=other_dims).values if other_dims else mask.values
        idx = np.flatnonzero(touched)
        slices[dim] = slice(max(idx[0] - 1, 0), idx[-1] + 2)
    return ds.isel(**slices)


def _grid2loc_var(var, ds, dsi, loc):
    """Interpolate one variable at `loc`'s scattered points.

    Split out from grid2loc() so each variable's (materialize + interpolate)
    work -- the actual cost of grid2loc(), see xoa.interp.grid2loc's
    ``da_tmp.values`` -- can run concurrently across variables instead of
    blocking one after another (that serial loop was leaving allocated
    CPUs idle: dask's own scheduler only parallelizes within one
    variable's chunks, and xoa's interpolation core runs single-threaded
    on already-materialized numpy).
    """
    import xoa.regrid as xregrid

    da = ds[var]
    if ("time" in da.dims) and ("z" in da.dims):
        da = xregrid.grid2loc(da, loc)
        dims = ["time", "z", "npts"]
        da = da.transpose(*dims)
        arr = da.data
        del da
        coords = dict(time=dsi.time, **loc.coords)
    elif ("time" in da.dims) and ("z" not in da.dims):
        da = xregrid.grid2loc(da, loc)
        dims = ["time", "npts"]
        da = da.transpose(*dims)
        arr = da.data
        del da
        coords = dict(time=dsi.time, **loc.coords)
    else:
        arr = xregrid.grid2loc(dsi[var], loc)
        dims = ["npts"]
        coords = dict(**loc.coords)
        if isinstance(arr, xr.DataArray):
            arr = arr.data
    dsvar = xr.Dataset(data_vars={var: (dims, arr)}, coords=coords)
    dsvar[var] = dsvar[var].assign_attrs(**dsi[var].attrs)
    return dsvar


def grid2loc(ds, coords: [(float, float)]):
    """Interpolate a dataset at specific coordinates.

    Parameters
    ----------
    ds: xr.Dataset
        Gridded dataset to interpolate at specific coordinates.
    coordinates : list of tuples
        Set of points coordinates (lon, lat) defining the coordinates to select.

    Returns
    -------
    xarray.Dataset, xarray.Dataset
        Dataset with elements located at specific coordinates.
    """
    import dask

    lat, lon = zip(*coords)
    loc = xr.Dataset(
        coords={
            "lon": (
                "npts",
                list(lon),
                {"axis": "X", "standard_name": "longitude", "units": "degrees_east"},
            ),
            "lat": (
                "npts",
                list(lat),
                {"axis": "Y", "standard_name": "latitude", "units": "degrees_north"},
            ),
        }
    )
    dsi = ds.copy()
    if "time" in ds:
        dso = xr.Dataset(coords=dict(time=dsi.time, **loc.coords))
    else:
        dso = xr.Dataset(coords=loc.coords)
    if "depth" in dsi.coords:
        if "time" in dsi.depth.dims:
            dsi = dsi.reset_coords("depth")
    vars_grid2loc = [var for var in dsi.data_vars if set(dsi.lon.dims).issubset(dsi[var].dims)]
    # One thread per variable, capped at the --dask-nworkers the caller
    # already configured (armoor.cli.io.configure_dask_scheduler) -- reuses
    # the existing knob instead of adding a new one. Threads, not
    # processes: each variable's work is dominated by dask chunk
    # computation and numpy/compiled interpolation, both of which release
    # the GIL, and threads avoid having to pickle `ds`/`dsi` across
    # processes.
    n_workers = max(dask.config.get('num_workers', default=1), 1)
    logger.debug(f"grid2loc: {len(vars_grid2loc)} variable(s), n_workers={n_workers}")
    with ThreadPoolExecutor(max_workers=n_workers) as pool:
        dss = list(pool.map(lambda var: _grid2loc_var(var, ds, dsi, loc), vars_grid2loc))
    dso = xr.merge(dss)
    if "depth" in dso:
        dso = dso.set_coords("depth")
    elif ("depth" in dsi.coords) and ("time" not in dsi["depth"].dims):
        dso["depth"] = dsi.depth
        dso = dso.set_coords("depth")
    return dso


def grid2track(ds, ds_ref):
    """Interpolate a gridded dataset onto another dataset's own moving track.

    Unlike `grid2loc` (which selects a fixed cloud of points and, when `ds`
    has a "time" dim, cross-products it against every one of those points),
    this pairs each `ds_ref` observation with its own (time, lon, lat) --
    e.g. one point per glider profile along a mission track -- so the
    output keeps a single "time" dim of the same length as `ds_ref.time`,
    not a "time" x "npts" grid.

    The pairing relies on `xoa.regrid.grid2loc` detecting a "time"
    coordinate on `loc` that shares `ds`'s own "time" dim name: it then
    interpolates in space *and* time together, point by point, instead of
    broadcasting space across every time step.

    Parameters
    ----------
    ds: xr.Dataset
        Gridded dataset to interpolate (must have a "time" dim already
        aligned in length/order with `ds_ref.time`, e.g. via `interp_time`).
    ds_ref: xr.Dataset
        Dataset whose own "time"-indexed lon/lat defines the track.

    Returns
    -------
    xarray.Dataset
        `ds` interpolated at each of `ds_ref`'s (time, lon, lat) points,
        indexed by "time" (and "z" when present).
    """
    import xoa.regrid as xregrid

    loc = xr.Dataset(
        coords={
            "lon": (
                "time",
                np.atleast_1d(ds_ref.lon.values),
                {"axis": "X", "standard_name": "longitude", "units": "degrees_east"},
            ),
            "lat": (
                "time",
                np.atleast_1d(ds_ref.lat.values),
                {"axis": "Y", "standard_name": "latitude", "units": "degrees_north"},
            ),
            "time": ("time", np.atleast_1d(ds_ref.time.values)),
        }
    )
    dsi = ds.copy()
    if "depth" in dsi.coords and "time" in dsi.depth.dims:
        dsi = dsi.reset_coords("depth")
    dss = []
    vars_grid2track = [var for var in dsi.data_vars if set(dsi.lon.dims).issubset(dsi[var].dims)]
    for var in vars_grid2track:
        da = xregrid.grid2loc(ds[var], loc)
        if "z" in da.dims:
            da = da.transpose("time", "z")
        else:
            da = da.transpose("time")
        dsvar = xr.Dataset(data_vars={var: (da.dims, da.data)}, coords=loc.coords)
        dsvar[var] = dsvar[var].assign_attrs(**dsi[var].attrs)
        dss.append(dsvar)
    dso = xr.merge(dss)
    if "depth" in dsi.coords and "time" not in dsi["depth"].dims:
        dso["depth"] = dsi.depth
        dso = dso.set_coords("depth")
    return dso


def grid2section(ds, coords: [(float, float), (float, float)], dx: float):
    """Interpolate a dataset on section.

    Parameters
    ----------
    ds: xr.Dataset
        Gridded dataset to interpolate at specific coordinates.
    coordinates : list
        Set of two coordinates (lat, lon) defining the bound coordinates of the section.
    dx: float
        Horizontal step.

    Returns
    -------
    xarray.Dataset, xarray.Dataset
        Dataset interpolated over a section.
    """
    from pyproj import Geod

    dx = dx * 1e3  # Convert to meters
    geod = Geod(ellps='WGS84')

    # Collect all interpolated points and distances for each segment
    all_lats = []
    all_lons = []
    all_distances = []
    cumulative_dist = 0.0

    # Process each segment between consecutive points
    for i in range(len(coords) - 1):
        lat0, lon0 = coords[i]
        lat1, lon1 = coords[i + 1]

        # Calculate segment properties
        d = geod.inv(lon0, lat0, lon1, lat1, return_back_azimuth=True)
        segment_length = d[-1]  # Total distance of segment

        # Get intermediate points for this segment
        r = geod.inv_intermediate(
            lon0, lat0, lon1, lat1, int(segment_length / dx), return_back_azimuth=True
        )

        # Add points from this segment
        for npt in range(r.npts):
            all_lats.append(r.lats[npt])
            all_lons.append(r.lons[npt])
            all_distances.append(cumulative_dist + npt * r.del_s)

        # Update cumulative distance for next segment
        cumulative_dist += segment_length

    # Add the final point
    all_lats.append(coords[-1][0])
    all_lons.append(coords[-1][1])
    all_distances.append(cumulative_dist)

    dist = xr.Dataset(
        coords=dict(
            distance=(["npts"], all_distances),
        )
    )
    # ds = grid2loc(ds, list(zip(r.lats, r.lons)))
    section_points = list(zip(all_lats, all_lons))
    ds = _crop_to_bbox(ds, section_points)
    ds = grid2loc(ds, section_points)
    ds = xr.merge([ds, dist])
    return ds


@contextmanager
def create_regridder(dsi, dso, method="bilinear"):
    """Context manager for safe regridder creation and cleanup."""
    import xesmf as xe

    regridder = None
    try:
        regridder = xe.Regridder(
            dsi,
            dso,
            method,
            parallel=False,
            ignore_degenerate=True,
            unmapped_to_nan=True,
        )
        yield regridder
    finally:
        if regridder is not None:
            del regridder
        import gc

        gc.collect()


def regrid(dsi, dso) -> xr.Dataset:
    """Regrid the variables on the x and y dimensions.

    The coordinates on the x and y dimensions other than lon and lat (depth
    of the sigma levels...) are regridded too.
    """
    coords = [
        name
        for name in dsi.coords
        if name not in ("lon", "lat") and {"x", "y"} <= set(dsi[name].dims)
    ]
    dsi = dsi.reset_coords(coords)
    vars2sub = geo_vars(dsi)

    with create_regridder(dsi, dso) as regridder:
        dsi_subset = dsi[vars2sub]
        dsio = regridder(dsi_subset, keep_attrs=True)

    return dsio.set_coords(coords)


def coarsen(
    dsi: xr.Dataset, factor: int, boundary: str = "trim", method: str = "mean"
) -> xr.Dataset:
    """Coarsen a gridded dataset by aggregating over spatial blocks.

    Each ``(factor × factor)`` block of cells is reduced to a single cell
    using the chosen aggregation method.  Spatial coordinates (``lon``,
    ``lat``) that share the ``x``/``y`` dimensions are coarsened in the
    same way.  Non-spatial dimensions (``time``, ``z``, …) are left intact.

    .. note::
        This function relies on :meth:`xarray.Dataset.coarsen`, which only
        supports **structured regular grids** (i.e. datasets with explicit
        ``x`` and ``y`` index dimensions).  Curvilinear or unstructured grids
        are not supported; use :func:`regrid` with an explicit target grid
        for those cases.

    Parameters
    ----------
    dsi : xr.Dataset
        Gridded dataset with ``x`` and ``y`` dimensions.
    factor : int
        Coarsening factor applied to both ``x`` and ``y``.  A factor of 4
        reduces a 1/12° grid to roughly 1/3°.
    boundary : str
        How to handle dimension sizes that are not divisible by *factor*:

        * ``"trim"`` (default) — drop the remainder.
        * ``"pad"`` — zero-pad to the next multiple.
    method : str
        Block aggregation method: ``"mean"`` (default), ``"median"``,
        ``"min"``, or ``"max"``.

    Returns
    -------
    xr.Dataset
        Dataset with ``x`` and ``y`` sizes divided by *factor* (rounded
        according to *boundary*).

    Raises
    ------
    ValueError
        If *dsi* has neither an ``x`` nor a ``y`` dimension.

    See Also
    --------
    regrid : bilinear regridding via xesmf (handles curvilinear grids).
    """
    spatial_dims = {dim: factor for dim in ("x", "y") if dim in dsi.dims}
    if not spatial_dims:
        raise ValueError("Dataset has no 'x' or 'y' dimensions to coarsen.")
    coarsener = dsi.coarsen(**spatial_dims, boundary=boundary)
    return getattr(coarsener, method)()


#: Mutually-exclusive vertical-coordinate candidates. Only one of these may
#: be an active coordinate at a time so that `xoa.regrid.regrid1d`'s
#: `coord_in_name` unambiguously resolves to a single vertical axis --
#: "dens" (in-situ density) and "pdens" (potential density, used for
#: isopycnal interpolation) are as mutually exclusive with "depth" as they
#: are with each other.
_VERTICAL_COORD_CANDIDATES = ("depth", "dens", "pdens")


def vinterp(ds, vname, vlevels, method="linear", extrap="both"):  # noqa: E501
    """Interpolate an xarray Dataset over specified vertical levels.

    Parameters
    ----------
    ds: xr.Dataset
        The input xarray Dataset containing variables to interpolate.
    vname: str
        The name of the vertical coordinate (e.g., "depth", "dens" for
        in-situ density, or "pdens" for potential density -- isopycnal
        interpolation).
    vlevels: list
        List of vertical levels to interpolate to.
    method: str (optional)
        The interpolation method to use. Default is "linear".
    extrap: str (optional)
        Extrapolation mode of :func:`xoa.regrid.regrid1d`, relative to the
        values of the vertical coordinate: ``"both"`` (default), ``"no"``,
        ``"bottom"`` (toward the smaller values: with a positive depth, toward
        the surface, without values below the deepest level) or ``"top"``.

    Returns
    -------
    xr.Dataset
        A new Dataset with variables interpolated to the specified vertical levels.
    """
    for candidate in _VERTICAL_COORD_CANDIDATES:
        if candidate != vname and candidate in ds.coords:
            ds = ds.reset_coords(candidate)
    if vname not in ds.coords:
        ds = ds.set_coords(vname)
    import numba
    import xoa.regrid as xregrid  # noqa: F811

    # regrid1d's underlying numba kernels are themselves parallel
    # (numba.njit(parallel=True)); when this runs as a dask task, dask
    # already parallelizes across chunks/variables, so letting numba also
    # spawn its own thread pool per task causes thread oversubscription
    # (dask threads x numba threads) -- cap numba to 1 thread per task and
    # let dask own the parallelism instead.
    numba.set_num_threads(1)
    das = []
    for var in ds.data_vars:
        if "z" in ds[var].dims:
            da = xregrid.regrid1d(
                ds[var],  # .chunk(dict(z=-1)),
                vlevels,
                method=method,
                extrap=extrap,
                dim="z",
                coord_in_name=vname,
            )
        else:
            da = ds[var]
        das.append(da)
    dsout = xr.merge(das, combine_attrs='drop_conflicts')
    if len(dsout.dims) == 1:
        dsout = dsout.set_xindex(vname)
    return dsout
