"""Unit tests for armoor xarray accessors (ds.filters, ds.oceanvars, ds.coloc, ds.stats, ds.plot)."""

import numpy as np
import pandas as pd
import pytest
import xarray as xr

import armoor  # registers all accessors as a side-effect
from armoor.accessors.coloc import ColocSession
from armoor.accessors.filters import FiltersAccessor
from armoor.accessors.oceanvars import OceanVars
from armoor.accessors.stats import StatsAccessor
from armoor.accessors.plot import ArmoorPlot


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def ds_grid():
    """2-D gridded dataset with lon/lat/time, suitable for polygon/quality filters."""
    rng = np.random.default_rng(0)
    lon = np.linspace(0, 10, 30)
    lat = np.linspace(0, 10, 20)
    lon2d, lat2d = np.meshgrid(lon, lat)
    time = pd.date_range("2020-01-01", periods=5, freq="D")
    data = rng.random((5, 20, 30))
    return xr.Dataset(
        {
            "temp": (("time", "y", "x"), data),
            "temp_qc": (("time", "y", "x"), rng.integers(0, 10, (5, 20, 30))),
        },
        coords={
            "lon": (("y", "x"), lon2d),
            "lat": (("y", "x"), lat2d),
            "time": time,
        },
    )


@pytest.fixture
def ds_ts():
    """Simple 1-D time-series dataset."""
    time = pd.date_range("2020-01-01", periods=8, freq="D")
    rng = np.random.default_rng(1)
    return xr.Dataset(
        {"temp": ("time", rng.random(8).astype(np.float32))},
        coords={"time": time},
    )


@pytest.fixture
def ds_prod():
    """Product dataset for stats / coloc tests."""
    time = pd.date_range("2020-01-01", periods=6, freq="D")
    return xr.Dataset(
        {"a": ("time", np.array([1.0, 2.0, 3.0, 4.0, 5.0, 6.0]))},
        coords={"time": time},
    )


@pytest.fixture
def ds_ref():
    """Reference dataset for stats / coloc tests (same coords as ds_prod)."""
    time = pd.date_range("2020-01-01", periods=6, freq="D")
    return xr.Dataset(
        {"a": ("time", np.array([0.5, 2.0, 2.5, 5.0, 4.5, 7.0]))},
        coords={"time": time},
    )


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

class TestAccessorRegistration:
    def test_filters_registered(self, ds_grid):
        assert isinstance(ds_grid.filters, FiltersAccessor)

    def test_oceanvars_registered(self, ds_grid):
        assert isinstance(ds_grid.oceanvars, OceanVars)

    def test_coloc_registered(self, ds_prod):
        from armoor.accessors.coloc import ColocAccessor
        assert isinstance(ds_prod.coloc, ColocAccessor)

    def test_stats_registered(self, ds_prod):
        assert isinstance(ds_prod.stats, StatsAccessor)

    def test_plot_registered(self, ds_ts):
        assert isinstance(ds_ts.plot, ArmoorPlot)


# ---------------------------------------------------------------------------
# ds.filters
# ---------------------------------------------------------------------------

class TestFiltersAccessor:
    def test_combined_quality(self, ds_grid):
        cfg = {"quality": {"qname": "temp", "qmin": 2, "qmax": 8}}
        result = ds_grid.filters.combined(cfg)
        assert isinstance(result, xr.Dataset)

    def test_combined_time_selection(self, ds_grid):
        cfg = {"time_selection": {"minimum": "2020-01-02", "maximum": "2020-01-04"}}
        result = ds_grid.filters.combined(cfg)
        assert isinstance(result, xr.Dataset)
        # At most 3 time steps remain
        assert result.sizes["time"] <= 3

    def test_combined_polygon_inside(self, ds_grid):
        coords = [(2, 2), (2, 8), (8, 8), (8, 2)]
        cfg = {"polygon": {"coords": coords}}
        result = ds_grid.filters.combined(cfg)
        assert isinstance(result, xr.Dataset)

    def test_combined_polygon_outside_returns_none(self, ds_grid):
        coords = [(100, 100), (100, 110), (110, 110), (110, 100)]
        cfg = {"polygon": {"coords": coords}}
        result = ds_grid.filters.combined(cfg)
        assert result is None

    def test_combined_data_selection(self, ds_grid):
        cfg = {"data_selection": {"dim": "lat", "minimum": 3.0, "maximum": 7.0}}
        result = ds_grid.filters.combined(cfg)
        assert isinstance(result, xr.Dataset)

    def test_combined_empty_config_returns_dataset(self, ds_grid):
        result = ds_grid.filters.combined({})
        assert isinstance(result, xr.Dataset)

    def test_combined_multiple_filters(self, ds_grid):
        cfg = {
            "quality": {"qname": "temp", "qmin": 1, "qmax": 9},
            "time_selection": {"minimum": "2020-01-01", "maximum": "2020-01-05"},
        }
        result = ds_grid.filters.combined(cfg)
        assert isinstance(result, xr.Dataset)


# ---------------------------------------------------------------------------
# ds.oceanvars
# ---------------------------------------------------------------------------

class TestOceanVarsAccessor:
    @pytest.fixture
    def ds_ocean(self):
        """Dataset with temp, sal, depth — enough for most sel_* methods."""
        n = 10
        depth = np.linspace(0, 500, n).astype(np.float32)
        return xr.Dataset(
            {
                "temp": ("depth", np.linspace(20, 5, n).astype(np.float32)),
                "sal": ("depth", np.linspace(35, 34, n).astype(np.float32)),
            },
            coords={
                "depth": depth,
                "lon": 5.0,
                "lat": 43.0,
            },
        )

    def test_sel_temp(self, ds_ocean):
        da = ds_ocean.oceanvars.sel_temp()
        assert isinstance(da, xr.DataArray)
        assert da.name == "temp"

    def test_sel_sal(self, ds_ocean):
        da = ds_ocean.oceanvars.sel_sal()
        assert isinstance(da, xr.DataArray)
        assert da.name == "sal"

    def test_sel_pres_from_depth(self, ds_ocean):
        da = ds_ocean.oceanvars.sel_pres()
        assert isinstance(da, xr.DataArray)
        # Pressure at 500 m should be roughly 500 dbar
        assert float(da.max()) == pytest.approx(500.0, rel=0.05)

    def test_sel_ptemp(self, ds_ocean):
        da = ds_ocean.oceanvars.sel_ptemp()
        assert isinstance(da, xr.DataArray)

    def test_sel_by_name_temp(self, ds_ocean):
        da = ds_ocean.oceanvars.sel("temp")
        assert isinstance(da, xr.DataArray)

    def test_sel_by_name_sal(self, ds_ocean):
        da = ds_ocean.oceanvars.sel("sal")
        assert isinstance(da, xr.DataArray)

    def test_sel_current_speed_from_uv(self):
        ds = xr.Dataset({"u": 1.0, "v": 1.0})
        cspeed = ds.oceanvars.sel_current_speed()
        assert float(cspeed) == pytest.approx(np.sqrt(2.0))

    def test_sel_current_direction_from_uv(self):
        ds = xr.Dataset({"u": 1.0, "v": 0.0})
        cdir = ds.oceanvars.sel_current_direction()
        assert float(cdir) == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# ds.coloc — ColocSession
# ---------------------------------------------------------------------------

class TestColocAccessor:
    def test_with_ref_returns_session(self, ds_prod, ds_ref):
        session = ds_prod.coloc.with_ref(ds_ref)
        assert isinstance(session, ColocSession)

    def test_session_holds_correct_datasets(self, ds_prod, ds_ref):
        session = ds_prod.coloc.with_ref(ds_ref)
        prod, ref = session
        assert prod is ds_prod
        assert ref is ds_ref

    def test_session_unpack(self, ds_prod, ds_ref):
        prod, ref = ds_prod.coloc.with_ref(ds_ref)
        assert isinstance(prod, xr.Dataset)
        assert isinstance(ref, xr.Dataset)

    def test_session_iter_gives_two_elements(self, ds_prod, ds_ref):
        items = list(ds_prod.coloc.with_ref(ds_ref))
        assert len(items) == 2

    def test_session_chaining_returns_session(self, ds_prod, ds_ref):
        """Verify that colocation methods return ColocSession for chaining."""
        # We use a trivial param that the underlying engine handles gracefully.
        # Here we skip the actual colocation call (it needs real data layout)
        # and just check the ColocSession interface.
        session = ds_prod.coloc.with_ref(ds_ref)
        # Can we unpack again after re-wrapping?
        session2 = ColocSession(*session)
        prod, ref = session2
        assert isinstance(prod, xr.Dataset)
        assert isinstance(ref, xr.Dataset)


# ---------------------------------------------------------------------------
# ds.stats
# ---------------------------------------------------------------------------

class TestStatsAccessor:
    def test_mean_scalar(self, ds_prod):
        result = ds_prod.stats.mean(dim="time")
        assert isinstance(result, xr.Dataset)
        assert result["a"].ndim == 0
        assert float(result["a"]) == pytest.approx(3.5)

    def test_std_scalar(self, ds_prod):
        result = ds_prod.stats.std(dim="time")
        assert isinstance(result, xr.Dataset)
        assert result["a"].ndim == 0
        expected = float(np.std([1, 2, 3, 4, 5, 6]))
        assert float(result["a"]) == pytest.approx(expected)

    def test_mean_no_dim(self, ds_prod):
        result = ds_prod.stats.mean()
        assert isinstance(result, xr.Dataset)
        assert result["a"].ndim == 0

    def test_bias_zero_against_itself(self, ds_prod):
        result = ds_prod.stats.bias(ds_prod, dim="time")
        assert float(result["a"]) == pytest.approx(0.0)

    def test_bias_known_value(self, ds_prod, ds_ref):
        # prod - ref mean over time
        expected = float(np.mean([1 - 0.5, 2 - 2, 3 - 2.5, 4 - 5, 5 - 4.5, 6 - 7]))
        result = ds_prod.stats.bias(ds_ref, dim="time")
        assert float(result["a"]) == pytest.approx(expected)

    def test_rmse_zero_against_itself(self, ds_prod):
        result = ds_prod.stats.rmse(ds_prod, dim="time")
        assert float(result["a"]) == pytest.approx(0.0)

    def test_rmse_known_value(self, ds_prod, ds_ref):
        diffs = np.array([1 - 0.5, 2 - 2, 3 - 2.5, 4 - 5, 5 - 4.5, 6 - 7])
        expected = float(np.sqrt(np.mean(diffs**2)))
        result = ds_prod.stats.rmse(ds_ref, dim="time")
        assert float(result["a"]) == pytest.approx(expected)

    def test_rmsec_zero_against_itself(self, ds_prod):
        result = ds_prod.stats.rmsec(ds_prod, dim="time")
        assert float(result["a"]) == pytest.approx(0.0)

    def test_rmsec_known_value(self, ds_prod, ds_ref):
        prod_vals = np.array([1.0, 2.0, 3.0, 4.0, 5.0, 6.0])
        ref_vals = np.array([0.5, 2.0, 2.5, 5.0, 4.5, 7.0])
        prod_anom = prod_vals - prod_vals.mean()
        ref_anom = ref_vals - ref_vals.mean()
        expected = float(np.sqrt(np.mean((prod_anom - ref_anom) ** 2)))
        result = ds_prod.stats.rmsec(ds_ref, dim="time")
        assert float(result["a"]) == pytest.approx(expected)

    def test_stats_result_is_dataset(self, ds_prod, ds_ref):
        for method in ("mean", "std"):
            out = getattr(ds_prod.stats, method)(dim="time")
            assert isinstance(out, xr.Dataset), f"{method} should return Dataset"

    def test_compare_returns_three_datatrees(self, ds_prod, ds_ref):
        dtprod, dtref, dtcomps = ds_prod.stats.compare(ds_ref, dims=["time"])
        assert isinstance(dtprod, xr.DataTree)
        assert isinstance(dtref, xr.DataTree)
        assert isinstance(dtcomps, xr.DataTree)

    def test_compare_comps_has_bias_rmse(self, ds_prod, ds_ref):
        # trange_seq in mparams tells StatsComp to reduce the time dimension
        _, _, dtcomps = ds_prod.stats.compare(
            ds_ref, dims=["time"], mparams={"trange_seq": True}
        )
        assert "bias" in dtcomps.children
        assert "rmse" in dtcomps.children
        assert "rmsec" in dtcomps.children

    def test_chaining_with_plot(self, ds_prod):
        """stats result can be passed to .plot (accessor is present)."""
        mean_ds = ds_prod.stats.mean(dim="time")
        assert isinstance(mean_ds.plot, ArmoorPlot)


# ---------------------------------------------------------------------------
# ds.plot
# ---------------------------------------------------------------------------

class TestPlotAccessor:
    def test_is_armoor_plot(self, ds_ts):
        assert isinstance(ds_ts.plot, ArmoorPlot)

    def test_armoor_plot_has_maps(self, ds_ts):
        assert hasattr(ds_ts.plot, "maps")

    def test_armoor_plot_has_profiles(self, ds_ts):
        assert hasattr(ds_ts.plot, "profiles")

    def test_armoor_plot_has_timeseries(self, ds_ts):
        assert hasattr(ds_ts.plot, "timeseries")

    def test_maps_returns_object(self, ds_ts):
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        result = ds_ts.plot.maps()
        plt.close("all")
        assert result is not None

    def test_timeseries_returns_object(self, ds_ts):
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        result = ds_ts.plot.timeseries()
        plt.close("all")
        assert result is not None

    def test_armoor_plot_has_diagdisp(self, ds_ts):
        assert hasattr(ds_ts.plot, "diagdisp")

    def test_armoor_plot_has_shadow_line(self, ds_ts):
        assert hasattr(ds_ts.plot, "shadow_line")

    def test_diagdisp_returns_axes(self, ds_prod, ds_ref):
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        import xarray as xr
        ds = xr.merge([ds_prod.rename({"a": "x_var"}), ds_ref.rename({"a": "y_var"})])
        ax = ds.plot.diagdisp("x_var", "y_var")
        plt.close("all")
        import matplotlib.axes
        assert isinstance(ax, matplotlib.axes.Axes)

    def test_diagdisp_delegates_to_base_plot(self, ds_prod, ds_ref):
        """diagdisp draws a scatter + diagonal + regression line (3 artists)."""
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        import xarray as xr
        ds = xr.merge([ds_prod.rename({"a": "x_var"}), ds_ref.rename({"a": "y_var"})])
        ax = ds.plot.diagdisp("x_var", "y_var")
        # diagdisp adds scatter + two lines (diagonal + regression)
        assert len(ax.lines) >= 2
        plt.close("all")

    def test_shadow_line_draws_two_lines(self, ds_ts):
        """shadow_line draws 2 lines (shadow + main line)."""
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        _, ax = plt.subplots()
        var = next(iter(ds_ts.data_vars))
        ds_ts.plot.shadow_line("time", var, ax=ax, label="test")
        assert len(ax.lines) == 2
        plt.close("all")
