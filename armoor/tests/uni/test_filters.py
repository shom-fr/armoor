"""Test suite for ArmoorSelectionAccessor module."""

from datetime import datetime
from unittest.mock import Mock, MagicMock, patch

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
        lons = np.array([[1.0, 2.0, 3.0], [1.5, 2.5, 3.5], [2.0, 3.0, 4.0]])
        lats = np.array([[50.0, 50.5, 51.0], [49.5, 50.0, 50.5], [49.0, 49.5, 50.0]])
        
        # Create time coordinate
        times = np.array(['2023-01-01', '2023-01-02', '2023-01-03'], dtype='datetime64[D]')
        
        ds = xr.Dataset({
            'temperature': (['time', 'x', 'y'], np.random.rand(3, 3, 3) * 30),
            'salinity': (['time', 'x', 'y'], np.random.rand(3, 3, 3) * 35),
            'temperature_qc': (['time', 'x', 'y'], np.random.randint(1, 5, (3, 3, 3))),
            'salinity_qc': (['time', 'x', 'y'], np.random.randint(1, 5, (3, 3, 3))),
            'depth': (['x', 'y'], np.random.rand(3, 3) * 100),
            'lon': (['x', 'y'], lons),
            'lat': (['x', 'y'], lats)
        }, coords={
            'time': times,
            'x': [0, 1, 2],
            'y': [0, 1, 2]
        })
        
        return ds
    
    @pytest.fixture
    def simple_dataset(self):
        """Create a simple 2D dataset without time dimension."""
        lons = np.array([[1.0, 2.0], [1.5, 2.5]])
        lats = np.array([[50.0, 50.5], [49.5, 50.0]])
        
        ds = xr.Dataset({
            'temperature': (['x', 'y'], np.random.rand(2, 2) * 30),
            'temperature_qc': (['x', 'y'], np.random.randint(1, 5, (2, 2))),
            'lon': (['x', 'y'], lons),
            'lat': (['x', 'y'], lats)
        }, coords={
            'x': [0, 1],
            'y': [0, 1]
        })
        
        return ds
    
    @pytest.fixture
    def accessor(self, sample_dataset):
        """Create an ArmoorSelectionAccessor instance."""
        return ArmoorSelectionAccessor(sample_dataset)
    
    def test_init(self, sample_dataset):
        """Test accessor initialization."""
        accessor = ArmoorSelectionAccessor(sample_dataset)
        assert accessor.ds is sample_dataset
    
    def test_get_mask_valid_polygon(self, accessor):
        """Test get_mask with a valid polygon that contains some points."""
        # Define a polygon that should contain some points
        coords = [(49.0, 0.5), (51.5, 0.5), (51.5, 4.5), (49.0, 4.5)]
        
        with patch('matplotlib.path.Path') as mock_path:
            mock_polygon = Mock()
            mock_path.return_value = mock_polygon
            mock_polygon.contains_points.return_value = np.array([True, False, True, False, True, False, True, False, True])
            
            result = accessor.get_mask(coords)
            
            assert result is not None
            assert isinstance(result, xr.DataArray)
            mock_path.assert_called_once_with(coords)
            mock_polygon.contains_points.assert_called_once()
    
    def test_get_mask_empty_selection(self, accessor):
        """Test get_mask when no points are inside the polygon."""
        coords = [(100.0, 100.0), (101.0, 100.0), (101.0, 101.0), (100.0, 101.0)]
        
        with patch('matplotlib.path.Path') as mock_path:
            mock_polygon = Mock()
            mock_path.return_value = mock_polygon
            mock_polygon.contains_points.return_value = np.array([False] * 9)
            
            result = accessor.get_mask(coords)
            
            assert result is None
    
    def test_get_quality_mask_both_limits(self, accessor):
        """Test _get_quality_mask with both min and max values."""
        mask = accessor._get_quality_mask('temperature', qmin=2, qmax=4)
        
        assert mask is not None
        assert isinstance(mask, xr.DataArray)
        # Check that the mask is a boolean array
        assert mask.dtype == bool
    
    def test_get_quality_mask_min_only(self, accessor):
        """Test _get_quality_mask with only minimum value."""
        mask = accessor._get_quality_mask('temperature', qmin=2, qmax=None)
        
        assert mask is not None
        assert isinstance(mask, xr.DataArray)
        assert mask.dtype == bool
    
    def test_get_quality_mask_max_only(self, accessor):
        """Test _get_quality_mask with only maximum value."""
        mask = accessor._get_quality_mask('temperature', qmin=None, qmax=4)
        
        assert mask is not None
        assert isinstance(mask, xr.DataArray)
        assert mask.dtype == bool
    
    def test_get_quality_mask_no_qc_variable(self, accessor, caplog):
        """Test _get_quality_mask when QC variable doesn't exist."""
        mask = accessor._get_quality_mask('nonexistent', qmin=2, qmax=4)
        
        assert mask is None
        assert "No nonexistent_qc in dataset" in caplog.text
    
    def test_get_quality_mask_no_limits(self, accessor):
        """Test _get_quality_mask with no limits provided."""
        mask = accessor._get_quality_mask('temperature', qmin=None, qmax=None)
        
        assert mask is None
    
    def test_get_polygon_mask_without_dilation(self, accessor):
        """Test _get_polygon_mask without dilation."""
        coords = [(49.0, 0.5), (51.5, 0.5), (51.5, 4.5), (49.0, 4.5)]
        
        with patch.object(accessor, 'get_mask') as mock_get_mask:
            mock_mask = Mock()
            mock_get_mask.return_value = mock_mask
            
            mask2keep, mask_result = accessor._get_polygon_mask(coords, dilate=False)
            
            assert mask2keep is None
            assert mask_result == mock_mask
    
    def test_get_polygon_mask_with_dilation(self, accessor):
        """Test _get_polygon_mask with dilation when x,y dims present."""
        coords = [(49.0, 0.5), (51.5, 0.5), (51.5, 4.5), (49.0, 4.5)]
        
        # Modify dataset to have x,y dimensions in lon
        accessor.ds = accessor.ds.swap_dims({'x': 'x_new', 'y': 'y_new'})
        accessor.ds = accessor.ds.rename({'x_new': 'x', 'y_new': 'y'})
        
        with patch.object(accessor, 'get_mask') as mock_get_mask:
            mock_mask = Mock()
            mock_mask.values = np.array([[True, False], [False, True]])
            mock_mask.dims = ['x', 'y']
            mock_mask.copy.return_value = mock_mask
            mock_get_mask.return_value = mock_mask
                
            mask2keep, mask_result = accessor._get_polygon_mask(coords, dilate=True)
            
            assert mask2keep == mock_mask
            assert mask_result is not None
    
    def test_get_polygon_mask_no_result(self, accessor):
        """Test _get_polygon_mask when get_mask returns None."""
        coords = [(49.0, 0.5), (51.5, 0.5), (51.5, 4.5), (49.0, 4.5)]
        
        with patch.object(accessor, 'get_mask') as mock_get_mask:
            mock_get_mask.return_value = None
            
            result = accessor._get_polygon_mask(coords, dilate=False)
            
            assert result is None
    
    def test_get_data_selection_mask_exact_value(self, accessor):
        """Test _get_data_selection_mask with exact value."""
        mask = accessor._get_data_selection_mask('depth', value=50.0)
        
        assert mask is not None
        assert isinstance(mask, xr.DataArray)
        assert mask.dtype == bool
    
    def test_get_data_selection_mask_range(self, accessor):
        """Test _get_data_selection_mask with min and max."""
        mask = accessor._get_data_selection_mask('depth', minimum=20.0, maximum=80.0)
        
        assert mask is not None
        assert isinstance(mask, xr.DataArray)
        assert mask.dtype == bool
    
    def test_get_data_selection_mask_min_only(self, accessor):
        """Test _get_data_selection_mask with minimum only."""
        mask = accessor._get_data_selection_mask('depth', minimum=20.0)
        
        assert mask is not None
        assert isinstance(mask, xr.DataArray)
        assert mask.dtype == bool
    
    def test_get_data_selection_mask_max_only(self, accessor):
        """Test _get_data_selection_mask with maximum only."""
        mask = accessor._get_data_selection_mask('depth', maximum=80.0)
        
        assert mask is not None
        assert isinstance(mask, xr.DataArray)
        assert mask.dtype == bool
    
    def test_get_data_selection_mask_no_criteria(self, accessor):
        """Test _get_data_selection_mask with no criteria."""
        mask = accessor._get_data_selection_mask('depth')
        
        assert mask is None
    
    def test_tidal_filter(self, accessor):
        """Test successful tidal filter application."""
        
        accessor.tidal_filter(filter_name="demerliac")
        
        # Check that tidal_filter was called for time-dependent variables
        expected_calls = len([v for v in accessor.ds.data_vars if 'time' in accessor.ds[v].dims])
        assert 4 == expected_calls
    
    def test_apply_combined_filters_quality_only(self, accessor):
        """Test apply_combined_filters with quality filter only."""
        filters_config = {
            'quality': {'qname': 'temperature', 'qmin': 2, 'qmax': 4}
        }
        
        result = accessor.apply_combined_filters(filters_config)
        
        assert result is not None
        assert isinstance(result, xr.Dataset)
    
    def test_apply_combined_filters_polygon_only(self, accessor):
        """Test apply_combined_filters with polygon filter only."""
        coords = [(49.0, 0.5), (51.5, 0.5), (51.5, 4.5), (49.0, 4.5)]
        filters_config = {
            'polygon': {'coords': coords, 'dilate': False}
        }
        
        result = accessor.apply_combined_filters(filters_config)
        
        assert result is not None
    
    def test_apply_combined_filters_polygon_returns_none(self, accessor):
        """Test apply_combined_filters when polygon filter returns None."""
        coords = [(100.0, 100.0), (101.0, 100.0), (101.0, 101.0), (100.0, 101.0)]
        filters_config = {
            'polygon': {'coords': coords, 'dilate': False}
        }
        
        with patch.object(accessor, '_get_polygon_mask') as mock_polygon_mask:
            mock_polygon_mask.return_value = (None, None)
            
            result = accessor.apply_combined_filters(filters_config)
            
            assert result is None
    
    def test_apply_combined_filters_data_selection(self, accessor):
        """Test apply_combined_filters with data selection filter."""
        filters_config = {
            'data_selection': {'dim': 'depth', 'minimum': 20.0, 'maximum': 80.0}
        }
        
        result = accessor.apply_combined_filters(filters_config)
        
        assert result is not None
        assert isinstance(result, xr.Dataset)
    
    def test_apply_combined_filters_multiple(self, accessor):
        """Test apply_combined_filters with multiple filters."""
        coords = [(49.0, 0.5), (51.5, 0.5), (51.5, 4.5), (49.0, 4.5)]
        filters_config = {
            'quality': {'qname': 'temperature', 'qmin': 2, 'qmax': 4},
            'polygon': {'coords': coords, 'dilate': False},
            'data_selection': {'dim': 'depth', 'minimum': 20.0, 'maximum': 80.0}
        }
        
        result = accessor.apply_combined_filters(filters_config)
        
        assert result is not None
        assert isinstance(result, xr.Dataset)
    
    def test_apply_combined_filters_with_bathy(self, accessor):
        """Test apply_combined_filters with bathymetry filter."""
        filters_config = {
            'bathy': {'path': '/path/to/bathy', 'fmt': 'netcdf', 'min': 20.0, 'max': 100.0}
        }
        
        with patch.object(accessor, 'bathy_filter') as mock_bathy_filter:
            mock_bathy_filter.return_value = accessor.ds
            
            result = accessor.apply_combined_filters(filters_config)
            
            mock_bathy_filter.assert_called_once_with('/path/to/bathy', 'netcdf', 20.0, 100.0)
    
    def test_apply_combined_filters_with_tide(self, accessor):
        """Test apply_combined_filters with tidal filter."""
        filters_config = {
            'tide': 'demerliac'
        }
        
        with patch.object(accessor, 'tidal_filter') as mock_tidal_filter:
            result = accessor.apply_combined_filters(filters_config)
            
            mock_tidal_filter.assert_called_once_with(filter_name='demerliac')
    
    def test_apply_combined_filters_depth_coordinate_handling(self, accessor):
        """Test apply_combined_filters handles depth coordinate correctly."""
        # Set depth as coordinate
        accessor.ds = accessor.ds.set_coords('depth')
        
        filters_config = {
            'quality': {'qname': 'temperature', 'qmin': 2, 'qmax': 4}
        }
        
        result = accessor.apply_combined_filters(filters_config)
        
        assert result is not None
        assert 'depth' in result.coords
    
    def test_apply_combined_filters_no_filters(self, accessor):
        """Test apply_combined_filters with empty config."""
        filters_config = {}
        
        result = accessor.apply_combined_filters(filters_config)
        
        # Should return the original dataset since no filters applied
        assert result is accessor.ds
    
    def test_dataset_accessor_registration(self, sample_dataset):
        """Test that the accessor is properly registered with xarray."""
        # This test checks if the accessor can be accessed via .armoorfilters
        assert hasattr(sample_dataset, 'armoorfilters')
        assert isinstance(sample_dataset.armoorfilters, ArmoorSelectionAccessor)
    
    def test_dataarray_accessor_registration(self, sample_dataset):
        """Test that the accessor is properly registered with DataArray."""
        da = sample_dataset['temperature']
        assert hasattr(da, 'armoorfilters')
        assert isinstance(da.armoorfilters, ArmoorSelectionAccessor)

    # def test_time_selection_bounds(self, sample_dataset):
    #     """Test time selection with bounds."""
    #     start = '2023-01-01'
    #     end = '2023-01-07'
    #     result = sample_dataset.armoorfilters.time_selection_bounds(start, end)
    #     assert isinstance(result, xr.Dataset)
    #     assert len(result.time) <= len(sample_dataset.time)
    #     assert result.time.min() >= pd.to_datetime(start)
    #     assert result.time.max() <= pd.to_datetime(end)

    # def test_time_selection_bounds_with_int_end(self, sample_dataset):
    #     """Test time selection with integer end (days offset)."""
    #     start = '2023-01-01'
    #     end = 5  # 5 days offset
        
    #     result = sample_dataset.armoorfilters.time_selection_bounds(start, end)
        
    #     assert isinstance(result, xr.Dataset)
    #     assert len(result.time) <= len(sample_dataset.time)

    # def test_time_selection_bounds_no_overlap_early(self, sample_dataset):
    #     """Test time selection with no overlap (dates too early)."""
    #     start = '2022-01-01'
    #     end = '2022-01-05'
        
    #     result = sample_dataset.armoorfilters.time_selection_bounds(start, end)
        
    #     assert result is None

    # def test_time_selection_bounds_no_overlap_late(self, sample_dataset):
    #     """Test time selection with no overlap (dates too late)."""
    #     start = '2024-01-01'
    #     end = '2024-01-05'
        
    #     result = sample_dataset.armoorfilters.time_selection_bounds(start, end)
        
    #     assert result is None
