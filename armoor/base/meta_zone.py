"""MetazonAccessor
"""
from datetime import datetime
import pandas
import xarray as xr
from shapely.geometry import Point
import numpy as np
from xoa.regrid import regrid1d
import matplotlib.path as path
import math

import logging

logger = logging.getLogger(__name__)


@xr.register_dataarray_accessor("meta")
@xr.register_dataset_accessor("meta")
class MetazoneAccessor:
    """
    Select a subset of the original object filtering elements with conditions across certain dimensions.

    Attributes
    ----------
    xarray_obj : xarray.Dataset
        Observation dataset to subset.
    """

    def __init__(self, xarray_obj):
        self._obj = xarray_obj

    def var_selection(self, vars):
        """
        Select the variable in the dataset.
        Parameters
        ----------
        vars : str
            Variable(s) to select

        Returns
        -------
        xarray.Dataset
            Dataset with the selected parameters
        """
        logger.info(f"Applying filter - var_selection")
        # create list of variables to keep
        list_names = ['lon', 'lat', 'time', 'depth', 'bathy']
        if 'temp' in vars:
            if type(self._obj.xoa.temp) is xr.core.dataarray.DataArray:
                list_names.append(self._obj.xoa.temp.name)
        if 'sal' in vars:
            if type(self._obj.xoa.sal) is xr.core.dataarray.DataArray:
                list_names.append(self._obj.xoa.sal.name)
        if 'dens' in vars:
            if type(self._obj.xoa.dens) is xr.core.dataarray.DataArray:
                list_names.append(self._obj.xoa.dens.name)
        if 'sndspd' in vars:
            if type(self._obj.xoa.sndspd) is xr.core.dataarray.DataArray:
                list_names.append(self._obj.xoa.sndspd.name)
        if 'gbt' in vars:
            if type(self._obj.xoa.ugbt) is xr.core.dataarray.DataArray:
                list_names.append(self._obj.xoa.ugbt.name)
                list_names.append(self._obj.xoa.vgbt.name)
        if 'mld' in vars:
            if type(self._obj.xoa.mld) is xr.core.dataarray.DataArray:
                list_names.append(self._obj.xoa.mld.name)
        if 'uv' in vars:
            if type(self._obj.xoa.u) is xr.core.dataarray.DataArray:
                list_names.append(self._obj.xoa.u.name)
                list_names.append(self._obj.xoa.v.name)

        # remove the other variables
        for var in self._obj.variables:
            if var not in list_names:
                self._obj = self._obj.drop_vars(var)

        return self._obj

    def quality_filter(self, quality: (str, int, int) = (None, None, None)) -> xr.Dataset:
        """
        Subset dataset filtering quality levels.

        Parameters
        ----------
        quality : (int, int)
            Minimal, Maximal quality level.

        Returns
        -------
        xarray.Dataset
            Dataset filtered with quality levels input restrictions.
        """
        logger.info(f"Applying filter - quality_filter")
        var, min_q, max_q = quality

        if var not in self._obj:
            var = "quality_level"

        if var in self._obj:
            if min_q and max_q:
                selection = (self._obj[var] >= min_q) & (self._obj[var] <= max_q)
            elif min_q:
                selection = (self._obj[var] >= min_q)
            elif max_q:
                selection = (self._obj[var] <= max_q)
            else:
                # nor max nor min nor value provided, there are no restriction to apply
                # we return the original dataset
                return self._obj
            if selection.any():
                return self._obj.where(selection, drop=True)
            else:
                return None
        else:
            # there is no quality to select
            return self._obj

    def horizontal_selection_polygon(self, coords: [(float, float)], ) -> xr.Dataset:
        """
        Subset dataset selecting elements located within the polygon geometry.

        Parameters
        ----------
        coords : list of tuples
           Set of points coordinates defining the geometry of the polygon.

        Returns
        -------
        xarray.Dataset
           Dataset with elements included inside the polygon.

        See Also
        --------
        https://matplotlib.org/stable/api/path_api.html
        """
        logger.info(f"Applying filter - horizontal_selection_polygon")
        # Create the polygon where to subset
        p = path.Path(coords)

        # Depending on the coordinate system, flag the points outside the polygon
        if 'lon' in self._obj.dims:  # Check if rect coordinates
            ds_coords = [(lon, lat) for lon in self._obj.lon.data for lat in self._obj.lat.data]
            flags = p.contains_points(ds_coords)
            mask_poly = np.reshape(flags, (len(self._obj.lon.data), len(self._obj.lat.data)))
            mask_poly = xr.DataArray(data=mask_poly, dims=['lon', 'lat'],
                                     coords=dict(lon=('lon', self._obj.lon.data), lat=('lat', self._obj.lat.data)), )
        elif 'x' in self._obj.dims:  # Check if curv coordinates
            lons, lats = self._obj.lon.data.flatten(), self._obj.lat.data.flatten()
            ds_coords = [(lons[i], lats[i]) for i in range(len(lons))]

            flags = p.contains_points(ds_coords)

            mask_poly = np.reshape(flags, [len(self._obj.y.data), len(self._obj.x.data)])
            mask_poly = xr.DataArray(data=mask_poly, dims=['y', 'x'],
                                     coords=dict(x=(['x'], self._obj.x.data), y=(['y'], self._obj.y.data)), )
        # Check if the polygon matches the coordinates of the data
        if True not in mask_poly:
            raise Exception('The polygon you have defined is not included in the data grid. '
                            'The horizontal selection does not work.')

        # Remove points outside the polygon
        self._obj = self._obj.where(mask_poly, drop=True)
        return self._obj

    def data_selection(self, dim: str, minimum: float = None, maximum: float = None, value: float = None) -> xr.Dataset:
        """
        Subset dataset filtering elements values along the specified dimension.

        Parameters
        ----------
        dim : str
            Dimension whom to apply the filter.
        minimum : float
            Minimum value kept.
        maximum : float
            Maximum value kept.
        value : float
            Only value kept (i.e. maximum = minimum).

        Returns
        -------
        xarray.Dataset
             Dataset with elements values meeting the condition(s).
        """
        logger.info(f"Applying filter - data_selection")

        if value is not None:
            selection = self._obj[dim] == value
        elif minimum is not None and maximum is not None:
            selection = (self._obj[dim] >= minimum) & (self._obj[dim] <= maximum)
        elif minimum is not None:
            selection = (self._obj[dim] >= minimum)
        elif maximum is not None:
            selection = (self._obj[dim] <= maximum)
        else:
            # nor max nor min nor value provided, there are no restriction to apply
            # we return the original dataset
            return self._obj
        return self._obj.where(selection, drop=True)

    def horizontal_selection_coords(self, coordinates: [(float, float)], method: str = None) -> xr.Dataset:
        """
        Subset dataset selecting elements located in cloud of specified dots plus those in a certain radius.

        Parameters
        ----------
        coordinates : list of tuples
            Set of points coordinates (lon, lat) defining the coordinates to select.
        method : str
            Method to select or interpolate the data.

        Returns
        -------
        xarray.Dataset
            Dataset with elements included inside the cloud/area.
        """
        logger.info(f"Applying filter - horizontal_selection_coords")

        lon_target = [lon for lon, lat in coordinates]
        lat_target = [lat for lon, lat in coordinates]

        if 'lon' in self._obj.dims:  # Regular grid
            if method in ["linear"]:
                return self._obj.interp(lon=lon_target, lat=lat_target, method=method)
            else:
                return self._obj.sel(lon=lon_target, lat=lat_target, method=method)
        elif 'x' in self._obj.dims:  # Curvilinear grid
            return self._obj.meta.sel_closest(lon_target, lat_target)

    def horizontal_selection_from_obs_radius(self, config_obj) -> xr.Dataset:
        """
        Subset dataset selecting the closest elements to the observations point located within the specified radius.

        Parameters
        ----------
        config_obj : dict
            Models, observation and meta-zone zone parameters from the parser.

        Returns
        -------
        xarray.Dataset
            Dataset with elements included inside the cloud/area.
        """

        radius = config_obj["meta_zones"]["radius"]

        obs = config_obj['observation']["xarray_meta"]
        obs_lon, obs_lat = obs.lon.values, obs.lat.values
        if obs_lon.size > 1:
            obs_lon, obs_lat = obs_lon[0], obs_lat[0]

        self._obj = self._obj.sel(lon=obs_lon, lat=obs_lat, method='nearest')
        distance = np.sqrt((self._obj.lon.values - obs_lon) ** 2 + (self._obj.lat.values - obs_lat) ** 2)
        radius_km = self._obj.meta.km_to_deg(radius)

        if distance > radius_km:
            logger.info(f'Oops, le modèle ne contient pas de point qui respecte le critère '
                        f'de rayon. Le point le plus proche est utilisé, à la position {xarray_obj.lat.data}N '
                        f'{xarray_obj.lon.data}E .')

        return self._obj

    def sel_closest(self, lon_target, lat_target):
        """

        Parameters
        ----------
        lon_target : float
        lat_target : float

        Returns
        -------
        x, y coordinates
        """
        logger.info(f"Applying filter - sel_closest")
        mindist = 100000
        i = 0
        j = 0
        for it in self._obj.x.values:
            for jt in self._obj.y.values:
                ds = self._obj.isel(x=it, y=jt)

                lon0, lat0, lon1, lat1 = ds.lon.values, ds.lat.values, lon_target, lat_target
                deg2rad = math.pi / 180.0
                dist = math.sin(deg2rad * (lat0 - lat1) * 0.5) ** 2
                dist += (math.cos(deg2rad * lat0) * math.cos(deg2rad * lat1) * math.sin(
                    deg2rad * (lon0 - lon1) * 0.5) ** 2)
                dist = 2.0 * math.asin(math.sqrt(dist))

                if dist <= mindist:
                    i = it
                    j = jt
                    mindist = dist

        ds = self._obj.isel(x=i, y=j)

        return ds

    def horizontal_selection_cloud_dots(self, cloud: [(float, float)], radius_km: float = 0.,
                                        method: str = None) -> xr.Dataset:
        """
        Subset dataset selecting elements located in cloud of specified dots plus those in a certain radius.

        Parameters
        ----------
        cloud : list of tuples
            Set of points coordinates (lon, lat) defining the cloud.
        radius_km : float
            Radius around the points to expand the considered area.

        Returns
        -------
        xarray.Dataset
            Dataset with elements included inside the cloud/area.
        """
        logger.info(f"Applying filter - horizontal_selection_cloud_dots")
        if radius_km == 0. or radius_km is None:
            return self._obj.meta.horizontal_selection_coords(cloud, method)
        else:
            radius = self._obj.meta.km_to_deg(radius_km)
            liste_ds = []
            idx_centre = 0
            lons, lats = cloud
            for i in range(len(lons)):
                lon, lat = lons[i], lats[i]
                tgt_lon = []
                tgt_lat = []
                point_cloud = Point(lon, lat).buffer(radius)
                for lon in self._obj.lon.data:
                    for lat in self._obj.lat.data:

                        if Point(lon, lat).within(point_cloud):
                            tgt_lon.append(lon)
                            tgt_lat.append(lat)
                tgt_lat = xr.DataArray(tgt_lat, dims='idx_point')
                tgt_lon = xr.DataArray(tgt_lon, dims='idx_point')

                ds = self._obj.sel(lon=tgt_lon, lat=tgt_lat)
                ds = ds.assign_coords(idx_centre=idx_centre)
                liste_ds.append(ds)

                idx_centre += 1

            if len(liste_ds) > 1:
                ds_all = xr.concat(liste_ds, 'idx_point', combine_attrs="drop")  # plusieurs point dans cloud
            else:
                ds_all = liste_ds[0]
            return ds_all

    def km_to_deg(self, radius_km):
        """
        Convert the km into degrees.
        Parameters
        ----------
        radius_km : float
            Radius value in km to convert into deg.

        Returns
        -------
        rad_lat_deg : float
            Radius converted into degrees.
        """
        lat_mean = float(self._obj.lat.mean().data)
        r_terre = 6371
        r_lat = r_terre * np.cos(lat_mean * np.pi / 180)
        rad_lon_deg = radius_km * 360 / (2 * np.pi * r_terre)
        rad_lat_deg = radius_km * 360 / (2 * np.pi * r_lat)

        return rad_lat_deg

    def horizontal_selection_bathy(self, minimum: float = None, maximum: float = None, ) -> xr.Dataset:
        """
        Subset dataset selecting elements whom bathymetry values are included in the specified bathymetry range.

        Parameters
        ----------
        minimum : float
            Minimum bathymetry value kept.
        maximum : float
            Maximum bathymetry value kept.

        Returns
        -------
        xarray.Dataset
             Dataset with bathymetry values meeting the condition(s).

        See Also
        --------
        cli.base.meta_zone.MetazoneAccessor.data_selection
        """

        logger.info(f"Applying filter - horizontal_selection_bathymetry")
        return self.data_selection(dim='bathy', minimum=minimum, maximum=maximum)

    def vertical_selection_depth(self, depth: list = None) -> xr.Dataset:
        """

        Parameters
        ----------
        depth

        Returns
        -------

        """
        logger.info(f"Applying filter - vertical_selection_depth")
        if depth and len(depth) == 1:
            return self.vertical_selection_ponct(depth[0], 'depth')
        elif depth:  # if output=profiles, only this option should apply
            return self.vertical_selection_range(depth, 'depth')
        else:
            return self._obj

    def vertical_selection_dens(self, depth: list = None) -> xr.Dataset:
        """

        Parameters
        ----------
        depth

        Returns
        -------

        """
        logger.info(f"Applying filter - vertical_selection_dens")
        if depth and len(depth) == 1:
            return self.vertical_selection_ponct(depth[0], 'dens')
        elif depth:  # if output=profiles, only this option should apply
            return self.vertical_selection_range(depth, 'dens')
        else:
            return self._obj

    def vertical_selection_ponct(self, depth: float, var_vert: str = 'depth') -> xr.Dataset:
        """
        Subset dataset selecting elements whom depth values are included in the specified depth range.

        Parameters
        ----------
        depth : float
            Only depth value kept (i.e. maximum = minimum).
        var_vert : str
            Variable on which to select the vertical : depth or density.
        Returns
        -------
        xarray.Dataset
             Dataset with depth values meeting the condition(s).

        See Also
        --------
        cli.base.meta_zone.MetazoneAccessor.data_selection
        """
        logger.info(f"Applying filter - vertical_selection_ponct")
        ds = self._obj
        if var_vert == 'depth':
            if 'depth' in ds.dims and len(ds.depth.dims) == 1:  # check if NEMO or TOPAZ
                return ds.sel(depth=depth, method='nearest')
            elif 'z' in ds.dims or 'level' in ds.dims or (
                    depth in ds.dims and len(ds.depth.dims) == 2):  # check if CROCO or HYCOM or profile
                tgt_depth = xr.DataArray([depth], dims="depth", name="depth")
                tgt_ds = ds
                for var in self._obj.variables:
                    if var == 'depth' or 'DEPH' in var:
                        tgt_ds = tgt_ds.drop_vars(var)
                    else:
                        for var_depth in ['level', 'z', 'DEPTH', 'sig']:
                            if var_depth in ds[var].dims and len(ds[var][var_depth]) > 1:
                                da = self._obj[var]
                                da_tgt = regrid1d(da, tgt_depth)
                                tgt_ds = tgt_ds.assign({var: da_tgt})
                return tgt_ds
            else:
                return ds
        elif var_vert == 'dens':
            return ds.sel(dens=depth, method='nearest')

    def vertical_selection_range(self, depth: list, var_vert: str = 'depth') -> xr.Dataset:
        """
        Subset dataset selecting elements whom depth values are included in the specified depth range.

        Parameters
        ----------
        depth : List
            List of float with minimum value, maximum value and number of steps.
        var_vert : str
            Vertical dimension to select

        Returns
        -------
        xarray.Dataset
             Dataset with depth values meeting the condition(s).

        See Also
        --------
        cli.base.meta_zone.MetazoneAccessor.data_selection
        """
        logger.info(f"Applying filter - vertical_selection_range")
        # Get min and max values
        min = depth[0]
        max = depth[1]
        # Select all depth between min and max
        if len(depth) == 2:
            selection = ((self._obj[var_vert] >= min) & (self._obj[var_vert] <= max))
            # return self._obj.where(selection, drop=True)
            return self._obj.where(self._obj.depth < 130, drop=True)

        # Select between min and max with a specific number of depths between
        elif len(depth) > 2:
            step = depth[2]
            depths = np.linspace(min, max, int(step))
            return self.vertical_selection_list(depths)

    def vertical_selection_list(self, depths: list) -> xr.Dataset:
        """
        Subset dataset selecting elements whom depth values are included in the specified depth range.

        Parameters
        ----------
        depths : List
            List of float of depths to select.

        Returns
        -------
        xarray.Dataset
             Dataset with depth values meeting the condition(s).

        See Also
        --------
        cli.base.meta_zone.MetazoneAccessor.data_selection
        """
        logger.info(f"Applying filter - vertical_selection_list")
        if 'depth' in self._obj.dims:  # Selection for NEMO or TOPAZ
            return self._obj.sel(depth=depths, method='nearest')

        elif 'z' in self._obj.dims or 'level' in self._obj.dims:  # Selection for CROCO or HYCOM
            tgt_depth = xr.DataArray(depths, name="depth", dims="depth")
            tgt_ds = self._obj
            for var in self._obj.variables:
                if var == 'depth':
                    tgt_ds = tgt_ds.drop_vars(var)
                elif 'level' in self._obj[var].dims or 'z' in self._obj[var].dims:
                    da = self._obj[var]
                    da_tgt = regrid1d(da, tgt_depth)
                    tgt_ds = tgt_ds.assign({var: da_tgt})
            return tgt_ds

    def vertical_selection_slice(self, slice: str = None, var_slice: str = None) -> xr.Dataset:
        """Return a new Dataset whose data is sorted per depth slice.

        Parameters
        ----------
        slice : float
            Size of the vertical slices

        Returns
        -------
        xarray.Dataset
            same Dataset averaged over the time interval
        """
        logger.info(f"Applying filter - vertical_selection_slice")

        if 'depth' not in self._obj.dims:
            depth_values = np.unique(self._obj.depth.data)

            if len(depth_values) > len(self._obj.z.data):
                logger.info(f"too many unique depth values, the grid is resampled with only {len(self._obj.z.data)}"
                            f" values")
                depth_values = np.linspace(depth_values[0], depth_values[-1], len(self._obj.z.data))
            self._obj = self._obj.meta.vertical_selection_list(depth_values)

        start = self._obj.isel(depth=[0])[var_slice].data[0]
        end = self._obj.isel(depth=[-1])[var_slice].data[0]
        vertical_slice = pandas.interval_range(start=start, end=end, freq=float(slice))
        ds_group = self._obj.groupby_bins(var_slice, vertical_slice)
        liste_ds = []

        for label, ds in ds_group:
            label = str(label)[1:-1].replace(", ", " to ") + ' '
            ds['slice_label'] = label
            liste_ds.append(ds)

        for i in range(len(liste_ds)):
            ds = liste_ds[i]
            ds = ds.assign_coords(slice=i)  # ajoute une dimension de date moyenne sur l'intervalle
            ds[var_slice + "_value"] = ds[var_slice]
            ds = ds.assign_coords(depth=np.arange(len(ds[var_slice])))  # change les dates en indices
            liste_ds[i] = ds

        ds = xr.concat(liste_ds, 'slice')
        ds = ds.rename({var_slice: 'idx_' + var_slice})
        ds = ds.rename({var_slice + '_value': var_slice})
        ds['slice'] = ds['slice_label']
        return ds

    def time_selection_start(self, start=None) -> xr.Dataset:
        """
        Subset dataset selecting elements starting after one defined date.
        Parameters
        ----------
        start : str
            Date at which to start the selection.

        Returns
        -------
        xarray.Dataset
             Dataset with density values meeting the condition(s).
        """
        logger.info(f"Applying filter - time_selection_start")
        if isinstance(start, int):
            return self.time_selection_relative(start, None)
        else:
            return self.time_selection_absolute(start, None)

    def time_selection_end(self, end=None) -> xr.Dataset:
        """
        Subset dataset selecting elements ending before one selected date.
        Parameters
        ----------
        end : str
            Date at which to start the selection.

        Returns
        -------
        xarray.Dataset
             Dataset with density values meeting the condition(s).
        """
        logger.info(f"Applying filter - time_selection_end")
        if isinstance(end, int):
            return self.time_selection_relative(None, end)
        else:
            return self.time_selection_absolute(None, end)

    def time_selection_absolute(self, start: str = None, end: str = None) -> xr.Dataset:
        """
        Subset dataset filtering elements along time dimension, selecting dates within a specified period.

        Parameters
        ----------
        start : str
            values kept from "start"
        end : str
            values kept until "end"

        Returns
        -------
        xarray.Dataset
             Dataset with date times included in the specified period.

        See Also
        --------
        https://docs.python.org/fr/3/library/datetime.html
        https://docs.python.org/3/library/datetime.html
        """
        logger.info(f"Applying filter - time_selection_absolute")
        if start == end:
            return self._obj.sel(time=start, method='nearest')

        else:
            return self._obj.sel(time=slice(start, end))

    def time_selection_relative(self, start: int = None, end: int = None) -> xr.Dataset:
        """
        Subset dataset filtering elements along time dimension, selecting dates within a specified period.

        Parameters
        ----------
        start : int
            values kept from "start", number of days relative to today's day at OO AM
        end : int
            values kept until "end", number of days relative to today's day at OO AM

        Returns
        -------
        xarray.Dataset
             Dataset with date times included in the specified period.

        See Also
        --------
        https://docs.python.org/fr/3/library/datetime.html
        https://docs.python.org/3/library/datetime.html
        """

        logger.info(f"Applying filter - time_selection_relative")
        now = pandas.to_datetime(datetime.today().strftime("%Y-%m-%d"))
        if start is not None:
            start = now + pandas.offsets.Day(start)
        if end is not None:
            end = now + pandas.offsets.Day(end + 1)
        return self._obj.sel(time=slice(start, end))

    # Overload time_selection
    def time_selection_list(self, times: list, method: str = 'nearest') -> xr.Dataset:
        """
        Subset dataset filtering elements along time dimension, selecting dates from a specified list.

        Parameters
        ----------
        times : list
            Dates to keep.

        Raises
        ------
        ValueError
            If not all 'times' are in the object.

        Returns
        -------
        xarray.Dataset
             Dataset with elements referring to the specified listed dates.
        """
        logger.info(f"Applying filter - time_selection_list")
        if method in ["linear"]:
            return self._obj.interp(time=pandas.to_datetime(times), method=method)
        else:
            return self._obj.sel(time=pandas.to_datetime(times), method=method)

    # Overload time_selection
    def time_selection_freq(self, freq: str = None, start: str = None, method: str = None) -> xr.Dataset:
        """
        Subset dataset filtering elements along time dimension, selecting dates from a "start" date with a specified
        frequency.

        Parameters
        ----------
        freq : str
            Frequency between values, can be 'hours', 'days' or 'months'.
        start : str
            Values kept from "start" (reference for the frequency).
            If "start" isn't provided, start takes the first time stamp of this object.

        Raises
        ------
        ValueError
            If not all 'times' are in this object.

        Returns
        -------
        xarray.Dataset
             Dataset with elements referring to the specified dates.

        See Also
        --------
        https://pandas.pydata.org/pandas-docs/stable/user_guide/timeseries.html#timeseries-offset-aliases

        Examples
        --------
        ds.meta.time_selection('17 days', '2020-07-04T12:00:00')
        ds.meta.time_selection('day', '2020-07-01T12:00:00')

        """
        logger.info(f"Applying filter - time_selection_freq")
        intervals = {'hour': 'H', 'hours': 'H', 'day': 'D', 'days': 'D', 'month': 'MS', 'months': 'MS'}
        args = freq.split(" ")
        if len(args) == 1:
            freq = intervals[args[0]]
        elif len(args) == 2:
            freq = args[0] + intervals[args[1]]
        else:
            return None

        if start is None:
            start = pandas.to_datetime(self._obj.time.data.min())
        else:
            start = pandas.to_datetime(start)

        start_days = start.day - 1

        start = start - pandas.offsets.Day(start_days)
        end = pandas.to_datetime(self._obj.time.data.max()) - pandas.offsets.Day(start_days)
        times = pandas.date_range(start, end, freq=freq) + pandas.offsets.Day(start_days)

        if method in ["linear"]:
            return self._obj.interp(time=times, method=method)
        else:
            return self._obj.sel(time=times, method=method)

    def time_selection_interval(self, interval: str = None, ) -> xr.Dataset:
        """Return a new Dataset whose data is sorted per time interval selected.

        Parameters
        ----------
        interval : str
            Length of the period, can be one hour, day, month or year.

        Returns
        -------
        xarray.Dataset
            same Dataset averaged over the time interval
        """
        logger.info(f"Applying filter - time_selection_interval")

        start = self._obj.isel(time=[0]).time.data[0]
        end = self._obj.isel(time=[-1]).time.data[0]

        start, end, interval = self._obj.meta.format_interval(start, end, interval)

        time_interval = pandas.date_range(start=start, end=end, freq=interval)

        ds_group = self._obj.groupby_bins('time', time_interval)
        liste_ds = []

        for label, ds in ds_group:
            label = str(label)[1:-1].replace(", ", " to ") + ' '
            ds['interval_label'] = label.replace(':00 ', ' ')
            liste_ds.append(ds)

        for i in range(len(liste_ds)):
            ds = liste_ds[i]
            ds = ds.assign_coords(interval=i)
            ds['date_time'] = ds.time
            ds = ds.assign_coords(time=np.arange(len(ds.time)))
            liste_ds[i] = ds

        ds = xr.concat(liste_ds, 'interval')
        ds = ds.rename({'time': 'idx_time'})
        ds = ds.rename({'date_time': 'time'})
        ds['interval'] = ds['interval_label']
        ds = ds.drop_vars('interval_label')
        return ds

    def format_interval(self, start, end, interval):
        """
        Retrieve the right inteval for monthly, yearly interval.
        Parameters
        ----------
        start : np.datime64
            Date of start
        end : np.datime64
            Date of end
        interval : str
            Required interval

        Returns
        -------

        """
        if interval in ["1M", "M"]:
            interval = "MS"
            start = np.datetime_as_string(start)[:7]
            day = np.datetime_as_string(end, unit='D').split('-')[2]
            if int(day) > 2:
                end = end + np.timedelta64(int(1 * 2.628e+15), 'ns')
        return start, end, interval

    # Overload emulation
    def time_selection_climatological(self, *args):
        """

        Parameters
        ----------
        args

        Returns
        -------

        """
        logger.info(f"Applying filter - time_selection_climatological")
        if len(args) == 1 and isinstance(args[0], str):
            return self.time_selection_climatological_interval(args[0])
        elif len(args) == 2 and isinstance(args[0], str) and isinstance(args[1], str):
            return self.time_selection_climatological_custom_interval(args[0], args[1])
        return None

    def time_selection_climatological_custom_interval(self, season_start: str = None,
                                                      season_end: str = None) -> xr.Dataset:
        """
        Subset dataset filtering elements along time dimension, selecting dates within the specified season.

        Parameters
        ----------
        season_start : str
            Start date of the season.
        season_end : str
            End date of the season.

        Returns
        -------
        xarray.Dataset
             Dataset with elements referring to the specified seasons.
        """
        logger.info(f"Applying filter - time_selection_climatological_custom_interval")

        start = pandas.to_datetime(self._obj.time.data.min())
        end = pandas.to_datetime(self._obj.time.data.max())

        index = []

        # ex 21/12 21/03
        season_start = season_start.split("/")
        season_end = season_end.split("/")

        if int(season_start[1]) > int(season_end[1]):
            season_in_2_years = True
        else:
            season_in_2_years = False

        interval = f'-{season_start[1]}-{season_start[0]}', f'-{season_end[1]}-{season_end[0]}'

        for year in range(start.year, end.year + 1):
            season_start, season_end = interval
            # season_start = \
            #     pandas.to_datetime(str(year - 1 if season_in_2_years else year) + season_start)
            season_start = f'{year - 1 if season_in_2_years else year}{season_start}'
            season_start = pandas.to_datetime(season_start)

            season_end = f'{str(year)}{season_end}'
            season_end = pandas.to_datetime(season_end) + pandas.DateOffset(1)

            for obj_time in self._obj.time.data:
                if season_start <= obj_time <= season_end:
                    index.append(obj_time)
                elif season_end < obj_time:
                    break
        return self._obj.sel(time=index)

    def time_selection_climatological_interval(self, interval: str = None, ) -> xr.Dataset:
        """
        Subset dataset filtering elements along time dimension, selecting dates within the specified period.

        Parameters
        ----------
        interval : str
            Period kept, can be one of the following : january, february, march,
            april, may, june, july, august, september, october, november, december,
            spring, summer, autumn, winter or
            from 2 to 12 consecutive letters in JFMAMJJASOND

        Returns
        -------
        xarray.Dataset
             Dataset with elements referring to the specified period.
        """
        logger.info(f"Applying filter - time_selection_climatological_interval")
        interval = interval.lower()

        climatological_interval = "jfmamjjasondjfmamjjasond"

        climatological_interval_month = {'january': 1, 'february': 2, 'march': 3, 'april': 4, 'may': 5, 'june': 6,
                                         'july': 7, 'august': 8, 'september': 9, 'october': 10, 'november': 11,
                                         'december': 12
                                         }
        climatological_interval_season = {'spring': ("21/03", "21/06"), 'summer': ("21/06", "23/09"),
                                          'autumn': ("23/09", "21/12"), 'winter': ("21/12", "21/03")
                                          }

        if interval in climatological_interval and 1 < len(interval) <= 12:
            i_start = climatological_interval.find(interval) + 1
            i_end = len(interval) - 1 + i_start
            month_selection = [i % 12 if i != 12 else 12 for i in range(i_start, i_end + 1)]
            return self._obj.sel(time=self._obj.time.dt.month.isin(month_selection))

        elif interval in climatological_interval_month:
            return self._obj.sel(time=self._obj.time.dt.month.isin(climatological_interval_month[interval]))

        elif interval in climatological_interval_season:
            season_start, season_end = climatological_interval_season[interval]
            return self.time_selection_climatological_custom_interval(season_start, season_end)
        return None

    def time_restriction(self, restriction: (int, int) = (None, None)) -> xr.Dataset:
        """
        Subset dataset filtering elements along time dimension, selecting times within the specified hour range.

        Parameters
        ----------
        restriction : (int, int)
            Start and end hours.

        Returns
        -------
        xarray.Dataset
            Dataset with elements referring to the specified hour range.
            If "start" is later then "end" : we take values from "start" until "end" trough midnight
            (i.e. day d at "start" to day d+1 at "end")
        """
        logger.info(f"Applying filter - time_restriction")
        start, end = restriction
        index = []
        for obj_time in self._obj.time.data:
            if start <= pandas.to_datetime(obj_time).hour <= end:
                index.append(obj_time)
            elif end < start:
                if start <= pandas.to_datetime(obj_time).hour <= 24 or 0 <= pandas.to_datetime(obj_time).hour <= end:
                    index.append(obj_time)
        if index:
            return self._obj.sel(time=index)

        return None
