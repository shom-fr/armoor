"""Test suite for ArmoorSelectionAccessor module."""

from datetime import datetime
from unittest.mock import MagicMock, patch

import numpy as np
import pandas as pd
import pytest
import xarray as xr

# Import the module to test
from armoor.base.filters import ArmoorSelectionAccessor


class TestArmoorSelectionAccessor:
    """Test suite for ArmoorSelectionAccessor class."""
    
    @pytest.fixture
    def sample_dataset(self):
        """Create a sample dataset for testing."""
        np.random.seed(42)
        
        # Create coordinate arrays
        time = pd.date_range('2023-01-01', periods=10, freq='D')
        lat = np.linspace(40, 45, 5)
        lon = np.linspace(-10, -5, 5)
        z = np.array([0, 10, 20, 30, 50])
        
        # Create data variables
        temp = np.random.rand(10, 5, 5, 5) * 20 + 10
        sal = np.random.rand(10, 5, 5, 5) * 5 + 30
        temp_qc = np.random.randint(1, 5, (10, 5, 5, 5))
        sal_qc = np.random.randint(1, 5, (10, 5, 5, 5))
        bathy = np.random.rand(5, 5) * 1000 + 100
        depth = np.random.rand(10, 5, 5, 5) * 100
        
        # Create dataset
        ds = xr.Dataset(
            {
                'temp': (['time', 'z', 'lat', 'lon'], temp),
                'sal': (['time', 'z', 'lat', 'lon'], sal),
                'temp_qc': (['time', 'z', 'lat', 'lon'], temp_qc),
                'sal_qc': (['time', 'z', 'lat', 'lon'], sal_qc),
                'bathy': (['lat', 'lon'], bathy),
                'depth': (['time', 'z', 'lat', 'lon'], depth),
            },
            coords={
                'time': time,
                'lat': lat,
                'lon': lon,
                'z': z,
            }
        )
        
        # Set depth as coordinate
        ds = ds.set_coords('depth')
        
        return ds
    
    @pytest.fixture
    def sample_2d_dataset(self):
        """Create a 2D dataset for testing horizontal selection."""
        np.random.seed(42)
        
        lat = np.linspace(40, 45, 8)
        lon = np.linspace(-10, -5, 10)
        
        lon, lat = np.meshgrid(lon, lat)
        
        temp = np.random.rand(8, 10) * 20 + 10
        
        ds = xr.Dataset(
            {
                'temp': (['y', 'x'], temp),
            },
            coords={
                'lat': (['y', 'x'], lat),
                'lon': (['y', 'x'], lon),
            }
        )
        
        return ds

    def test_quality_filter_with_qmin_qmax(self, sample_dataset):
        """Test quality filter with both minimum and maximum values."""
        result = sample_dataset.armoorfilters.quality_filter('temp', 2, 4)
        
        # Check that values outside quality range are masked
        assert isinstance(result, xr.Dataset)
        assert 'temp' in result.data_vars
        
        # Verify that quality filtering was applied
        original_temp_qc = sample_dataset['temp_qc']
        mask = (original_temp_qc >= 2) & (original_temp_qc <= 4)
        expected_nan_count = np.sum(~mask)
        actual_nan_count = np.sum(np.isnan(result['temp'].values))
        
        assert actual_nan_count >= expected_nan_count

    def test_quality_filter_qmin_only(self, sample_dataset):
        """Test quality filter with only minimum value."""
        result = sample_dataset.armoorfilters.quality_filter('temp', 3, None)
        
        assert isinstance(result, xr.Dataset)
        original_temp_qc = sample_dataset['temp_qc']
        mask = original_temp_qc >= 3
        expected_nan_count = np.sum(~mask)
        actual_nan_count = np.sum(np.isnan(result['temp'].values))
        
        assert actual_nan_count >= expected_nan_count

    def test_quality_filter_qmax_only(self, sample_dataset):
        """Test quality filter with only maximum value."""
        result = sample_dataset.armoorfilters.quality_filter('temp', None, 3)
        
        assert isinstance(result, xr.Dataset)
        original_temp_qc = sample_dataset['temp_qc']
        mask = original_temp_qc <= 3
        expected_nan_count = np.sum(~mask)
        actual_nan_count = np.sum(np.isnan(result['temp'].values))
        
        assert actual_nan_count >= expected_nan_count

    def test_quality_filter_no_qc_variable(self, sample_dataset):
        """Test quality filter when quality control variable doesn't exist."""
        # Remove quality control variable
        ds_no_qc = sample_dataset.drop_vars(['temp_qc'])
        
        result = ds_no_qc.armoorfilters.quality_filter('temp', 2, 4)
        
        # Should return original dataset unchanged
        assert result.equals(ds_no_qc)

    def test_quality_filter_no_limits(self, sample_dataset):
        """Test quality filter with no limits provided."""
        result = sample_dataset.armoorfilters.quality_filter('temp', None, None)
        
        # Should return original dataset unchanged
        assert result.equals(sample_dataset)

    def test_get_mask_polygon(self, sample_2d_dataset):
        """Test get_mask method with polygon coordinates."""
        # Define a simple polygon
        coords = [(41, -8), (41, -7), (43, -7), (43, -8), (41, -8)]
        
        result = sample_2d_dataset.armoorfilters.get_mask(coords)
        
        assert result is not None
        mask, dims_name = result
        assert isinstance(mask, xr.DataArray)
        assert mask.dtype == bool
        assert len(dims_name) > 0

    def test_get_mask_no_points_inside(self, sample_2d_dataset):
        """Test get_mask when no points are inside the polygon."""
        # Define a polygon far from the data
        coords = [(50, 50), (51, 50), (51, 51), (50, 51), (50, 50)]
        
        result = sample_2d_dataset.armoorfilters.get_mask(coords)
        
        assert result is None

    def test_horizontal_selection_polygon(self, sample_2d_dataset):
        """Test horizontal selection with polygon."""
        # Define a polygon that includes some points
        coords = [(-8, 41), (-7, 41), (-7, 43), (-8, 43), (-8, 41)]
        
        with patch.object(sample_2d_dataset.armoorfilters, 'get_mask') as mock_get_mask:
            # Mock the get_mask method
            mock_mask = xr.DataArray(
                np.ones((8, 10), dtype=bool),
                dims=['y', 'x']
            )
            mock_get_mask.return_value = (mock_mask, ('y', 'x'))
            
            result = sample_2d_dataset.armoorfilters.horizontal_selection_polygon(coords)
            
            assert isinstance(result, xr.Dataset)
            mock_get_mask.assert_called_once_with(coords)

    def test_horizontal_selection_polygon_no_data(self, sample_2d_dataset):
        """Test horizontal selection when no data points are selected."""
        coords = [(-8, 41), (-7, 41), (-7, 43), (-8, 43), (-8, 41)]
        
        with patch.object(sample_2d_dataset.armoorfilters, 'get_mask') as mock_get_mask:
            mock_get_mask.return_value = None
            
            result = sample_2d_dataset.armoorfilters.horizontal_selection_polygon(coords)
            
            assert result is None

    def test_horizontal_selection_polygon_dilat(self, sample_2d_dataset):
        """Test horizontal selection with polygon dilation."""
        coords = [(-8, 41), (-7, 41), (-7, 43), (-8, 43), (-8, 41)]
        
        with patch.object(sample_2d_dataset.armoorfilters, 'get_mask') as mock_get_mask:
            mock_mask = xr.DataArray(
                np.ones((10, 10), dtype=bool),
                dims=['lat', 'lon']
            )
            mock_get_mask.return_value = (mock_mask, ('lat', 'lon'))
            
            with patch('scipy.ndimage.binary_dilation') as mock_dilation:
                mock_dilation.return_value = np.ones((10, 10), dtype=bool)
                
                result = sample_2d_dataset.armoorfilters.horizontal_selection_polygon_dilat(coords)
                
                assert isinstance(result, xr.Dataset)
                assert 'mask' in result.data_vars
                # mock_dilation.assert_called_once()

    # def test_data_selection_with_value(self, sample_dataset):
    #     """Test data selection with specific value."""
    #     result = sample_dataset.armoorfilters.data_selection('z', value=10)
        
    #     assert isinstance(result, xr.Dataset)
    #     # Check that only the specified value is selected
    #     selected_z = result['z'].values
    #     print(selected_z)
    #     assert np.all((selected_z == 10) | np.isnan(selected_z))

    # def test_data_selection_with_range(self, sample_dataset):
    #     """Test data selection with minimum and maximum."""
    #     result = sample_dataset.armoorfilters.data_selection('z', minimum=10, maximum=30)
        
    #     assert isinstance(result, xr.Dataset)
    #     # Check that values are within the specified range
    #     selected_z = result['z'].values
    #     valid_z = selected_z[~np.isnan(selected_z)]
    #     assert np.all((valid_z >= 10) & (valid_z <= 30))

    # def test_data_selection_minimum_only(self, sample_dataset):
    #     """Test data selection with minimum only."""
    #     result = sample_dataset.armoorfilters.data_selection('z', minimum=20)
        
    #     assert isinstance(result, xr.Dataset)
    #     selected_z = result['z'].values
    #     valid_z = selected_z[~np.isnan(selected_z)]
    #     assert np.all(valid_z >= 20)

    # def test_data_selection_maximum_only(self, sample_dataset):
    #     """Test data selection with maximum only."""
    #     result = sample_dataset.armoorfilters.data_selection('z', maximum=20)
        
    #     assert isinstance(result, xr.Dataset)
    #     selected_z = result['z'].values
    #     valid_z = selected_z[~np.isnan(selected_z)]
    #     assert np.all(valid_z <= 20)

    # def test_data_selection_no_conditions(self, sample_dataset):
    #     """Test data selection with no conditions."""
    #     result = sample_dataset.armoorfilters.data_selection('z')
        
    #     # Should return dataset with all NaN for the selected dimension
    #     assert isinstance(result, xr.Dataset)

    # @patch('xoa.regrid.grid2loc')
    # def test_horizontal_selection_coords(self, mock_grid2loc, sample_dataset):
    #     """Test horizontal selection at specific coordinates."""
    #     coordinates = [(-7.5, 42.5), (-6.5, 43.5)]
        
    #     # Mock the grid2loc function
    #     mock_grid2loc.return_value = np.array([15.0, 16.0])
        
    #     result = sample_dataset.armoorfilters.horizontal_selection_coords(coordinates)
        
    #     assert isinstance(result, xr.Dataset)
    #     assert 'npts' in result.dims
    #     assert result.sizes['npts'] == 2
    #     assert mock_grid2loc.call_count > 0

    # @patch('xoa.geo.get_distances')
    # def test_sel_closest_without_time_in_coords(self, mock_get_distances, sample_2d_dataset):
    #     """Test selecting closest point without time in coordinates."""
    #     # Create observation dataset
    #     obs_ds = xr.Dataset(
    #         coords={
    #             'lat': (['npts'], [42.0]),
    #             'lon': (['npts'], [-7.0]),
    #         }
    #     )
        
    #     # Mock distance calculation
    #     mock_distances = xr.DataArray(
    #         np.array([[1.0, 2.0, 3.0, 4.0, 5.0]]),
    #         dims=['member', 'lat']
    #     )
    #     mock_get_distances.return_value = mock_distances
        
    #     result = sample_2d_dataset.armoorfilters.sel_closest(obs_ds)
        
    #     assert isinstance(result, xr.Dataset)
    #     mock_get_distances.assert_called_once()

    # def test_horizontal_selection_bathy(self, sample_dataset):
    #     """Test horizontal selection by bathymetry."""
    #     result = sample_dataset.armoorfilters.horizontal_selection_bathy(
    #         minimum=200, maximum=800
    #     )
        
    #     assert isinstance(result, xr.Dataset)
    #     # The result should have bathymetry values filtered
    #     bathy_values = result['bathy'].values
    #     valid_bathy = bathy_values[~np.isnan(bathy_values)]
    #     if len(valid_bathy) > 0:
    #         assert np.all((valid_bathy >= 200) & (valid_bathy <= 800))

    # def test_vertical_selection_range(self, sample_dataset):
    #     """Test vertical selection with ranges."""
    #     vranges = [[0, 15], [20, 40]]
        
    #     result = sample_dataset.armoorfilters.vertical_selection_range('z', vranges)
        
    #     assert isinstance(result, xr.Dataset)
    #     assert 'vrange' in result.dims
    #     assert result.sizes['vrange'] == 2
    #     assert 'vbin' in result['vrange'].dims

    # @patch('xoa.regrid.regrid1d')
    # def test_vertical_selection_levels(self, mock_regrid1d, sample_dataset):
    #     """Test vertical selection at specific levels."""
    #     vlevels = [5, 15, 25]
        
    #     # Mock the regrid1d function
    #     mock_regrid1d.return_value = sample_dataset['temp'].isel(z=slice(0, 3))
        
    #     result = sample_dataset.armoorfilters.vertical_selection_levels('z', vlevels)
        
    #     assert isinstance(result, xr.Dataset)
    #     mock_regrid1d.assert_called()

    def test_time_selection_bounds(self, sample_dataset):
        """Test time selection with bounds."""
        start = '2023-01-03'
        end = '2023-01-07'
        
        result = sample_dataset.armoorfilters.time_selection_bounds(start, end)
        
        assert isinstance(result, xr.Dataset)
        assert len(result.time) <= len(sample_dataset.time)
        assert result.time.min() >= pd.to_datetime(start)
        assert result.time.max() <= pd.to_datetime(end)

    def test_time_selection_bounds_with_int_end(self, sample_dataset):
        """Test time selection with integer end (days offset)."""
        start = '2023-01-03'
        end = 5  # 5 days offset
        
        result = sample_dataset.armoorfilters.time_selection_bounds(start, end)
        
        assert isinstance(result, xr.Dataset)
        assert len(result.time) <= len(sample_dataset.time)

    def test_time_selection_bounds_no_overlap_early(self, sample_dataset):
        """Test time selection with no overlap (dates too early)."""
        start = '2022-01-01'
        end = '2022-01-05'
        
        result = sample_dataset.armoorfilters.time_selection_bounds(start, end)
        
        assert result is None

    def test_time_selection_bounds_no_overlap_late(self, sample_dataset):
        """Test time selection with no overlap (dates too late)."""
        start = '2024-01-01'
        end = '2024-01-05'
        
        result = sample_dataset.armoorfilters.time_selection_bounds(start, end)
        
        assert result is None

    # def test_time_selection_terms_with_dates(self, sample_dataset):
    #     """Test time selection with specific dates."""
    #     dates = ['2023-01-02', '2023-01-05', '2023-01-08']
        
    #     result = sample_dataset.armoorfilters.time_selection_terms(dates=dates)
        
    #     assert isinstance(result, xr.Dataset)
    #     assert len(result.time) == 3

    # def test_time_selection_terms_with_frequency(self, sample_dataset):
    #     """Test time selection with start, end, and frequency."""
    #     start = '2023-01-01'
    #     end = '2023-01-10'
    #     freq = '2D'
        
    #     result = sample_dataset.armoorfilters.time_selection_terms(
    #         start=start, end=end, freq=freq
    #     )
        
    #     assert isinstance(result, xr.Dataset)
    #     assert len(result.time) == 5  # Every 2 days over 10 days

    # @patch('armoor.base.meta_zone.get_time_bins')
    # def test_time_selection_range_seq(self, mock_get_time_bins, sample_dataset):
    #     """Test sequential time range selection."""
    #     start = '2023-01-01'
    #     end = '2023-01-10'
    #     tbin = '3D'
        
    #     # Mock time bins
    #     mock_time_bins = pd.date_range(start, end, freq=tbin)
    #     mock_get_time_bins.return_value = mock_time_bins
        
    #     result = sample_dataset.armoorfilters.time_selection_range_seq(start, end, tbin)
        
    #     assert hasattr(result, 'groups')  # Should be a GroupBy object
    #     mock_get_time_bins.assert_called_once_with(start, end, tbin)

    # def test_time_selection_range_clim_with_string(self, sample_dataset):
    #     """Test climatological time range selection with string."""
    #     start = '2023-01-01'
    #     end = '2023-01-10'
    #     tbin = 'month'
        
    #     result = sample_dataset.armoorfilters.time_selection_range_clim(start, end, tbin)
        
    #     assert hasattr(result, 'groups')  # Should be a GroupBy object

    # def test_time_selection_range_clim_with_dict(self, sample_dataset):
    #     """Test climatological time range selection with dictionary."""
    #     start = '2023-01-01'
    #     end = '2023-01-10'
    #     tbin = {'winter': [12, 1, 2], 'summer': [6, 7, 8]}
        
    #     result = sample_dataset.armoorfilters.time_selection_range_clim(start, end, tbin)
        
    #     assert hasattr(result, 'groups')  # Should be a GroupBy object

    # def test_time_selection_cut_hour(self, sample_dataset):
    #     """Test time selection cut by hour."""
    #     # Add hourly time component
    #     ds_hourly = sample_dataset.copy()
    #     ds_hourly = ds_hourly.assign_coords(
    #         time=pd.date_range('2023-01-01 06:00', periods=10, freq='H')
    #     )
        
    #     result = ds_hourly.armoorfilters.time_selection_cut('hour', 8, 12)
        
    #     assert isinstance(result, xr.Dataset)
    #     hours = result.time.dt.hour
    #     assert np.all((hours >= 8) & (hours <= 12))

    # def test_time_selection_cut_month(self, sample_dataset):
    #     """Test time selection cut by month."""
    #     # Create dataset spanning multiple months
    #     ds_monthly = sample_dataset.copy()
    #     ds_monthly = ds_monthly.assign_coords(
    #         time=pd.date_range('2023-01-01', periods=10, freq='M')
    #     )
        
    #     result = ds_monthly.armoorfilters.time_selection_cut('month', 3, 8)
        
    #     assert isinstance(result, xr.Dataset)
    #     months = result.time.dt.month
    #     assert np.all((months >= 3) & (months <= 8))

    # def test_time_selection_cut_year(self, sample_dataset):
    #     """Test time selection cut by year."""
    #     # Create dataset spanning multiple years
    #     ds_yearly = sample_dataset.copy()
    #     ds_yearly = ds_yearly.assign_coords(
    #         time=pd.date_range('2020-01-01', periods=10, freq='Y')
    #     )
        
    #     result = ds_yearly.armoorfilters.time_selection_cut('year', 2022, 2025)
        
    #     assert isinstance(result, xr.Dataset)
    #     years = result.time.dt.year
    #     assert np.all((years >= 2022) & (years <= 2025))

    # def test_time_selection_cut_invalid_freq(self, sample_dataset):
    #     """Test time selection cut with invalid frequency."""
    #     with pytest.raises(SystemExit):
    #         sample_dataset.armoorfilters.time_selection_cut('invalid', 1, 10)


class TestUtilityFunctions:
    """Test utility functions in the module."""
    
    # @patch('armoor.base.meta_zone.FILTERS')
    # def test_apply_trange_seq(self, mock_filters):
    #     """Test apply_trange function with sequential range."""
    #     mock_ds = MagicMock()
    #     mock_filter_func = MagicMock()
    #     mock_filter_func.return_value = mock_ds
    #     mock_filters.__getitem__.return_value = mock_filter_func
        
    #     metazone = {
    #         'trange_seq': '1D',
    #         'tbound': ['2023-01-01', '2023-01-10']
    #     }
        
    #     from armoor.base.meta_zone import apply_trange
    #     result = apply_trange(mock_ds, metazone)
        
    #     assert result == mock_ds
    #     mock_filters.__getitem__.assert_called_with('trange_seq')

    # @patch('armoor.base.meta_zone.FILTERS')
    # def test_apply_vrange(self, mock_filters):
    #     """Test apply_vrange function."""
    #     mock_ds = MagicMock()
    #     mock_ds.attrs = {'test': 'value'}
    #     mock_filter_func = MagicMock()
    #     mock_filter_func.return_value = mock_ds
    #     mock_filters.__getitem__.return_value = mock_filter_func
        
    #     metazone = {
    #         'vrange': {'z': [0, 100]}
    #     }
        
    #     from armoor.base.meta_zone import apply_vrange
    #     result = apply_vrange(mock_ds, metazone)
        
    #     assert result == mock_ds
    #     mock_filters.__getitem__.assert_called_with('vrange')

    # def test_get_time_bins(self):
    #     """Test get_time_bins function."""
    #     from armoor.base.meta_zone import get_time_bins
        
    #     start = '2023-01-01'
    #     end = '2023-01-10'
    #     tbin = '2D'
        
    #     result = get_time_bins(start, end, tbin)
        
    #     assert isinstance(result, pd.DatetimeIndex)
    #     assert len(result) == 5  # 0, 2, 4, 6, 8 days
    #     assert result[0] == pd.to_datetime(start)

    def test_create_optimized_mask(self):
        """Test create_optimized_mask function."""
        from armoor.base.filters import create_optimized_mask

        # Create test dataset
        ds = xr.Dataset({
            'temp': (['x', 'y'], np.random.rand(5, 5) * 30)
        })
        
        bins = [(10, 15), (20, 25)]
        
        result = create_optimized_mask(ds, 'temp', bins)
        
        assert isinstance(result, xr.DataArray)
        assert result.dtype == bool
        assert result.shape == ds['temp'].shape


# class TestEdgeCases:
#     """Test edge cases and error conditions."""
    
#     def test_quality_filter_no_start_date_sys_exit(self):
#         """Test that missing start date causes sys.exit in time_selection_bounds."""
#         ds = xr.Dataset({
#             'temp': (['time'], [1, 2, 3]),
#             'time': pd.date_range('2023-01-01', periods=3)
#         })
        
#         with pytest.raises(SystemExit):
#             ds.armoorfilters.time_selection_bounds(None, '2023-01-05')

#     def test_time_selection_range_seq_invalid_regex(self):
#         """Test invalid regex pattern in time_selection_range_seq."""
#         ds = xr.Dataset({
#             'temp': (['time'], [1, 2, 3]),
#             'time': pd.date_range('2023-01-01', periods=3)
#         })
        
#         with pytest.raises(SystemExit):
#             ds.armoorfilters.time_selection_range_seq('2023-01-01', '2023-01-10', '1M')

    # def test_empty_dataset_handling(self):
    #     """Test handling of empty datasets."""
    #     empty_ds = xr.Dataset()
        
    #     # Should not raise errors for most operations
    #     result = empty_ds.armoorfilters.quality_filter('temp', 1, 5)
    #     assert isinstance(result, xr.Dataset)
        
    #     result = empty_ds.armoorfilters.data_selection('z', minimum=0, maximum=100)
    #     assert isinstance(result, xr.Dataset)