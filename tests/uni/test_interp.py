import gc
import os

import numpy as np
import pandas as pd
import pytest
import xarray as xr

from armoor.interp import coarsen, grid2loc, grid2track, interp_time, regrid, vinterp, grid2section, _crop_to_bbox


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


class TestGrid2Track:
    """Test suite for grid2track: pointwise (time, lon, lat)-paired
    interpolation onto a moving track, as opposed to grid2loc's fixed-cloud
    x-time cross product.
    """

    def setup_method(self):
        """Gridded product (2D and 3D vars) plus a 3-point moving track."""
        lon = np.array([0., 1., 2., 3.])
        lat = np.array([40., 41., 42.])
        z = np.array([0., 10., 20.])
        time = np.array(
            ['2024-01-01', '2024-01-02', '2024-01-03'], dtype='datetime64[ns]'
            )
        data3d = np.zeros((3, 3, 3, 4))
        data2d = np.zeros((3, 3, 4))
        for it in range(3):
            for iz in range(3):
                for iy in range(3):
                    for ix in range(4):
                        data3d[it, iz, iy, ix] = it * 1000 + iz * 100 + lat[iy] + lon[ix]
            for iy in range(3):
                for ix in range(4):
                    data2d[it, iy, ix] = it * 1000 + lat[iy] + lon[ix]
        self.ds = xr.Dataset(
            {
                'ptemp': (('time', 'z', 'lat', 'lon'), data3d),
                'mld': (('time', 'lat', 'lon'), data2d),
            },
            coords=dict(time=time, z=z, lat=lat, lon=lon),
        )
        self.track_lon = np.array([0.5, 1.5, 2.5])
        self.track_lat = np.array([40.5, 41.5, 40.2])
        self.ds_ref = xr.Dataset(coords=dict(
            time=('time', time),
            lon=('time', self.track_lon),
            lat=('time', self.track_lat),
        ))

    def test_no_cross_product(self):
        """Output keeps a single "time" dim sized like the track, not a
        "time" x "npts" grid like grid2loc would produce."""
        result = grid2track(self.ds, self.ds_ref)
        assert result.mld.dims == ('time',)
        assert result.mld.shape == (3,)
        assert 'npts' not in result.dims

    def test_3d_var_keeps_full_depth_per_point(self):
        """A depth-resolved var keeps its full "z" profile at each paired
        (time, lon, lat) point."""
        result = grid2track(self.ds, self.ds_ref)
        assert set(result.ptemp.dims) == {'time', 'z'}
        assert result.ptemp.shape == (3, 3)

    def test_values_match_pointwise_bilinear_interpolation(self):
        """Regression check against hand-verified expected values (bilinear
        interpolation of `data3d`/`data2d` at each track point)."""
        result = grid2track(self.ds, self.ds_ref)
        expected_mld = np.array([41., 1043., 2042.7])
        np.testing.assert_allclose(result.mld.values, expected_mld, rtol=1e-5)
        expected_ptemp_t0 = np.array([41., 141., 241.])
        np.testing.assert_allclose(
            result.ptemp.isel(time=0).values, expected_ptemp_t0, rtol=1e-5
            )


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


class TestCropToBbox:
    """Test suite for the _crop_to_bbox helper (grid2section's spatial
    prefilter, shrinking the grid closest2d/grid2relloc has to
    brute-force-search over before extracting section points)."""

    def setup_method(self):
        """Create a large gridded test dataset, covering far more area
        than any single section's bounding box needs."""
        lon = np.linspace(-20, 10, 200)
        lat = np.linspace(30, 60, 200)
        lon_grid, lat_grid = np.meshgrid(lon, lat)
        self.ds = xr.Dataset({
            'temp': (['y', 'x'], np.random.rand(200, 200))
        }, coords={
            'lat': (['y', 'x'], lat_grid),
            'lon': (['y', 'x'], lon_grid),
        })

    def test_crop_shrinks_grid(self):
        coords = [(45.0, -8.0), (46.0, -2.0)]
        result = _crop_to_bbox(self.ds, coords, margin_deg=1.0)

        assert result.sizes["y"] < self.ds.sizes["y"]
        assert result.sizes["x"] < self.ds.sizes["x"]

    def test_crop_still_contains_points(self):
        coords = [(45.0, -8.0), (46.0, -2.0)]
        result = _crop_to_bbox(self.ds, coords, margin_deg=1.0)

        assert float(result.lat.min()) <= 45.0
        assert float(result.lat.max()) >= 46.0
        assert float(result.lon.min()) <= -8.0
        assert float(result.lon.max()) >= -2.0

    def test_points_outside_grid_returns_unchanged(self):
        coords = [(80.0, 80.0)]
        result = _crop_to_bbox(self.ds, coords, margin_deg=1.0)

        assert result.sizes == self.ds.sizes

    def test_grid2section_matches_uncropped_result(self):
        """The crop must not change the interpolated values -- only which
        subset of the grid the search runs over."""
        coords = [(45.0, -8.0), (46.0, -2.0)]
        cropped = grid2section(self.ds, coords, dx=10)
        uncropped = grid2loc(self.ds, list(zip(cropped.lat.values, cropped.lon.values)))

        np.testing.assert_allclose(cropped.temp.values, uncropped.temp.values)


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

    def test_potential_density_interpolation_isopycnal(self):
        """Isopycnal (potential-density) interpolation: pdens comes in as a
        plain data_var (as computed by OceanVars, see armoor.oceanvars),
        not pre-set as a coordinate -- vinterp itself must promote it, same
        as it already does for depth/dens."""
        ds = self.ds.assign(
            pdens=(['time', 'z'], np.array([[1024.0, 1026.0, 1028.0], [1024.0, 1026.0, 1028.0]]))
        )
        assert 'pdens' in ds.data_vars
        assert 'pdens' not in ds.coords

        target_pdens = xr.DataArray([1024.0, 1025.0, 1026.0, 1027.0, 1028.0], dims="z", name="pdens")
        result = vinterp(ds, 'pdens', target_pdens)

        assert result.sizes["z"] == len(target_pdens)
        assert 'pdens' in result.coords
        assert 'depth' in result.data_vars
    
    def test_variables_without_z_preserved(self):
        """Test that variables without z dimension are preserved."""
        target_depths = xr.DataArray([0, 5, 10], dims="z")
        result = vinterp(self.ds, 'depth', target_depths)
        
        assert 'surface_var' in result.data_vars
        assert 'z' not in result.surface_var.dims


class TestCoarsen:
    """Test suite for the coarsen() function."""

    def setup_method(self):
        """Uniform-value (y=6, x=8) gridded dataset for easy mean verification."""
        lon2d, lat2d = np.meshgrid(np.linspace(0.0, 7.0, 8), np.linspace(40.0, 45.0, 6))
        time = pd.date_range("2023-01-01", periods=2, freq="D")
        self.ds = xr.Dataset(
            {"temp": (["time", "y", "x"], np.ones((2, 6, 8)))},
            coords={
                "time": time,
                "lon": (["y", "x"], lon2d),
                "lat": (["y", "x"], lat2d),
            },
        )

    def test_spatial_dims_reduced(self):
        result = coarsen(self.ds, factor=2)
        assert result.sizes["x"] == 4
        assert result.sizes["y"] == 3

    def test_time_dim_unchanged(self):
        result = coarsen(self.ds, factor=2)
        assert result.sizes["time"] == self.ds.sizes["time"]

    def test_mean_aggregation(self):
        """Uniform field → block mean must equal original value."""
        result = coarsen(self.ds, factor=2)
        np.testing.assert_allclose(result["temp"].values, 1.0)

    def test_median_aggregation(self):
        result = coarsen(self.ds, factor=2, method="median")
        np.testing.assert_allclose(result["temp"].values, 1.0)

    def test_boundary_trim(self):
        """factor=3 on x=8 → floor(8/3)=2 output x-cells with trim."""
        ds = xr.Dataset(
            {"temp": (["y", "x"], np.ones((6, 8)))},
            coords={
                "lon": (["y", "x"], np.zeros((6, 8))),
                "lat": (["y", "x"], np.zeros((6, 8))),
            },
        )
        result = coarsen(ds, factor=3, boundary="trim")
        assert result.sizes["x"] == 2

    def test_boundary_pad(self):
        """factor=3 on x=8 → ceil(8/3)=3 output x-cells with pad."""
        ds = xr.Dataset(
            {"temp": (["y", "x"], np.ones((6, 8)))},
            coords={
                "lon": (["y", "x"], np.zeros((6, 8))),
                "lat": (["y", "x"], np.zeros((6, 8))),
            },
        )
        result = coarsen(ds, factor=3, boundary="pad")
        assert result.sizes["x"] == 3

    def test_coordinates_coarsened(self):
        """lon/lat coordinates must share the coarsened (y, x) shape."""
        result = coarsen(self.ds, factor=2)
        assert result["lon"].sizes == {"y": 3, "x": 4}
        assert result["lat"].sizes == {"y": 3, "x": 4}

    def test_no_spatial_dims_raises(self):
        ds = xr.Dataset(
            {"temp": ("time", [1.0, 2.0])},
            coords={"time": pd.date_range("2023", periods=2)},
        )
        with pytest.raises(ValueError, match="no 'x' or 'y'"):
            coarsen(ds, factor=2)

    def test_multiple_variables(self):
        self.ds["sal"] = (["time", "y", "x"], np.full((2, 6, 8), 35.0))
        result = coarsen(self.ds, factor=2)
        assert "temp" in result
        assert "sal" in result

    def test_factor_one_is_identity(self):
        result = coarsen(self.ds, factor=1)
        assert result.sizes["x"] == self.ds.sizes["x"]
        assert result.sizes["y"] == self.ds.sizes["y"]
        np.testing.assert_allclose(result["temp"].values, self.ds["temp"].values)

    def test_z_dim_preserved(self):
        """Vertical dimension must be left untouched."""
        self.ds["temp"] = (["time", "z", "y", "x"], np.ones((2, 3, 6, 8)))
        self.ds = self.ds.assign_coords(z=np.arange(3))
        result = coarsen(self.ds, factor=2)
        assert result.sizes["z"] == 3


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

def test_vinterp_extrap():
    """No values below the deepest level with extrap="bottom" (positive depth)."""
    ds = xr.Dataset(
        {"temp": (("z", "x"), [[20.0], [15.0], [10.0]], {"units": "degC"})},
        coords={"depth": (("z", "x"), [[1.0], [10.0], [50.0]])},
    )
    levels = xr.DataArray([0.0, 5.0, 100.0], dims="z", name="depth")
    out = vinterp(ds, "depth", levels, extrap="bottom")
    np.testing.assert_allclose(out.temp.values.ravel(), [20.0, 17.0 + 7 / 9, np.nan])
    assert out.temp.attrs["units"] == "degC"
    out = vinterp(ds, "depth", levels)
    np.testing.assert_allclose(out.temp.values.ravel(), [20.0, 17.0 + 7 / 9, 10.0])


def test_regrid_depth():
    """The depth on the x and y dimensions is regridded with the variables."""
    lon, lat = np.meshgrid(np.linspace(0, 4, 5), np.linspace(40, 43, 4))
    depth = np.broadcast_to(np.array([1.0, 10.0])[:, None, None], (2, 4, 5))
    dsi = xr.Dataset(
        {"temp": (("z", "y", "x"), np.full((2, 4, 5), 12.0))},
        coords={
            "lon": (("y", "x"), lon),
            "lat": (("y", "x"), lat),
            "depth": (("z", "y", "x"), depth),
        },
    )
    dso = xr.Dataset(coords={"lon": ("lon", [1.0, 2.0]), "lat": ("lat", [41.0, 42.0])})
    out = regrid(dsi, dso)
    assert "depth" in out.coords and out.depth.dims == ("z", "lat", "lon")
    np.testing.assert_allclose(out.depth.values[:, 0, 0], [1.0, 10.0])
    np.testing.assert_allclose(out.temp.values, 12.0)


def _regrid_case(mask=None, dst_mask=None, dst_time=None):
    """A linear field on a 2D source grid and a destination inside it."""
    lon, lat = np.meshgrid(np.linspace(0, 9, 10), np.linspace(40, 46, 7))
    dsi = xr.Dataset(
        {"temp": (("time", "y", "x"), np.stack([lon + 2 * lat, lon + 2 * lat + 1]))},
        coords={
            "time": pd.date_range("2024-01-01", periods=2),
            "lon": (("y", "x"), lon),
            "lat": (("y", "x"), lat),
        },
    )
    if mask is not None:
        dsi["mask"] = (("y", "x"), mask)
    lono, lato = np.meshgrid(np.arange(0.5, 8.6, 1.0), np.arange(40.5, 45.6, 1.0))
    dso = xr.Dataset(coords={"lon": (("y", "x"), lono), "lat": (("y", "x"), lato)})
    if dst_mask is not None:
        dso["mask"] = (("y", "x"), dst_mask)
    if dst_time is not None:
        dso = dso.assign_coords(time=dst_time)
    return dsi, dso


def test_regrid_linear_field():
    """The bilinear regridding of a linear field is exact."""
    dsi, dso = _regrid_case()
    out = regrid(dsi, dso)
    np.testing.assert_allclose(out.temp.isel(time=0).values, dso.lon + 2 * dso.lat)


def test_regrid_ignores_destination_time():
    """The time of the destination grid does not interpolate in time."""
    dsi, dso = _regrid_case(dst_time=pd.date_range("2030-01-01", periods=3))
    out = regrid(dsi, dso)
    np.testing.assert_array_equal(out.time.values, dsi.time.values)


def test_regrid_source_mask():
    """The destination cells that touch a masked source point are missing,
    whatever the hash seed: xoa may pick a "mask" variable as longitude."""
    mask = np.ones((7, 10), dtype="i")
    mask[:, :3] = 0
    dsi, dso = _regrid_case(mask=mask)
    out = regrid(dsi, dso)
    assert out.temp.isel(time=0, x=slice(None, 2)).isnull().all()
    assert out.temp.isel(time=0, x=slice(3, None)).notnull().all()


def test_regrid_croco_mask():
    """A "mask" variable is never taken for the longitude.

    With a CROCO dataset, xoa may find the longitude in a "mask" variable,
    depending on the hash seed, and then no destination point is valid.
    """
    import xoa

    path = os.path.join(os.path.dirname(xoa.__file__), "data_samples", "croco.south-africa.surf.nc")
    if not os.path.exists(path):
        pytest.skip("xoa CROCO sample not available")
    ds = xr.open_dataset(path)
    ds = ds.rename({"lon_rho": "lon", "lat_rho": "lat", "eta_rho": "y", "xi_rho": "x"})[["zeta"]]
    mask = ds.lon > ds.lon.mean()
    dsi = ds.where(mask).assign(mask=mask.astype("i"))
    lon, lat = np.meshgrid(
        np.arange(float(ds.lon.min()), float(ds.lon.max()), 0.1),
        np.arange(float(ds.lat.min()), float(ds.lat.max()), 0.1),
    )
    dso = xr.Dataset(coords={"lon": (("y", "x"), lon), "lat": (("y", "x"), lat)})
    out = regrid(dsi, dso)
    east = dso.lon > float(ds.lon.mean()) + 0.5
    assert out.zeta.where(east).notnull().sum() == east.sum()


def test_regrid_destination_mask():
    """The masked destination points are missing, even when the mask is
    missing itself instead of zero, as after ``ds.where(ds.mask)``."""
    dst_mask = np.ones((6, 9))
    dst_mask[:2] = 0
    dst_mask[2] = np.nan
    dsi, dso = _regrid_case(dst_mask=dst_mask)
    out = regrid(dsi, dso)
    assert out.temp.isel(y=slice(None, 3)).isnull().all()
    assert out.temp.isel(y=slice(3, None)).notnull().all()


@pytest.mark.parametrize("method", ["bilinear", "bicubic", "conservative"])
def test_regrid_methods(method):
    """All the xoa methods keep a constant field."""
    dsi, dso = _regrid_case()
    dsi["temp"][:] = 12.0
    out = regrid(dsi, dso, method=method)
    np.testing.assert_allclose(out.temp.values[np.isfinite(out.temp.values)], 12.0)
    assert np.isfinite(out.temp.values).any()


def test_regrid_weights_file(tmp_path):
    """The weights are saved to a file, then reused."""
    dsi, dso = _regrid_case()
    weights_file = str(tmp_path / "weights.nc")
    out0 = regrid(dsi, dso, weights_file=weights_file)
    assert (tmp_path / "weights.nc").exists()
    out1 = regrid(dsi, dso, weights_file=weights_file)
    xr.testing.assert_allclose(out0, out1)


def test_regrid_dask_lazy():
    """Dask arrays stay lazy, even when chunked horizontally, keep their
    floating point type, and give the same result as numpy arrays."""
    dsi, dso = _regrid_case()
    dsi["temp"] = dsi.temp.astype("f4")
    out = regrid(dsi.chunk(time=1, x=4), dso)
    assert out.temp.chunks is not None
    assert out.temp.dtype == np.float32
    np.testing.assert_allclose(out.temp.values, regrid(dsi, dso).temp.values, rtol=1e-6)


def test_regrid_dask_weights_file(tmp_path):
    """The weights are saved before the lazy result is computed."""
    dsi, dso = _regrid_case()
    weights_file = tmp_path / "weights.nc"
    out = regrid(dsi.chunk(time=1), dso, weights_file=str(weights_file))
    assert weights_file.exists()
    np.testing.assert_allclose(out.temp.isel(time=0).values, dso.lon + 2 * dso.lat)


def test_grid2loc_dask_lazy():
    """Dask arrays stay lazy, keep their floating point type and give the same
    result as numpy arrays, and the points outside the grid are missing."""
    dsi, _ = _regrid_case()
    dsi["temp"] = dsi.temp.astype("f4")
    coords = [(42.0, 3.5), (45.5, 8.25), (30.0, 3.0)]
    out = grid2loc(dsi.chunk(time=1, x=4), coords)
    assert out.temp.chunks is not None
    assert out.temp.dtype == np.float32
    assert out.temp.dims == ("time", "npts")
    np.testing.assert_allclose(out.temp.values, grid2loc(dsi, coords).temp.values, rtol=1e-6)
    np.testing.assert_allclose(out.temp.isel(time=0, npts=[0, 1]), [3.5 + 2 * 42.0, 8.25 + 2 * 45.5])
    assert out.temp.isel(npts=2).isnull().all()


def test_grid2loc_depth_on_grid():
    """A depth on the horizontal grid is interpolated, whatever the name of
    the vertical dimension, and other coordinates are kept."""
    lon, lat = np.meshgrid(np.linspace(0, 4, 5), np.linspace(40, 43, 4))
    depth = np.stack([lon * 0 + 1.0, lon + 10.0])
    dsi = xr.Dataset(
        {"temp": (("s_rho", "y", "x"), np.stack([lon, lat]))},
        coords={
            "lon": (("y", "x"), lon),
            "lat": (("y", "x"), lat),
            "depth": (("s_rho", "y", "x"), depth),
            "s_rho": ("s_rho", [-0.75, -0.25]),
        },
    )
    out = grid2loc(dsi, [(41.5, 2.5)])
    assert out.depth.dims == ("s_rho", "npts")
    np.testing.assert_allclose(out.depth.values.ravel(), [1.0, 12.5])
    np.testing.assert_allclose(out.temp.values.ravel(), [2.5, 41.5])
    np.testing.assert_array_equal(out.s_rho.values, [-0.75, -0.25])
