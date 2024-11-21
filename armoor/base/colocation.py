"""Colocate models and obs"""
import logging, os
import xesmf as xe
import xarray as xr
import numpy as np
import dask
from dask.distributed import Client, LocalCluster
from xoa.regrid import regrid1d, grid2loc
import xoa.geo as xgeo
import xoa.coords as xcoords

logger = logging.getLogger(__name__)

def horizontal_regrid(dsi, dso) -> xr.Dataset:
        """
        Regrid a variable.

        Parameters
        ----------
        dai : xarray.DataArray
            Single variable to regrid.

        Returns
        -------
        xarray.DataArray
            Regridded variable.
        """
        dlon = dso.lon.diff("x").max()
        dlat = dso.lat.diff("y").max()
        
        dso = dso.where((
            dso.lat > dso.lat.min() + dlat
        ) & (
            dso.lat < dso.lat.max() - dlat
        ) & (
            dso.lon > dso.lon.min() + dlon
        ) &(
            dso.lon < dso.lon.max() - dlon
        ), drop=True)
        regridder = xe.Regridder(dsi, dso, "bilinear")
        dsi = regridder(dsi)
        return dsi, dso

def vertical(dsi, dsref) -> xr.Dataset:
    """
    Interpolate at specific vertical levels.

    Parameters
    ----------
    vlevels : list
        List of vertical levels.
    vname : str
        Name of vertical coordinate.
    method : str
        Method of interpolation.

    Returns
    -------
    xarray.Dataset
    """
    logger.info("Vertical interpolation")
    das = []
    for var in dsi.data_vars:
        if "z" in dsi[var].dims:
            da = regrid1d(dsi[var].chunk(dict(z=-1)), dsref.chunk(dict(z=-1)), method="linear")
        else:
            da = dsi[var]
        da.attrs = dsi[var].attrs
        das.append(da)
    dso = xr.merge(das)
    dso.attrs = dsi.attrs
    return dso.load()

def obs_coords_radius_postproc(ds):
    ds = ds.drop(
        ["lon", "lat", "lon_1", "lat_1"]
    )
    ds = ds.rename({
        "lon_0": "lon",
        "lat_0": "lat"
    })
    return ds

def obs_coords_radius(ds_obs, ds_model, radius) -> xr.Dataset:
    """
    Select the closest elements to the observations point located within the specified radius.

    Parameters
    ----------
    ds_obs : xr.Dataset
        Dataset containing observation.

    Returns
    -------
    xarray.Dataset
        Dataset with elements around observation points.
    """
    logger.info("Colocate model on observation: obs_coords_radius")
    ds_model = xcoords.geo_stack(ds_model, "member")

    dss_model = []
    dss_obs = []
    if "time" not in ds_obs.lon.dims:
        dist_model2obs = xgeo.get_distances(
            ds_model,
            ds_obs
        ).squeeze().rename(
            npts0="member"
        ).assign_coords(member=ds_model.member)
        ds = ds_model.where(
            dist_model2obs < radius * 1e3,
            drop=True
        )
        ds_model = obs_coords_radius_postproc(ds)
    else:
        for itime, time in enumerate(ds_obs.time):
            dist_model2obs = xgeo.get_distances(
                ds_model.isel(time=itime),
                ds_obs.isel(time=itime)
            ).squeeze().rename(
                npts0="member"
            ).assign_coords(member=ds_model.member)
            #print(dist_model2obs)
            ds = ds_model.isel(time=itime).where(
                dist_model2obs < radius * 1e3,
                drop=True
            )
            if ds.sizes["member"] == 0:
                continue
            ds = ds.assign_coords({"time": time})
            for coord in ["lon_0", "lat_0"]:
                ds[coord] = ds[coord].expand_dims(dim="time")
            ds = obs_coords_radius_postproc(ds)
            dss_model.append(ds)
            dss_obs.append(ds_obs.isel(time=[itime]))
            ds.close()
        ds_model = xr.combine_nested(dss_model, "time")
        ds_obs = xr.combine_nested(dss_obs, "time")
    if "depth" not in ds_model.coords and "depth" in ds_model.data_vars:
        ds_model = ds_model.set_coords("depth")
    return ds_obs, ds_model

def obs_coords(ds_obs, ds_model) -> xr.Dataset:
    """
    Colocate model on observation whose coordinate depend on time.

    Parameters
    ----------
    ds_obs : xr.Dataset
        Dataset containing observation.

    Returns
    -------
    xarray.Dataset
        Dataset with elements around observation points.
    """
    logger.info("Grid2loc")
    # dlon = ds_model.lon.diff(dim="x").mean().values
    # dlat = ds_model.lat.diff(dim="y").mean().values
    # mask = (
    #     (ds_model.lon > ds_obs.lon.min().values - 2 * dlon) &
    #     (ds_model.lon < ds_obs.lon.max().values + 2 * dlon) &
    #     (ds_model.lat > ds_obs.lat.min().values - 2 * dlat) &
    #     (ds_model.lat < ds_obs.lat.max().values + 2 * dlat) 
    # ).compute()
    # ds_model = ds_model.where(
    #     mask,
    #     drop=True
    # )
    if "depth" in ds_model.coords:
        ds_model = ds_model.reset_coords("depth")
    dss = []
    for var in ds_model.data_vars:
        logger.info(var)
        dain = ds_model[var]
        if "time" in dain.dims:
            loc = xr.Dataset(
                coords={
                    "time": ('time', ds_obs.time.values),
                    "lon": ('time', ds_obs.lon.values),
                    "lat": ('time', ds_obs.lat.values),
                }
            )
        else:
            loc = xr.Dataset(
                coords={
                    "lon": ('time', ds_obs.lon.values),
                    "lat": ('time', ds_obs.lat.values),
                }
            )
        if "z" in dain.dims:
            daout = xr.DataArray(
                data=np.zeros((ds_obs.sizes["time"], ds_model.sizes["z"])),
                dims=["time", "z"],
                coords=dict(
                    time=(["time"], ds_obs.time.values),
                    lat=(["time"], ds_obs.lat.values),
                    lon=(["time"], ds_obs.lon.values),
                )
            )
            cluster = LocalCluster(
                n_workers=os.cpu_count(),
                threads_per_worker=1,
                processes=True,
            )
            client = Client(cluster)
            logger.info(client)
            futures = []
            for iz in range(dain.sizes['z']):
                clargs = (dain.isel(z=iz).load(), loc)
                futures.append(dask.delayed(grid2loc)(*clargs))
            del clargs
            try:
                res = dask.compute(*futures)
            finally:
                daout = client.gather(res)
                daout = xr.concat(daout, "z")
                client.close()
                cluster.close()
                del futures
        else:
            daout = grid2loc(dain, loc)
        dss.append(daout.to_dataset(name=var))

    dso = xr.merge(dss).load()
    if "depth" in dso:
        dso = dso.set_coords("depth")
    return dso

# def colocate_all(obs, mod, flags, tgt_grid, coloc_method='nearest', coloc_method_z=None):
#     """
#     Colocate the model and observation on the required dimensions, grid and method.
#     Parameters
#     ----------
#     obs : xarray.Dataset
#         Observation dataset.
#     mod : xarray.Dataset
#         Model dataset.
#     flags : list of bools
#         Time, horizontal and vertical flags.
#     tgt_grid :
#         Targetted grid on which to colocate:  auto, observation or model.
#     coloc_method : str
#         Colocation method for horizontal and time dimension.
#     coloc_method_z : str
#         Colocation method for vertical dimension.

#     Returns
#     -------
#     obs_coloc : xarray.Dataset
#         Colocated observation dataset.
#     mod_coloc : xarray.Dataset
#         Colocated model dataset.
#     """
#     # Read the colocation flags
#     time_flag, hor_flag, ver_flag = flags
#     if ver_flag and coloc_method_z is None:
#         coloc_method_z = 'nearest'
#     # Colocate
#     if tgt_grid == 'auto':
#         logger.info('Auto colocation : the model and observation will be colocated '
#                     'on the regular grid with the minimum step size of the products')
#         tgt = min_grid_all(obs, mod, hor_flag, ver_flag, time_flag)
#         obs_coloc = obs
#         mod_coloc = mod

#         if time_flag:
#             obs_coloc = temporal_colocation(obs_coloc, tgt, coloc_method)
#             mod_coloc = temporal_colocation(mod_coloc, tgt, coloc_method)
#         if hor_flag:
#             obs_coloc = horizontal_colocation(obs_coloc, tgt, coloc_method)
#             mod_coloc = horizontal_colocation(mod_coloc, tgt, coloc_method)
#         if ver_flag:
#             obs_coloc = vertical_colocation(obs_coloc, tgt, coloc_method)
#             mod_coloc = vertical_colocation(mod_coloc, tgt, coloc_method)

#     else:
#         # Colocate on the observation grid
#         if tgt_grid == 'observation':
#             logger.info('Colocating the model on the observation grid')
#             obs_coloc = obs
#             mod_coloc = mod

#             # If observation is profiler
#             if time_flag and 'time' in obs.lon.dims:
#                 logger.info('Profiler type colocation')
#                 if 'instr' in obs.dims:
#                     mod_coloc = colocate_lon_lat_time_instr(mod, obs, coloc_method, coloc_method_z)
#                 else:
#                     mod_coloc = colocate_lon_lat_time(mod, obs, coloc_method, coloc_method_z)

#             else:
#                 # Temporal colocation
#                 if time_flag:
#                     mod_coloc = temporal_colocation(mod_coloc, obs, coloc_method)
#                 # Horizontal colocation
#                 if hor_flag:
#                     mod_coloc = horizontal_colocation(mod_coloc, obs, coloc_method)
#                 # Vertical colocation
#                 if ver_flag:
#                     mod_coloc = vertical_colocation(mod_coloc, obs, coloc_method_z)
#         # Colocate on the model grid
#         elif tgt_grid == 'model':
#             logger.info('Colocating the observation on the model grid')
#             mod_coloc = mod
#             obs_coloc = obs

#             # Temporal colocation
#             if time_flag:
#                 obs_coloc = temporal_colocation(obs_coloc, mod, coloc_method)

#             # Horizontal colocation
#             if hor_flag:
#                 obs_coloc = horizontal_colocation(obs_coloc, mod, coloc_method)

#             # Vertical colocation
#             if ver_flag:
#                 obs_coloc = vertical_colocation(obs_coloc, mod, coloc_method_z)

#     obs_coloc = coloc_var(obs_coloc)
#     mod_coloc = coloc_var(mod_coloc)

#     return obs_coloc, mod_coloc

# def coloc_var(obj_coloc):
#     if isinstance(obj_coloc, xr.Dataset):
#         logger.info('coloc_var')
#         for var in obj_coloc.variables:
#             if var[0] == 'u':
#                 type = var[1:]
#                 obj_coloc = obj_coloc.sel_var.get_norm_dir(type=type)
#     return obj_coloc

# def temporal_colocation(ds_to_coloc, time, coloc_method="linear"):
#     """
#     Temporal colocation of the model and observation.
#     Parameters
#     ----------
#     ds_to_coloc : xarray.Dataset
#         Dataset to colocate.
#     tgt : xarray.Dataset
#         Dataset on which to colocate.
#     coloc_method : str
#         Colocation method.

#     Returns
#     -------
#     ds_to_coloc : xarray.Dataset
#         Colocated dataset.

#     """
#     logger.info('Time colocation')
#     if len(ds_to_coloc.time.data) > 1:
#         ds_to_coloc = ds_to_coloc.interp(time=times, method=coloc_method)

#     ds_to_coloc = ds_to_coloc.assign_coords(time=tgt.time.data)

#     return ds_to_coloc


# def horizontal_colocation(ds_to_coloc, tgt, coloc_method):
#     """
#     Horizontal colocation of the model and observation.
#     Parameters
#     ----------
#     ds_to_coloc : xarray.Dataset
#         Dataset to colocate.
#     tgt : xarray.Dataset
#         Dataset on which to colocate.
#     coloc_method : str
#         Colocation method.

#     Returns
#     -------
#     ds_coloc : xarray.Dataset
#         Colocated dataset.

#     """
#     logger.info('Horizontal colocation')

#     # Drop duplicates in lon/lat
#     if 'lon' in ds_to_coloc.dims:
#         ds_to_coloc = ds_to_coloc.drop_duplicates('lon').drop_duplicates('lat')

#     # Get lon / lat values
#     if 'lon' in tgt.dims:
#         lon_values = tgt.drop_duplicates('lon').lon.values
#         lat_values = tgt.drop_duplicates('lat').lat.values
#     else:
#         lon_values = np.unique(tgt.lon.values)
#         lat_values = np.unique(tgt.lat.values)

#     # If tgt lon/lat depend on x/y (ex if tgt from TOPAZ)
#     if 'x' in tgt.dims:
#         ds_coloc_xy = []
#         for i_x, _ in enumerate(tgt.x):
#             tgt_xy = tgt.isel(x=i_x)
#             ds_x = ds_to_coloc.interp(lon=tgt_xy.lon.values, lat=tgt_xy.lat.values,
#                                       method=coloc_method)
#             ds_x = ds_x.stack(y=('lon', 'lat')).reset_index('y')
#             ds_x = ds_x.isel(y=range(0, len(ds_x.y) + 1, len(tgt_xy.y) + 1))
#             lons = xr.DataArray(ds_x.lon.values, dims='y', coords={'y': tgt_xy.y.values},
#                                 name='lon')
#             lats = xr.DataArray(ds_x.lat.values, dims='y', coords={'y': tgt_xy.y.values},
#                                 name='lat')
#             ds_x = ds_x.assign_coords({'lon': lons, 'lat': lats})
#             ds_coloc_xy.append(ds_x)

#         ds_coloc = xr.concat(ds_coloc_xy, 'x')
#         ds_coloc = ds_coloc.assign_coords(tgt.coords)

#         # Make sure x y are in the same order in both datasets
#         dims = list(tgt.dims.keys())
#         if len(dims) == 2:
#             ds_coloc = ds_coloc.transpose(dims[0], dims[1])
#         elif len(dims) == 3:
#             ds_coloc = ds_coloc.transpose(dims[0], dims[1], dims[2])
#         elif len(dims) == 4:
#             ds_coloc = ds_coloc.transpose(dims[0], dims[1], dims[2], dims[3])

#     # Regrid ds if necessary
#     elif 'x' in ds_to_coloc.dims:
#         if np.size(lon_values) == 1 and np.size(lat_values) == 1:
#             ds_coloc = ds_to_coloc.meta.sel_closest(lon_values, lat_values)

#         else:
#             ds_coloc = convert_curv_rect(ds_to_coloc, lon_values, lat_values)

#     else:
#         # Fill Nans for the interpolation
#         ds_to_coloc = ds_to_coloc.sortby('lon')
#         ds_to_coloc = ds_to_coloc.interpolate_na(dim='lon', method=coloc_method)
#         ds_coloc = ds_to_coloc.interp(lon=lon_values, lat=lat_values, method=coloc_method)

#     return ds_coloc


# def vertical_colocation(ds_to_coloc, tgt, coloc_method):
#     """
#     Vertical colocation of the model and observation.
#     Parameters
#     ----------
#     ds_to_coloc : xarray.Dataset
#         Dataset to colocate.
#     tgt : xarray.Dataset
#         Dataset on which to colocate.
#     coloc_method : str
#         Colocation method.

#     Returns
#     -------
#     ds_coloc : xarray.Dataset
#         Colocated dataset.

#     """
#     logger.info('Vertical colocation')
#     depth_ds = ds_to_coloc.depth
#     depth_tgt = tgt.depth

#     if coloc_method is None:
#         coloc_method = "nearest"

#     # Colocate only if needed
#     if np.size(depth_tgt) == np.size(depth_ds) and (depth_tgt == depth_ds).all():
#         return ds_to_coloc
#     else:
#         if np.size(depth_tgt) != 1 and np.size(depth_ds) != 1:
#             # Case ds has lat(lat) dimension
#             if 'lat' in ds_to_coloc.dims and 'lat' not in tgt.dims:
#                 ds_to_coloc = ds_to_coloc.squeeze()
#                 ds_coloc = ds_to_coloc.interp(depth=depth_tgt, method=coloc_method)

#             # Case ds and tgt have depth(depth) dimension
#             elif 'depth' in depth_tgt.dims and 'depth' in depth_ds.dims:
#                 ds_coloc = ds_to_coloc.interp(depth=depth_tgt, method=coloc_method)

#             # Case ds has depth(lon/lat/time) dimension and tgt has depth(depth) dimension
#             elif 'depth' in depth_tgt.dims and 'depth' not in depth_ds.dims:
#                 ds_coloc = ds_to_coloc.meta.vertical_selection_croco_hycom(depth_tgt)

#             return ds_coloc
#     return ds_to_coloc


# def pick_time(ds_to_sel, time_values):
#     """Pick data in case of dims['time'] = 1.
#     Parameters
#     ----------
#     ds_to_sel : xarray.Dataset
#     time_values : list of times

#     Returns
#     -------
#     ds_sel : xarray.Dataset
#     """
#     dss = []
#     for time_value in time_values:
#         ds0 = ds_to_sel.isel(time=[0])
#         ds0 = ds0.assign_coords({"time": [time_value]})
#         dss.append(ds0)
#     ds_sel = xr.concat(dss, "time", compat="no_conflicts", coords="different", data_vars="all")
#     return ds_sel


# def min_grid_all(obs, mod, horizontal_colocation_flag, vertical_colocation_flag,
#                  temporal_colocation_flag):
#     """
#     Gives the grid that has the minimum resolution along each dimension
#     of the observation and model.
#     Parameters
#     ----------
#     obs : xarray.Dataset
#         Observation dataset.
#     mod : xarray.Dataset
#         Model dataset.
#     horizontal_colocation_flag : bool
#         Colocate on horizontal (lon/lat) dimension or not.
#     vertical_colocation_flag : bool
#         Colocate on vertical (depth) dimension or not.
#     temporal_colocation_flag : bool
#         Colocate on temporal (time) dimension or not.

#     Returns
#     -------
#     tgt_grid : xarray.Dataset
#         Grid on which to colocate the model and observation, with the minimum resolution.
#     """
#     dims = []
#     if horizontal_colocation_flag:
#         dims.append('lon')
#         dims.append('lat')
#     if vertical_colocation_flag:
#         dims.append('depth')
#     if temporal_colocation_flag:
#         dims.append('time')

#     dict_coords = min_dimensions(obs, mod, dims)
#     tgt_grid = xr.DataArray(dims=dims, coords=dict(dict_coords))
#     return tgt_grid


# def min_dimensions(obs, mod, dims):
#     """
#     Gives the minimum resolution of the model and observation dataset
#     to build the grid for the colocation.
#     Parameters
#     ----------
#     obs : xarray.Dataset
#         Observation dataset.
#     mod : xarray.Dataset
#         Model dataset.
#     dims : list of str
#         Dimensions on which to take the minimum resolution.

#     Returns
#     -------
#     tgt_dims_values : dict
#         Values of the grid along each dimension.
#     """
#     tgt_dims_values = {}
#     for dim in dims:
#         step_mod = get_step_size(mod, dim)
#         step_obs = get_step_size(obs, dim)
#         max_val = np.nanmax([step_obs, step_mod])
#         if not np.isnan(max_val):  # the dimension is either in the model or the observation
#             if max_val == step_mod:
#                 tgt_dims_values[dim] = mod[dim]
#             else:
#                 tgt_dims_values[dim] = obs[dim]

#     return tgt_dims_values


# def colocate_lon_lat_time_instr(mod, obs, method, method_z):
#     list_mod_instr = []
#     for i, _ in enumerate(obs.instr.values):
#         obs_i = obs.isel(instr=i)
#         mod_i = colocate_lon_lat_time(mod, obs_i, method, method_z)
#         list_mod_instr.append(mod_i)
#     mod_coloc = xr.concat(list_mod_instr, 'instr')
#     return mod_coloc


# def colocate_lon_lat_time(mod, obs, method, method_z):
#     """
#     Colocate a datased on the target grid using the colocation method defined.
#     Parameters
#     ----------
#     mod : xarray.Dataset
#         Model dataset to be colocated.
#     obs : xarray.Dataset
#         Observation arget grid dataset on which to colocate.
#     method : str
#         Method of colocation for time and horizontal dimension.
#     method_z : str
#         Method of colocation for vertical dimension.

#     Returns
#     -------
#     mod_coloc : xarray.Dataset
#         Colocated model.
#     """

#     # Simplify vertical colocation
#     if 'depth' in obs.dims and len(obs.depth.data) == 1:
#         mod = mod.meta.vertical_selection_depth(obs.depth.data)
#         mod = mod.expand_dims('depth')
#         method_z = None
#     list_ds = []
#     for i, time in enumerate(obs.time.values):
#         # Colocation time
#         if len(mod.time) > 2:  # Interpolation returns NaN otherwise
#             mod_interp = mod.interp(time=time, method=method)
#         else:
#             mod_interp = mod.sel(time=time, method='nearest')
#         mod_interp = mod_interp.assign_coords(time=time)
#         # Colocation lon/lat
#         if 'lon' in obs.coords:
#             lon = obs.lon.isel(time=[i]).values
#             lat = obs.lat.isel(time=[i]).values
#             if 'lon' in mod_interp.dims:  # For rect. grids
#                 mod_interp = mod_interp.interp(lon=lon, lat=lat, method=method, kwargs={"fill_value": "extrapolate"}).squeeze(['lon', 'lat'])  #
#             elif 'x' in mod_interp.dims:  # For curv. grids
#                 mod_interp = mod_interp.meta.sel_closest(lon, lat)
#         # Colocate depth
#         if method_z:
#             if 'depth' in obs.dims:
#                 if 'DEPH' in obs.variables:
#                     depth = np.unique(obs.DEPH.fillna(0).values)
#                 else:
#                     depth = np.unique(obs.depth.values)
#                 if 'depth' not in mod_interp:
#                     logger.warning(
#                         'Caution : the product you are using does not contain a depth dimension - '
#                         'probably a 2D file. The vertical colocation will fail.')

#                 if 'depth' in mod_interp.dims:
#                     mod_interp = mod_interp.interp(depth=depth, method=method_z,
#                                                    kwargs={"fill_value": "extrapolate"
#                                                            })
#                 elif 'level' in mod_interp.dims or 'z' in mod_interp.dims:  # Croco or hycom
#                     mod_interp = mod_interp.meta.vertical_selection_croco_hycom(depth)
#                 mod_interp = mod_interp.assign_coords(depth=obs.depth)

#             elif 'z' in obs.dims:
#                 depths = obs.depth.isel(time=i)
#                 if 'level' in mod_interp.dims or 'z' in mod_interp.dims:  # Croco or hycom
#                     mod_interp = mod_interp.meta.vertical_selection_croco_hycom(depths)
#                     mod_interp = mod_interp.swap_dims({"depth": 'z'})
#                     mod_interp = mod_interp.assign_coords(z=obs.z)
#                 else:
#                     mod_interp = mod_interp.interp(depth=depths, method=method_z)

#         list_ds.append(mod_interp)

#     mod_coloc = xr.concat(list_ds, 'time')
#     return mod_coloc


# def get_step_size(ds_to_sel, dim):
#     """
#     Returns the step size of the dataset along the specified dimension.

#     Attributes
#     ----------
#     ds_to_sel : xarray.Dataset
#         Dataset from which to get the resolution.
#     dim : str
#         Dimension to get the resolution.

#     Returns
#     -------
#     step : float
#         Step size along the dimension.
#     """

#     if dim in ds_to_sel.dims:  # initially was dim in ds.coords
#         try:
#             if len(ds_to_sel[dim]) > 1:
#                 step = abs(ds_to_sel[dim][0].data - ds_to_sel[dim][1].data)
#             else:
#                 step = 0
#         except step.nan:  # si dim(time= None)
#             step = np.nan
#     elif dim in ds_to_sel.coords:  # CROCO, lon, lat sont dans coords apres decode_sigma
#         try:
#             if len(ds_to_sel[dim]) > 1:
#                 step = abs(ds_to_sel[dim][0].data - ds_to_sel[dim][1].data)
#             else:
#                 step = 0
#         except step.nan:
#             step = np.nan
#     else:
#         step = np.nan

#     if isinstance(step, np.timedelta64):
#         step = step.astype('timedelta64[s]').astype(float)

#     if isinstance(step, np.ndarray):
#         step = np.nan

#     return step


# def convert_curv_rect(ds_to_conv, lon, lat):
#     """
#     Convert curvilinear grid into rectangular grid.
#     Parameters
#     ----------
#     ds_to_conv : xarray.Dataset
#         Curvilinear dataset to convert.
#     lon : array
#         Longitude values.
#     lat : array
#         Latitude values.

#     Returns
#     -------
#     ds_rect : xarray.Dataset
#         Dataset converted on a regular grid.

#     """
#     lon_min, lon_max, step_lon = np.min(lon), np.max(lon), (np.max(lon) - np.min(lon)) / len(lon)
#     lat_min, lat_max, step_lat = np.min(lat), np.max(lat), (np.max(lat) - np.min(lat)) / len(lat)
#     ds_out = xe.util.grid_2d(lon_min, lon_max, step_lon, lat_min, lat_max, step_lat)
#     regridder = xe.Regridder(ds_to_conv, ds_out, 'bilinear', unmapped_to_nan=True)
#     ds_rect = xr.Dataset()
#     for var in ds_to_conv.variables:
#         if 'x' in ds_to_conv[var].dims and var not in ['lon', 'lat', 'x', 'y']:
#             da_rect = regridder(ds_to_conv[var])
#             da_rect = xoa.grid.to_rect(da_rect)
#             ds_rect[var] = da_rect
#     ds_rect = ds_rect.assign_coords(lon=lon, lat=lat)

#     return ds_rect
