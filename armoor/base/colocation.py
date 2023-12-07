"""Colocate models and obs"""
import logging
import xarray as xr
import numpy as np
import xoa.grid
import xesmf as xe

logger = logging.getLogger(__name__)


def colocate_all(obs, mod, flags, tgt_grid, coloc_method='nearest', coloc_method_z=None):
    """
    Colocate the model and observation on the required dimensions, grid and method.
    Parameters
    ----------
    obs : xarray.Dataset
        Observation dataset.
    mod : xarray.Dataset
        Model dataset.
    flags : list of bools
        Time, horizontal and vertical flags.
    tgt_grid :
        Targetted grid on which to colocate:  auto, observation or model.
    coloc_method : str
        Colocation method for horizontal and time dimension.
    coloc_method_z : str
        Colocation method for vertical dimension.

    Returns
    -------
    obs_coloc : xarray.Dataset
        Colocated observation dataset.
    mod_coloc : xarray.Dataset
        Colocated model dataset.
    """
    # Read the colocation flags
    time_flag, hor_flag, ver_flag = flags
    if ver_flag and coloc_method_z is None:
        coloc_method_z = 'nearest'

    # Colocate
    if tgt_grid == 'auto':
        logger.info('Auto colocation : the model and observation will be colocated '
                    'on the regular grid with the minimum step size of the products')
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

    else:
        # Colocate on the observation grid
        if tgt_grid == 'observation':
            logger.info('Colocating the model on the observation grid')
            obs_coloc = obs
            mod_coloc = mod

            # If observation is profiler
            if time_flag and 'time' in obs.lon.dims:
                logger.info('Profiler type colocation')
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
            logger.info('Colocating the observation on the model grid')
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


def temporal_colocation(ds_to_coloc, tgt, coloc_method):
    """
    Temporal colocation of the model and observation.
    Parameters
    ----------
    ds_to_coloc : xarray.Dataset
        Dataset to colocate.
    tgt : xarray.Dataset
        Dataset on which to colocate.
    coloc_method : str
        Colocation method.

    Returns
    -------
    ds_to_coloc : xarray.Dataset
        Colocated dataset.

    """
    logger.info('Time colocation')
    time_values = np.unique(tgt.time.values)
    if len(ds_to_coloc.time.data) > 1:
        ds_to_coloc = ds_to_coloc.interp(time=time_values, method=coloc_method)
    else:
        ds_to_coloc = pick_time(ds_to_coloc, time_values)

    ds_to_coloc = ds_to_coloc.assign_coords(time=tgt.time)

    return ds_to_coloc


def horizontal_colocation(ds_to_coloc, tgt, coloc_method):
    """
    Horizontal colocation of the model and observation.
    Parameters
    ----------
    ds_to_coloc : xarray.Dataset
        Dataset to colocate.
    tgt : xarray.Dataset
        Dataset on which to colocate.
    coloc_method : str
        Colocation method.

    Returns
    -------
    ds_coloc : xarray.Dataset
        Colocated dataset.

    """
    logger.info('Horizontal colocation')

    # Drop duplicates in lon/lat
    if 'lon' in ds_to_coloc.dims:
        ds_to_coloc = ds_to_coloc.drop_duplicates('lon').drop_duplicates('lat')

    # Get lon / lat values
    if 'lon' in tgt.dims:
        lon_values = tgt.drop_duplicates('lon').lon.values
        lat_values = tgt.drop_duplicates('lat').lat.values
    else:
        lon_values = np.unique(tgt.lon.values)
        lat_values = np.unique(tgt.lat.values)

    # If tgt lon/lat depend on x/y (ex if tgt from TOPAZ)
    if 'x' in tgt.dims:
        ds_coloc_xy = []
        for i_x, _ in enumerate(tgt.x):
            tgt_xy = tgt.isel(x=i_x)
            ds_x = ds_to_coloc.interp(lon=tgt_xy.lon.values, lat=tgt_xy.lat.values,
                                      method=coloc_method)
            ds_x = ds_x.stack(y=('lon', 'lat')).reset_index('y')
            ds_x = ds_x.isel(y=range(0, len(ds_x.y) + 1, len(tgt_xy.y) + 1))
            lons = xr.DataArray(ds_x.lon.values, dims='y', coords={'y': tgt_xy.y.values},
                                name='lon')
            lats = xr.DataArray(ds_x.lat.values, dims='y', coords={'y': tgt_xy.y.values},
                                name='lat')
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
            ds_coloc = ds_coloc.transpose(dims[0], dims[1], dims[2], dims[3])

    # Regrid ds if necessary
    elif 'x' in ds_to_coloc.dims:
        if np.size(lon_values) == 1 and np.size(lat_values) == 1:
            ds_coloc = ds_to_coloc.meta.sel_closest(lon_values, lat_values)

        else:
            ds_coloc = convert_curv_rect(ds_to_coloc, lon_values, lat_values)

    else:
        ds_coloc = ds_to_coloc.interp(lon=lon_values, lat=lat_values, method=coloc_method,
                                      kwargs={"fill_value": "extrapolate"})

    return ds_coloc


def vertical_colocation(ds_to_coloc, tgt, coloc_method):
    """
    Vertical colocation of the model and observation.
    Parameters
    ----------
    ds_to_coloc : xarray.Dataset
        Dataset to colocate.
    tgt : xarray.Dataset
        Dataset on which to colocate.
    coloc_method : str
        Colocation method.

    Returns
    -------
    ds_coloc : xarray.Dataset
        Colocated dataset.

    """
    logger.info('Vertical colocation')
    depth_ds = ds_to_coloc.depth
    depth_tgt = tgt.depth

    if coloc_method is None:
        coloc_method = "nearest"

    # Colocate only if needed
    if np.size(depth_tgt) == np.size(depth_ds) and (depth_tgt == depth_ds).all():
        return ds_to_coloc
    else:
        if np.size(depth_tgt) != 1 and np.size(depth_ds) != 1:
            # Case ds and tgt have depth(depth) dimension
            if 'depth' in depth_tgt.dims and 'depth' in depth_ds.dims:
                ds_coloc = ds_to_coloc.interp(depth=depth_tgt, method=coloc_method)

            # Case ds has depth(lon/lat/time) dimension and tgt has depth(depth) dimension
            elif 'depth' in depth_tgt.dims and 'depth' not in depth_ds.dims:
                ds_coloc = ds_to_coloc.meta.vertical_selection_croco_hycom(depth_tgt)

            return ds_coloc
    return ds_to_coloc


def pick_time(ds_to_sel, time_values):
    """Pick data in case of dims['time'] = 1.
    Parameters
    ----------
    ds_to_sel : xarray.Dataset
    time_values : list of times

    Returns
    -------
    ds_sel : xarray.Dataset
    """
    dss = []
    for time_value in time_values:
        ds0 = ds_to_sel.isel(time=[0])
        ds0 = ds0.assign_coords({"time": [time_value]})
        dss.append(ds0)
    ds_sel = xr.concat(dss, "time", compat="no_conflicts", coords="different", data_vars="all")
    return ds_sel


def min_grid_all(obs, mod, horizontal_colocation_flag, vertical_colocation_flag,
                 temporal_colocation_flag):
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
    mod : xarray.Dataset
        Model dataset to be colocated.
    obs : xarray.Dataset
        Observation arget grid dataset on which to colocate.
    method : str
        Method of colocation for time and horizontal dimension.
    method_z : str
        Method of colocation for vertical dimension.

    Returns
    -------
    mod_coloc : xarray.Dataset
        Colocated model.
    """

    # Simplify vertical colocation
    if 'depth' in obs.dims and len(obs.depth.data) == 1:
        mod = mod.meta.vertical_selection_depth(obs.depth.data)
        mod = mod.expand_dims('depth')
        method_z = None

    list_ds = []
    for i, time in enumerate(obs.time.values):
        # Colocation time
        if len(mod.time) > 2:  # Interpolation returns NaN otherwise
            mod_interp = mod.interp(time=time, method=method)
        else:
            mod_interp = mod.sel(time=time, method='nearest')
        mod_interp = mod_interp.assign_coords(time=time)

        # Colocation lon/lat
        if 'lon' in obs.coords:
            lon = obs.lon.isel(time=[i]).values
            lat = obs.lat.isel(time=[i]).values
            if 'lon' in mod_interp.dims:  # For rect. grids
                mod_interp = mod_interp.interp(lon=lon, lat=lat, method=method,
                                               kwargs={"fill_value": "extrapolate"}).squeeze(
                    ['lon', 'lat'])
            elif 'x' in mod_interp.dims:  # For curv. grids
                mod_interp = mod_interp.meta.sel_closest(lon, lat)

        # Colocate depth
        if method_z:
            if 'depth' in obs.dims:
                if 'DEPH' in obs.variables:
                    depth = np.unique(obs.DEPH.fillna(0).values)
                else:
                    depth = np.unique(obs.depth.values)
                if 'depth' not in mod_interp:
                    logger.warning(
                        'Caution : the product you are using does not contain a depth dimension - '
                        'probably a 2D file. The vertical colocation will fail.')

                if 'depth' in mod_interp.dims:
                    mod_interp = mod_interp.interp(depth=depth, method=method_z,
                                                   kwargs={"fill_value": "extrapolate"
                                                           })
                elif 'level' in mod_interp.dims or 'z' in mod_interp.dims:  # Croco or hycom
                    mod_interp = mod_interp.meta.vertical_selection_croco_hycom(depth)
                mod_interp = mod_interp.assign_coords(depth=obs.depth)

            elif 'z' in obs.dims:
                depths = obs.depth.isel(time=i)
                if 'level' in mod_interp.dims or 'z' in mod_interp.dims:  # Croco or hycom
                    mod_interp = mod_interp.meta.vertical_selection_croco_hycom(depths)
                    mod_interp = mod_interp.swap_dims({"depth": 'z'})
                    mod_interp = mod_interp.assign_coords(z=obs.z)
                else:
                    mod_interp = mod_interp.interp(depth=depths, method=method_z)

        list_ds.append(mod_interp)

    mod_coloc = xr.concat(list_ds, 'time')
    return mod_coloc


def get_step_size(ds_to_sel, dim):
    """
    Returns the step size of the dataset along the specified dimension.

    Attributes
    ----------
    ds_to_sel : xarray.Dataset
        Dataset from which to get the resolution.
    dim : str
        Dimension to get the resolution.

    Returns
    -------
    step : float
        Step size along the dimension.
    """

    if dim in ds_to_sel.dims:  # initially was dim in ds.coords
        try:
            if len(ds_to_sel[dim]) > 1:
                step = abs(ds_to_sel[dim][0].data - ds_to_sel[dim][1].data)
            else:
                step = 0
        except step.nan:  # si dim(time= None)
            step = np.nan
    elif dim in ds_to_sel.coords:  # CROCO, lon, lat sont dans coords apres decode_sigma
        try:
            if len(ds_to_sel[dim]) > 1:
                step = abs(ds_to_sel[dim][0].data - ds_to_sel[dim][1].data)
            else:
                step = 0
        except step.nan:
            step = np.nan
    else:
        step = np.nan

    if isinstance(step, np.timedelta64):
        step = step.astype('timedelta64[s]').astype(float)

    if isinstance(step, np.ndarray):
        step = np.nan

    return step


def convert_curv_rect(ds_to_conv, lon, lat):
    """
    Convert curvilinear grid into rectangular grid.
    Parameters
    ----------
    ds_to_conv : xarray.Dataset
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
    regridder = xe.Regridder(ds_to_conv, ds_out, 'bilinear', unmapped_to_nan=True)
    ds_rect = xr.Dataset()
    for var in ds_to_conv.variables:
        if 'x' in ds_to_conv[var].dims and var not in ['lon', 'lat', 'x', 'y']:
            da_rect = regridder(ds_to_conv[var])
            da_rect = xoa.grid.to_rect(da_rect)
            ds_rect[var] = da_rect
    ds_rect = ds_rect.assign_coords(lon=lon, lat=lat)

    return ds_rect
