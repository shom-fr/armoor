"""Colocate models and obs"""
import xarray as xr
import numpy as np
from xoa.regrid import regrid1d
import xoa.grid
import xesmf as xe
import logging
import pandas as pd
import matplotlib.pyplot as plt

logger = logging.getLogger(__name__)


def colocate_all(obs, mod, flags, tgt_grid, vertical_step=None, horizontal_step=None, coloc_method='nearest',
                 coloc_method_z='nearest'):
    # Read the colocation flags
    time_flag, hor_flag, ver_flag = flags

    # Colocate
    if tgt_grid == 'auto':
        logger.info(f'Auto colocation : the model and observation will be colocated '
                    f'on the regular grid with the minimum step size of the products')
        tgt = min_grid_all(obs, mod, hor_flag, ver_flag, time_flag)
        obs_coloc = obs
        mod_coloc = mod
        if time_flag:
            obs_coloc = temporal_colocation(obs_coloc, tgt, coloc_method)
            mod_coloc = temporal_colocation(mod_coloc, tgt, coloc_method)
        if hor_flag:
            obs_coloc = horizontal_colocation(obs_coloc, tgt, coloc_method)
            mod_coloc = horizontal_colocation(mod_coloc, tgt, coloc_method)
        if ver_flag:
            obs_coloc = vertical_colocation(obs_coloc, tgt, coloc_method)
            mod_coloc = vertical_colocation(mod_coloc, tgt, coloc_method)

    elif vertical_step and horizontal_step:
        logger.info(f'Colocating on the vertical and horizontal step defined grid')
        # Vertical grid
        mod_coloc, obs_coloc = set_vert_step(mod, obs, tgt_grid, vertical_step, coloc_method_z)

        # Horizontal grid
        mod_coloc, obs_coloc = set_hor_step(mod_coloc, obs_coloc, horizontal_step, coloc_method)

    else:
        # Colocate on the observation grid
        if tgt_grid == 'observation':
            logger.info(f'Colocating the model on the observation grid')
            obs_coloc = obs
            mod_coloc = mod
            # If observation is profiler
            if 'time' in obs.lon.dims and len(obs.time) > 1:
                logger.info(f'Profiler type colocation')
                mod_coloc = colocate_lon_lat_time(mod, obs, coloc_method, coloc_method_z)

            else:
                # Temporal colocation
                if time_flag:
                    mod_coloc = temporal_colocation(mod_coloc, obs, coloc_method)

                # Horizontal colocation
                if hor_flag:
                    mod_coloc = horizontal_colocation(mod_coloc, obs, coloc_method)

                # Vertical colocation
                if ver_flag:
                    mod_coloc = vertical_colocation(mod_coloc, obs, coloc_method_z)

        # Colocate on the model grid
        elif tgt_grid == 'model':
            logger.info(f'Colocating the observation on the model grid')
            mod_coloc = mod
            obs_coloc = obs

            # Temporal colocation
            if time_flag:
                obs_coloc = temporal_colocation(obs_coloc, mod, coloc_method)

            # Horizontal colocation
            if hor_flag:
                obs_coloc = horizontal_colocation(obs_coloc, mod, coloc_method)

            # Vertical colocation
            if ver_flag:
                obs_coloc = vertical_colocation(obs_coloc, mod, coloc_method_z)

    return obs_coloc, mod_coloc


def temporal_colocation(ds, tgt, coloc_method):
    logger.info('Time colocation')
    time_values = np.unique(tgt.time.values)

    if ds.dims["time"] > 1:
        ds = ds.interp(time=time_values, method=coloc_method, kwargs={"fill_value": "extrapolate"})
    else:
        ds = pick_time(ds, time_values)

    return ds


def horizontal_colocation(ds, tgt, coloc_method):
    logger.info('Horizontal colocation')
    # Drop duplicates in lon/lat
    ds = ds.drop_duplicates('lon').drop_duplicates('lat')

    # Get lon / lat values
    if 'lon' in tgt.dims:
        lon_values = tgt.drop_duplicates('lon').lon.values
        lat_values = tgt.drop_duplicates('lat').lat.values
    else:
        lon_values = np.unique(tgt.lon.values)
        lat_values = np.unique(tgt.lat.values)

    # If tgt lon/lat depend on x/y (ex if tgt from TOPAZ) : DOES NOT WORK
    if 'x' in tgt.dims:
        ds_coloc_xy = []
        for i_x, x in enumerate(tgt.x):
            tgt_xy = tgt.isel(x=i_x)
            ds_x = ds.interp(lon=tgt_xy.lon.values, lat=tgt_xy.lat.values, method=coloc_method)
            ds_x = ds_x.stack(y=('lon', 'lat')).reset_index('y')
            ds_x = ds_x.isel(y=slice(0, -1, len(tgt_xy.y)))
            lons = xr.DataArray(ds_x.lon.values, dims='y', coords={'y': tgt_xy.y.values}, name='lon')
            lats = xr.DataArray(ds_x.lat.values, dims='y', coords={'y': tgt_xy.y.values}, name='lat')
            ds_x = ds_x.assign_coords({'lon': lons, 'lat': lats})
            ds_coloc_xy.append(ds_x)

        ds_coloc = xr.concat(ds_coloc_xy, 'x')
        ds_coloc = ds_coloc.assign_coords(tgt.coords)


        # Make sure x y are in the same order in both datasets
        dims = list(tgt.dims.keys())
        if len(dims) == 2:
            ds_coloc = ds_coloc.transpose(dims[0], dims[1])
        elif len(dims) == 3:
            ds_coloc = ds_coloc.transpose(dims[0], dims[1], dims[2])
        elif len(dims) == 4:
            ds_coloc = ds_coloc.transpose(dims[0], dims[1], dims[2], dims[4])

    # Regrid ds if necessary
    elif 'x' in ds.dims:
        ds_coloc = convert_curv_rect(ds, lon_values, lat_values)

    else:
        ds_coloc = ds.interp(lon=lon_values, lat=lat_values, method=coloc_method, kwargs={"fill_value": "extrapolate"})

    return ds_coloc


def vertical_colocation(ds, tgt, coloc_method):
    logger.info('Vertical colocation')
    depth_ds = ds.depth
    depth_tgt = tgt.depth

    # Case ds and tgt have depth(depth) dimension
    if 'depth' in depth_tgt.dims and 'depth' in depth_ds.dims:
        ds = ds.interp(depth=depth_tgt, method=coloc_method)

    # Case ds has depth(lon/lat/time) dimension and tgt has depth(depth) dimension
    elif 'depth' in depth_tgt.dims and 'depth' not in depth_ds.dims:
        da_depth = xr.DataArray(depth_tgt.values, name="depth", dims="depth")
        for var in ds.variables:  # Regrid for all variables
            if 'sig' in ds[var].dims:
                ds[var] = regrid1d(ds[var], da_depth)
    return ds


def set_hor_step(mod, obs, horizontal_step, coloc_method='linear'):
    """
    Colocate the model and obs on the chosen horizontal grid.
    Parameters
    ----------
    obs : xarray.Dataset
        Observation dataset.
    mod : xarray.Dataset
        Model dataset.
    hor_step : float
        Horizontal step of the grid on which to colocate.
    Returns
    -------
    models : dict
        Dictionnary with models with the updated projection grid.
    observation : dict
        Dictionnary with models with the updated projection grid.
    """
    horizontal_step = obs.meta.km_to_deg(horizontal_step)

    obs_deb, obs_end = obs.isel(time=0), obs.isel(time=-1)
    total_distance_obs = np.sqrt((obs_deb.lon - obs_end.lon) ** 2 + (obs_deb.lat - obs_end.lat) ** 2)
    total_duration_obs = obs_end.time - obs_deb.time

    time_step_grid = horizontal_step * total_duration_obs / total_distance_obs

    time_step_grid = time_step_grid.data.astype('timedelta64[s]')
    time_step_grid = str(time_step_grid).split()[0] + 'S'
    time_min, time_max = obs_deb.time.values, obs_end.time.values
    time_min, time_max = np.datetime64(time_min), np.datetime64(time_max)

    # Create the new times array to select to retrieve the horizontal resolution
    tgt_time = pd.date_range(time_min, time_max, freq=time_step_grid)

    # Interpolate the observation on the targeted times
    obs_coloc = obs.interp(time=tgt_time, method=coloc_method)

    # Interpolate the model on the observation times and locations
    mod_coloc = colocate_lon_lat_time(mod, obs_coloc, coloc_method, method_z=False)
    return mod_coloc, obs_coloc


def set_vert_step(mod, obs, tgt_grid, vertical_step, coloc_method_z):
    """
    Colocate the model and obs on the chosen vertical grid.
    Parameters
    ----------
    obs : xarray.Dataset
        Observation dataset.
    mod : xarray.Dataset
        Model dataset.
    vertical_step : float
        Vertical step of the grid on which to colocate.
    Returns
    -------
    models : dict
        Dictionnary with models with the updated projection grid.
    observation : dict
        Dictionnary with models with the updated projection grid.
    """
    # Define the target vertical grid
    if tgt_grid == 'observation':
        depths = np.arange(np.nanmin(obs.depth.values), np.nanmax(obs.depth.values), vertical_step)
    elif tgt_grid == 'model':
        depths = np.arange(np.nanmin(obs.depth.values), np.nanmax(obs.depth.values), vertical_step)

    # Model
    if 'level' in mod.depth.dims:  # Case croco
        mod_coloc = mod.meta.vertical_selection_list(depths)
    else:
        mod_coloc = mod.interp(depth=depths, method=coloc_method_z)

    # Observation
    if 'z' in obs.depth.dims:  # Case CMEMS data : depth(z,time)
        obs_coloc = obs.meta.vertical_selection_list(depths)
    else:
        obs_coloc = obs.interp(depth=depths, method=coloc_method_z)

    return mod_coloc, obs_coloc


def pick_time(ds, time_values):
    """Pick data in case of dims['time'] = 1.
    Parameters
    ----------
    ds : xarray.Dataset
    time_values : list of times

    Returns
    -------
    ds : xarray.Dataset
    """
    dss = []
    for time_value in time_values:
        ds0 = ds.isel(time=[0])
        ds0 = ds0.assign_coords({"time": [time_value]})
        dss.append(ds0)
    ds = xr.concat(dss, "time", compat="no_conflicts", coords="different", data_vars="all")
    return ds


def min_grid_all(obs, mod, horizontal_colocation_flag, vertical_colocation_flag, temporal_colocation_flag):
    """
    Gives the grid that has the minimum resolution along each dimension
    of the observation and model.
    Parameters
    ----------
    obs : xarray.Dataset
        Observation dataset.
    mod : xarray.Dataset
        Model dataset.
    horizontal_colocation_flag : bool
        Colocate on horizontal (lon/lat) dimension or not.
    vertical_colocation_flag : bool
        Colocate on vertical (depth) dimension or not.
    temporal_colocation_flag : bool
        Colocate on temporal (time) dimension or not.

    Returns
    -------
    tgt_grid : xarray.Dataset
        Grid on which to colocate the model and observation, with the minimum resolution.
    """
    dims = []
    if horizontal_colocation_flag:
        dims.append('lon')
        dims.append('lat')
    if vertical_colocation_flag:
        dims.append('depth')
    if temporal_colocation_flag:
        dims.append('time')

    dict_coords = min_dimensions(obs, mod, dims)
    tgt_grid = xr.DataArray(dims=dims, coords=dict(dict_coords))
    return tgt_grid


def min_dimensions(obs, mod, dims):
    """
    Gives the minimum resolution of the model and observation dataset
    to build the grid for the colocation.
    Parameters
    ----------
    obs : xarray.Dataset
        Observation dataset.
    mod : xarray.Dataset
        Model dataset.
    dims : list of str
        Dimensions on which to take the minimum resolution.

    Returns
    -------
    tgt_dims_values : dict
        Values of the grid along each dimension.
    """
    tgt_dims_values = {}
    for dim in dims:
        step_mod = get_step_size(mod, dim)
        step_obs = get_step_size(obs, dim)
        max_val = np.nanmax([step_obs, step_mod])
        if not np.isnan(max_val):  # the dimension is either in the model or the observation
            if max_val == step_mod:
                tgt_dims_values[dim] = mod[dim]
            else:
                tgt_dims_values[dim] = obs[dim]

    return tgt_dims_values


def colocate_lon_lat_time(mod, obs, method, method_z):
    """
    Colocate a datased on the target grid using the colocation method defined.
    Parameters
    ----------
    ds : xarray.Dataset
        Dataset to be colocated.
    tgt : xarray.Dataset
        Target grid dataset on which to colocate.
    method : str
        Method of colocation

    Returns
    -------
    ds : xarray.Dataset
        Colocated dataset.
    """
    list_ds = []
    for i, time in enumerate(obs.time.values):
        # Colocation time
        mod_interp = mod.interp(time=time, method=method, kwargs={"fill_value": "extrapolate"})

        # Colocation lon/lat
        if 'lon' in obs.coords:
            lon = obs.lon.isel(time=[i]).values
            lat = obs.lat.isel(time=[i]).values
            if 'lon' in mod_interp.dims:  # For rect. grids
                mod_interp = mod_interp.interp(lon=lon, lat=lat, method=method,
                                               kwargs={"fill_value": "extrapolate"}).squeeze()
            elif 'x' in mod_interp.dims:  # For curv. grids
                if __name__ == '__main__':
                    mod_interp = mod_interp.meta.sel_closest(lon, lat)

        # Colocate depth
        if method_z:
            if 'depth' in obs.squeeze().dims:
                if 'DEPH' in obs.variables:
                    depth = np.unique(obs.DEPH.fillna(0).values)
                else:
                    depth = np.unique(obs.depth.values)
                if 'depth' not in mod_interp:
                    logger.warning(
                        'Caution : the product you are using does not contain a depth dimension - probably a 2D file.'
                        ' The vertical colocation will fail.')
                mod_interp = mod_interp.interp(depth=depth, method=method_z,
                                               kwargs={"fill_value": "extrapolate"}).squeeze()
            elif 'z' in obs.squeeze().dims:
                depths = obs.depth.isel(time=i)
                mod_interp = mod_interp.interp(depth=depths, method=method_z)

        list_ds.append(mod_interp)

    mod_coloc = xr.concat(list_ds, 'time')
    return mod_coloc


def get_step_size(ds, dim):
    """
    Returns the step size of the dataset along the specified dimension.

    Attributes
    ----------
    ds : xarray.Dataset
        Dataset from which to get the resolution.
    dim : str
        Dimension to get the resolution.

    Returns
    -------
    step : float
        Step size along the dimension.
    """

    if dim in ds.dims:  # initially was dim in ds.coords
        try:
            if len(ds[dim]) > 1:
                step = abs(ds[dim][0].data - ds[dim][1].data)
            else:
                step = 0
        except:  # si dim(time= None)
            step = np.nan
    elif dim in ds.coords:  # CROCO, lon, lat sont dans coords apres decode_sigma
        try:
            if len(ds[dim]) > 1:
                step = abs(ds[dim][0].data - ds[dim][1].data)
            else:
                step = 0
        except:
            step = np.nan
    else:
        step = np.nan

    if type(step) == np.timedelta64:
        step = step.astype('timedelta64[s]').astype(float)

    if type(step) == np.ndarray:
        step = np.nan

    return step


def convert_curv_rect(ds, lon, lat):
    """
    Convert curvilinear grid into rectangular grid.
    Parameters
    ----------
    ds : xarray.Dataset
        Curvilinear dataset to convert.
    lon : array
        Longitude values.
    lat : array
        Latitude values.

    Returns
    -------
    ds_rect : xarray.Dataset
        Dataset converted on a regular grid.

    """
    lon_min, lon_max, step_lon = np.min(lon), np.max(lon), (np.max(lon) - np.min(lon)) / len(lon)
    lat_min, lat_max, step_lat = np.min(lat), np.max(lat), (np.max(lat) - np.min(lat)) / len(lat)
    ds_out = xe.util.grid_2d(lon_min, lon_max, step_lon, lat_min, lat_max, step_lat)
    regridder = xe.Regridder(ds, ds_out, 'bilinear', unmapped_to_nan=True)
    ds_rect = xr.Dataset()
    for var in ds.variables:
        if 'x' in ds[var].dims and var not in ['lon', 'lat', 'x', 'y']:
            da_rect = regridder(ds[var])
            da_rect = xoa.grid.to_rect(da_rect)
            ds_rect[var] = da_rect

    return ds_rect
