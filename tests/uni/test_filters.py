import os
import pytest
import numpy as np
import xarray as xr
import pandas as pd
import logging
from armoor import ArmoorError
from armoor.filters import ArmoorFilters  # Replace with actual import

# Fixtures
@pytest.fixture
def sample_ds():
    """Create a sample xarray Dataset for testing."""
    lon = np.linspace(0, 10, 60)
    lat = np.linspace(0, 10, 100)
    lon, lat = np.meshgrid(lon, lat)
    time = pd.date_range("2020-01-01", periods=5, freq='D')
    data = np.random.rand(5, 100, 60)
    ds = xr.Dataset(
        {
            "var1": (("time", "y", "x"), data),
            "var1_qc": (("time", "y", "x"), np.random.randint(0, 10, (5, 100, 60))),
        },
        coords={
            "lon": (("y", "x"), lon),
            "lat": (("y", "x"), lat),
            "time": time
        },
    )
    return ds

@pytest.fixture
def sample_ds_with_depth():
    """Create a sample xarray Dataset with depth coordinate for testing tsmooth."""
    lon = np.linspace(0, 10, 60)
    lat = np.linspace(0, 10, 100)
    lon, lat = np.meshgrid(lon, lat)
    time = pd.date_range("2020-01-01", periods=50, freq='1h')  # More frequent for smoothing
    data = np.random.rand(50, 100, 60)
    ds = xr.Dataset(
        {
            "var1": (("time", "y", "x"), data),
            "var1_qc": (("time", "y", "x"), np.random.randint(0, 10, (50, 100, 60))),
        },
        coords={
            "lon": (("y", "x"), lon.astype(np.float64)),
            "lat": (("y", "x"), lat.astype(np.float64)),
            "time": time,
            "depth": np.float64(10.0)  # scalar depth as float
        },
    )
    return ds

@pytest.fixture
def sample_ds_no_time():
    """Create a sample xarray Dataset without time dimension for testing."""
    lon = np.linspace(0, 10, 60)
    lat = np.linspace(0, 10, 100)
    lon, lat = np.meshgrid(lon, lat)
    data = np.random.rand(100, 60)
    ds = xr.Dataset(
        {
            "var1": (("y", "x"), data),
            "var1_qc": (("y", "x"), np.random.randint(0, 10, (100, 60))),
        },
        coords={
            "lon": (("y", "x"), lon),
            "lat": (("y", "x"), lat),
        },
    )
    return ds

@pytest.fixture
def sample_ds_oceanvars():
    """Create a sample dataset with raw ocean variables (temp/sal), from which
    derived variables like ptemp can be computed."""
    ds = xr.Dataset(
        {
            "temp": (("time", "z"), 15 + np.random.rand(3, 4)),
            "sal": (("time", "z"), 35 + np.random.rand(3, 4)),
            "depth": (("time", "z"), np.tile(np.arange(4) * 10.0, (3, 1))),
        },
        coords={
            "time": pd.date_range("2020-01-01", periods=3, freq="D"),
            "lon": 10.0,
            "lat": 40.0,
        },
    )
    return ds

# Tests
class TestArmoorFilters:
    
    def test_get_mask(self, sample_ds):
        """Test get_mask with a simple polygon."""
        coords = [(2, 2), (2, 8), (8, 8), (8, 2)]
        af = ArmoorFilters(sample_ds)
        mask = af.get_mask(coords)
        assert mask is not None
        assert isinstance(mask, xr.DataArray)
        assert mask.dtype == bool

    def test_get_mask_empty(self, sample_ds):
        """Test get_mask with a polygon that contains no points."""
        coords = [(100, 100), (100, 110), (110, 110), (110, 100)]
        af = ArmoorFilters(sample_ds)
        mask = af.get_mask(coords)
        assert mask is None

    def test__get_quality_mask(self, sample_ds):
        """Test _get_quality_mask with min and max."""
        af = ArmoorFilters(sample_ds)
        mask = af._get_quality_mask("var1", 2, 8)
        assert mask is not None
        assert isinstance(mask, xr.DataArray)
        assert mask.dtype == bool

    def test__get_quality_mask_no_qc(self, sample_ds):
        """Test _get_quality_mask with non-existent QC variable."""
        af = ArmoorFilters(sample_ds)
        mask = af._get_quality_mask("nonexistent", 2, 8)
        assert mask is None

    def test__get_polygon_mask(self, sample_ds):
        """Test _get_polygon_mask."""
        coords = [(2, 2), (2, 8), (8, 8), (8, 2)]
        af = ArmoorFilters(sample_ds)
        mask2keep, mask = af._get_polygon_mask(coords)
        assert mask is not None
        assert isinstance(mask, xr.DataArray)
        # mask2keep will be None since dilate=False by default
        assert mask2keep is None

    def test__get_polygon_mask_with_dilate(self, sample_ds):
        """Test _get_polygon_mask with dilation."""
        coords = [(2, 2), (2, 8), (8, 8), (8, 2)]
        af = ArmoorFilters(sample_ds)
        mask2keep, mask = af._get_polygon_mask(coords, dilate=True)
        assert mask is not None
        assert isinstance(mask, xr.DataArray)
        # mask2keep should be the original mask before dilation
        assert mask2keep is not None

    def test__get_data_selection_mask_range(self, sample_ds):
        """Test _get_data_selection_mask with min and max."""
        af = ArmoorFilters(sample_ds)
        mask = af._get_data_selection_mask("lat", minimum=2, maximum=8)
        assert mask is not None
        assert isinstance(mask, xr.DataArray)
        assert mask.dtype == bool

    def test__get_data_selection_mask_value(self, sample_ds):
        """Test _get_data_selection_mask with specific value."""
        af = ArmoorFilters(sample_ds)
        mask = af._get_data_selection_mask("lat", value=5.0)
        assert mask is not None
        assert isinstance(mask, xr.DataArray)
        assert mask.dtype == bool

    def test__get_time_bounds_mask(self, sample_ds):
        """Test _get_time_bounds_mask with valid start and end."""
        af = ArmoorFilters(sample_ds)
        mask = af._get_time_bounds_mask(start="2020-01-02", end="2020-01-04")
        assert mask is not None
        assert isinstance(mask, xr.DataArray)

    def test__get_time_bounds_mask_invalid(self, sample_ds):
        """Test _get_time_bounds_mask with invalid start and end."""
        af = ArmoorFilters(sample_ds)
        mask = af._get_time_bounds_mask(start="2025-01-01", end="2025-01-02")
        assert mask is None

    def test__get_time_bounds_mask_with_duration(self, sample_ds):
        """Test _get_time_bounds_mask with start and duration in days."""
        af = ArmoorFilters(sample_ds)
        mask = af._get_time_bounds_mask(start="2020-01-02", end=2)
        assert mask is not None
        assert isinstance(mask, xr.DataArray)

    def test__get_time_hours_range_mask_not_crossing_midnight(self, sample_ds):
        """Test _get_time_hours_range_mask when not crossing midnight"""
        af = ArmoorFilters(sample_ds)
        mask = af._get_time_hours_range_mask('08:00:00', '12:00:00')
        filtered = sample_ds.where(mask, drop=True)
        hours = pd.DatetimeIndex(filtered.time.values).hour
        assert all((hours >= 8) & (hours <= 12))
    
    def test__get_time_hours_range_mask_crossing_midnight(self, sample_ds):
        """Test _get_time_hours_range_mask when not crossing midnight"""
        af = ArmoorFilters(sample_ds)
        mask = af._get_time_hours_range_mask('22:00:00', '3:00:00')
        filtered = sample_ds.where(mask, drop=True)
        hours = pd.DatetimeIndex(filtered.time.values).hour
        assert all((hours >= 22) | (hours <= 3))

    def test_apply_combined_filters_quality_and_polygon(self, sample_ds):
        """Test apply_combined_filters with quality and polygon filters."""
        filters_config = {
            "quality": {"qname": "var1", "qmin": 2, "qmax": 8},
            "polygon": {"coords": [(2, 2), (2, 8), (8, 8), (8, 2)]},
        }
        af = ArmoorFilters(sample_ds)
        result = af.apply_combined_filters(filters_config)
        # Result may be a dask delayed object, compute it
        if hasattr(result, 'compute'):
            result = result.compute()
        assert result is not None
        assert isinstance(result, xr.Dataset)

    def test_apply_combined_filters_data_selection(self, sample_ds):
        """Test apply_combined_filters with data selection."""
        filters_config = {
            "data_selection": {"dim": "lat", "minimum": 3, "maximum": 7},
        }
        af = ArmoorFilters(sample_ds)
        result = af.apply_combined_filters(filters_config)
        # Result may be a dask delayed object, compute it
        if hasattr(result, 'compute'):
            result = result.compute()
        assert result is not None
        assert isinstance(result, xr.Dataset)

    def test_apply_combined_filters_time_selection(self, sample_ds):
        """Test apply_combined_filters with time selection."""
        filters_config = {
            "time_selection": {"minimum": "2020-01-02", "maximum": "2020-01-04"},
        }
        af = ArmoorFilters(sample_ds)
        result = af.apply_combined_filters(filters_config)
        # Result may be a dask delayed object, compute it
        if hasattr(result, 'compute'):
            result = result.compute()
        assert result is not None
        assert isinstance(result, xr.Dataset)

    def test_apply_combined_filters_empty_result(self, sample_ds):
        """Test apply_combined_filters with polygon that contains no points."""
        filters_config = {
            "polygon": {"coords": [(100, 100), (100, 110), (110, 110), (110, 100)]},
        }
        af = ArmoorFilters(sample_ds)
        result = af.apply_combined_filters(filters_config)
        assert result is None

    def test_apply_combined_filters_multiple(self, sample_ds):
        """Test apply_combined_filters with multiple filter types."""
        filters_config = {
            "quality": {"qname": "var1", "qmin": 2, "qmax": 8},
            "polygon": {"coords": [(2, 2), (2, 8), (8, 8), (8, 2)]},
            "data_selection": {"dim": "lat", "minimum": 3, "maximum": 7},
            "time_selection": {"minimum": "2020-01-02", "maximum": "2020-01-04"},
        }
        af = ArmoorFilters(sample_ds)
        result = af.apply_combined_filters(filters_config)
        # Result may be a dask delayed object, compute it
        if hasattr(result, 'compute'):
            result = result.compute()
        assert result is not None
        assert isinstance(result, xr.Dataset)

    def test_oceanvars_filter(self, sample_ds_oceanvars):
        """oceanvars_filter keeps only the requested (or derived) variables."""
        result = ArmoorFilters.oceanvars_filter(sample_ds_oceanvars, ["ptemp"])
        assert list(result.data_vars) == ["ptemp"]
        assert "depth" in result.coords
        assert "lon" in result.coords
        assert "lat" in result.coords

    def test_oceanvars_filter_unknown_name_raises(self, sample_ds_oceanvars):
        """An unrecognized ocean variable name must raise, not crash on None."""
        with pytest.raises(ArmoorError, match="depth"):
            ArmoorFilters.oceanvars_filter(sample_ds_oceanvars, ["depth"])

    def test_oceanvars_filter_missing_dependency_raises(self, sample_ds_oceanvars):
        """A known variable that can't be derived from what's available must raise."""
        ds = sample_ds_oceanvars.drop_vars("temp")
        with pytest.raises(ArmoorError, match="ptemp"):
            ArmoorFilters.oceanvars_filter(ds, ["ptemp"])

    # @patch('armoor.filters.open_decode')
    def test_bathy_filter(self, sample_ds_no_time):
        """Test bathy_filter static method."""
        # Create mock bathymetry dataset
        mock_bathy = xr.Dataset({
            "bathy": (("y", "x"), np.random.rand(100, 60) * 100)
        }, coords={
            "lon": sample_ds_no_time.lon,
            "lat": sample_ds_no_time.lat
        })
        # mock_open_decode.return_value = mock_bathy
        mock_bathy_path = "mock_bathy_path.nc"
        mock_bathy.to_netcdf(mock_bathy_path)
        # Note: Since bathy_filter is @dask.delayed, we need to call .compute() on the result
        result = ArmoorFilters.bathy_filter(
            sample_ds_no_time, 
            path=mock_bathy_path, 
            fmt="armoor",
            minimum=10,
            maximum=50
        ).compute()
        os.remove(mock_bathy_path)
        assert result is not None
        assert isinstance(result, xr.Dataset)

    def test_tidal_filter(self, sample_ds):
        """Test tidal_filter static method."""
        # Note: Since tidal_filter is @dask.delayed, we need to call .compute()
        result = ArmoorFilters.tidal_filter(sample_ds, filter_name="demerliac").compute()
        assert result is not None
        assert isinstance(result, xr.Dataset)

    def test_tidal_filter_errors(self, sample_ds):
        """A tidal filter of data sampled less than hourly: warning or error."""
        daily = sample_ds[["var1"]].assign_coords(
            time=pd.date_range("2020-01-01", periods=sample_ds.sizes["time"], freq="1D")
        )
        result = ArmoorFilters.tidal_filter(daily.copy(), filter_name="demerliac")
        xr.testing.assert_identical(result, daily)
        with pytest.raises(Exception, match="less than hourly"):
            ArmoorFilters.tidal_filter(daily.copy(), filter_name="demerliac", errors="raise")

    def test_filters_time_dependent_depth(self):
        """The depth that depends on time is filtered with the variables."""
        times = pd.date_range("2020-01-01", periods=120, freq="1h")
        hours = np.arange(times.size)
        tide = np.cos(2 * np.pi * hours / 12.42)
        ds = xr.Dataset(
            {"var1": (("time", "x"), np.stack([10 + tide, 10 + tide], axis=1))},
            coords={
                "time": times,
                "lon": ("x", [0.0, 1.0]),
                "depth": (("time", "x"), np.stack([5 + tide, 5 + tide], axis=1)),
            },
        )
        result = ArmoorFilters.tidal_filter(ds.copy(), filter_name="demerliac")
        assert "depth" in result.coords
        valid = result.depth.isel(time=slice(40, 80))
        np.testing.assert_allclose(valid, 5.0, atol=0.05)
        np.testing.assert_allclose(result.var1.isel(time=slice(40, 80)), 10.0, atol=0.05)
        result = ArmoorFilters.tresample(ds, freq="1D")
        assert "depth" in result.coords and result.depth.dims == ("time", "x")
        np.testing.assert_allclose(result.depth.values[0], ds.depth.values[:24].mean(axis=0))

    def test_tsmooth_without_depth(self, sample_ds_with_depth):
        """tsmooth of a dataset without depth."""
        ds = sample_ds_with_depth[["var1"]].drop_vars("depth")
        result = ArmoorFilters.tsmooth(ds, freq="6h").compute()
        assert result["var1"].shape == ds["var1"].shape

    def test_tresample(self, sample_ds):
        """Test tresample static method."""
        # Note: Since tresample is @dask.delayed, we need to call .compute()
        result = ArmoorFilters.tresample(sample_ds, freq="1D").compute()
        assert result is not None
        assert isinstance(result, xr.Dataset)

    def test_tsmooth(self, sample_ds_with_depth):
        """Test tsmooth static method."""
        # Note: Since tsmooth is @dask.delayed, we need to call .compute()
        vars2drop = [var for var in sample_ds_with_depth.data_vars if "qc" in var]
        sample_ds_with_depth = sample_ds_with_depth.drop_vars(vars2drop)
        result = ArmoorFilters.tsmooth(sample_ds_with_depth, freq="6h").compute()
        assert result is not None
        assert isinstance(result, xr.Dataset)

    def test_clean_ds(self, sample_ds):
        """Test clean_ds static method."""
        # Add depth and bathy for testing
        ds_with_extras = sample_ds.copy()
        ds_with_extras = ds_with_extras.assign_coords(
            depth=xr.DataArray(np.random.rand(5), dims="time")
        )
        ds_with_extras["bathy"] = xr.DataArray(
            np.random.rand(5, 100, 60), dims=("time", "y", "x")
        )
        
        # Note: Since clean_ds is @dask.delayed, we need to call .compute()
        result = ArmoorFilters.clean_ds(ds_with_extras, depth_was_coord=True).compute()
        assert result is not None
        assert isinstance(result, xr.Dataset)
        # Check that depth is now a coordinate
        assert "depth" in result.coords
        # Check that bathy no longer has time dimension
        assert "time" not in result["bathy"].dims

    def test_create_optimized_mask(self, sample_ds):
        """Test create_optimized_mask function."""
        from armoor.filters import create_optimized_mask
        
        bins = [(0, 3), (7, 10)]
        mask = create_optimized_mask(sample_ds, "var1_qc", bins)
        assert mask is not None
        assert isinstance(mask, xr.DataArray)
        assert mask.dtype == bool

    def test_generate_kernel_from_freq(self):
        """Test generate_kernel_from_freq function."""
        from armoor.filters import generate_kernel_from_freq
        
        time_index = pd.date_range("2020-01-01", periods=100, freq='1h')
        kernel, size = generate_kernel_from_freq("6h", time_index, kernel_type="gaussian")
        
        assert kernel is not None
        assert isinstance(kernel, np.ndarray)
        assert size > 0
        assert len(kernel) == size
        # Check normalization
        assert np.isclose(kernel.sum(), 1.0)

    def test_generate_kernel_boxcar(self):
        """Test generate_kernel_from_freq with boxcar kernel."""
        from armoor.filters import generate_kernel_from_freq
        
        time_index = pd.date_range("2020-01-01", periods=100, freq='1h')
        kernel, size = generate_kernel_from_freq("6h", time_index, kernel_type="boxcar")
        
        assert kernel is not None
        assert isinstance(kernel, np.ndarray)
        assert np.isclose(kernel.sum(), 1.0)
        # Boxcar should have equal values
        assert np.allclose(kernel, kernel[0])

    def test_generate_kernel_irregular_time(self):
        """Test generate_kernel_from_freq with irregular time index."""
        from armoor.filters import generate_kernel_from_freq
        
        # Create irregular time index
        time_index = pd.DatetimeIndex([
            "2020-01-01 00:00", "2020-01-01 01:00", 
            "2020-01-01 03:00", "2020-01-01 04:00"
        ])
        
        with pytest.raises(ValueError, match="Time index must have a regular frequency"):
            generate_kernel_from_freq("6h", time_index)

    # def test_sel_closest_with_time(self, sample_ds):
    #     """Test sel_closest method when model has time dimension."""
    #     # Create observation dataset
    #     obs_data = xr.Dataset({
    #         "obs_var": (("time",), np.random.rand(5)),
    #     }, coords={
    #         "lon": (("time",), np.full(5, 5.0)),
    #         "lat": (("time",), np.full(5, 5.0)),
    #         "time": sample_ds.time
    #     })
        
    #     af = ArmoorFilters(sample_ds)
    #     result = af.sel_closest(obs_data)
        
    #     assert result is not None
    #     assert isinstance(result, xr.Dataset)

    # def test_sel_closest_no_time(self, sample_ds_no_time):
    #     """Test sel_closest method when model has no time dimension."""
    #     # Create observation dataset without time
    #     obs_data = xr.Dataset({
    #         "obs_var": 1.0,
    #     }, coords={
    #         "lon": 5.0,
    #         "lat": 5.0,
    #     })
        
    #     af = ArmoorFilters(sample_ds_no_time)
    #     result = af.sel_closest(obs_data)
        
    #     assert result is not None
    #     assert isinstance(result, xr.Dataset)