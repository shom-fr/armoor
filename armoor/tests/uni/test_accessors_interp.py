"""Unit tests for ds.interp accessor."""

import numpy as np
import pandas as pd
import pytest
import xarray as xr

import armoor  # registers all accessors
from armoor.accessors.interp import InterpAccessor


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def ds_ts():
    """Regular hourly time-series with two variables."""
    time = pd.date_range("2020-01-01", periods=48, freq="h")
    rng = np.random.default_rng(0)
    return xr.Dataset(
        {
            "temp": ("time", rng.random(48).astype(np.float32)),
            "sal":  ("time", (rng.random(48) * 2 + 34).astype(np.float32)),
        },
        coords={"time": time},
    )


@pytest.fixture
def ds_gridded():
    """Small 2-D (y, x) gridded dataset with time."""
    lon1d = np.linspace(0.0, 5.0, 12)
    lat1d = np.linspace(40.0, 45.0, 10)
    lon2d, lat2d = np.meshgrid(lon1d, lat1d)
    time = pd.date_range("2020-01-01", periods=3, freq="D")
    rng = np.random.default_rng(1)
    data = rng.random((3, 10, 12)).astype(np.float32)
    return xr.Dataset(
        {"temp": (("time", "y", "x"), data)},
        coords={
            "lon": (("y", "x"), lon2d.astype(np.float32)),
            "lat": (("y", "x"), lat2d.astype(np.float32)),
            "time": time,
        },
    )


@pytest.fixture
def ds_vertical():
    """Dataset with a 'z' vertical dimension and depth/dens coords."""
    z = np.arange(5)
    depth = np.array([0.0, 10.0, 50.0, 100.0, 200.0], dtype=np.float32)
    return xr.Dataset(
        {"temp": ("z", np.linspace(20.0, 5.0, 5).astype(np.float32))},
        coords={"depth": ("z", depth), "z": z},
    ).set_coords("depth")


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

class TestInterpRegistration:
    def test_interp_accessor_registered(self, ds_ts):
        assert isinstance(ds_ts.interp, InterpAccessor)


# ---------------------------------------------------------------------------
# __call__ — xarray native interp preserved
# ---------------------------------------------------------------------------

class TestInterpCallXarray:
    def test_call_interpolates_time(self, ds_ts):
        target = pd.date_range("2020-01-01 00:30", periods=5, freq="h")
        result = ds_ts.interp(time=target)
        assert isinstance(result, xr.Dataset)
        assert result.sizes["time"] == 5

    def test_call_returns_dataset(self, ds_ts):
        target = pd.date_range("2020-01-01 06:00", periods=2, freq="h")
        result = ds_ts.interp(time=target)
        assert isinstance(result, xr.Dataset)
        assert "temp" in result

    def test_call_linear_values(self):
        """Verify that __call__ really forwards to xarray's linear interp."""
        ds = xr.Dataset({"a": ("x", [0.0, 2.0, 4.0])}, coords={"x": [0, 1, 2]})
        result = ds.interp(x=[0.5, 1.5])
        np.testing.assert_allclose(result["a"].values, [1.0, 3.0])


# ---------------------------------------------------------------------------
# .time — armoor interp_time
# ---------------------------------------------------------------------------

class TestInterpTime:
    def test_in_range_dates(self, ds_ts):
        dates = ["2020-01-01 06:00", "2020-01-01 12:00", "2020-01-01 18:00"]
        result = ds_ts.interp.time(dates)
        assert isinstance(result, xr.Dataset)
        assert result.sizes["time"] == 3

    def test_output_times_match_targets(self, ds_ts):
        target = pd.Timestamp("2020-01-01 10:00")
        result = ds_ts.interp.time([target])
        assert pd.Timestamp(result.time.values[0]) == target

    def test_before_range_extrapolated(self, ds_ts):
        """Dates before dataset start → first value is repeated."""
        early = pd.Timestamp("2019-12-31")
        result = ds_ts.interp.time([early])
        assert isinstance(result, xr.Dataset)
        assert result.sizes["time"] == 1

    def test_after_range_extrapolated(self, ds_ts):
        """Dates after dataset end → last value is repeated."""
        late = pd.Timestamp("2020-01-10")
        result = ds_ts.interp.time([late])
        assert isinstance(result, xr.Dataset)
        assert result.sizes["time"] == 1

    def test_mixed_dates(self, ds_ts):
        dates = [
            pd.Timestamp("2019-12-31"),   # before
            pd.Timestamp("2020-01-01 12:00"),  # in range
            pd.Timestamp("2020-01-10"),   # after
        ]
        result = ds_ts.interp.time(dates)
        assert isinstance(result, xr.Dataset)
        assert result.sizes["time"] == 3

    def test_variables_preserved(self, ds_ts):
        dates = [pd.Timestamp("2020-01-01 08:00")]
        result = ds_ts.interp.time(dates)
        assert "temp" in result
        assert "sal" in result

    def test_nontime_vars_preserved(self, ds_ts):
        """Variables without a time dimension must be copied unchanged."""
        ds = ds_ts.copy()
        ds["station_id"] = xr.DataArray(42)  # scalar, no time dim
        result = ds.interp.time(["2020-01-01 06:00"])
        assert "station_id" in result


# ---------------------------------------------------------------------------
# .grid2loc — scattered location interpolation
# ---------------------------------------------------------------------------

class TestInterpGrid2loc:
    def test_returns_dataset(self, ds_gridded):
        coords = [(42.5, 2.5), (43.5, 1.0)]
        result = ds_gridded.interp.grid2loc(coords)
        assert isinstance(result, xr.Dataset)

    def test_npts_dimension(self, ds_gridded):
        coords = [(42.0, 1.0), (44.0, 3.0), (41.5, 2.0)]
        result = ds_gridded.interp.grid2loc(coords)
        assert "npts" in result.dims
        assert result.sizes["npts"] == 3

    def test_output_has_lon_lat(self, ds_gridded):
        coords = [(42.0, 1.0)]
        result = ds_gridded.interp.grid2loc(coords)
        assert "lon" in result.coords
        assert "lat" in result.coords

    def test_output_variable_present(self, ds_gridded):
        coords = [(42.0, 2.5)]
        result = ds_gridded.interp.grid2loc(coords)
        assert "temp" in result

    def test_single_point(self, ds_gridded):
        coords = [(42.5, 2.5)]
        result = ds_gridded.interp.grid2loc(coords)
        assert result.sizes["npts"] == 1


# ---------------------------------------------------------------------------
# .grid2section — section interpolation
# ---------------------------------------------------------------------------

class TestInterpGrid2section:
    def test_returns_dataset(self, ds_gridded):
        coords = [(42.0, 1.0), (44.0, 4.0)]
        result = ds_gridded.interp.grid2section(coords, dx=50.0)
        assert isinstance(result, xr.Dataset)

    def test_has_distance_coord(self, ds_gridded):
        coords = [(42.0, 1.0), (44.0, 4.0)]
        result = ds_gridded.interp.grid2section(coords, dx=50.0)
        assert "distance" in result.coords

    def test_distance_is_positive(self, ds_gridded):
        coords = [(42.0, 1.0), (44.0, 4.0)]
        result = ds_gridded.interp.grid2section(coords, dx=50.0)
        assert float(result.distance.min()) >= 0.0

    def test_npts_grows_with_smaller_dx(self, ds_gridded):
        coords = [(42.0, 1.0), (44.0, 4.0)]
        r_coarse = ds_gridded.interp.grid2section(coords, dx=100.0)
        r_fine   = ds_gridded.interp.grid2section(coords, dx=50.0)
        assert r_fine.sizes["npts"] >= r_coarse.sizes["npts"]

    def test_multisegment(self, ds_gridded):
        coords = [(42.0, 1.0), (43.0, 2.5), (44.0, 4.0)]
        result = ds_gridded.interp.grid2section(coords, dx=80.0)
        assert isinstance(result, xr.Dataset)
        assert result.sizes["npts"] > 1


# ---------------------------------------------------------------------------
# .vertical — vertical interpolation
# ---------------------------------------------------------------------------

class TestInterpVertical:
    def test_returns_dataset(self, ds_vertical):
        result = ds_vertical.interp.vertical("depth", [0.0, 25.0, 75.0])
        assert isinstance(result, xr.Dataset)

    def test_output_levels(self, ds_vertical):
        levels = [0.0, 25.0, 75.0, 150.0]
        result = ds_vertical.interp.vertical("depth", levels)
        assert "temp" in result

    def test_linear_interpolation_value(self, ds_vertical):
        """Between depth=0 (temp=20) and depth=10 (temp~=16.25), at 5 m → ~18.125."""
        result = ds_vertical.interp.vertical("depth", [5.0])
        val = float(result["temp"].values.flat[0])
        assert val == pytest.approx(18.125, rel=0.05)

    def test_variable_preserved(self, ds_vertical):
        result = ds_vertical.interp.vertical("depth", [0.0, 50.0])
        assert "temp" in result
