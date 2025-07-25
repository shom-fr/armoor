from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

import numpy as np
import pandas as pd
import pytest
import xarray as xr
import xesmf as xe

from armoor.base.interp import grid2loc, interp_time, regrid, vinterp
from armoor.base.misc import geo_vars


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
            'x': np.arange(3),
            'y': np.arange(3)
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
        exact_date = self.ds.time.isel(time=0).data
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
    
    def test_diurnal_vars(self):
        """Test diurnal variables functionality."""
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


class TestGrid2Loc:
    """Test suite for the grid2loc function."""
    
    def setup_method(self):
        """Create a gridded test dataset with 2D and 3D variables."""
        lon = np.linspace(-10, 0, 3)
        lat = np.linspace(40, 50, 3)
        lon, lat = np.meshgrid(lon, lat)
        self.ds = xr.Dataset({
            'temp': (['time', 'y', 'x'], np.random.rand(2, 3, 3)),
            'temp_3d': (['time', 'z', 'y', 'x'], np.random.rand(2, 2, 3, 3))
        }, coords={
            'time': (["time"], pd.date_range('2023-01-01', periods=2)),
            'lat': (["y", "x"], lat),
            'lon': (["y", "x"], lon),
            'depth': ("z", np.array([0, 10]))
        })
    
    def test_2d_interpolation(self):
        """Test 2D interpolation (time + space dimensions)."""
        mock_grid2loc = xr.DataArray(
            np.random.rand(2, 2),
            dims=['time', 'npts']
        )
        
        coords = [(45.0, -5.0), (46.0, -4.0)]
        result = grid2loc(self.ds.isel(z=0), coords)
        print(result.dims)
        assert 'npts' in result.dims
        assert len(result.npts) == 2
        assert mock_grid2loc.dims == tuple(result.dims)
    
    def test_3d_interpolation(self):
        """Test 3D interpolation (time + z + space dimensions)."""
        mock_grid2loc = xr.DataArray(
            np.random.rand(2, 2, 1),
            dims=['time', 'z', 'npts']
        )
        
        coords = [(45.0, -5.0)]
        result = grid2loc(self.ds, coords)
        assert 'temp_3d' in result.data_vars
        assert set(mock_grid2loc.dims).issubset(set(result.dims))


class TestRegrid:
    """Test suite for the regrid function."""
    
    def setup_method(self):
        """Create source and target datasets for regridding tests."""
        lon = np.linspace(-10, 0, 4)
        lat = np.linspace(40, 50, 3)
        lon, lat = np.meshgrid(lon, lat)
        self.dsi = xr.Dataset({
            'temp': (['time', 'y', 'x'], np.random.rand(2, 3, 4))
        }, coords={
            'time': pd.date_range('2023-01-01', periods=2),
            'lat': (["y", "x"], lat),
            'lon': (["y", "x"], lon)
        })
        lon = np.linspace(-8, -1, 8)
        lat = np.linspace(42, 49, 6)
        lon, lat = np.meshgrid(lon, lat)
        self.dso = xr.Dataset(coords={
            'time': pd.date_range('2023-01-01', periods=2),
            'lat': (["y", "x"], lat),
            'lon': (["y", "x"], lon)
        })
    
    def test_regrid_basic(self):
        """Test basic regridding functionality."""
                
        result = regrid(self.dsi, self.dso)
        
        assert result.sizes == self.dso.sizes


class TestVinterp:
    """Test suite for the vinterp function."""
    
    def setup_method(self):
        """Create a test dataset with vertical dimension."""
        lon = np.linspace(-8, -1, 8)
        lat = np.linspace(42, 49, 6)
        lon, lat = np.meshgrid(lon, lat)
        self.ds = xr.Dataset({
            'temp': (['time', 'z', 'y', 'x'], np.random.rand(2, 3, 6, 8)),
            'depth': (['time', 'z'], np.array([[0, 5, 10], [0, 5, 10]])),
            'surface_var': (['time', 'y', 'x'], np.random.rand(2, 6, 8))
        }, coords={
            'time': pd.date_range('2023-01-01', periods=2),
            'z': np.arange(3),
            'lat': (["y", "x"], lat),
            'lon': (["y", "x"], lon)
        })
    
    def test_depth_interpolation(self):
        """Test vertical interpolation on depth coordinate."""
        
        target_depths = xr.DataArray([0, 2.5, 5, 7.5, 10], dims="z")
        result = vinterp(self.ds, 'depth', target_depths)

        assert result.sizes["z"] ==  len(target_depths)
        assert 'surface_var' in result.data_vars  # Variable without z preserved
    
    def test_density_interpolation(self):
        """Test vertical interpolation on density coordinate."""
        # Add a density coordinate
        self.ds = self.ds.assign_coords(
            dens=(['time', 'z'], np.random.rand(2, 3))
        )
        
        target_densities = xr.DataArray([1020, 1025, 1030], dims="z")
        result = vinterp(self.ds, 'dens', target_densities)
        
        assert result.sizes["z"] ==  len(target_densities)


class TestIntegration:
    """Integration tests combining multiple functions."""
    
    def setup_method(self):
        """Setup for integration tests."""
        dates = pd.date_range('2023-01-01', periods=4, freq='D')
        lon = np.linspace(-8, -1, 8)
        lat = np.linspace(42, 49, 6)
        lon, lat = np.meshgrid(lon, lat)
        self.ds = xr.Dataset({
            'temp': (['time', 'z', 'y', 'x'], np.random.rand(4, 3, 6, 8))
        }, coords={
            'time': dates,
            'depth': (['time', 'z', 'y', 'x'], 100 * np.random.rand(4, 3, 6, 8)),
            'lat': (["y", "x"], lat),
            'lon': (["y", "x"], lon)
        })
    
    def test_time_then_space_then_vertical_interpolation(self):
        """Test temporal interpolation followed by spatial interpolation."""

        # Temporal interpolation
        target_date = pd.Timestamp('2023-01-01T12:00:00')
        temp_result = interp_time(self.ds, target_date)
        
        # Spatial interpolation
        coords = [(45.0, -5.0), (46.0, -4.0)]
        temp_result = grid2loc(temp_result, coords)
        
        #Vertical interpolation
        target_depths = xr.DataArray([0, 2.5, 5, 7.5, 10], dims="z")
        final_result = vinterp(temp_result, 'depth', target_depths)
        
        assert len(final_result.time) == 1
        assert len(final_result.npts) == 2
        assert len(final_result.z) == 5