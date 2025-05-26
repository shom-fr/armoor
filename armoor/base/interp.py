"""Interpolation functions."""
import re
import numpy as np
import pandas as pd
import xarray as xr
import xesmf as xe
import xoa.regrid as xregrid

from armoor.base.misc import geo_vars


def interp_time(
    ds,
    dates,
    preserve_encoding=False,
    keep_flag=False,
    diurnal_vars=None,
    persistency=None,
    ):
    """Interpolate a dataset in time.

    A single interpolation per time step, with persistency.

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
    
    varstime = [var for var in ds if "time" in ds[var].dims]
    varsnotime = [var for var in ds if "time" not in ds[var].dims]
    # Time dim
    time_name = "time"
    time = ds.indexes[time_name]
    begindate_nc = time[0]
    enddate_nc = time[-1]
    dates = pd.to_datetime(dates)

    # For persistency
    ds_first = ds.isel({time_name: slice(0, 1)})
    ds_last = ds.isel({time_name: slice(-1, None)})

    # Loop on target times
    dss = []
    for date in dates:
        # Persistency
        if date < begindate_nc or date > enddate_nc:
            # New dataset
            this_ds = ds_first if date < begindate_nc else ds_last

            # New time
            this_ds = this_ds.assign_coords({time_name: [date]})
            this_ds[time_name].attrs.update(ds[time_name].attrs)

            if persistency:
                m = re.search(
                    r"mean_(?P<term>.*)(?P<units>.)", persistency, re.DOTALL
                )
                if m:
                    ds_tr = ds.copy()
                    timedelta = pd.to_timedelta(int(m["term"]), m["units"])
                    if date > enddate_nc:
                        date_target = enddate_nc - timedelta
                        ds_tr = ds_tr.where(
                            ds_tr[time_name] >= date_target
                        ).mean(dim=time_name, keepdims=True)
                    elif date < begindate_nc:
                        date_target = begindate_nc + timedelta
                        ds_tr = ds_tr.where(
                            ds_tr[time_name] <= date_target
                        ).mean(dim=time_name, keepdims=True)
                    for vname in ds_tr:
                        this_ds[vname] = this_ds[vname].copy(
                            data=ds_tr[vname].data
                        )
            if diurnal_vars:
                if date < begindate_nc:
                    time_target = date + pd.to_timedelta("24h")
                elif date > enddate_nc:
                    time_target = date - pd.to_timedelta("24h")
                for dss_target in dss:
                    if dss_target[time_name].values[0] == time_target:
                        for vname in this_ds:
                            if vname in diurnal_vars:
                                this_ds[vname] = this_ds[vname].copy(
                                    data=dss_target[vname].data
                                )
        # Interpolation
        else:

            # Pick this date directly if available
            if date in time:
                this_ds = ds.sel({time_name: [date]})
            # Interpolate because not available
            else:
                # Load a two-time steps dataset
                it = ds.indexes[time_name].get_indexer([date], method="ffill")[
                    0
                ]
                tmp_ds = ds.isel({time_name: slice(it, it + 2)}).chunk(
                    {time_name: (2,)}
                )
                # Interpolate
                this_ds = tmp_ds.interp({time_name: [date]}).load()
                # Preserve netcdf compression
                if preserve_encoding:
                    for vname, var in tmp_ds.items():
                        this_ds[vname].encoding.update(var.encoding)

            # New time
            this_ds = this_ds.assign_coords({time_name: [date]})
            this_ds[time_name].attrs.update(ds[time_name].attrs)

        # Append to list
        dss.append(this_ds)
        del this_ds
    # Concatenate
    dso = xr.concat(
        [ds[varstime] for ds in dss],
        time_name,
        compat="no_conflicts",
        coords="different",
        data_vars="all",
        )
    for var in varsnotime:
        dso[var] = ds[var]
    # Attributes and encoding
    dso[time_name].attrs.update(ds[time_name].attrs)
    dso[time_name].encoding.update(ds[time_name].encoding)
    if preserve_encoding:
        for vname, var in ds.items():
            dso[vname].encoding.update(var.encoding)
    dso = dso.transpose(time_name, ...)

    return dso

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
    lat, lon = zip(*coords)
    loc = xr.Dataset(
        coords={
            "lon": ("npts", list(lon)),
            "lat": ("npts", list(lat)),
            }
        )
    dsi = ds.copy()
    dso = xr.Dataset(coords=dict(time=dsi.time, **loc.coords))
    if "depth" in dsi.coords:
        if "time" in dsi.depth.dims:
            dsi = dsi.reset_coords("depth")
    dss = []
    for var in dsi.data_vars:
        if ("time" in dsi[var].dims) and ("z" in dsi[var].dims):
            arr = np.nan * np.zeros(
                (dsi.sizes["time"], dsi.sizes["z"], len(lon))
                )
            for itime in range(dsi.sizes["time"]):
                for iz in range(dsi.sizes["z"]):
                    arr[itime, iz, :] = xregrid.grid2loc(
                        dsi[var].isel(time=itime, z=iz), loc
                        )
            dims = ["time", "z", "npts"]
            coords = dict(time=dsi.time, **loc.coords)
        elif ("time" in dsi[var].dims) and ("z" not in dsi[var].dims):
            arr = np.nan * np.zeros((dsi.sizes["time"], len(lon)))
            for itime in range(dsi.sizes["time"]):
                arrin = dsi[var].isel(time=itime).squeeze()
                arr[itime, :] = xregrid.grid2loc(
                    arrin,
                    loc
                    )
            dims = ["time", "npts"]
            coords = dict(time=dsi.time, **loc.coords)
        else:
            arr = xregrid.grid2loc(dsi[var], loc)
            dims = ["npts"]
            coords = dict(**loc.coords)
            if isinstance(arr, xr.DataArray):
                arr = arr.data
        dsvar = xr.Dataset(data_vars={var: (dims, arr)}, coords=coords)
        dsvar[var] = dsvar[var].assign_attrs(**dsi[var].attrs)
        dss.append(dsvar)
    dso = xr.merge(dss)
    if "depth" in dso:
        dso = dso.set_coords("depth")
    elif ("depth" in dsi.coords) and ("time" not in dsi["depth"].dims):
        dso["depth"] = dsi.depth
        dso = dso.set_coords("depth")
    return dso
    
def regrid(dsi, dso) -> xr.Dataset:
    """
    Regrid a variable.

    Parameters
    ----------
    dsi: xarray.Dataset
        Dataset to regrid.
    dso: xarray.Dataset
        Dataset containing output grid.

    Returns
    -------
    xarray.Dataset
        Regridded dataset.
    """
    dlon = dsi.lon.diff("x").max().values
    dlat = dsi.lat.diff("y").max().values
    
    vars2sub = geo_vars(dsi)
    dsi = dsi[vars2sub].where(
        (dsi.lat >= dso.lat.min().values - 2 * dlat)
        & (dsi.lat <= dso.lat.max().values + 2 * dlat)
        & (dsi.lon >= dso.lon.min().values - 2 * dlon)
        & (dsi.lon <= dso.lon.max().values + 2 * dlon),
        # drop=True,
    )
    
    if "mask" in dso.keys():
        dso = dso.where(dso.mask == 1 , drop=True)
    
    regridder = xe.Regridder(dsi, dso, "bilinear", parallel=False)
    dss = []
    for var in vars2sub:
        daio = regridder(dsi[var])
        dsio = daio.to_dataset(name=var)
        dss.append(dsio)
    dsio = xr.merge(dss)
    # dsio = regridder(dsi)
    regridder.grid_in.destroy()
    regridder.grid_out.destroy()
    # for var in dsi.data_vars:
    #     dsio[var].assign_attrs(**dsi[var].attrs)
    return dsio

def vinterp(ds, vname, vlevels, method="linear"):
    """Interpolate an xarray Dataset over specified vertical levels.
    
    Parameters
    ----------
    ds: xr.Dataset
        The input xarray Dataset containing variables to interpolate.
    vname: str
        The name of the vertical coordinate (e.g., "depth" or "dens").
    vlevels: list
        List of vertical levels to interpolate to.
    method: str (optional)
        The interpolation method to use. Default is "linear".
    
    Returns
    -------
    xr.Dataset
        A new Dataset with variables interpolated to the specified vertical levels.
    """
    if (vname == "depth") and ("dens" in ds.coords):
        ds = ds.reset_coords("dens")
    elif (vname == "dens") and ("depth" in ds.coords):
        ds = ds.reset_coords("depth")
        if "dens" not in ds.coords:
            ds = ds.set_coords("dens")
    das = []
    for var in ds.data_vars:
        if "z" in ds[var].dims:
            da = xregrid.regrid1d(
                ds[var].chunk(dict(z=-1)),
                vlevels,
                method=method,
                extrap="bottom"
            )
        else:
            da = ds[var]
        das.append(da)
    dsout = xr.merge(das, combine_attrs='drop_conflicts')
    dsout = dsout.set_xindex(vname)
    return dsout