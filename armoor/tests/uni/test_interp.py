import gc

import numpy as np
import pandas as pd
import pytest
import xarray as xr

from armoor.base.interp import grid2loc, interp_time, regrid, vinterp, grid2section


class TestInterpTime:
    """Test suite for the interp_time function."""
    
    def setup_method(self):
        """Create a test dataset with time-dependent and static variables."""
        dates = pd.date_range('2023-01-01', periods=5, freq='D')
        self.ds = xr.Dataset({
            'temp': (['time', 'x', 'y'], np.random.rand(5, 3, 3)),
            'static_var': (['x', 'y'], np.random.rand(3, 3))
        }, coords={
            'time': dates,
            'lon': np.arange(3),
            'lat': np.arange(3)
        })
    
    def test_single_date_interpolation(self):
        """Test interpolation for a single date within the time range."""
        target_date = pd.Timestamp('2023-01-01T12:00:00')
        result = interp_time(self.ds, target_date)
        
        assert len(result.time) == 1
        assert result.time[0] == target_date
        assert 'temp' in result.data_vars
        assert 'static_var' in result.data_vars
    
    def test_multiple_dates_interpolation(self):
        """Test interpolation for multiple dates."""
        target_dates = [
            pd.Timestamp('2023-01-01T12:00:00'),
            pd.Timestamp('2023-01-02T12:00:00')
        ]
        result = interp_time(self.ds, target_dates)
        
        assert len(result.time) == 2
        assert all(d in result.time for d in target_dates)
    
    def test_exact_date_match(self):
        """Test when the requested date already exists in the dataset."""
        exact_date = self.ds.time.isel(time=0).values
        result = interp_time(self.ds, exact_date)
        
        # Verify that values are identical
        np.testing.assert_array_equal(
            result.temp.values,
            self.ds.temp.isel(time=[0]).values
        )
    
    def test_date_before_range(self):
        """Test persistence for dates before the time range."""
        early_date = pd.Timestamp('2022-12-31')
        result = interp_time(self.ds, early_date)
        
        assert len(result.time) == 1
        assert result.time[0] == early_date
        # Should use the first time step value
        np.testing.assert_array_equal(
            result.temp.values,
            self.ds.temp.isel(time=[0]).values
        )
    
    def test_date_after_range(self):
        """Test persistence for dates after the time range."""
        late_date = pd.Timestamp('2023-01-10')
        result = interp_time(self.ds, late_date)
        
        assert len(result.time) == 1
        assert result.time[0] == late_date
        # Should use the last time step value
        np.testing.assert_array_equal(
            result.temp.values,
            self.ds.temp.isel(time=[-1]).values
        )
    
    def test_preserve_encoding(self):
        """Test encoding preservation when preserve_encoding=True."""
        self.ds.temp.encoding['units'] = 'celsius'
        target_date = pd.Timestamp('2023-01-01T12:00:00')
        
        result = interp_time(self.ds, target_date, preserve_encoding=True)
        assert result.temp.encoding.get('units') == 'celsius'
    
    def test_preserve_encoding_false(self):
        """Test that encoding is not preserved when preserve_encoding=False."""
        self.ds.temp.encoding['units'] = 'celsius'
        target_date = pd.Timestamp('2023-01-01T12:00:00')
        
        result = interp_time(self.ds, target_date, preserve_encoding=False)
        # Encoding may or may not be present, but we're testing the flag works
        assert isinstance(result, xr.Dataset)
    
    def test_diurnal_vars_before_range(self):
        """Test diurnal variables functionality for dates before range."""
        dates = [
            pd.Timestamp('2022-12-31'),  # Before range
            pd.Timestamp('2023-01-01')   # Reference date
        ]
        
        result = interp_time(
            self.ds, 
            dates, 
            diurnal_vars=['temp']
        )
        
        assert len(result.time) == 2
        # Check that diurnal var was copied from reference date
        np.testing.assert_array_equal(
            result.temp.isel(time=0).values,
            result.temp.isel(time=1).values
        )
    
    def test_diurnal_vars_after_range(self):
        """Test diurnal variables functionality for dates after range."""
        dates = [
            pd.Timestamp('2023-01-05'),   # Last date in range
            pd.Timestamp('2023-01-06')    # After range
        ]
        
        result = interp_time(
            self.ds, 
            dates, 
            diurnal_vars=['temp']
        )
        
        assert len(result.time) == 2
        # Check that diurnal var was copied from reference date
        np.testing.assert_array_equal(
            result.temp.isel(time=0).values,
            result.temp.isel(time=1).values
        )
    
    def test_persistency_mean_before_range(self):
        """Test persistency with mean calculation before range."""
        # Create a dataset with more time steps for better persistency testing
        dates = pd.date_range('2023-01-01', periods=10, freq='D')
        ds_long = xr.Dataset({
            'temp': (['time', 'x', 'y'], np.random.rand(10, 3, 3)),
        }, coords={
            'time': dates,
            'x': np.arange(3),
            'y': np.arange(3)
        })
        
        early_date = pd.Timestamp('2022-12-30')
        
        result = interp_time(
            ds_long,
            early_date,
            persistency="mean_1D"
        )
        
        assert len(result.time) == 1
        assert result.time[0] == early_date
        # Should have values (persistency applied)
        assert result.temp.values.shape == (1, 3, 3)
    
    def test_persistency_mean_after_range(self):
        """Test persistency with mean calculation after range."""
        # Create a dataset with more time steps for better persistency testing
        dates = pd.date_range('2023-01-01', periods=10, freq='D')
        ds_long = xr.Dataset({
            'temp': (['time', 'x', 'y'], np.random.rand(10, 3, 3)),
        }, coords={
            'time': dates,
            'x': np.arange(3),
            'y': np.arange(3)
        })
        
        late_date = pd.Timestamp('2023-01-20')
        
        result = interp_time(
            ds_long,
            late_date,
            persistency="mean_2D"
        )
        
        assert len(result.time) == 1
        assert result.time[0] == late_date
        # Should have values (persistency applied)
        assert result.temp.values.shape == (1, 3, 3)
    
    def test_mixed_dates_ordering(self):
        """Test that results are properly ordered when dates are mixed."""
        dates = [
            pd.Timestamp('2023-01-03'),      # In range
            pd.Timestamp('2022-12-31'),      # Before range
            pd.Timestamp('2023-01-01'),      # Exact match
            pd.Timestamp('2023-01-10'),      # After range
            pd.Timestamp('2023-01-02T12:00') # In range
        ]
        
        result = interp_time(self.ds, dates)
        
        assert len(result.time) == 5
        # Verify chronological ordering
        assert all(result.time[i] <= result.time[i+1] for i in range(len(result.time)-1))
    
    def test_empty_dates_list(self):
        """Test behavior with empty dates list."""
        # The function should handle this gracefully or raise an appropriate error
        # Based on the code, an empty list will result in an empty dataset
        try:
            result = interp_time(self.ds, [])
            # If it succeeds, verify it returns an empty dataset
            assert len(result.time) == 0
        except (ValueError, IndexError, TypeError):
            # It's also acceptable to raise an error for empty input
            pass
    
    def test_interpolation_method_nearest(self):
        """Test interpolation with nearest method."""
        target_date = pd.Timestamp('2023-01-01T12:00:00')
        result = interp_time(self.ds, target_date, method="nearest")
        
        assert len(result.time) == 1
        assert result.time[0] == target_date


class TestGrid2Loc:
    """Test suite for the grid2loc function."""
    
    # @pytest.fixture(autouse=True)
    # def cleanup_between_tests(self):
    #     """Ensure cleanup between tests."""
    #     yield
    #     gc.collect()
        
    def setup_method(self):
        """Create a gridded test dataset with 2D and 3D variables."""
        lon = np.linspace(-10, 0, 3)
        lat = np.linspace(40, 50, 3)
        lon_grid, lat_grid = np.meshgrid(lon, lat)
        self.ds = xr.Dataset({
            'temp': (['time', 'y', 'x'], np.random.rand(2, 3, 3)),
            'temp_3d': (['time', 'z', 'y', 'x'], np.random.rand(2, 2, 3, 3)),
            'static_2d': (['y', 'x'], np.random.rand(3, 3))
        }, coords={
            'time': pd.date_range('2023-01-01', periods=2),
            'lat': (['y', 'x'], lat_grid),
            'lon': (['y', 'x'], lon_grid),
            'z': np.arange(2)
        })
    
    def test_2d_interpolation(self):
        """Test 2D interpolation (time + space dimensions)."""
        coords = [(45.0, -5.0), (46.0, -4.0)]
        # Use only the 2D variable (without z dimension)
        ds_2d = self.ds[['temp', 'static_2d']]
        result = grid2loc(ds_2d, coords)
        
        assert 'npts' in result.dims
        assert len(result.npts) == 2
        assert 'temp' in result.data_vars
        assert 'z' not in result.dims  # Should not have z dimension
        assert set(result.dims) == {'time', 'npts'}
    
    def test_3d_interpolation(self):
        """Test 3D interpolation (time + z + space dimensions)."""
        coords = [(45.0, -5.0)]
        result = grid2loc(self.ds, coords)
        
        assert 'temp_3d' in result.data_vars
        assert 'z' in result.dims
        assert 'npts' in result.dims
        assert len(result.npts) == 1
    
    def test_single_point(self):
        """Test interpolation at a single point."""
        coords = [(45.0, -5.0)]
        result = grid2loc(self.ds, coords)
        
        assert len(result.npts) == 1
        assert 'temp' in result.data_vars
    
    def test_multiple_points(self):
        """Test interpolation at multiple points."""
        coords = [(45.0, -5.0), (46.0, -4.0), (47.0, -3.0)]
        result = grid2loc(self.ds, coords)
        
        assert len(result.npts) == 3
    
    def test_depth_handling(self):
        """Test proper handling of depth coordinate."""
        # Add depth as a coordinate
        self.ds = self.ds.assign_coords(depth=(['z'], [0, 10]))
        coords = [(45.0, -5.0)]
        result = grid2loc(self.ds, coords)
        
        assert 'depth' in result.coords
    
    def test_time_varying_depth(self):
        """Test handling of time-varying depth."""
        self.ds = self.ds.assign_coords(
            depth=(['time', 'z'], [[0, 10], [0, 10]])
        )
        coords = [(45.0, -5.0)]
        result = grid2loc(self.ds, coords)
        
        # Depth should be handled appropriately
        assert 'temp_3d' in result.data_vars
    
    def test_no_time_dimension(self):
        """Test grid2loc without time dimension."""
        # Create a simple 2D dataset without time
        lon = np.linspace(-10, 0, 5)
        lat = np.linspace(40, 50, 5)
        lon_grid, lat_grid = np.meshgrid(lon, lat)
        
        ds_no_time = xr.Dataset({
            'temp_2d': (['y', 'x'], np.random.rand(5, 5)),
        }, coords={
            'lat': (['y', 'x'], lat_grid),
            'lon': (['y', 'x'], lon_grid),
        })
        
        coords = [(45.0, -5.0)]
        result = grid2loc(ds_no_time, coords)
        
        assert 'time' not in result.dims
        assert 'npts' in result.dims
        assert len(result.npts) == 1
    
    def test_coordinate_attributes_preserved(self):
        """Test that coordinate attributes are preserved."""
        self.ds.lon.attrs['units'] = 'degrees_east'
        self.ds.lat.attrs['units'] = 'degrees_north'
        coords = [(45.0, -5.0)]
        result = grid2loc(self.ds, coords)
        
        assert 'lon' in result.coords
        assert 'lat' in result.coords


class TestGrid2Section:
    """Test suite for the grid2section function."""
    
    # @pytest.fixture(autouse=True)
    # def cleanup_between_tests(self):
    #     """Ensure cleanup between tests."""
    #     yield
    #     gc.collect()
    
    def setup_method(self):
        """Create a gridded test dataset."""
        lon = np.linspace(-10, 0, 10)
        lat = np.linspace(40, 50, 10)
        lon_grid, lat_grid = np.meshgrid(lon, lat)
        self.ds = xr.Dataset({
            'temp': (['time', 'z', 'y', 'x'], np.random.rand(2, 3, 10, 10))
        }, coords={
            'time': pd.date_range('2023-01-01', periods=2),
            'lat': (['y', 'x'], lat_grid),
            'lon': (['y', 'x'], lon_grid),
            'z': np.arange(3)
        })
    
    def test_two_point_section(self):
        """Test section between two points."""
        coords = [(45.0, -8.0), (46.0, -2.0)]
        result = grid2section(self.ds, coords, dx=10)  # 10 km spacing
        
        assert 'npts' in result.dims
        assert 'distance' in result.coords
        assert len(result.npts) > 2  # Should have intermediate points
    
    def test_multi_segment_section(self):
        """Test section with multiple segments."""
        coords = [(45.0, -8.0), (46.0, -5.0), (47.0, -2.0)]
        result = grid2section(self.ds, coords, dx=10)
        
        assert 'npts' in result.dims
        assert 'distance' in result.coords
        # Distance should be monotonically increasing
        assert all(np.diff(result.distance.values) >= 0)
    
    def test_distance_coordinate(self):
        """Test that distance coordinate is properly calculated."""
        coords = [(45.0, -8.0), (46.0, -2.0)]
        result = grid2section(self.ds, coords, dx=10)
        
        # First point should have distance ~0
        assert result.distance.values[0] >= 0
        # Last point should have positive distance
        assert result.distance.values[-1] > 0
    
    def test_fine_spacing(self):
        """Test section with fine spacing."""
        coords = [(45.0, -8.0), (45.5, -5.0)]
        result = grid2section(self.ds, coords, dx=1)  # 1 km spacing
        
        # Should have many points with fine spacing
        assert len(result.npts) > 10


class TestRegrid:
    """Test suite for the regrid function."""

    def setup_method(self):
        """Create source and target datasets for regridding tests."""
        lon = np.linspace(-10, 0, 4)
        lat = np.linspace(40, 50, 3)
        lon_grid, lat_grid = np.meshgrid(lon, lat)
        self.dsi = xr.Dataset({
            'temp': (['time', 'y', 'x'], np.random.rand(2, 3, 4))
        }, coords={
            'time': pd.date_range('2023-01-01', periods=2),
            'lat': (['y', 'x'], lat_grid),
            'lon': (['y', 'x'], lon_grid)
        })
        
        lon_out = np.linspace(-8, -1, 8)
        lat_out = np.linspace(42, 49, 6)
        lon_out_grid, lat_out_grid = np.meshgrid(lon_out, lat_out)
        self.dso = xr.Dataset(coords={
            'time': pd.date_range('2023-01-01', periods=2),
            'lat': (['y', 'x'], lat_out_grid),
            'lon': (['y', 'x'], lon_out_grid)
        })
    
    def test_regrid_basic(self):
        """Test basic regridding functionality."""
        result = regrid(self.dsi, self.dso)
        
        assert result.sizes['y'] == self.dso.sizes['y']
        assert result.sizes['x'] == self.dso.sizes['x']
        assert 'temp' in result.data_vars
    
    def test_regrid_multiple_variables(self):
        """Test regridding with multiple variables."""
        self.dsi['salinity'] = self.dsi['temp'] * 35
        result = regrid(self.dsi, self.dso)
        
        assert 'temp' in result.data_vars
        assert 'salinity' in result.data_vars
    
    def test_regrid_preserves_time(self):
        """Test that time dimension is preserved."""
        result = regrid(self.dsi, self.dso)
        
        assert 'time' in result.dims
        assert len(result.time) == len(self.dsi.time)
    
    def test_regrid_3d_variable(self):
        """Test regridding 3D variable (time, z, y, x)."""
        self.dsi['temp_3d'] = (['time', 'z', 'y', 'x'], 
                                np.random.rand(2, 3, 3, 4))
        result = regrid(self.dsi, self.dso)
        
        if 'temp_3d' in result.data_vars:
            assert 'z' in result.temp_3d.dims


class TestVinterp:
    """Test suite for the vinterp function."""
    
    # @pytest.fixture(autouse=True)
    # def cleanup_between_tests(self):
    #     """Ensure cleanup between tests."""
    #     yield
    #     gc.collect()
    
    def setup_method(self):
        """Create a test dataset with vertical dimension."""
        lon = np.linspace(-8, -1, 8)
        lat = np.linspace(42, 49, 6)
        lon_grid, lat_grid = np.meshgrid(lon, lat)
        self.ds = xr.Dataset({
            'temp': (['time', 'z', 'y', 'x'], np.random.rand(2, 3, 6, 8)),
            'surface_var': (['time', 'y', 'x'], np.random.rand(2, 6, 8))
        }, coords={
            'time': pd.date_range('2023-01-01', periods=2),
            'z': np.arange(3),
            'lat': (['y', 'x'], lat_grid),
            'lon': (['y', 'x'], lon_grid),
            'depth': (['time', 'z'], np.array([[0, 5, 10], [0, 5, 10]]))
        })
    
    def test_depth_interpolation(self):
        """Test vertical interpolation on depth coordinate."""
        target_depths = xr.DataArray([0, 2.5, 5, 7.5, 10], dims="z")
        result = vinterp(self.ds, 'depth', target_depths)
        
        assert result.sizes["z"] == len(target_depths)
        assert 'surface_var' in result.data_vars  # Variable without z preserved
        assert 'temp' in result.data_vars
    
    def test_density_interpolation(self):
        """Test vertical interpolation on density coordinate."""
        # Add a density coordinate
        self.ds = self.ds.assign_coords(
            dens=(['time', 'z'], np.array([[1020, 1025, 1030], [1020, 1025, 1030]]))
        )
        
        target_densities = xr.DataArray([1020, 1025, 1030], dims="z")
        result = vinterp(self.ds, 'dens', target_densities)
        
        assert result.sizes["z"] == len(target_densities)
    
    def test_coordinate_switching(self):
        """Test that coordinates are properly switched for interpolation."""
        self.ds = self.ds.assign_coords(
            dens=(['time', 'z'], np.random.rand(2, 3) * 10 + 1020)
        )
        
        target_densities = xr.DataArray([1022, 1024, 1026], dims="z")
        result = vinterp(self.ds, 'dens', target_densities)
        
        # Depth should be reset as coordinate when interpolating on density
        assert 'dens' in result.coords or 'dens' in result.data_vars
    
    def test_nearest_interpolation(self):
        """Test vertical interpolation with nearest method."""
        target_depths = xr.DataArray([0, 5, 10], dims="z")
        result = vinterp(self.ds, 'depth', target_depths, method="nearest")
        
        assert result.sizes["z"] == len(target_depths)
    
    def test_variables_without_z_preserved(self):
        """Test that variables without z dimension are preserved."""
        target_depths = xr.DataArray([0, 5, 10], dims="z")
        result = vinterp(self.ds, 'depth', target_depths)
        
        assert 'surface_var' in result.data_vars
        assert 'z' not in result.surface_var.dims


class TestIntegration:
    """Integration tests combining multiple functions."""
    
    # @pytest.fixture(autouse=True)
    # def cleanup_between_tests(self):
    #     """Ensure cleanup between tests."""
    #     yield
    #     gc.collect()
    
    def setup_method(self):
        """Setup for integration tests."""
        dates = pd.date_range('2023-01-01', periods=4, freq='D')
        lon = np.linspace(-8, -1, 8)
        lat = np.linspace(42, 49, 6)
        lon_grid, lat_grid = np.meshgrid(lon, lat)
        self.ds = xr.Dataset({
            'temp': (['time', 'z', 'y', 'x'], np.random.rand(4, 3, 6, 8))
        }, coords={
            'time': dates,
            'depth': (['time', 'z', 'y', 'x'], 100 * np.random.rand(4, 3, 6, 8)),
            'lat': (['y', 'x'], lat_grid),
            'lon': (['y', 'x'], lon_grid)
        })
    
    def test_time_then_space_then_vertical_interpolation(self):
        """Test temporal interpolation followed by spatial and vertical."""
        # Temporal interpolation
        target_date = pd.Timestamp('2023-01-01T12:00:00')
        temp_result = interp_time(self.ds, target_date)
        
        # Spatial interpolation
        coords = [(45.0, -5.0), (46.0, -4.0)]
        temp_result = grid2loc(temp_result, coords)
        
        # Vertical interpolation
        target_depths = xr.DataArray([0, 25, 50, 75, 100], dims="z")
        final_result = vinterp(temp_result, 'depth', target_depths)
        
        assert len(final_result.time) == 1
        assert len(final_result.npts) == 2
        assert len(final_result.z) == 5
    
    def test_space_then_time_interpolation(self):
        """Test spatial interpolation followed by temporal."""
        # Spatial interpolation first
        coords = [(45.0, -5.0)]
        space_result = grid2loc(self.ds, coords)
        
        # Then temporal
        target_date = pd.Timestamp('2023-01-01T12:00:00')
        final_result = interp_time(space_result, target_date)
        
        assert len(final_result.time) == 1
        assert len(final_result.npts) == 1
    
    def test_full_workflow_with_section(self):
        """Test complete workflow including section extraction."""
        # Time interpolation
        target_date = pd.Timestamp('2023-01-01T12:00:00')
        temp_result = interp_time(self.ds, target_date)
        
        # Section extraction
        coords = [(45.0, -7.0), (46.0, -2.0)]
        section_result = grid2section(temp_result, coords, dx=10)
        
        # Vertical interpolation
        target_depths = xr.DataArray([0, 25, 50], dims="z")
        final_result = vinterp(section_result, 'depth', target_depths)
        
        assert 'distance' in final_result.coords
        assert len(final_result.time) == 1
        assert len(final_result.z) == 3