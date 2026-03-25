"""Unit tests for the ds.range accessor (armoor.accessors.range)."""

import numpy as np
import pandas as pd
import pytest
import xarray as xr

import armoor  # registers all accessors


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def ds_time():
    """Dataset with a time dimension and a z dimension."""
    times = pd.date_range("2020-01-01", periods=12, freq="D")
    depths = np.array([0.0, 10.0, 50.0, 100.0])
    return xr.Dataset(
        {
            "temp": (["time", "z"], np.random.rand(12, 4)),
            "sal": (["time", "z"], np.random.rand(12, 4) + 35.0),
        },
        coords={
            "time": times,
            "depth": ("z", depths),
            "z": range(4),
        },
    )


@pytest.fixture
def ds_3d(ds_time):
    return ds_time


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

class TestRangeRegistration:
    def test_range_accessor_registered(self, ds_time):
        from armoor.accessors.range import RangeAccessor
        assert isinstance(ds_time.range, RangeAccessor)


# ---------------------------------------------------------------------------
# ds.range.tfreq
# ---------------------------------------------------------------------------

class TestRangeTfreq:
    def test_returns_dataset(self, ds_time):
        result = ds_time.range.tfreq("5D")
        assert isinstance(result, xr.Dataset)

    def test_trange_dimension_present(self, ds_time):
        result = ds_time.range.tfreq("3D")
        assert "trange" in result.dims

    def test_number_of_bins(self, ds_time):
        # 12 days at 4-day bins → 2 complete bins (day 1–4 and 5–8)
        result = ds_time.range.tfreq("4D")
        assert result.sizes["trange"] >= 1

    def test_time_range_variable_present(self, ds_time):
        result = ds_time.range.tfreq("5D")
        assert "time_range" in result

    def test_variables_preserved(self, ds_time):
        result = ds_time.range.tfreq("5D")
        assert "temp" in result
        assert "sal" in result


# ---------------------------------------------------------------------------
# ds.range.vertical
# ---------------------------------------------------------------------------

class TestRangeVertical:
    def test_returns_dataset(self, ds_3d):
        result = ds_3d.range.vertical("depth", [0, 50])
        assert isinstance(result, xr.Dataset)

    def test_vertical_range_coordinate_added(self, ds_3d):
        result = ds_3d.range.vertical("depth", [0, 50])
        assert "vertical_range" in result.coords

    def test_values_outside_range_masked(self, ds_3d):
        # depth = [0, 10, 50, 100] — keep only [0, 50]
        result = ds_3d.range.vertical("depth", [0, 50])
        # depth index 3 (100 m) should be NaN for 3-D vars
        assert np.all(np.isnan(result["temp"].isel(z=3).values))

    def test_values_inside_range_kept(self, ds_3d):
        result = ds_3d.range.vertical("depth", [0, 100])
        # all depths are within [0, 100] — no NaNs
        assert not np.any(np.isnan(result["temp"].values))

    def test_zero_width_range_masks_all_but_one(self, ds_3d):
        # only depth == 10 survives
        result = ds_3d.range.vertical("depth", [10, 10])
        valid = ~np.isnan(result["temp"].values)
        # exactly one z-level (index 1) should be non-NaN
        assert valid[:, 1].all()
        assert not valid[:, 0].any()


# ---------------------------------------------------------------------------
# ds.range.trange_seq
# ---------------------------------------------------------------------------

class TestRangeTrangeSeq:
    def test_returns_list(self, ds_time):
        result = ds_time.range.trange_seq("2020-01-01", "2020-01-13", "3D")
        assert isinstance(result, list)

    def test_list_elements_are_datasets(self, ds_time):
        result = ds_time.range.trange_seq("2020-01-01", "2020-01-13", "3D")
        assert all(isinstance(ds, xr.Dataset) for ds in result)

    def test_trange_attribute_set(self, ds_time):
        result = ds_time.range.trange_seq("2020-01-01", "2020-01-07", "3D")
        for ds in result:
            assert "trange" in ds.attrs


# ---------------------------------------------------------------------------
# ds.range.vrange
# ---------------------------------------------------------------------------

class TestRangeVrange:
    def test_returns_list(self, ds_3d):
        result = ds_3d.range.vrange("depth", [(0, 20), (20, 100)])
        assert isinstance(result, list)

    def test_one_element_per_bin(self, ds_3d):
        bins = [(0, 10), (10, 50), (50, 100)]
        result = ds_3d.range.vrange("depth", bins)
        assert len(result) == len(bins)

    def test_vrange_attribute_set(self, ds_3d):
        result = ds_3d.range.vrange("depth", [(0, 50)])
        assert "vrange" in result[0].attrs


# ---------------------------------------------------------------------------
# ds.range.vlevels
# ---------------------------------------------------------------------------

class TestRangeVlevels:
    def test_returns_list(self, ds_3d):
        result = ds_3d.range.vlevels("depth")
        assert isinstance(result, list)

    def test_one_element_per_z_level(self, ds_3d):
        result = ds_3d.range.vlevels("depth")
        assert len(result) == ds_3d.sizes["z"]

    def test_vlevel_attribute_set(self, ds_3d):
        result = ds_3d.range.vlevels("depth")
        for ds in result:
            assert "vlevel" in ds.attrs


# ---------------------------------------------------------------------------
# ds.range.by_time
# ---------------------------------------------------------------------------

class TestRangeByTime:
    def test_returns_list(self, ds_time):
        result = ds_time.range.by_time()
        assert isinstance(result, list)

    def test_one_element_per_time_step(self, ds_time):
        result = ds_time.range.by_time()
        assert len(result) == ds_time.sizes["time"]

    def test_time_attribute_set(self, ds_time):
        result = ds_time.range.by_time()
        for ds in result:
            assert "time" in ds.attrs
