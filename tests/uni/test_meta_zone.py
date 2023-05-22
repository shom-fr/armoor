import xarray as xrsamuelsamuel

from armoor import base
from armoor.hmi.script_tools import create_folder
from tests.int.base import change_path
from armoor.base.open_decode import open_decode
import numpy as np

folder_test = 'open_data'
out_path, logger = change_path(folder_test)
path_ds_lon_lat = [f"../data/test_uni/meta_zone/model_lon_lat.nc"]
ds_lon_lat_depth = open_decode(path_ds_lon_lat)

path_ds_xy = [f"../data/test_uni/meta_zone/model_x_y.nc"]
ds_xy = open_decode(path_ds_xy)


class TestMetaZone:

    def test_sel_hor_plg(self):  # OK
        logger.info('test_sel_hor_plg')
        plg = [[-9.91004944, 45.4280090], [-9.72228241, 45.7325592], [-9.42116928, 45.6329498],
               [-9.45437145, 45.3993874], [-9.73487663, 45.3604622], [-9.90890408, 45.4234314]]
        point_a_tester = [-9.166667, 45]
        ds_meta = ds_lon_lat_depth.meta.horizontal_selection_polygon(plg)

        before = point_a_tester[0] in ds_lon_lat_depth.lon.values and point_a_tester[1] in ds_lon_lat_depth.lat.values
        after = point_a_tester[0] not in ds_meta.lon.values and point_a_tester[1] not in ds_meta.lat.values

        assert before and after

    def test_sel_hor_plg_xy(self):  # OK
        logger.info('test_sel_hor_plg_xy')
        plg = [[-89.2571487, 63.3048820], [-91.3409653, 60.6578712], [-87.9336395, 58.5177307],
               [-84.7234344, 61.0239449], [-87.0888443, 63.3048820], [-89.1726685, 63.3893623]]
        point_a_tester = [-20.75, -25.875]  # lon, lat = -83.73, 60.85
        ds_meta = ds_xy.meta.horizontal_selection_polygon(plg)

        # test before
        point_xy = ds_xy.sel(x=point_a_tester[0], y=point_a_tester[1])
        before = np.isnan(point_xy.ptemp.data[0])

        # test after
        point_xy = ds_meta.sel(x=point_a_tester[0], y=point_a_tester[1])
        after = np.isnan(point_xy.ptemp.data[0])

        assert not before and after

    def test_sel_hor_coords(self):  # OK
        logger.info('test_sel_hor_coords')
        coords = [[-9.91004944, 45.4280090], [-9.72228241, 45.7325592]]
        ds_meta = ds_lon_lat_depth.meta.horizontal_selection_coords(coords, method='nearest')
        assert len(ds_meta.lon.values) == 2

    def test_sel_hor_coords_xy(self):  # OK
        logger.info('test_sel_hor_coords_xy')
        coords = [[-89.2571487, 63.3048820], [-91.3409653, 60.6578712]]
        ds_meta = ds_xy.meta.horizontal_selection_coords(coords, method='nearest')
        assert len(ds_meta.lon.values) == 2

    def test_sel_hor_cloud_dots(self):  # OK
        logger.info('test_sel_hor_cloud_dots')
        point = [-9.536], [45.625]
        radius = 35

        ds_meta = ds_lon_lat_depth.meta.horizontal_selection_cloud_dots(point, radius, method='nearest')

        point_in = [-9.583333, 45.416668]
        test_in = point_in[0] in ds_meta.lon.values and point_in[1] in ds_meta.lat.values

        point_out = [-9.25, 45]
        test_out = point_out[0] not in ds_meta.lon.values or point_out[1] not in ds_meta.lat.values

        assert test_in and test_out

    def test_sel_time_abs(self):  # OK
        logger.info('test_sel_time_abs')
        start = np.datetime64('2022-01-03T06')
        end = np.datetime64('2022-01-04T12')

        ds_meta = ds_lon_lat_depth.meta.time_selection_absolute(start=start, end=end)

        date_in = np.datetime64('2022-01-03T18')
        date_out = np.datetime64('2022-01-04T18')
        test_in = date_in in ds_meta.time.values
        test_out = date_out not in ds_meta.time.values

        assert test_in and test_out

    def test_sel_time_interval(self):  # OK
        logger.info('test_sel_time_interval')
        interval = '24h'

        ds_meta = ds_lon_lat_depth.meta.time_selection_interval(interval=interval)

        assert len(ds_meta.interval) == 2

    def test_time_selection_list(self):  # OK
        logger.info('test_time_selection_list')
        time_list = [np.datetime64('2022-01-03T00'), np.datetime64('2022-01-04T00'), np.datetime64('2022-01-05T00')]

        ds_meta = ds_lon_lat_depth.meta.time_selection_list(times=time_list)

        assert len(ds_meta.time) == 3

    def test_vertical_selection_range(self):
        logger.info('test_vertical_selection_range')
        depth_min, depth_max = 2, 5

        ds_meta = ds_lon_lat_depth.meta.vertical_selection_range([depth_min, depth_max], var_vert='depth')

        assert ds_meta.depth.min() > depth_min and ds_meta.depth.max() < depth_max

    def test_vertical_selection_list(self):
        logger.info('test_vertical_selection_list')
        depth_list = [2, 5, 7]

        ds_meta = ds_lon_lat_depth.meta.vertical_selection_list(depth_list)

        assert len(ds_meta.depth) == 3

    def test_vertical_selection_slice(self):
        logger.info('test_vertical_selection_slice')

        slice = '3'

        ds_meta = ds_lon_lat_depth.meta.vertical_selection_slice(slice=slice, var_slice='depth')
        assert len(ds_meta.slice) == 5
