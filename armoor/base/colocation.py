"""Colocate models and obs"""
import xarray as xr
import numpy as np
from xoa.regrid import regrid1d
import xoa.grid
import xesmf as xe
import logging
import pandas as pd

logger = logging.getLogger(__name__)


def colocate_all(obs, mod, horizontal_colocation_flag, vertical_colocation_flag, temporal_colocation_flag,
                 coloc_method='nearest', opt_grid=None, vertical_step=None, horizontal_step=None,
                 coloc_method_z='nearest'):
    """
    Put the model and observation dataset on the same grid defined
    according to the selected method.

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
    coloc_method : str
        Method to use for the colocation
    opt_grid : str
        Defines the targeted grid on which to colocate the datasets : model, observation or auto.
    vertical_step : float
        Vertical step of the grid on which to colocate.
    horizontal_step : float
        Horizontal step of the grid on which to colocate.

    Returns
    -------
    obs : xarray.Dataset
        colocated observation dataset.
    mod: xarray.Dataset
        colocated model dataset.
    """
    # Define the target grid
    if opt_grid == 'observation':
        ds_tgt = obs
    elif opt_grid == 'model':
        ds_tgt = mod
    elif opt_grid == 'auto':
        ds_tgt = min_grid_all(obs, mod, horizontal_colocation_flag, vertical_colocation_flag, temporal_colocation_flag)
    else:
        raise Warning('Caution, opt_grid values should be "observation" or "model" or "auto"')

    logger.info(f"Colocation to grid {opt_grid}")

    # Time colocation
    if temporal_colocation_flag:
        mod, obs = temporal_colocation(mod, obs, ds_tgt, coloc_method)

    # Horizontal colocation
    if horizontal_colocation_flag:
        mod, obs = horizontal_colocation(mod, obs, ds_tgt, coloc_method)

    if horizontal_step:
        mod, obs = set_hor_step(mod, obs, horizontal_step, coloc_method)

    # Vertical colocation
    if vertical_colocation_flag:
        mod, obs = vertical_colocation(mod, obs, ds_tgt, coloc_method_z)

    if vertical_step:
        mod, obs = set_vert_step(mod, obs, vertical_step, coloc_method_z)

    return obs, mod


def temporal_colocation(mod, obs, ds_tgt, coloc_method):
    time_values = np.unique(ds_tgt.time.values)

    logger.info("Temporal model colocation")

    if mod.dims["time"] > 1:
        mod = mod.interp(time=time_values, method=coloc_method, kwargs={"fill_value": "extrapolate"})
    else:
        mod = pick_time(mod, time_values)

    logger.info("Temporal observation colocation")

    if obs.dims["time"] > 1:
        obs = obs.interp(time=time_values, method=coloc_method, kwargs={"fill_value": "extrapolate"})
    else:
        obs = pick_time(obs, time_values)

    return mod, obs


def horizontal_colocation(mod, obs, ds_tgt, coloc_method):
    # Colocation for observations whose positions depend on time (profilers etc.)
    if 'time' in ds_tgt.lon.dims and len(ds_tgt.time) > 1:
        logger.info("Target grid positions are depending on time")
        try:
            logger.info("Observation positions colocation")
            obs = colocate_lon_lat_time_obs(obs, ds_tgt, coloc_method)
        except:
            logger.warning("Observation positions colocation : Failed.")
            pass

        logger.info("Model positions colocation")
        mod = colocate_lon_lat_time_mod(mod, ds_tgt, coloc_method)
    else:
        lon_values = np.unique(ds_tgt.lon.values)
        lat_values = np.unique(ds_tgt.lat.values)

        # If x/y coords remains after to_rect, we use xesmf to convert curv into rect grid
        if 'x' in mod.dims:
            logger.info("Curvilinear to rectilinear conversion")
            mod = convert_curv_rect(mod, lon_values, lat_values)
            logger.info("Curvilinear to rectilinear conversion : done.")

        # Colocate model
        try:
            logger.info("Horizontal model colocation")
            mod = mod.interp(lon=lon_values, lat=lat_values, method=coloc_method, kwargs={"fill_value": "extrapolate"})
        except:
            logger.warning("Horizontal model colocation : Failed.")

        # Colocate observation
        try:
            logger.info("Horizontal observation colocation")
            obs = obs.interp(lon=lon_values, lat=lat_values, method=coloc_method, kwargs={"fill_value": "extrapolate"})
        except:
            logger.warning("Horizontal observation colocation : Failed.")
    return mod, obs


def vertical_colocation(mod, obs, ds_tgt, coloc_method):
    if 'DEPH' in ds_tgt.variables:
        depth_values = np.unique(ds_tgt.DEPH.fillna(0).values)
    else:
        depth_values = np.unique(ds_tgt.depth.fillna(0).values)

    if len(depth_values) != 1:
        logger.info("Vertical model colocation.")
        # Interpolation for HYCOM/Croco
        if 'level' in mod.dims and 'depth' not in mod.dims:
            if len(depth_values) > 50:
                logger.warning(f"Too many unique depth values encountered in the target product :"
                               f" please specify the vertical step you need with the option \'vertical_step\'. "
                               f"The grid will be resampled with only 50 values.")
                depth_values = np.linspace(depth_values[0], depth_values[-1], 50)

            mod = mod.meta.vertical_selection_list(depth_values)

        # Interpolation for CROCO
        elif 'sig' in mod.dims:
            depth = xr.DataArray(depth_values, name="depth", dims="depth")
            for var in mod.variables:
                if 'sig' in mod[var].dims:
                    mod[var] = regrid1d(mod[var], depth)

        # Interpolation for other models
        else:
            mod = mod.interp(depth=depth_values, method=coloc_method, kwargs={"fill_value": "extrapolate"})
        logger.info("Vertical colocation of observation")

        # Interpolation for CMEMS in-situ when depth is calculated from pressure
        if 'depth' not in obs.dims and 'depth' in obs.coords:
            depth = xr.DataArray(depth_values, name="depth", dims="depth")
            ds_coloc = xr.Dataset()
            for var in obs.variables:
                if var in ['lon', 'lat'] or obs[var].data.dtype == 'object':
                    pass
                elif 'depth' in obs[var].coords and var != 'depth':
                    ds_coloc[var] = regrid1d(obs[var], depth)
                elif var != 'depth':
                    ds_coloc[var] = obs[var]
            obs = ds_coloc
            obs['depth'] = depth
        else:
            obs = obs.interp(depth=depth_values, method=coloc_method, kwargs={"fill_value": "extrapolate"})

    return mod, obs


def set_hor_step(mod, obs, hor_step, coloc_method='linear'):
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

    hor_step = obs.meta.km_to_deg(hor_step)

    # Calculate the time step and distance step in the data
    pos0, pos1 = mod.isel(time=0), mod.isel(time=1)
    time_step_data = pos1.time.data - pos0.time.data

    dist_step = np.sqrt((pos1.lon - pos0.lon) ** 2 + (pos1.lat - pos0.lat) ** 2)
    time_step = time_step_data * hor_step / dist_step
    time_step = time_step.data.astype('timedelta64[s]')
    time_step = str(time_step).split()[0] + 'S'
    time_min, time_max = mod.time[0].data, mod.time[-1].data
    time_min, time_max = np.datetime64(time_min), np.datetime64(time_max)

    # Create the new times array to select to retrieve the horizontal resolution
    tgt_time = pd.date_range(time_min, time_max, freq=time_step)

    # Interpolate the model and obs on the targeted times
    mod = mod.interp(time=tgt_time, method=coloc_method)
    obs = obs.interp(time=tgt_time, method=coloc_method)
    return mod, obs


def set_vert_step(mod, obs, vert_step, coloc_method='linear'):
    """
    Colocate the model and obs on the chosen vertical grid.
    Parameters
    ----------
    obs : xarray.Dataset
        Observation dataset.
    mod : xarray.Dataset
        Model dataset.
    vert_step : float
        Vertical step of the grid on which to colocate.
    Returns
    -------
    models : dict
        Dictionnary with models with the updated projection grid.
    observation : dict
        Dictionnary with models with the updated projection grid.
    """

    depth_min, depth_max = mod.depth.min(), mod.depth.max()
    tgt_depth = np.arange(depth_min, depth_max, vert_step)
    if 'depth' in mod.dims:
        mod = mod.interp(depth=tgt_depth, method=coloc_method)
    if 'depth' in obs.dims:
        obs = obs.interp(depth=tgt_depth, method=coloc_method)

    return mod, obs


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


def colocate_lon_lat_time_mod(ds, tgt, method):
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
    for i, time in enumerate(tgt.time.values):
        # Colocation time
        ds_interp = ds.interp(time=time, method=method, kwargs={"fill_value": "extrapolate"}).squeeze()
        # Colocation depth
        if 'depth' in tgt.squeeze().dims:
            if 'DEPH' in tgt.variables:
                depth = np.unique(tgt.DEPH.fillna(0).values)
            else:
                depth = np.unique(tgt.depth.values)
            if 'depth' not in ds_interp:
                logger.warning(
                    'Caution : the product you are using does not contain a depth dimension - probably a 2D file.'
                    ' The vertical colocation will fail.')
            ds_interp = ds_interp.interp(depth=depth, method=method, kwargs={"fill_value": "extrapolate"}).squeeze()

        # Colocation lon/lat
        if 'lon' in tgt.coords:
            lon = tgt.isel(time=[i]).lon.values
            lat = tgt.isel(time=[i]).lat.values
            if 'lon' in ds.dims:  # For rect. grids
                ds_interp = ds_interp.interp(lon=lon, lat=lat, method=method,
                                             kwargs={"fill_value": "extrapolate"}).squeeze()
            elif 'x' in ds.dims:  # For curv. grids
                if __name__ == '__main__':
                    ds_interp = ds_interp.meta.sel_closest(lon, lat)

        list_ds.append(ds_interp)
    ds = xr.concat(list_ds, 'time')
    return ds


def colocate_lon_lat_time_obs(ds, tgt, method):  # quand lon et lat dependent de time
    """
    Colocate a datased on the target grid using the colocation method defined. Used for observation in which the
    horizontal coordinated (lon/lat) depend on time.
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
    for i, time in enumerate(tgt.time.values):
        ds_interp = ds.isel(time=i)
        # Colocation depth
        if 'depth' in tgt.squeeze().dims:
            if 'DEPH' in tgt.variables:
                depth = np.unique(tgt.DEPH.fillna(0).values)
                ds_interp['depth'] = ds_interp['DEPH']
            else:
                depth = np.unique(tgt.depth.values)
            ds_interp = ds_interp.dropna('depth').interp(depth=depth, method=method,
                                                         kwargs={"fill_value": "extrapolate"}).squeeze()
        list_ds.append(ds_interp)
    ds = xr.concat(list_ds, 'time')
    return ds


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
    lon_min, lon_max, step_lon = np.min(lon), np.max(lon), lon[1] - lon[0]
    lat_min, lat_max, step_lat = np.min(lat), np.max(lat), lat[1] - lat[0]
    ds_out = xe.util.grid_2d(lon_min, lon_max, step_lon, lat_min, lat_max, step_lat)
    regridder = xe.Regridder(ds, ds_out, 'bilinear', unmapped_to_nan=True)
    ds_rect = xr.Dataset()
    for var in ds.variables:
        if 'x' in ds[var].dims and var not in ['lon', 'lat', 'x', 'y']:
            da_rect = regridder(ds[var])
            da_rect = xoa.grid.to_rect(da_rect)
            ds_rect[var] = da_rect

    return ds_rect
