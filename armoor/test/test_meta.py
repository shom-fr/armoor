import pandas
from datetime import datetime
import math
import xarray as xr
import xoa.grid
import matplotlib.pyplot as plt
import cartopy.crs as ccrs
import cartopy.feature as cfeature
import pandas as pd
import numpy as np


class TestMeta:
    filename_mod = 'N:\\1144-FE_Shom_Outils_validation_et_bulletins\\REALISATION\\Technique\\shared_data\\example\\mod.nc'
    mod = xr.open_dataset(filename_mod)
    mod = mod.read.decode()

    filename_obs = 'N:\\1144-FE_Shom_Outils_validation_et_bulletins\\REALISATION\\Technique\\shared_data\\example\\SST_L3MONOSENSOR.nc'
    obs = xr.open_dataset(filename_obs)
    obs = obs.read.decode()

    filename_mod3D = 'N:\\1144-FE_Shom_Outils_validation_et_bulletins\\REALISATION\\Technique\\shared_data\\example\\3D_mod.nc'
    mod3D = xr.open_dataset(filename_mod3D)
    mod3D = mod3D.read.decode()

    filename_mod3dbathy = 'N:\\1144-FE_Shom_Outils_validation_et_bulletins\\REALISATION\\Technique\\shared_data\\example\\loire.nc'
    mod3dbathy = xr.open_dataset(filename_mod3dbathy)
    mod3dbathy = mod3dbathy.read.decode()

    def test_time_intervalle(self):
        filename = '../../shared_data/example/model_pour_test.nc'

        ds = xr.open_dataset(filename)
        ds = ds.read.decode()
        ds = ds.meta.time_selection_interval('3H')

        assert isinstance(ds, xr.Dataset)

    def test_haversine(self):
        assert self.mod.meta.haversine(52.370216, 4.895168, 52.520008, 13.404954) == 945793.4375088713

    def test_horizontal_selection_coords_method_nearest(self):
        target = [[-5.76, 48.52], [-5.52, 48.52], [-5.26, 48.52],
                  [-5.76, 48.26], [-5.52, 48.26], [-5.26, 48.26],
                  [-5.76, 48.02], [-5.52, 48.02], [-5.26, 48.02]]
        print(f'Target coordinates : {target}')

        expected = [[-5.75, 48.5], [-5.5, 48.5], [-5.25, 48.5],
                    [-5.75, 48.25], [-5.5, 48.25], [-5.25, 48.25],
                    [-5.75, 48.0], [-5.5, 48.0], [-5.25, 48.0]]
        print(f'Expected coordinates result : {expected}')

        da = self.mod.meta.horizontal_selection_coords(target, method="nearest")
        result = [[lon, lat] for lon, lat in zip(da.lon.data, da.lat.data)]
        print(f'Coordinates result : {result}')

        assert np.testing.assert_allclose(result, expected) is None

    def test_horizontal_selection_coords_method_linear(self):
        target = [[-5.76, 48.52], [-5.52, 48.52], [-5.26, 48.52],
                  [-5.76, 48.26], [-5.52, 48.26], [-5.26, 48.26],
                  [-5.76, 48.02], [-5.52, 48.02], [-5.26, 48.02]]
        print(f'Target coordinates : {target}')

        expected = target
        print(f'Expected coordinates result : {expected}')

        da = self.mod.meta.horizontal_selection_coords(target, method="linear")
        result = [[lon, lat] for lon, lat in zip(da.lon.data, da.lat.data)]
        print(f'Coordinates result : {result}')

        assert np.testing.assert_allclose(result, expected) is None

    def test_quality_filter_all(self):
        quality = 3, 5
        da = self.obs.meta.quality_filter(quality)
        assert da == self.obs

    def test_quality_filter_empty(self):
        da = self.obs.meta.quality_filter()
        assert da == self.obs

    def test_quality_filter_min(self):
        quality = 3, None
        da = self.obs.meta.quality_filter(quality)
        assert da == self.obs

    def test_quality_filter_max(self):
        quality = None, 3
        da = self.obs.meta.quality_filter(quality)
        assert da is None

    def test_time_selection_absolute(self):
        max_ini = self.mod.time.data.max()
        min_ini = self.mod.time.data.min()
        start = pandas.to_datetime('2020-02-04T13:00:00')
        end = pandas.to_datetime('2021-02-04T11:00:00')
        da = self.mod.meta.time_selection_absolute(start, end)

        assert da.time.data.max() <= end <= max_ini and da.time.data.min() >= start >= min_ini

    def test_time_selection_list(self):
        target = ['2020-02-04T12:00:00', '2020-02-05T12:00:00',
                  '2020-02-06T12:00:00', '2020-02-07T12:00:00']
        print(f'Target times : {target}')

        expected = pd.to_datetime(target)
        print(f'Expected times result : {expected}')

        da = self.mod.meta.time_selection(target)
        result = list(da.time.data)
        print(f'Times result : {result}')

        assert np.testing.assert_array_equal(result, expected) is None

    def test_time_selection_list_method_nearest(self):
        target = ['2020-02-04T10:00:00', '2020-02-05T23:00:00',
                  '2020-02-06T14:00:00', '2020-02-07T17:00:00'], 'nearest'
        print(f'Target times : {target}')

        expected = pd.to_datetime(['2020-02-04T12:00:00', '2020-02-05T12:00:00',
                                   '2020-02-06T12:00:00', '2020-02-07T12:00:00'])
        print(f'Expected times result : {expected}')

        da = self.mod.meta.time_selection(target[0], method=target[1])
        result = list(da.time.data)
        print(f'Times result : {result}')

        assert np.testing.assert_array_equal(result, expected) is None

    def test_time_selection_list_method_linear(self):
        target = ['2020-02-04T10:00:00', '2020-02-05T23:00:00',
                  '2020-02-06T14:00:00', '2020-02-07T17:00:00'], 'linear'
        print(f'Target times : {target}')

        expected = pd.to_datetime(target[0])
        print(f'Expected times result : {expected}')

        da = self.mod.meta.time_selection(target[0], method=target[1])
        result = list(da.time.data)
        print(f'Times result : {result}')

        assert np.testing.assert_array_equal(result, expected) is None

    def test_time_selection_freq(self):
        target = 'month'
        print(f'Target times : {target}')

        expected = []
        for year in range(2019, 2021 + 1):
            for month in range(1, 12 + 1):
                expected.append(str(year) + '-' + ("0" if month < 10 else "") + str(month) + '-01T12:00:00')
                if year == 2021 and month == 6:
                    break
        expected = pd.to_datetime(expected)
        print(f'Expected times result : {expected}')

        da = self.mod.meta.time_selection(target)
        result = list(da.time.data)
        print(f'Times result : {result}')

        assert np.testing.assert_array_equal(result, expected) is None

    def test_time_selection_freq_start_m1(self):
        target = 'month', '2020-07-02T12:00:00'
        print(f'Target times : {target}')

        expected = []
        year = 2020
        month = 7
        while year != 2021 or month != 6 + 1:
            expected.append(str(year) + '-' + str(month) + '-02T12:00:00')
            month = month + 1 if month < 12 else 1
            year = year + 1 if month == 1 else year
        expected = pd.to_datetime(expected)
        print(f'Expected times result : {expected}')

        da = self.mod.meta.time_selection(target[0], target[1])
        result = list(da.time.data)
        print(f'Times result : {result}')

        assert np.testing.assert_array_equal(result, expected) is None

    def test_time_selection_freq_start_m1_method_nearest(self):
        target = 'month', '2020-07-02T07:00:00', 'nearest'
        print(f'Target times : {target}')

        expected = []
        year = 2020
        month = 7
        while year != 2021 or month != 6 + 1:
            expected.append(str(year) + '-' + str(month) + '-02T12:00:00')
            month = month + 1 if month < 12 else 1
            year = year + 1 if month == 1 else year
        expected = pd.to_datetime(expected)
        print(f'Expected times result : {expected}')

        da = self.mod.meta.time_selection(target[0], target[1], method=target[2])
        result = list(da.time.data)
        print(f'Times result : {result}')

        assert np.testing.assert_array_equal(result, expected) is None

    def test_time_selection_freq_start_m1_method_linear(self):
        target = 'month', '2020-07-02T7:00:00', 'linear'
        print(f'Target times : {target}')

        expected = []
        year = 2020
        month = 7
        while year != 2021 or month != 6 + 1:
            expected.append(str(year) + '-' + str(month) + '-02T7:00:00')
            month = month + 1 if month < 12 else 1
            year = year + 1 if month == 1 else year
        expected = pd.to_datetime(expected)
        print(f'Expected times result : {expected}')

        da = self.mod.meta.time_selection(target[0], target[1], method=target[2])
        result = list(da.time.data)
        print(f'Times result : {result}')

        assert np.testing.assert_array_equal(result, expected) is None

    def test_time_selection_freq_start_m2(self):
        target = '2 months', '2020-04-02T12:00:00'
        print(f'Target times : {target}')

        expected = []
        year = 2020
        month = 4
        while year != 2021 or month != 6 + 2:
            expected.append(str(year) + '-' + str(month) + '-02T12:00:00')
            month = month + 2 if month < 12 else 2
            year = year + 1 if month == 2 else year
        expected = pd.to_datetime(expected)
        print(f'Expected times result : {expected}')

        da = self.mod.meta.time_selection(target[0], target[1])
        result = list(da.time.data)
        print(f'Times result : {result}')

        assert np.testing.assert_array_equal(result, expected) is None

    def test_time_selection_freq_start_d1(self):
        target = 'day', '2020-07-01T12:00:00'
        print(f'Target times : {target}')

        expected = []
        year = 2020
        month = 7
        while year != 2021 or month != 6 + 1:
            days = pandas.to_datetime(str(year) + '-' + str(month)).days_in_month
            for d in range(1, int(days) + 1):
                expected.append(str(year) + '-' + str(month) + '-' + str(d) + 'T12:00:00')
                if year == 2021 and month == 6 and d == 2:
                    break
            month = month + 1 if month < 12 else 1
            year = year + 1 if month == 1 else year
        expected = pd.to_datetime(expected)
        print(f'Expected times result : {expected}')

        da = self.mod.meta.time_selection(target[0], target[1])
        result = list(da.time.data)
        print(f'Times result : {result}')

        assert np.testing.assert_array_equal(result, expected) is None

    def test_time_selection_freq_start_d5(self):
        target = '5 days', '2020-07-04T12:00:00'
        print(f'Target times : {target}')

        expected = []
        year = 2020
        month = 7
        day = 4
        while year != 2021 or month != 6 + 1:

            days = pandas.to_datetime(str(year) + '-' + str(month)).days_in_month
            for d in range(day, int(days) + 1, 5):
                expected.append(str(year) + '-' + str(month) + '-' + str(d) + 'T12:00:00')
                last_day = d
                if year == 2021 and month == 6 and d > 2:
                    expected.pop()
                    break
            day = 5 + last_day - days
            print("day {} days {}".format(day, days))
            month = month + 1 if month < 12 else 1
            year = year + 1 if month == 1 else year
        expected = pd.to_datetime(expected)
        print(f'Expected times result : {expected}')

        da = self.mod.meta.time_selection(target[0], target[1])
        result = list(da.time.data)
        print(f'Times result : {result}')

        assert np.testing.assert_array_equal(result, expected) is None

    def test_time_selection_freq_start_d17(self):
        target = '17 days', '2020-07-04T12:00:00'
        print(f'Target times : {target}')

        expected = []
        year = 2020
        month = 7
        day = 4
        while year != 2021 or month != 6 + 1:

            days = pandas.to_datetime(str(year) + '-' + str(month)).days_in_month
            for d in range(day, int(days) + 1, 17):
                expected.append(str(year) + '-' + str(month) + '-' + str(d) + 'T12:00:00')
                last_day = d
                if year == 2021 and month == 6 and d > 2:
                    expected.pop()
                    break
            day = 17 + last_day - days
            month = month + 1 if month < 12 else 1
            year = year + 1 if month == 1 else year
        expected = pd.to_datetime(expected)
        print(f'Expected times result : {expected}')

        da = self.mod.meta.time_selection(target[0], target[1])
        result = list(da.time.data)
        print(f'Times result : {result}')

        assert np.testing.assert_array_equal(result, expected) is None

    def test_time_selection_freq_start_h24(self):
        target = '24 hours', '2020-07-01T12:00:00'
        print(f'Target times : {target}')

        expected = []
        year = 2020
        month = 7
        while year != 2021 or month != 6 + 1:
            days = pandas.to_datetime(str(year) + '-' + str(month)).days_in_month
            for d in range(1, int(days) + 1):
                expected.append(str(year) + '-' + str(month) + '-' + str(d) + 'T12:00:00')
                if year == 2021 and month == 6 and d == 2:
                    break
            month = month + 1 if month < 12 else 1
            year = year + 1 if month == 1 else year
        expected = pd.to_datetime(expected)
        print(f'Expected times result : {expected}')

        da = self.mod.meta.time_selection(target[0], target[1])
        result = list(da.time.data)
        print(f'Times result : {result}')

        assert np.testing.assert_array_equal(result, expected) is None

    def test_time_selection_climatological_interval_march(self):
        target = 'march'
        print(f'Target times : {target}')

        expected = []
        year = 2019
        month = 3
        while year <= 2021:
            days = pandas.to_datetime(str(year) + '-' + str(month)).days_in_month
            for d in range(1, int(days) + 1):
                expected.append(str(year) + '-' + str(month) + '-' + str(d) + 'T12:00:00')
            year += 1
        expected = pd.to_datetime(expected)
        print(f'Expected times result : {expected}')

        da = self.mod.meta.time_selection_climatological(target)
        result = list(da.time.data)
        print(f'Times result : {result}')

        assert np.testing.assert_array_equal(result, expected) is None

    def test_time_selection_climatological_interval_winter(self):
        target = 'winter'
        print(f'Target times : {target}')

        expected = []
        year = 2019
        month = 1
        start_day = 1
        while year != 2021 or month <= 3:
            days = pandas.to_datetime(str(year) + '-' + str(month)).days_in_month
            for d in range(start_day, int(days) + 1):
                expected.append(str(year) + '-' + str(month) + '-' + str(d) + 'T12:00:00')
                if month == 12 and d == 31:
                    year += 1
                    month = 0
                    start_day = 1
                elif month == 3 and d == 21:
                    month = 11
                    start_day = 21
                    break
                else:
                    start_day = 1
            month += 1
        expected = pd.to_datetime(expected)
        print(f'Expected times result : {expected}')

        da = self.mod.meta.time_selection_climatological(target)
        result = list(da.time.data)
        print(f'Times result : {result}')

        assert np.testing.assert_array_equal(result, expected) is None

    def test_time_selection_climatological_custom_interval_winter(self):
        target = "21/12", "21/03"
        print(f'Target time interval : {target}')

        expected = self.mod.meta.time_selection_climatological('winter')
        expected = list(expected.time.data)
        print(f'Expected times result : {expected}')

        result = self.mod.meta.time_selection_climatological(target[0], target[1])
        result = list(result.time.data)
        print(f'Expected interval result : {result}')

        assert np.testing.assert_array_equal(result, expected) is None

    def test_time_selection_climatological_custom_interval_december(self):
        target = "1/12", "31/12"
        print(f'Target time interval : {target}')

        expected = self.mod.meta.time_selection_climatological('december')
        expected = list(expected.time.data)
        print(f'Expected times result : {expected}')

        result = self.mod.meta.time_selection_climatological(target[0], target[1])
        result = list(result.time.data)
        print(f'Expected interval result : {result}')

    def test_time_selection_climatological_custom_interval_summer(self):
        target = "21/06", "23/09"
        print(f'Target time interval : {target}')

        expected = self.mod.meta.time_selection_climatological('summer')
        expected = list(expected.time.data)
        print(f'Expected times result : {expected}')

        result = self.mod.meta.time_selection_climatological(target[0], target[1])
        result = list(result.time.data)
        print(f'Expected interval result : {result}')

        assert np.testing.assert_array_equal(result, expected) is None

    def test_time_selection_climatological_custom_interval_jaso(self):
        target = "1/07", "31/10"
        print(f'Target time interval : {target}')

        expected = self.mod.meta.time_selection_climatological('JASO')
        expected = list(expected.time.data)
        print(f'Expected times result : {expected}')

        result = self.mod.meta.time_selection_climatological(target[0], target[1])
        result = list(result.time.data)
        print(f'Expected interval result : {result}')

        assert np.testing.assert_array_equal(result, expected) is None

    def test_time_selection_climatological_custom_interval_ndj(self):
        target = "1/11", "31/01"
        print(f'Target time interval : {target}')

        expected = self.mod.meta.time_selection_climatological('NDJ')
        expected = list(expected.time.data)
        print(f'Expected times result : {expected}')

        result = self.mod.meta.time_selection_climatological(target[0], target[1])
        result = list(result.time.data)
        print(f'Expected interval result : {result}')

        assert np.testing.assert_array_equal(result, expected) is None

    def test_time_selection_climatological_custom_interval_fma(self):
        target = "1/02", "30/04"
        print(f'Target time interval : {target}')

        expected = self.mod.meta.time_selection_climatological('FMA')
        expected = list(expected.time.data)
        print(f'Expected times result : {expected}')

        result = self.mod.meta.time_selection_climatological(target[0], target[1])
        result = list(result.time.data)
        print(f'Expected interval result : {result}')

        assert np.testing.assert_array_equal(result, expected) is None

    def test_time_selection_climatological_custom_interval_fm(self):
        target = "1/02", "31/03"
        print(f'Target time interval : {target}')

        expected = self.mod.meta.time_selection_climatological('FM')
        expected = list(expected.time.data)
        print(f'Expected times result : {expected}')

        result = self.mod.meta.time_selection_climatological(target[0], target[1])
        result = list(result.time.data)
        print(f'Expected interval result : {result}')

        assert np.testing.assert_array_equal(result, expected) is None

    def test_time_restriction_11to13(self):
        target = 11, 13
        print(f'Target time interval : {target}')

        expected = self.mod
        expected = list(expected.time.data)
        print(f'Expected times result : {expected}')

        result = self.mod.meta.time_restriction(target)
        result = list(result.time.data)
        print(f'Expected interval result : {result}')

        assert np.testing.assert_array_equal(result, expected) is None

    def test_time_restriction_2to5(self):
        target = 2, 5
        print(f'Target time interval : {target}')

        expected = None
        print(f'Expected times result : {expected}')

        result = self.mod.meta.time_restriction(target)
        print(f'Expected interval result : {result}')

        assert result is expected

    def test_time_restriction_13to11(self):
        target = 13, 11
        print(f'Target time interval : {target}')

        expected = None
        print(f'Expected times result : {expected}')

        result = self.mod.meta.time_restriction(target)
        print(f'Expected interval result : {result}')

        assert result is expected

    def test_time_restriction_11to5(self):
        target = 11, 5
        print(f'Target time interval : {target}')

        expected = self.mod
        expected = list(expected.time.data)
        print(f'Expected times result : {expected}')

        result = self.mod.meta.time_restriction(target)
        result = list(result.time.data)
        print(f'Expected interval result : {result}')

        assert np.testing.assert_array_equal(result, expected) is None

    def test_time_restriction_23to13(self):
        target = 23, 13
        print(f'Target time interval : {target}')

        expected = self.mod
        expected = list(expected.time.data)
        print(f'Expected times result : {expected}')

        result = self.mod.meta.time_restriction(target)
        result = list(result.time.data)
        print(f'Expected interval result : {result}')

        assert np.testing.assert_array_equal(result, expected) is None

    def test_time_selection_relative(self):
        start = pandas.to_datetime('2020-02-01T00:00:00')
        end = pandas.to_datetime('2020-03-01T00:00:00')
        target = start, end
        print(f'Target time interval : {target}')

        expected = self.mod.meta.time_selection_absolute(start, end)
        expected = list(expected.time.data)
        print(f'Expected times result : {expected}')

        now = pandas.to_datetime(datetime.today().strftime("%Y-%m-%d"))
        target = datetime(2020, 3, 1)
        delta = (now - target).days
        nb_days_since_start = delta + 29  # +29 for the day before : 1/02/2020
        nb_days_since_end = delta + 1  # +1  for the day before : 29/02/2020
        result = self.mod.meta.time_selection_relative(-nb_days_since_start, -nb_days_since_end)
        result = list(result.time.data)
        print(f'Expected interval result : {result}')

        assert np.testing.assert_array_equal(result, expected) is None

    def test_time_selection_relative_noend(self):
        start = pandas.to_datetime('2020-02-01T00:00:00')
        end = None
        target = start, end
        print(f'Target time interval : {target}')

        expected = self.mod.meta.time_selection_absolute(start)
        expected = list(expected.time.data)
        print(f'Expected times result : {expected}')

        now = pandas.to_datetime(datetime.today().strftime("%Y-%m-%d"))
        target = datetime(2020, 3, 1)
        delta = (now - target).days
        nb_days_since_start = delta + 29  # +29 for the day before : 1/02/2020
        result = self.mod.meta.time_selection_relative(-nb_days_since_start)
        result = list(result.time.data)
        print(f'Expected interval result : {result}')

        assert np.testing.assert_array_equal(result, expected) is None

    def test_time_selection_relative_nostart(self):
        start = None
        end = pandas.to_datetime('2020-03-01T00:00:00')
        target = start, end
        print(f'Target time interval : {target}')

        expected = self.mod.meta.time_selection_absolute(end=end)
        expected = list(expected.time.data)
        print(f'Expected times result : {expected}')

        now = pandas.to_datetime(datetime.today().strftime("%Y-%m-%d"))
        target = datetime(2020, 3, 1)
        delta = (now - target).days
        nb_days_since_end = delta + 1  # +1  for the day before : 29/02/2020
        result = self.mod.meta.time_selection_relative(end=-nb_days_since_end)
        result = list(result.time.data)
        print(f'Expected interval result : {result}')

        assert np.testing.assert_array_equal(result, expected) is None

    def test_vertical_selection_level(self):
        target = [0.494]
        print(f'Target : {target}')

        expected = [0.49402499198913574]
        print(f'Expected : {expected}')

        result = self.mod.meta.vertical_selection(target)
        result = result.depth.data
        print(f'Result : {result}')

        assert np.testing.assert_array_equal(result, expected) is None

    def test_vertical_selection_level_3d_depth(self):
        target = [10.0]
        print(f'Target : {target}')

        expected = [10.0]
        print(f'Expected : {expected}')

        result = self.mod3D.meta.vertical_selection(target)
        result = result.depth.data
        print(f'Result : {result}')

        assert np.testing.assert_array_equal(result, expected) is None

    def test_vertical_selection_level_3d_depth_min_max(self):
        target = [10.0, 60.0]
        print(f'Target : {target}')

        expected = [10.0, 15.0, 20.0, 25.0, 30.0, 40.0, 50.0, 60.0]
        print(f'Expected : {expected}')

        result = self.mod3D.meta.vertical_selection(target)
        result = result.depth.data
        print(f'Result : {result}')

        assert np.testing.assert_array_equal(result, expected) is None

    def test_vertical_selection_level_3d_depth_min_max_step(self):
        target = [10.0, 60.0, 10.0]
        print(f'Target : {target}')

        expected = [10.0, 20.0, 30.0, 40.0, 50.0, 60.0]
        print(f'Expected : {expected}')

        result = self.mod3D.meta.vertical_selection(target)
        result = result.depth.data
        print(f'Result : {result}')

        assert np.testing.assert_array_equal(result, expected) is None

    # TODO test bathy :horizontal_selection_bathymetry
    # TODO test density :vertical_selection_density

    def test_horizontal_selection_polygon_square(self):
        lon_min_target, lat_min_target = -6., 47.
        lon_max_target, lat_max_target = -4., 49.
        lon0, lat0 = lon_max_target, lat_max_target
        lon1, lat1 = lon_min_target, lat_max_target
        lon2, lat2 = lon_min_target, lat_min_target
        lon3, lat3 = lon_max_target, lat_min_target
        target = [(lon0, lat0), (lon1, lat1), (lon2, lat2), (lon3, lat3)]
        print(f'Target : min : ({lon_min_target},{lat_min_target}) max : ({lon_max_target},{lat_max_target})')

        lon_min_old, lat_min_old = self.mod['lon'].min().data, self.mod['lat'].min().data
        lon_max_old, lat_max_old = self.mod['lon'].max().data, self.mod['lat'].max().data
        print(f'Previous : min : ({lon_min_old},{lat_min_old}) max : ({lon_max_old},{lat_max_old})')

        result = self.mod.meta.horizontal_selection_polygon(target)
        lon_min_result, lat_min_result = result['lon'].min().data, result['lat'].min().data
        lon_max_result, lat_max_result = result['lon'].max().data, result['lat'].max().data
        print(f'Result  : min : ({lon_min_result},{lat_min_result}) max : ({lon_max_result},{lat_max_result})')

        assert lon_min_old < lon_min_target <= lon_min_result and \
               lat_min_old < lat_min_target <= lat_min_result and \
               lon_max_result <= lon_max_target < lon_max_old and \
               lat_max_result <= lat_max_target < lat_max_old

    def test_horizontal_selection_polygon_diamond(self):
        lon_mid, lat_mid = -5., 48.
        diag = 4.
        lon0, lat0 = lon_mid - diag, lat_mid
        lon1, lat1 = lon_mid, lat_mid + diag
        lon2, lat2 = lon_mid + diag, lat_mid
        lon3, lat3 = lon_mid, lat_mid - diag

        target = [(lon0, lat0), (lon1, lat1),
                  (lon2, lat2), (lon3, lat3)]

        out = []

        result = self.mod.meta.horizontal_selection_polygon(target)
        for lon in result['lon'].data - lon_mid:
            for lat in result['lat'].data - lat_mid:
                # values inside diamond
                all_lon_lat_in_diamond = (lat <= diag - lon) and \
                                         (lat >= lon - diag) and \
                                         (lat >= -lon - diag) and \
                                         (lat <= diag + lon)
                # remaining values in the square must be nan
                if not all_lon_lat_in_diamond:
                    for var in result.sel(lat=(lat + lat_mid), lon=(lon + lon_mid))['ptemp'].data:
                        if not math.isnan(var):
                            # if not nan add coordinates to out list
                            out.append((lon + lon_mid, lat + lat_mid))
        print(out)
        assert out == []

    def test_horizontal_selection_polygon_square_curvi(self):
        lon_min_target, lat_min_target = -3, 47.
        lon_max_target, lat_max_target = -1.5, 47.5
        lon0, lat0 = lon_max_target, lat_max_target
        lon1, lat1 = lon_min_target, lat_max_target
        lon2, lat2 = lon_min_target, lat_min_target
        lon3, lat3 = lon_max_target, lat_min_target
        target = [(lon0, lat0), (lon1, lat1), (lon2, lat2), (lon3, lat3)]
        print(f'Target : min : ({lon_min_target},{lat_min_target}) max : ({lon_max_target},{lat_max_target})')

        lon_min_old, lat_min_old = self.mod3dbathy.xoa.lon.min().data, self.mod3dbathy.xoa.lat.min().data
        lon_max_old, lat_max_old = self.mod3dbathy.xoa.lon.max().data, self.mod3dbathy.xoa.lat.max().data
        print(f'Previous : min : ({lon_min_old},{lat_min_old}) max : ({lon_max_old},{lat_max_old})')
        #TODO horizontal_selection_polygon_curv à revoir
        result = self.mod3dbathy.meta.horizontal_selection_polygon(target)
        lon_min_result, lat_min_result = result.xoa.lon.min().data, result.xoa.lat.min().data
        lon_max_result, lat_max_result = result.xoa.lon.max().data, result.xoa.lat.max().data
        print(f'Result  : min : ({lon_min_result},{lat_min_result}) max : ({lon_max_result},{lat_max_result})')

        assert lon_min_old < lon_min_target <= lon_min_result and \
               lat_min_old < lat_min_target <= lat_min_result and \
               lon_max_result <= lon_max_target < lon_max_old and \
               lat_max_result <= lat_max_target < lat_max_old


    # def test_horizontal_selection_cloud_dots_one(self):
    #     r = 2.
    #
    #     lon_d, lat_d = -7.5, 48.
    #
    #     coords = [(lon_d, lat_d)]
    #
    #     out = []
    #     da = self.mod.meta.horizontal_selection_cloud_dots(coords, r)
    #     for lon in da['lon'].data:
    #         for lat in da['lat'].data:
    #             # values inside circle
    #             all_lon_lat_in_circle = (lat - lat_d) * (lat - lat_d) + (lon - lon_d) * (lon - lon_d) <= r * r
    #             if not all_lon_lat_in_circle:
    #                 # remaining values in the square must be nan
    #                 for var in da.sel(lat=lat, lon=lon)['thetao'].data:
    #                     if not math.isnan(var):
    #                         # if not nan add coordinates to out list
    #                         out.append((lon, lat))
    #     print(out)
    #     assert out == []
    #
    # def test_horizontal_selection_cloud_dots_multi(self):
    #     r = 1.
    #
    #     lon_1, lat_1 = -7.5, 48.
    #     lon_2, lat_2 = -5.5, 47.
    #
    #     coords = [(lon_1, lat_1), (lon_2, lat_2)]
    #
    #     out = []
    #     da = self.mod.meta.horizontal_selection_cloud_dots(coords, r)
    #     for lon in da['lon'].data:
    #         for lat in da['lat'].data:
    #             # values inside circle
    #             all_lon_lat_in_circle = False
    #             for (lon_d, lat_d) in coords:
    #                 all_lon_lat_in_circle |= (lat - lat_d) * (lat - lat_d) + (lon - lon_d) * (lon - lon_d) <= r * r
    #             if not all_lon_lat_in_circle:
    #                 # remaining values in the square must be nan
    #                 for var in da.sel(lat=lat, lon=lon)['thetao'].data:
    #                     if not math.isnan(var):
    #                         # if not nan add coordinates to out list
    #                         out.append((lon, lat))
    #     print(out)
    #     assert out == []
    #
    # def test_horizontal_selection_cloud_dots_multi_2(self):
    #     r = 0.2
    #
    #     lon0, lat0 = -10., 49.5
    #     lon00, lat00 = -7.5, 48
    #     lon1, lat1 = -6., 49.5
    #     lon2, lat2 = -3., 48
    #     lon3, lat3 = -6., 46.5
    #     lon4, lat4 = -9., 46.5
    #     lon5, lat5 = -10.2, 53.2
    #     coordinates = [(lon0, lat0), (lon5, lat5), (lon00, lat00),
    #                    (lon1, lat1), (lon2, lat2),
    #                    (lon3, lat3), (lon4, lat4)]
    #
    #     out = []
    #     da = self.mod.meta.horizontal_selection_cloud_dots(coordinates, r)
    #     for lon in da['lon'].data:
    #         for lat in da['lat'].data:
    #             # values inside circle
    #             all_lon_lat_in_circle = False
    #             for (lon_d, lat_d) in coordinates:
    #                 all_lon_lat_in_circle |= (lat - lat_d) * (lat - lat_d) + (lon - lon_d) * (lon - lon_d) <= r * r
    #             if not all_lon_lat_in_circle:
    #                 # remaining values in the square must be nan
    #                 for var in da.sel(lat=lat, lon=lon)['thetao'].data:
    #                     if not math.isnan(var):
    #                         # if not nan add coordinates to out list
    #                         out.append((lon, lat))
    #     print(out)
    #     assert out == []

    ################ tests Ergane
    path_CROCO = 'N:\\1144-FE_Shom_Outils_validation_et_bulletins\\REALISATION\\Technique\\old\\Donnees\\Sorties de modeles\\CROCO\\loire.nc'
    path_TOPAZ = 'N:\\1144-FE_Shom_Outils_validation_et_bulletins\\REALISATION\\Technique\\old\\Donnees\\Sorties de modeles\\TOPAZ\\dataset-ran-arc-day-myoceanv2-be_1627999680806.nc'
    path_NEMO = 'N:\\1144-FE_Shom_Outils_validation_et_bulletins\\REALISATION\\Technique\\old\\Donnees\\Sorties de modeles\\NEMO\\global-reanalysis-phy-001-030-monthly_1621524026022.nc'

    mod_CROCO = xr.open_dataset(path_CROCO).read.decode()
    mod_TOPAZ = xr.open_dataset(path_TOPAZ).read.decode()
    mod_NEMO = xr.open_dataset(path_NEMO).read.decode()
    mod_HYCOM_h = xoa.open_data_sample("hycom.gdp.h.nc")
    mod_HYCOM = xoa.open_data_sample("hycom.gdp.v.nc").read.decode(mod_HYCOM_h)

    mods = [mod_HYCOM, mod_TOPAZ, mod_CROCO, mod_NEMO]

    lon_min1, lat_min1 = -3.3, 46.8
    lon_max1, lat_max1 = -2.1, 47.5
    coords_1 = [(lon_max1, lat_max1), (lon_min1, lat_max1),
                (lon_min1, lat_min1), (lon_max1, lat_min1)]

    lon_min2, lat_min2 = -3.1, 44.7
    lon_max2, lat_max2 = -2.4, 45.2

    coords_2 = [(lon_max2, lat_max2), (lon_min2, lat_max2),
                (lon_min2, lat_min2), (lon_max2, lat_min2)]

    def test_sel_variable(self):
        variables = ['temp', 'dens', 'sal']
        for mod in self.mods:
            test = mod.meta.var_selection(variables)
        assert True

    def test_meta_square(self):
        mod = self.mod_CROCO
        test = mod.meta.horizontal_selection_polygon(self.coords_1)
        f = plt.figure(figsize=(10, 20))
        ax = f.add_subplot(1, 1, 1, projection=ccrs.PlateCarree())
        ax.set_extent([-5, -1, 46, 48], crs=ccrs.PlateCarree())
        gl = ax.gridlines(crs=ccrs.PlateCarree(), draw_labels=True)  # , dms=True)#, x_inline=False, y_inline=False)
        gl.ylabels_right = False
        gl.xlabels_top = False
        ax.add_feature(cfeature.LAND, zorder=1, edgecolor='k')
        im = ax.pcolor(test.lon, test.lat, test.xoa.temp.isel(time=[0], z=[1]).squeeze(), vmin=10, vmax=20)
        cbar = f.colorbar(im, ticklocation='right')
        assert True

    def test_vertical_sel_ponct(self):
        for mod in self.mods:
            mod.meta.vertical_selection([0])
        assert True

    # def test_vertical_sel_range(self):
    #     for mod in self.mods:
    #         mod.meta.vertical_selection([0, 10, 5])
    #     assert True

    def test_vertical_sel_empty(self):
        for mod in self.mods:
            mod.meta.vertical_selection()
        assert True
