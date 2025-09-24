import pytest
import numpy as np
import xarray as xr
import pandas as pd
from unittest.mock import patch, MagicMock
import logging
from armoor.base.filters import ArmoorFilters  # Replace with actual import

# Fixtures
@pytest.fixture
def sample_ds():
    """Create a sample xarray Dataset for testing."""
    lon = np.linspace(0, 10, 60)
    lat = np.linspace(0, 10, 100)
    lon, lat = np.meshgrid(lon, lat)
    time = pd.date_range("2020-01-01", periods=5)
    data = np.random.rand(5, 100, 60)
    ds = xr.Dataset({
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
def sample_ds_no_time():
    """Create a sample xarray Dataset without time dimension for testing."""
    lon = np.linspace(0, 10, 60)
    lat = np.linspace(0, 10, 100)
    lon, lat = np.meshgrid(lon, lat)
    data = np.random.rand(100, 60)
    ds = xr.Dataset({
            "var1": (("y", "x"), data),
            "var1_qc": (("y", "x"), np.random.randint(0, 10, (100, 60))),
            },
        coords={
            "lon": (("y", "x"), lon),
            "lat": (("y", "x"), lat),
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
        _, mask = af._get_polygon_mask(coords)
        assert mask is not None
        assert isinstance(mask, xr.DataArray)

    def test__get_data_selection_mask(self, sample_ds):
        """Test _get_data_selection_mask with min and max."""
        af = ArmoorFilters(sample_ds)
        mask = af._get_data_selection_mask("lat", 2, 8)
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

    def test_apply_combined_filters(self, sample_ds):
        """Test apply_combined_filters with quality and polygon filters."""
        filters_config = {
            "quality": {"qname": "var1", "qmin": 2, "qmax": 8},
            "polygon": {"coords": [(2, 2), (2, 8), (8, 8), (8, 2)]},
        }
        af = ArmoorFilters(sample_ds)
        result = af.apply_combined_filters(filters_config)
        assert result is not None
        assert isinstance(result, xr.Dataset)
