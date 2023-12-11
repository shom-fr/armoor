"""MetazonAccessor
"""
import logging
import copy
import math
from datetime import datetime
import pandas
from pandas.tseries.offsets import MonthEnd
import xarray as xr
from shapely.geometry import Point
import numpy as np
from xoa.regrid import regrid1d
from matplotlib import path

R_terre = 6371
logger = logging.getLogger(__name__)
xr.set_options(keep_attrs=True)


@xr.register_dataarray_accessor("meta")
@xr.register_dataset_accessor("meta")
class MetazoneAccessor:
    """
    Select a subset of the original object filtering elements with conditions
    across certain dimensions.

    Attributes
    ----------
    xarray_obj : xarray.Dataset
        Observation dataset to subset.
    """

    def __init__(self, xarray_obj):
        self._obj = xarray_obj

    def quality_filter(self, quality: (str, int, int) = (None, None, None)) -> xr.Dataset:
        """
        Subset dataset filtering quality levels.

        Parameters
        ----------
        quality : (str, int, int)
            Variable name, Minimal, Maximal quality level.

        Returns
        -------
        xarray.Dataset
            Dataset filtered with quality levels input restrictions.
        """
        logger.info("Applying filter - quality_filter")
        var, min_q, max_q = quality
        min_q, max_q = int(min_q), int(max_q)

        if var in list(self._obj.keys()):
            pass
        elif "QC_" + var[:-3] in list(self._obj.keys()):
            var = "QC_" + var[:-3]
        else:
            var = "quality_level"

        if var in self._obj:
            if min_q and max_q:
                selection = (self._obj[var] >= min_q) & (self._obj[var] <= max_q)
            elif min_q:
                selection = self._obj[var] >= min_q
            elif max_q:
                selection = self._obj[var] <= max_q
            else:
                selection = None
            return self._obj.where(selection, drop=True)

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
        logger.info("Applying filter - horizontal_selection_polygon")
        # Create the polygon where to subset
        polygon = path.Path(coords)
        # Depending on the coordinate system, flag the points outside the polygon
        if 'lon' in self._obj.dims:  # Check if rect coordinates
            ds_coords = [(lon, lat) for lon in self._obj.lon.data for lat in self._obj.lat.data]
            flags = polygon.contains_points(ds_coords)
            mask_poly = np.reshape(flags, (len(self._obj.lon.data), len(self._obj.lat.data)))
            mask_poly = xr.DataArray(data=mask_poly, dims=['lon', 'lat'],
                                     coords={"lon": ('lon', self._obj.lon.data),
                                             "lat": ('lat', self._obj.lat.data),
                                             })
        elif 'x' in self._obj.dims:  # Check if curv coordinates
            lons, lats = self._obj.lon.data.flatten(), self._obj.lat.data.flatten()
            ds_coords = [(lons[i_lon], lats[i_lon]) for i_lon, _ in enumerate(lons)]

            flags = polygon.contains_points(ds_coords)

            mask_poly = np.reshape(flags, [len(self._obj.y.data), len(self._obj.x.data)])
            mask_poly = xr.DataArray(data=mask_poly, dims=['y', 'x'],
                                     coords={'x': (['x'], self._obj.x.data),
                                             'y': (['y'], self._obj.y.data),
                                             })

            # Check if the polygon matches the coordinates of the data
            if True not in mask_poly:
                raise ValueError('The polygon you have defined is not included in the data grid. '
                                 'The horizontal selection does not work.')
        # Profilers/drifter
        elif 'lon' in self._obj.coords and 'time' in self._obj.lon.dims:
            ds_coords = [(self._obj.lon.data[i], self._obj.lat.data[i]) for i in
                         range(len(self._obj.time))]
            flags = polygon.contains_points(ds_coords)
            mask_poly = xr.DataArray(data=flags, dims=['time'])

        # Remove points outside the polygon
        self._obj = self._obj.where(mask_poly, drop=True)

        return self._obj

    def data_selection(self, dim: str, minimum: float = None, maximum: float = None,
                       value: float = None) -> xr.Dataset:
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
        logger.info("Applying filter - data_selection")

        if value is not None:
            selection = self._obj[dim] == value
        elif minimum is not None and maximum is not None:
            selection = (self._obj[dim] >= minimum) & (self._obj[dim] <= maximum)
        elif minimum is not None:
            selection = self._obj[dim] >= minimum
        elif maximum is not None:
            selection = self._obj[dim] <= maximum
        else:
            selection = None
        return self._obj.where(selection)

    def horizontal_selection_coords(self, coordinates: [(float, float)],
                                    method: str = None) -> xr.Dataset:
        """
        Subset dataset selecting elements located in cloud of specified dots plus those
        in a certain radius.

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
        logger.info("Applying filter - horizontal_selection_coords")

        lon_target = [lon for lon, lat in coordinates]
        lat_target = [lat for lon, lat in coordinates]

        if 'lon' in self._obj.dims:  # Regular grid
            if method in ["linear"] or method is None:
                return self._obj.interp(lon=lon_target, lat=lat_target, method=method)
            return self._obj.sel(lon=lon_target, lat=lat_target, method=method)

        if 'x' in self._obj.dims:  # Curvilinear grid
            list_ds_point = []
            for i_lon, lon in enumerate(lon_target):
                list_ds_point.append(self._obj.meta.sel_closest(lon, lat_target[i_lon]))
            return xr.concat(list_ds_point, dim='x')

    def horizontal_selection_from_obs_radius(self, config_obj) -> xr.Dataset:
        """
        Subset dataset selecting the closest elements to the observations point located
        within the specified radius.

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

        self._obj = self._obj.interp(lon=obs_lon, lat=obs_lat, method='linear')
        distance = np.sqrt(
            (self._obj.lon.values - obs_lon) ** 2 + (self._obj.lat.values - obs_lat) ** 2)
        radius_km = self._obj.meta.km_to_deg(radius)

        if distance > radius_km:
            logger.info('Oops, the model does not contain a point that meets the radius criteria. '
                        'The nearest point is used at position %s N %s E.', self._obj.lat.data,
                        self._obj.lon.data)

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
        logger.info("Applying filter - sel_closest")
        mindist = 100000
        for i_x, _ in enumerate(self._obj.x.values):
            dataset = self._obj.isel(x=i_x)
            lon0, lat0 = dataset.lon.values, dataset.lat.values
            lon1, lat1 = lon_target, lat_target
            deg2rad = math.pi / 180.0
            dist = np.sin(deg2rad * (lat0 - lat1) * 0.5) ** 2
            dist += (np.cos(deg2rad * lat0) * np.cos(deg2rad * lat1) * np.sin(
                deg2rad * (lon0 - lon1) * 0.5) ** 2)
            dist = 2.0 * np.arcsin(np.sqrt(dist))
            argmin = np.argmin(dist)
            dist = np.min(dist)

            if dist <= mindist:
                i_x_min = i_x
                i_y_min = argmin
                mindist = dist
        dataset = self._obj.isel(x=i_x_min, y=i_y_min)

        return dataset

    def horizontal_selection_cloud_dots(self, cloud: [(float, float)], radius_km: float = 0.,
                                        method: str = None) -> xr.Dataset:
        """
        Subset dataset selecting elements located in cloud of specified dots plus those
        in a certain radius.

        Parameters
        ----------
        cloud : list of tuples
            Set of points coordinates (lon, lat) defining the cloud.
        radius_km : float
            Radius around the points to expand the considered area.
        method : str
            Selection method.

        Returns
        -------
        xarray.Dataset
            Dataset with elements included inside the cloud/area.
        """
        logger.info("Applying filter - horizontal_selection_cloud_dots")
        if radius_km == 0. or radius_km is None:
            return self._obj.meta.horizontal_selection_coords(cloud, method)

        radius = self._obj.meta.km_to_deg(radius_km)
        liste_ds = []
        idx_centre = 0

        lons, lats = cloud
        for i_lon, _ in enumerate(lons):
            lon, lat = lons[i_lon], lats[i_lon]
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

            dataset = self._obj.sel(lon=tgt_lon, lat=tgt_lat)
            dataset = dataset.assign_coords(idx_centre=idx_centre)
            liste_ds.append(dataset)

            idx_centre += 1

        if len(liste_ds) > 1:
            ds_all = xr.concat(liste_ds, 'idx_point',
                               combine_attrs="drop")  # plusieurs point dans cloud
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
        r_lat = R_terre * np.cos(lat_mean * np.pi / 180)
        rad_lat_deg = radius_km * 360 / (2 * np.pi * r_lat)

        return rad_lat_deg

    def horizontal_selection_bathy(self, minimum: float = None,
                                   maximum: float = None, ) -> xr.Dataset:
        """
        Subset dataset selecting elements whom bathymetry values are included in the specified
        bathymetry range.

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

        logger.info("Applying filter - horizontal_selection_bathymetry")
        return self.data_selection(dim='bathy', minimum=minimum, maximum=maximum)

    def vertical_selection_depth(self, depth: list = None) -> xr.Dataset:
        """

        Parameters
        ----------
        depth

        Returns
        -------

        """
        logger.info("Applying filter - vertical_selection_depth")
        depth = np.array(depth, dtype=float)
        if len(depth) == 1:
            return self.vertical_selection_ponct(depth[0], 'depth')
        return self.vertical_selection_list(depth)

    def vertical_selection_min_depth(self, min_depth: list = None) -> xr.Dataset:
        """

        Parameters
        ----------
        depth

        Returns
        -------

        """
        logger.info("Applying filter - vertical_selection_depth")
        max_depth = self._obj.depth.max(skipna=True)
        return self.vertical_selection_range([min_depth, max_depth], 'depth')

    def vertical_selection_max_depth(self, max_depth: list = None) -> xr.Dataset:
        """

        Parameters
        ----------
        depth

        Returns
        -------

        """
        logger.info("Applying filter - vertical_selection_depth")
        min_depth = self._obj.depth.min(skipna=True)
        return self.vertical_selection_range([min_depth, max_depth], 'depth')

    def vertical_selection_min_dens(self, min_dens: list = None) -> xr.Dataset:
        """

        Parameters
        ----------
        min_dens

        Returns
        -------

        """
        max_dens = self._obj.pdens.max(skipna=True)
        return self.vertical_selection_range([min_dens, max_dens], 'dens')

    def vertical_selection_max_dens(self, max_dens: list = None) -> xr.Dataset:
        """

        Parameters
        ----------
        max_dens

        Returns
        -------

        """
        min_dens = self._obj.pdens.min(skipna=True)
        return self.vertical_selection_range([min_dens, max_dens], 'dens')

    def vertical_selection_dens(self, dens: list = None) -> xr.Dataset:
        """

        Parameters
        ----------
        depth

        Returns
        -------

        """
        logger.info("Applying filter - vertical_selection_dens")
        dens = np.array(dens, dtype=float)

        if dens and np.size(dens) == 1:
            return self.vertical_selection_ponct(dens, 'dens')
        if dens:  # if output=profiles, only this option should apply
            return self.vertical_selection_range(dens, 'dens')
        return self._obj

    def vertical_selection_dens_from_depth(self, pdens):
        difference_densite = np.abs(self._obj['pdens'] - pdens).fillna(100000)
        if 'z' in self._obj.dims:
            indice_min_densite = difference_densite.argmin(dim='z')
            self._obj = self._obj.isel(z=indice_min_densite)
        elif 'depth' in self._obj.dims:
            indice_min_densite = difference_densite.argmin(dim='depth')
            self._obj = self._obj.isel(depth=indice_min_densite)
        self._obj = self._obj.drop('pdens').assign_coords({'pdens': pdens})
        if 'depth' in self._obj.coords:
            self._obj = self._obj.reset_coords('depth')
        return self._obj

    def vertical_selection_ponct(self, depth: float, var_vert: str = 'depth') -> xr.Dataset:
        """
        Subset dataset selecting elements whom depth values are included in the
        specified depth range.

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

        logger.info("Applying filter - vertical_selection_ponct")
        dataset = copy.copy(self._obj)

        if var_vert == 'depth':
            if 'depth' in dataset.dims and len(dataset.depth.dims) == 1:  # NEMO or TOPAZ
                dataset = dataset.interp(depth=depth, method='linear')
                dataset['depth'] = depth
                return dataset

            if list(dataset.dims) == ['time', 'z']:  # CMEMS profilers
                return dataset.meta.vertical_selection_ponct_cmems(depth)

            if 'z' in dataset.dims or 'level' in dataset.dims or (
                    depth in dataset.dims and len(dataset.depth.dims) == 2):  # CROCO or HYCOM
                return dataset.meta.vertical_selection_croco_hycom(depth)

            return dataset
        if var_vert == 'dens':
            if 'pdens' in dataset.dims:
                return dataset.interp(pdens=depth, method='linear')
            elif 'pdens' not in dataset:
                dataset["pdens"] = dataset.sel_var.sel_pdensity()
            return dataset.meta.vertical_selection_dens_from_depth(pdens=depth)

    def vertical_selection_ponct_cmems(self, depth):
        """
        Vertical selection of one level in a CMEMS product.
        Parameters
        ----------
        depth : float
            Depth to select.

        Returns
        -------
        CMEMS product at the required depth.

        """
        depth_diff = np.abs(self._obj['depth'] - depth)
        nearest_depth_index = [np.nanargmin(depth_diff.isel(time=i_time).data) for i_time, time in
                               enumerate(self._obj.time)]

        ds_nearest_depth = [self._obj.isel(time=i_time, z=nearest_depth_index[i_time]) for
                            i_time, time in enumerate(self._obj.time)]
        tgt_ds = xr.concat(ds_nearest_depth, dim='time')
        tgt_ds = tgt_ds.drop('depth').assign_coords(depth=depth)
        return tgt_ds

    def vertical_selection_croco_hycom(self, depth):
        """
        Vertical selection of one level in a Croco or Hycom product.
        Parameters
        ----------
        depth : float or list of floats
            Depth(s) to select.

        Returns
        -------
        Croco or Hycom product at the required depth.
        """
        # Regrid1D only seems to work with negative depths for croco:
        # the following lines adapt the depths values to correctly select the depth defined.
        dataset = copy.copy(self._obj)
        if 'type' in dataset.attrs and dataset.attrs['type'] == 'CROCO':  # For croco
            dataset['depth'] = -dataset['depth']
            depth = -depth
            if np.size(depth) != 1 and depth[0] > depth[-1]:
                depth = np.flip(depth)

        # Create target depth(s) dataset
        if np.size(depth) == 1:
            depth = [float(depth)]
        else:
            depth = np.array(depth)
        tgt_depth = xr.DataArray(depth, dims="depth", name="depth")
        # Select depth(s)
        tgt_ds = dataset
        for var in dataset.variables:
            if var == 'depth' or 'DEPH' in var:
                pass
            else:
                for var_depth in ['level', 'z', 'DEPTH', 'sig']:
                    if var_depth in dataset[var].dims and len(dataset[var][var_depth]) > 1:
                        da_var = dataset[var]
                        da_tgt = regrid1d(da_var, tgt_depth)
                        tgt_ds = tgt_ds.assign({var: da_tgt})

        # Assign depth coordinates values
        if "depth" not in list(tgt_ds.coords):
            tgt_ds = tgt_ds.assign_coords(depth=tgt_depth)

        # Positive depths for croco
        if 'type' in dataset.attrs and dataset.attrs['type'] == 'CROCO':  # For croco
            tgt_ds['depth'] = -tgt_ds['depth']

        tgt_ds = tgt_ds.squeeze()
        # Reindex depths if necessary
        if np.size(tgt_ds.depth.data) > 1 and tgt_ds.depth.data[0] > tgt_ds.depth.data[-1]:
            tgt_ds = tgt_ds.reindex(depth=tgt_ds.depth[::-1])

        return tgt_ds

    def vertical_seletion_croco_hycom_dens(self, depth):
        """
        Vertical selection of one level in a Croco or Hycom product.
        Parameters
        ----------
        depth : float or list of floats
            Depth(s) to select.

        Returns
        -------
        Croco or Hycom product at the required depth.
        """
        # Regrid1D only seems to work with negative depths for croco:
        # the following lines adapt the depths values to correctly select the depth defined.
        dataset = copy.copy(self._obj)
        if 'type' in dataset.attrs and dataset.attrs['type'] == 'CROCO':  # For croco
            dataset['depth'] = -dataset['depth']
            depth = -depth
            if np.size(depth) != 1 and depth[0] > depth[-1]:
                depth = np.flip(depth)

        # Create target depth(s) dataset
        if np.size(depth) == 1:
            depth = [depth]
        else:
            depth = np.array(depth)
        tgt_depth = xr.DataArray(depth, dims="depth", name="depth")

        # Select depth(s)
        tgt_ds = dataset
        for var in dataset.variables:
            if var == 'depth' or 'DEPH' in var:
                pass
            else:
                for var_depth in ['level', 'z', 'DEPTH', 'sig']:
                    if var_depth in dataset[var].dims and len(dataset[var][var_depth]) > 1:
                        da_var = dataset[var]
                        da_tgt = regrid1d(da_var, tgt_depth)
                        tgt_ds = tgt_ds.assign({var: da_tgt})

        # Assign depth coordinates values
        if "depth" not in list(tgt_ds.coords):
            tgt_ds = tgt_ds.assign_coords(depth=tgt_depth)

        # Positive depths for croco
        if 'type' in dataset.attrs and dataset.attrs['type'] == 'CROCO':  # For croco
            tgt_ds['depth'] = -tgt_ds['depth']

        tgt_ds = tgt_ds.squeeze()
        # Reindex depths if necessary
        if np.size(tgt_ds.depth.data) > 1 and tgt_ds.depth.data[0] > tgt_ds.depth.data[-1]:
            tgt_ds = tgt_ds.reindex(depth=tgt_ds.depth[::-1])

        return tgt_ds

    def vertical_selection_range(self, depth: list, var_vert: str = 'depth') -> xr.Dataset:
        """
        Subset dataset selecting elements whom depth values are included in the
        specified depth range.

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
        logger.info("Applying filter - vertical_selection_range")
        # Get min and max values
        dmin = float(depth[0])
        dmax = float(depth[1])
        # Select all depth between min and max
        if len(depth) == 2:
            selection = (self._obj[var_vert] >= dmin) & (self._obj[var_vert] <= dmax)
            return self._obj.where(selection, drop=True)

        # Select between min and max with a specific number of depths between
        if len(depth) == 3:
            step = depth[2]
            depths = np.linspace(dmin, dmax, int(step))
            return self.vertical_selection_list(depths)

    def vertical_selection_list(self, depths: list) -> xr.Dataset:
        """
        Subset dataset selecting elements whom depth values are included in the
        specified depth range.

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
        if 'depth' in self._obj.dims:  # Selection for NEMO or TOPAZ
            return self._obj.interp(depth=depths, method='linear')

        if list(self._obj.dims.keys()) == ['time', 'z']:  # CMEMS profilers
            return self._obj.meta.vertical_selection_croco_hycom(depths)

        if 'z' in self._obj.dims or 'level' in self._obj.dims:  # Selection for CROCO or HYCOM
            return self._obj.meta.vertical_selection_croco_hycom(depths)

    def vertical_selection_slice(self, slices: list = None, var_slice: str = None) -> xr.Dataset:
        """Return a new Dataset whose data is sorted per depth slice.

        Parameters
        ----------
        slices : list of floats
            Levels of the slices required.
        var_slice : str
            Variable on which to select the slices : depth or dens.

        Returns
        -------
        xarray.Dataset
            same Dataset averaged over the vertical slice.
        """
        logger.info("Applying filter - vertical_selection_slice")

        # Initialise dataset
        liste_ds = []

        # Separate slices
        mins = [min for min, max in slices]
        maxs = [max for min, max in slices]

        for i_slice, _ in enumerate(mins):
            min_slice, max_slice = mins[i_slice], maxs[i_slice]
            ds_slice = self._obj.meta.vertical_selection_range([min_slice, max_slice], var_slice)
            label = f'{min_slice} to {max_slice}'
            ds_slice['slice_label'] = label
            liste_ds.append(ds_slice)

        for i_ds, ds_slice in enumerate(liste_ds):
            ds_slice = ds_slice.assign_coords(
                slice=i_ds)  # ajoute une dimension de date moyenne sur l'intervalle
            ds_slice[var_slice + "_value"] = ds_slice[var_slice]
            ds_slice = ds_slice.assign_coords(
                depth=np.arange(len(ds_slice[var_slice])))  # change les profondeurs en indices
            liste_ds[i_ds] = ds_slice

        dataset = xr.concat(liste_ds, 'slice')
        dataset = dataset.rename({var_slice: 'idx_' + var_slice})
        dataset = dataset.rename({var_slice + '_value': var_slice})
        dataset['slice'] = dataset['slice_label']
        if "depth" in dataset:
            dataset = dataset.assign_coords({"depth": dataset.depth})

        return dataset

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
        logger.info("Applying filter - time_selection_start")
        if isinstance(start, int):
            return self.time_selection_relative(start, None)
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
        logger.info("Applying filter - time_selection_end")
        if isinstance(end, int):
            return self.time_selection_relative(None, end)
        return self.time_selection_absolute(None, end)

    def time_selection_absolute(self, start: str = None, end: str = None) -> xr.Dataset:
        """
        Subset dataset filtering elements along time dimension, selecting dates within
        a specified period.

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
        logger.info("Applying filter - time_selection_absolute")
        if start == end:
            return self._obj.interp(time=start, method='linear')
        return self._obj.sel(time=slice(start, end))

    def time_selection_relative(self, start: int = None, end: int = None) -> xr.Dataset:
        """
        Subset dataset filtering elements along time dimension, selecting dates within a
        specified period.

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

        logger.info("Applying filter - time_selection_relative")
        now = pandas.to_datetime(datetime.today().strftime("%Y-%m-%d"))
        if start is not None:
            start = now + pandas.offsets.Day(start)
        if end is not None:
            end = now + pandas.offsets.Day(end + 1)
        return self._obj.sel(time=slice(start, end))

    # Overload time_selection
    def time_selection_list(self, times: list, method: str = 'linear') -> xr.Dataset:
        """
        Subset dataset filtering elements along time dimension, selecting dates from a
        specified list.

        Parameters
        ----------
        times : list
            Dates to keep.
        method : str
            Method to use for the selection.
        Raises
        ------
        ValueError
            If not all 'times' are in the object.

        Returns
        -------
        xarray.Dataset
             Dataset with elements referring to the specified listed dates.
        """
        logger.info("Applying filter - time_selection_list")
        if method in ["linear"]:
            return self._obj.interp(time=pandas.to_datetime(times), method=method)
        return self._obj.sel(time=pandas.to_datetime(times), method=method)

    # Overload time_selection
    def time_selection_freq(self, freq: str = None, start: str = None,
                            method: str = None) -> xr.Dataset:
        """
        Subset dataset filtering elements along time dimension, selecting dates from a "start"
        date with a specified
        frequency.

        Parameters
        ----------
        freq : str
            Frequency between values, can be 'hours', 'days' or 'months'.
        start : str
            Values kept from "start" (reference for the frequency).
            If "start" isn't provided, start takes the first time stamp of this object.
        method : str
            Method to use for the selection.
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
        logger.info("Applying filter - time_selection_freq")
        intervals = {'hour': 'H', 'hours': 'H', 'day': 'D', 'days': 'D', 'month': 'MS',
                     'months': 'MS'
                     }
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
        logger.info("Applying filter - time_selection_interval")

        if interval in ["1M", "M"]:
            interval = "MS"

        start = self._obj.isel(time=[0]).time.data[0]
        end = self._obj.isel(time=[-1]).time.data[0]
        end = pandas.to_datetime(end) + MonthEnd(1) + pandas.to_timedelta(1, 'D')

        time_interval = pandas.date_range(start=start, end=end, freq=interval)

        ds_group = self._obj.groupby_bins('time', time_interval, right=False)
        liste_ds = []

        for label, dataset in ds_group:
            label = str(label)[1:-1].split(',')
            label0 = np.datetime_as_string(np.datetime64(label[0]), unit='h')
            label1 = np.datetime_as_string(np.datetime64(label[1]), unit='h')
            dataset['interval_label'] = f"{label0} to {label1}"
            liste_ds.append(dataset)

        for i_ds, dataset in enumerate(liste_ds):
            dataset = dataset.assign_coords(interval=i_ds)
            dataset['date_time'] = dataset.time
            dataset = dataset.assign_coords(time=np.arange(len(dataset.time)))
            liste_ds[i_ds] = dataset

        dataset = xr.concat(liste_ds, 'interval')
        dataset = dataset.rename({'time': 'idx_time'})
        dataset = dataset.rename({'date_time': 'time'})
        dataset['interval'] = dataset['interval_label']
        dataset = dataset.drop_vars('interval_label')
        dataset = dataset.assign_coords({'time': dataset.time})

        return dataset

    def time_selection_climatological(self, cycle: str):
        """
                Subset dataset filtering elements along time dimension, selecting dates within
                the specified period.

                Parameters
                ----------
                cycle : str
                    Period kept, can be one of the following : january, february, march,
                    april, may, june, july, august, september, october, november, december,
                    spring, summer, autumn, winter or
                    from 2 to 12 consecutive letters in JFMAMJJASOND

                Returns
                -------
                xarray.Dataset
                     Dataset with elements referring to the specified period.
                """
        logger.info("Applying filter - time_selection_climatological")

        climatological_interval = "jfmamjjasondjfmamjjasond"

        climatological_month = {'january': 1, 'february': 2, 'march': 3, 'april': 4, 'may': 5,
                                'june': 6, 'july': 7, 'august': 8, 'september': 9, 'october': 10,
                                'november': 11, 'december': 12
                                }
        climatological_season = {'winter': 'DJF', 'spring': 'MAM', 'summer': 'JJA', 'autumn': "SON"
                                 }

        cycle = cycle[0]
        if cycle in climatological_interval and 1 < len(cycle) <= 12:
            i_start = climatological_interval.find(cycle) + 1
            i_end = len(cycle) - 1 + i_start
            month_selection = [i % 12 if i != 12 else 12 for i in range(i_start, i_end + 1)]
            return self._obj.sel(time=self._obj.time.dt.month.isin(month_selection))

        if cycle in climatological_month:
            return self._obj.sel(time=self._obj['time.month'] == climatological_month[cycle])

        if cycle in climatological_season:
            ds_season_group = self._obj.groupby('time.season')
            for label_season, ds_season in ds_season_group:
                if label_season == climatological_season[cycle]:
                    return ds_season
        return None

    def time_selection_climatological_custom_interval(self, season_start: str = None,
                                                      season_end: str = None) -> xr.Dataset:
        """
        Subset dataset filtering elements along time dimension, selecting dates within
         the specified season.

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
        logger.info("Applying filter - time_selection_climatological_custom_interval")

        start = pandas.to_datetime(self._obj.time.data.min())
        end = pandas.to_datetime(self._obj.time.data.max())

        index = []

        # ex 21/12 21/03
        season_start = season_start.split("/")
        season_end = season_end.split("/")

        season_in_2_years = int(season_start[1]) > int(season_end[1])

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

    def time_restriction(self, restriction: (int, int) = (None, None)) -> xr.Dataset:
        """
        Subset dataset filtering elements along time dimension, selecting times within
        the specified hour range.

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
        logger.info("Applying filter - time_restriction")
        start, end = restriction
        index = []
        for obj_time in self._obj.time.data:
            if start <= pandas.to_datetime(obj_time).hour <= end:
                index.append(obj_time)
            elif end < start:
                if start <= pandas.to_datetime(obj_time).hour <= 24 or 0 <= pandas.to_datetime(
                        obj_time).hour <= end:
                    index.append(obj_time)
        if index:
            return self._obj.sel(time=index)

        return None
