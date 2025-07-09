"""Interpolation functions."""
import re, logging
import numpy as np
import pandas as pd
import xarray as xr
import xesmf as xe
import xoa.regrid as xregrid
    
from armoor.base.misc import geo_vars

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
    """Interpolate a dataset in time - OPTIMIZED VERSION.

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

    logger = logging.getLogger(__name__)
    
    # Conversion et tri des dates (une seule fois)
    dates = pd.to_datetime(dates)
    if hasattr(dates, '__len__') and len(dates) > 1:
        dates = sorted(dates)
    elif not hasattr(dates, '__len__'):
        dates = [dates]
    
    # Classification des variables (une seule fois)
    varstime = [var for var in ds if "time" in ds[var].dims]
    varsnotime = [var for var in ds if "time" not in ds[var].dims]
    
    # Time dim et bornes
    time_name = "time"
    time = ds.indexes[time_name]
    begindate_nc = time[0]
    enddate_nc = time[-1]
    
    # Pré-calcul des datasets de persistance
    ds_first = ds.isel({time_name: slice(0, 1)})
    ds_last = ds.isel({time_name: slice(-1, None)})
    
    # Parsing persistency une seule fois
    persistency_config = None
    if persistency:
        m = re.search(r"mean_(?P<term>.*)(?P<units>.)", persistency, re.DOTALL)
        if m:
            persistency_config = {
                'timedelta': pd.to_timedelta(int(m["term"]), m["units"]),
                'term': int(m["term"]),
                'units': m["units"]
            }
    
    # Classification des dates pour traitement par lot
    dates_in_range = []
    dates_before = []
    dates_after = []
    dates_exact = []
    
    for date in dates:
        if date in time:
            dates_exact.append(date)
        elif date < begindate_nc:
            dates_before.append(date)
        elif date > enddate_nc:
            dates_after.append(date)
        else:
            dates_in_range.append(date)
    
    # Traitement par lots
    dss = []
    
    # 1. Dates exactes (sélection directe par lot)
    if dates_exact:
        exact_ds = ds.sel({time_name: dates_exact})
        for i, date in enumerate(dates_exact):
            this_ds = exact_ds.isel({time_name: i}).expand_dims(time_name)
            this_ds = this_ds.assign_coords({time_name: [date]})
            dss.append((date, this_ds))
    
    # 2. Dates avant la plage (persistance)
    if dates_before:
        base_ds = ds_first
        
        # Pré-calcul persistency pour toutes les dates avant
        if persistency_config:
            date_target = begindate_nc + persistency_config['timedelta']
            ds_pers = ds.where(ds[time_name] <= date_target).mean(dim=time_name, keepdims=True)
        
        for date in dates_before:
            this_ds = base_ds.copy(deep=False)
            this_ds = this_ds.assign_coords({time_name: [date]})
            
            if persistency_config:
                for vname in ds_pers:
                    if vname in this_ds:
                        this_ds[vname] = this_ds[vname].copy(data=ds_pers[vname].data)
            
            dss.append((date, this_ds))
    
    # 3. Dates après la plage (persistance)
    if dates_after:
        base_ds = ds_last
        
        # Pré-calcul persistency pour toutes les dates après
        if persistency_config:
            date_target = enddate_nc - persistency_config['timedelta']
            ds_pers = ds.where(ds[time_name] >= date_target).mean(dim=time_name, keepdims=True)
        
        for date in dates_after:
            this_ds = base_ds.copy(deep=False)
            this_ds = this_ds.assign_coords({time_name: [date]})
            
            if persistency_config:
                for vname in ds_pers:
                    if vname in this_ds:
                        this_ds[vname] = this_ds[vname].copy(data=ds_pers[vname].data)
            
            dss.append((date, this_ds))
    
    # 4. Interpolations par lot (plus efficace)
    if dates_in_range:        
        # Grouper les interpolations adjacentes pour réduire les lectures
        sorted_dates_in_range = sorted(dates_in_range)
        
        for date in sorted_dates_in_range:            
            # Trouver les indices pour l'interpolation
            it = ds.indexes[time_name].get_indexer([date], method="ffill")[0]
            
            # Charger seulement 2 time steps avec chunking optimal
            tmp_ds = ds.isel({time_name: slice(it, it + 2)}).chunk({time_name: 2})
            
            # Interpolation avec options optimisées
            this_ds = tmp_ds.interp(
                {time_name: [date]}, 
                method=method,  # Explicite plus rapide
                assume_sorted=True  # Optimisation
            )
            
            # Éviter .load() si possible - garder lazy
            this_ds = this_ds.assign_coords({time_name: [date]})
            
            # Préserver encoding seulement si demandé
            if preserve_encoding:
                for vname, var in tmp_ds.items():
                    if vname in this_ds:
                        this_ds[vname].encoding.update(var.encoding)
            
            dss.append((date, this_ds))
            del tmp_ds  # Libération mémoire explicite
    
    # Traitement diurnal optimisé (si nécessaire)
    if diurnal_vars:
        dss_dict = {date: ds_item for date, ds_item in dss}
        
        for date, this_ds in dss:
            if date < begindate_nc:
                time_target = date + pd.to_timedelta("24h")
            elif date > enddate_nc:
                time_target = date - pd.to_timedelta("24h")
            else:
                continue
                
            if time_target in dss_dict:
                target_ds = dss_dict[time_target]
                for vname in diurnal_vars:
                    if vname in this_ds and vname in target_ds:
                        this_ds[vname] = this_ds[vname].copy(data=target_ds[vname].data)
    
    # Tri par date et extraction des datasets
    dss.sort(key=lambda x: x[0])
    sorted_datasets = [ds_item for _, ds_item in dss]
    
    # Concaténation avec paramètres optimisés
    dso = xr.concat(
        [ds_item[varstime] for ds_item in sorted_datasets],
        time_name,
        compat="no_conflicts",
        coords="minimal",  # Plus rapide que "different"
        data_vars="all",
    )
    
    # Ajout des variables sans temps
    for var in varsnotime:
        dso[var] = ds[var]
    
    # Attributs et encoding (optimisé)
    dso[time_name].attrs.update(ds[time_name].attrs)
    dso[time_name].encoding.update(ds[time_name].encoding)
    
    if preserve_encoding:
        for vname, var in ds.items():
            if vname in dso:
                dso[vname].encoding.update(var.encoding)
    
    # Transpose final
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
        da = ds[var]
        if ("time" in da.dims) and ("z" in da.dims):
            da = xregrid.grid2loc(
                        da, loc
                        )
            dims = ["time", "z", "npts"]
            da = da.transpose(*dims)
            arr = da.data
            del da
            coords = dict(time=dsi.time, **loc.coords)
        elif ("time" in da.dims) and ("z" not in da.dims):
            da = xregrid.grid2loc(
                        da, loc
                        )
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
    # dlon = dsi.lon.diff("x").max().values
    # dlat = dsi.lat.diff("y").max().values
    
    vars2sub = geo_vars(dsi)
    # dsi = dsi[vars2sub].where(
    #     (dsi.lat >= dso.lat.min().values - 2 * dlat)
    #     & (dsi.lat <= dso.lat.max().values + 2 * dlat)
    #     & (dsi.lon >= dso.lon.min().values - 2 * dlon)
    #     & (dsi.lon <= dso.lon.max().values + 2 * dlon),
    #     # drop=True,
    # )
    
    # if "mask" in dsi.keys():
    #     dsi = dsi.where(dsi.mask == 1 , drop=True)
    
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
    if vname == "depth":
        if "dens" in ds.coords:
            ds = ds.reset_coords("dens")
        if "depth" not in ds.coords:
            ds = ds.set_coords("depth")
    elif vname == "dens":
        if "depth" in ds.coords:
            ds = ds.reset_coords("depth")
        if "dens" not in ds.coords:
            ds = ds.set_coords("dens")
    das = []
    for var in ds.data_vars:
        if "z" in ds[var].dims:
            da = xregrid.regrid1d(
                ds[var],#.chunk(dict(z=-1)),
                vlevels,
                method=method,
                extrap="bottom"
            )
        else:
            da = ds[var]
        das.append(da)
    dsout = xr.merge(das, combine_attrs='drop_conflicts')
    if len(dsout.dims) == 1:
        dsout = dsout.set_xindex(vname)
    return dsout