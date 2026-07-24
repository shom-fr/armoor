"""Unit tests for OutputProcessor's data-type awareness in armoor.data.output.

Before this, _validate_output_compatibility/_process_output_type always read
the flat, ocean-model-shaped OUTPUTS_PARAMS dict regardless of the actual
dataset's type. For an eddies dataset, whose outputs_params only defines
"pdf_eddies", this would have incorrectly treated e.g. otype="maps" as
valid (ocean model's own entry), letting eddy data reach stats code that
assumes ptemp/depth. Now it must be skipped (logged forbidden, no crash).
"""
from unittest.mock import patch

import numpy as np
import pandas as pd
import pytest
import xarray as xr

from armoor.data.datatype import DataEddies, DataMeteo, DataOceanModel
from armoor.data.output import (
    OutputProcessor, get_datatrees, get_dim_stats,
    _merge_zless_into_shallowest, _merge_minmax_dicts,
)


class TestValidateOutputCompatibilityPerType:

    def test_ocean_model_maps_is_valid(self):
        processor = OutputProcessor()
        outputs_params = DataOceanModel().outputs_params
        output = {"otype": "maps"}
        assert processor._validate_output_compatibility(output, {}, "mz1", outputs_params)

    def test_eddies_maps_is_forbidden(self):
        processor = OutputProcessor()
        outputs_params = DataEddies().outputs_params
        output = {"otype": "maps"}
        assert not processor._validate_output_compatibility(output, {}, "mz1", outputs_params)

    def test_meteo_maps_and_timeseries_and_mapseries_are_valid(self):
        processor = OutputProcessor()
        outputs_params = DataMeteo().outputs_params
        for otype in ("maps", "timeseries", "mapseries"):
            assert processor._validate_output_compatibility(
                {"otype": otype}, {}, "mz1", outputs_params
            )

    def test_meteo_profile_and_diagts_otypes_are_forbidden(self):
        """Vertical-profile/theta-saln otypes make no sense for a
        surface-only, non-oceanographic source -- DataMeteo.outputs_params
        deliberately omits them, so they must be rejected here."""
        processor = OutputProcessor()
        outputs_params = DataMeteo().outputs_params
        for otype in ("vprofiles_sel", "mvprofiles", "uvprofiles",
                      "diagts_sel", "mdiagts", "udiagts"):
            assert not processor._validate_output_compatibility(
                {"otype": otype}, {}, "mz1", outputs_params
            )


class TestGenerateOutputsPerType:

    def test_eddies_dataset_produces_no_outputs_without_touching_files(self):
        # outputs_params is empty for eddies, so _validate_output_compatibility
        # must reject every otype before _process_output_type ever runs --
        # fouts=[] would blow up downstream if that guard didn't hold.
        processor = OutputProcessor()
        ncouts = processor._generate_outputs(
            fouts=[],
            metazone="mz1",
            mparams={},
            outputs={"o1": {"otype": "maps"}},
            prod_name="eddy1",
            ncouts={},
            outputs_params=DataEddies().outputs_params,
        )
        assert ncouts == {}


class TestPrepareInterpolationParamsDoesNotCorruptMetazones:
    """Regression test for the mparams=None crash.

    _prepare_interpolation_params used to mutate the caller's metazones dict
    in place (via validate_metazone_params) to signal "no interpolation
    needed" for a metazone missing both vlevel and vfreq. _process_metazone
    then re-read that *same*, now-corrupted metazones[metazone] as mparams
    for unrelated time/vertical range processing, crashing with
    "TypeError: argument of type 'NoneType' is not iterable" the moment a
    metazone had no interpolation params configured at all -- an entirely
    ordinary case (see REFACTOR_PLAN_DATA_DATATYPE.md follow-up).

    Exercised directly at this level (no real dataset/file I/O) since the
    bug lives entirely in the metazones-dict handling, not in dataset
    processing itself.
    """

    def test_metazone_without_interpolation_params_stays_intact(self):
        # No vlevel/vfreq at all -- exactly the case that used to null out
        # this same metazone dict before _process_metazone read it.
        metazones = {"mz1": {}}
        processor = OutputProcessor()

        interp_params = processor._prepare_interpolation_params(metazones)

        assert interp_params == {"mz1": None}
        # The caller's own metazones dict must come out exactly as it went in.
        assert metazones == {"mz1": {}}


class TestComputeDiags:
    """_compute_diags always runs armoor.diags.eddies.compute_vars (a no-op
    for non-eddy datasets), and additionally runs the pdf diagnostic when
    otype == "pdf_eddies"."""

    def test_adds_vmax_radius_regardless_of_otype(self):
        processor = OutputProcessor()
        ds = xr.Dataset({"vmax_area": ("obs", [np.pi])})
        ds = processor._compute_diags(ds, "netcdf")

        assert "vmax_radius" in ds
        np.testing.assert_allclose(ds["vmax_radius"], [1.0])


class TestProcessTreeDatasetObsConcat:
    """Eddy detections are obs-indexed (one row per detection, no time/z
    grid) -- concat_dim=["obs"] is DataEddies.outputs_params["pdf_eddies"]'s
    fusion strategy (see armoor.data.datatype), sorting the result by time
    since detections across files aren't necessarily in chronological
    order."""

    def _make_node(self, ds):
        node = type("Node", (), {"to_dataset": lambda self: ds})()
        return {"data": node}

    def test_concatenates_along_obs_and_sorts_by_time(self):
        processor = OutputProcessor()
        ds1 = xr.Dataset(
            {"vmax_area": ("obs", [1.0, 2.0])},
            coords={"time": ("obs", np.array(["2020-01-02", "2020-01-03"], dtype="datetime64[ns]"))},
        )
        ds2 = xr.Dataset(
            {"vmax_area": ("obs", [3.0])},
            coords={"time": ("obs", np.array(["2020-01-01"], dtype="datetime64[ns]"))},
        )
        dts0 = [self._make_node(ds1), self._make_node(ds2)]

        out = processor._process_tree_dataset(dts0, "data", ["obs"], {"otype": "netcdf"})

        assert out.sizes["obs"] == 3
        assert list(out.time.values) == sorted(out.time.values)

    def test_runs_compute_diags_and_assigns_output_attrs(self):
        processor = OutputProcessor()
        ds = xr.Dataset(
            {"vmax_area": ("obs", [np.pi])},
            coords={"time": ("obs", np.array(["2020-01-01"], dtype="datetime64[ns]"))},
        )
        dts0 = [self._make_node(ds)]

        out = processor._process_tree_dataset(dts0, "data", ["obs"], {"otype": "netcdf", "extra": "value"})

        assert "vmax_radius" in out
        assert out.attrs == {"extra": "value"}
        assert "otype" not in out.attrs


class TestApplyRangeProcessingNativeVerticalFallback:
    """Regression test for the "all z levels overlaid as one line" bug in
    armoor-data's timeseries/maps plots (seen in comp_clim-style CI output).

    When a metazone configures neither vlevel nor vrange,
    _apply_range_processing used to leave the dataset's "z" dimension
    entirely intact and unsplit -- a plot then draws one line per native
    z-level on the same axes instead of one figure per level. It must now
    fall back to splitting by the dataset's own native vertical levels,
    exactly like ranges.vlevels does when vlevel is explicitly configured.
    """

    def _make_ds(self):
        return xr.Dataset(
            {"temp": (["time", "z", "y", "x"], np.zeros((2, 3, 2, 2)))},
            coords={
                "time": ("time", np.array(["2020-01-01", "2020-01-02"], dtype="datetime64[ns]")),
                "depth": ("z", [0.0, 10.0, 20.0]),
            },
        )

    def test_splits_by_native_depth_when_unconfigured(self):
        processor = OutputProcessor()
        ds = self._make_ds()

        dss = processor._apply_range_processing(ds, mparams={})

        assert len(dss) == 3
        assert sorted(d.attrs["vlevel"] for d in dss) == ["0.0", "10.0", "20.0"]

    def test_vlevel_configured_takes_precedence(self):
        # By this point in the real pipeline, _apply_interpolations has
        # already vertically interpolated the dataset onto the requested
        # "levels" -- ranges.vlevels just splits whatever z-points are
        # already there, it doesn't filter by the "levels" list itself.
        processor = OutputProcessor()
        ds = xr.Dataset(
            {"temp": (["time", "z", "y", "x"], np.zeros((2, 2, 2, 2)))},
            coords={
                "time": ("time", np.array(["2020-01-01", "2020-01-02"], dtype="datetime64[ns]")),
                "depth": ("z", [0.0, 20.0]),
            },
        )

        dss = processor._apply_range_processing(
            ds, mparams={"vlevel": {"vname": "depth", "levels": [0.0, 20.0]}}
        )

        assert len(dss) == 2

    def test_no_z_dim_is_a_no_op(self):
        processor = OutputProcessor()
        ds = xr.Dataset(
            {"sst": (["time", "y", "x"], np.zeros((2, 2, 2)))},
            coords={"time": ("time", np.array(["2020-01-01", "2020-01-02"], dtype="datetime64[ns]"))},
        )

        dss = processor._apply_range_processing(ds, mparams={})

        assert len(dss) == 1

    def test_vlevel_configured_but_no_z_dim_is_ignored(self):
        """A metazone can configure vlevel for the sake of a depth-resolved
        source (e.g. a model) sharing it with a surface-only one (e.g.
        satellite SST) -- the latter must not crash trying to split by a
        "z" dimension it doesn't have."""
        processor = OutputProcessor()
        ds = xr.Dataset(
            {"sst": (["time", "y", "x"], np.zeros((2, 2, 2)))},
            coords={"time": ("time", np.array(["2020-01-01", "2020-01-02"], dtype="datetime64[ns]"))},
        )

        dss = processor._apply_range_processing(
            ds, mparams={"vlevel": {"vname": "depth", "levels": [0, 10]}}
        )

        assert len(dss) == 1

    def test_depth_with_spurious_time_dim_does_not_crash(self):
        """Regression test: CMEMS glo12 data can carry "depth" with a
        leftover "time" dim (constant across time in practice, but not
        squeezed away), which made ranges.vlevels crash with
        "unsupported format string passed to numpy.ndarray.__format__"
        when formatting the per-level attrs label."""
        processor = OutputProcessor()
        ds = xr.Dataset(
            {"temp": (["time", "z", "y", "x"], np.zeros((2, 3, 2, 2)))},
            coords={
                "time": ("time", np.array(["2020-01-01", "2020-01-02"], dtype="datetime64[ns]")),
                "depth": (["time", "z"], np.tile([0.0, 10.0, 20.0], (2, 1))),
            },
        )

        dss = processor._apply_range_processing(ds, mparams={})

        assert len(dss) == 3
        assert sorted(d.attrs["vlevel"] for d in dss) == ["0.0", "10.0", "20.0"]


class TestApplyInterpolationsSkipsVerticalWithoutZ:
    """Same "ignore, don't reject" rule as _apply_range_processing, but for
    the interpolation stage: vertical params configured for a
    depth-resolved sibling source must not be applied to a "z"-less one."""

    def test_vertical_skipped_without_z_dim(self):
        processor = OutputProcessor()
        ds = xr.Dataset({"sst": (["y", "x"], np.zeros((2, 2)))})

        with patch("armoor.data.output.process_vertical_interpolation") as mock_vert:
            processor._apply_interpolations(ds, {"vertical": ["vlevel"]}, {})

        mock_vert.assert_not_called()

    def test_vertical_applied_with_z_dim(self):
        processor = OutputProcessor()
        ds = xr.Dataset({"temp": (["z", "y", "x"], np.zeros((2, 2, 2)))})

        with patch("armoor.data.output.process_vertical_interpolation", return_value=ds) as mock_vert:
            processor._apply_interpolations(ds, {"vertical": ["vlevel"]}, {})

        mock_vert.assert_called_once()

    def test_time_interpolation_skipped_for_climatology(self):
        """A climatology's "time" is a month-of-year index, not a real
        calendar date -- applying tfreq-style time interpolation to it
        crashes (TypeError comparing Timestamp to a plain float)."""
        processor = OutputProcessor()
        ds = xr.Dataset({"ptemp": (["time"], np.zeros(3))})

        with patch("armoor.data.output.process_time_interpolation") as mock_time:
            processor._apply_interpolations(
                ds, {"time": ["tfreq"]}, {}, is_climatology=True
            )

        mock_time.assert_not_called()

    def test_time_interpolation_applied_for_non_climatology(self):
        processor = OutputProcessor()
        ds = xr.Dataset({"ptemp": (["time"], np.zeros(3))})

        with patch("armoor.data.output.process_time_interpolation", return_value=ds) as mock_time:
            processor._apply_interpolations(
                ds, {"time": ["tfreq"]}, {}, is_climatology=False
            )

        mock_time.assert_called_once()


class TestApplyRangeProcessingSkipsTimeForClimatology:
    """Same "ignore, don't reject" rule, but for the range-splitting
    stage: tfreq/trange_seq don't apply to a climatology's month-of-year
    "time" axis, so it stays a single unsplit group."""

    def test_tfreq_skipped_for_climatology(self):
        processor = OutputProcessor()
        ds = xr.Dataset({"ptemp": (["time"], np.zeros(3))}, coords={"time": [1.0, 2.0, 3.0]})

        dss = processor._apply_range_processing(
            ds, mparams={"tfreq": "1D"}, is_climatology=True
        )

        assert len(dss) == 1

    def test_tfreq_applied_for_non_climatology(self):
        processor = OutputProcessor()
        ds = xr.Dataset(
            {"ptemp": (["time"], np.zeros(2))},
            coords={"time": np.array(["2020-01-01", "2020-01-02"], dtype="datetime64[ns]")},
        )

        dss = processor._apply_range_processing(
            ds, mparams={"tfreq": "1D"}, is_climatology=False
        )

        assert len(dss) == 2


class TestGetDatatreesNoStatWhenNothingConfigured:
    """When a metazone configures neither tfreq/trange_seq nor vrange,
    get_dim_stats legitimately reduces "maps"'s stat=["time","z"] down to
    an empty list ("y"/"x" aren't stat candidates for "maps", unlike
    "timeseries"), and get_datatrees correctly skips creating "mean"/"std"
    nodes in that case -- there is nothing meaningful to average over.
    Unlike comp_*, which always has vlevel/vrange/trange_seq configured,
    armoor-data must let this "nothing configured" case through: the plot
    layer (armoor.data.plot) is responsible for falling back to the raw
    "data" node when "mean" isn't there, not this layer manufacturing one.
    """

    def _make_ds(self):
        return xr.Dataset(
            {"temp": (["time", "z", "y", "x"], np.arange(8, dtype=float).reshape(2, 1, 2, 2))},
            coords={"time": ("time", np.array(["2020-01-01", "2020-01-02"], dtype="datetime64[ns]"))},
            attrs={"data_name": "glo12"},
        )

    def test_maps_stat_empty_when_unconfigured(self):
        ds = self._make_ds()

        result = get_dim_stats(ds, ["time", "z"], mparams={})

        assert result == []

    def test_no_mean_or_std_node_when_stat_is_empty(self):
        ds = self._make_ds()

        dts = get_datatrees([ds], ["time", "z"], mparams={})

        assert "mean" not in dts[0].children
        assert "std" not in dts[0].children
        assert "data" in dts[0].children

    def test_timeseries_stat_still_reduces_yx(self):
        """"timeseries"-style stat lists (which include "y") are unaffected:
        time/z stay excluded from stat (preserved as plot axes), "y"/"x"
        remain to be reduced -- unchanged pre-existing behavior."""
        ds = self._make_ds()

        result = get_dim_stats(ds, ["time", "z", "y", "x"], mparams={})

        assert result == ["y", "x"]

    def test_no_stat_requested_returns_none(self):
        ds = self._make_ds()

        assert get_dim_stats(ds, None, mparams={}) is None


class TestMapseriesOutputsParams:
    """mapseries has no "stat" key at all (unlike "maps", which has one
    that happens to reduce to an empty list when nothing is configured) --
    get_datatrees must build a DataTree with only a "data" child
    regardless of what's configured on the metazone, matching the "no
    aggregated mode" requirement."""

    def _make_ds(self):
        return xr.Dataset(
            {"ptemp": (["time", "y", "x"], np.random.rand(3, 2, 2))},
            coords={
                "time": pd.date_range("2024-01-01", periods=3),
                "lon": (["y", "x"], np.array([[0.0, 1.0], [0.0, 1.0]])),
                "lat": (["y", "x"], np.array([[0.0, 0.0], [1.0, 1.0]])),
            },
            attrs={"data_name": "model"},
        )

    def test_no_stat_key_in_outputs_params(self):
        oparams = DataOceanModel().outputs_params["mapseries"]
        assert "stat" not in oparams
        assert oparams["sort"] == ["time", "z"]
        assert "concat" not in oparams

    def test_only_data_child_when_stat_is_absent(self):
        """dim=None (oparams.get("stat") on a dict with no "stat" key)
        short-circuits get_dim_stats before it even looks at mparams --
        unlike "maps"'s stat=["time","z"], which merely *reduces* to []
        for an unconfigured metazone (see
        TestGetDatatreesNoStatWhenNothingConfigured above)."""
        ds = self._make_ds()
        oparams = DataOceanModel().outputs_params["mapseries"]

        dts = get_datatrees([ds], oparams.get("stat"), mparams={})

        assert list(dts[0].keys()) == ["data"]


class TestValidateOutputCompatibilityClimatologyGuard:
    """A climatology (is_climatology=True, e.g. woa18/bobyclim) is meant to
    be referenced by name via an output's "clim" setting, not to render
    its own mapseries series -- see _resolve_clim_ranges below for how
    that reference is actually used."""

    def setup_method(self):
        self.processor = OutputProcessor()
        self.outputs_params = DataOceanModel().outputs_params

    def test_climatology_skips_mapseries(self):
        output = {"otype": "mapseries"}
        assert not self.processor._validate_output_compatibility(
            output, {}, "mz1", self.outputs_params, is_climatology=True
        )

    def test_non_climatology_allows_mapseries(self):
        output = {"otype": "mapseries"}
        assert self.processor._validate_output_compatibility(
            output, {}, "mz1", self.outputs_params, is_climatology=False
        )

    def test_climatology_still_allows_other_otypes(self):
        """The guard is specific to mapseries -- a climatology stays
        eligible for otypes it was already compatible with."""
        output = {"otype": "maps"}
        assert self.processor._validate_output_compatibility(
            output, {}, "mz1", self.outputs_params, is_climatology=True
        )


class TestResolveClimRanges:
    """_resolve_clim_ranges pre-resolves, per metazone, the min/max of
    every [data] source referenced via an output's "clim" setting -- the
    source armoor.data.plot.PlotOceanModel._mapseries_scalar reads to draw
    the min/max table's optional "clim" row."""

    def _write_nc(self, path, data_name, ptemp_values):
        ds = xr.Dataset(
            {"ptemp": (["time", "y", "x"], ptemp_values)},
            coords={
                "time": pd.date_range("2024-01-01", periods=ptemp_values.shape[0]),
                "lon": (["y", "x"], np.array([[0.0, 1.0], [0.0, 1.0]])),
                "lat": (["y", "x"], np.array([[0.0, 0.0], [1.0, 1.0]])),
            },
            attrs={"data_name": data_name, "data_type": "ocean_model"},
        )
        ds.to_netcdf(path)
        return str(path)

    def test_only_clim_source_is_resolved(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        model_nc = self._write_nc(
            tmp_path / "model.nc", "model",
            np.array([[[10.0, 11.0], [12.0, 13.0]]]),
        )
        clim_nc = self._write_nc(
            tmp_path / "clim.nc", "woa18",
            np.array([[[5.0, 6.0], [7.0, 8.0]]]),
        )
        metazones = {"mz1": {}}
        outputs = {"mapseries": {"otype": "mapseries", "clim": "woa18"}}
        processor = OutputProcessor()
        interp_params = processor._prepare_interpolation_params(metazones)

        clim_ranges = processor._resolve_clim_ranges(
            [model_nc, clim_nc], metazones, outputs, interp_params
        )

        assert set(clim_ranges.keys()) == {("mz1", "woa18", None)}
        vmin, vmax = clim_ranges[("mz1", "woa18", None)]["ptemp"]
        assert vmin == pytest.approx(5.0)
        assert vmax == pytest.approx(8.0)

    def test_no_clim_configured_returns_empty(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        model_nc = self._write_nc(
            tmp_path / "model.nc", "model",
            np.array([[[10.0, 11.0], [12.0, 13.0]]]),
        )
        metazones = {"mz1": {}}
        outputs = {"mapseries": {"otype": "mapseries"}}
        processor = OutputProcessor()
        interp_params = processor._prepare_interpolation_params(metazones)

        clim_ranges = processor._resolve_clim_ranges(
            [model_nc], metazones, outputs, interp_params
        )

        assert clim_ranges == {}


class TestResolveSeriesRanges:
    """_resolve_series_ranges pools a source's own mean/std across its
    whole series, per (metazone, data_name) -- needed because mapseries
    now saves one zarr per (time, z) group (see
    armoor.data.datatype.DataOceanModel.outputs_params["mapseries"]), so
    a single zarr no longer holds the full series to compute this from."""

    def _write_nc(self, path, data_name, ptemp_value, with_vector=False, data_type="ocean_model"):
        data_vars = {"ptemp": (["time", "y", "x"], np.full((1, 2, 2), ptemp_value))}
        if with_vector:
            data_vars["u"] = (["time", "y", "x"], np.full((1, 2, 2), 3.0))
            data_vars["v"] = (["time", "y", "x"], np.full((1, 2, 2), 4.0))
        ds = xr.Dataset(
            data_vars,
            coords={
                "time": pd.date_range("2024-01-01", periods=1),
                "lon": (["y", "x"], np.array([[0.0, 1.0], [0.0, 1.0]])),
                "lat": (["y", "x"], np.array([[0.0, 0.0], [1.0, 1.0]])),
            },
            attrs={"data_name": data_name, "data_type": data_type},
        )
        ds.to_netcdf(path)
        return str(path)

    def test_pools_mean_std_across_files(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        nc1 = self._write_nc(tmp_path / "d1.nc", "model", 10.0)
        nc2 = self._write_nc(tmp_path / "d2.nc", "model", 12.0)
        metazones = {"mz1": {}}
        outputs = {"mapseries": {"otype": "mapseries"}}
        processor = OutputProcessor()
        interp_params = processor._prepare_interpolation_params(metazones)

        stats = processor._resolve_series_ranges([nc1, nc2], metazones, outputs, interp_params)

        mean, std = stats[("mz1", "model", None)]["ptemp"]
        assert mean == pytest.approx(11.0)
        assert std == pytest.approx(1.0)

    def test_pools_cspeed_from_u_v(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        nc1 = self._write_nc(tmp_path / "d1.nc", "model", 10.0, with_vector=True)
        metazones = {"mz1": {}}
        outputs = {"mapseries": {"otype": "mapseries"}}
        processor = OutputProcessor()
        interp_params = processor._prepare_interpolation_params(metazones)

        stats = processor._resolve_series_ranges([nc1], metazones, outputs, interp_params)

        mean, std = stats[("mz1", "model", None)]["cspeed"]
        assert mean == pytest.approx(5.0)  # sqrt(3**2 + 4**2)
        assert std == pytest.approx(0.0)

    def test_climatology_excluded(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        nc1 = self._write_nc(tmp_path / "clim.nc", "woa18", 999.0, data_type="woa18")
        metazones = {"mz1": {}}
        outputs = {"mapseries": {"otype": "mapseries"}}
        processor = OutputProcessor()
        interp_params = processor._prepare_interpolation_params(metazones)

        stats = processor._resolve_series_ranges([nc1], metazones, outputs, interp_params)

        assert stats == {}

    def test_no_mapseries_output_returns_empty(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        nc1 = self._write_nc(tmp_path / "d1.nc", "model", 10.0)
        metazones = {"mz1": {}}
        outputs = {"maps": {"otype": "maps"}}
        processor = OutputProcessor()
        interp_params = processor._prepare_interpolation_params(metazones)

        stats = processor._resolve_series_ranges([nc1], metazones, outputs, interp_params)

        assert stats == {}


class TestAttachSeriesRange:

    def test_injects_series_mean_std_when_otype_mapseries(self):
        processor = OutputProcessor()
        processor._series_stats = {("mz1", "model", None): {"ptemp": (11.0, 1.0)}}
        ds = xr.Dataset({"ptemp": ("x", [1.0])})

        processor._attach_series_range(ds, "mz1", "model", {"otype": "mapseries"})

        assert ds.attrs["series_mean_ptemp"] == 11.0
        assert ds.attrs["series_std_ptemp"] == 1.0

    def test_noop_for_other_otypes(self):
        processor = OutputProcessor()
        processor._series_stats = {("mz1", "model", None): {"ptemp": (11.0, 1.0)}}
        ds = xr.Dataset({"ptemp": ("x", [1.0])})

        processor._attach_series_range(ds, "mz1", "model", {"otype": "maps"})

        assert "series_mean_ptemp" not in ds.attrs


class TestResolveCbarRanges:
    """_resolve_cbar_ranges pools a shared min/max envelope, per
    (metazone, cbar_group), across every non-climatology source -- e.g. an
    obs and a model series of the same variable end up on the same
    colorbar instead of each computing its own bounds independently."""

    def _write_nc(self, path, data_name, ptemp_values, data_type="ocean_model"):
        ds = xr.Dataset(
            {"ptemp": (["time", "y", "x"], ptemp_values)},
            coords={
                "time": pd.date_range("2024-01-01", periods=ptemp_values.shape[0]),
                "lon": (["y", "x"], np.array([[0.0, 1.0], [0.0, 1.0]])),
                "lat": (["y", "x"], np.array([[0.0, 0.0], [1.0, 1.0]])),
            },
            attrs={"data_name": data_name, "data_type": data_type},
        )
        ds.to_netcdf(path)
        return str(path)

    def test_pools_min_max_across_sources_sharing_cbar_group(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        obs_nc = self._write_nc(
            tmp_path / "obs.nc", "sst_obs", np.array([[[8.0, 9.0], [10.0, 11.0]]])
        )
        model_nc = self._write_nc(
            tmp_path / "model.nc", "sst_model", np.array([[[12.0, 13.0], [14.0, 15.0]]])
        )
        metazones = {"mz1": {}}
        outputs = {
            "mapseries_obs": {"otype": "mapseries", "cbar_group": "sst"},
            "mapseries_model": {"otype": "mapseries", "cbar_group": "sst"},
        }
        processor = OutputProcessor()
        interp_params = processor._prepare_interpolation_params(metazones)

        cbar_ranges = processor._resolve_cbar_ranges(
            [obs_nc, model_nc], metazones, outputs, interp_params
        )

        assert set(cbar_ranges.keys()) == {("mz1", "sst", None)}
        vmin, vmax = cbar_ranges[("mz1", "sst", None)]["ptemp"]
        assert vmin == pytest.approx(8.0)
        assert vmax == pytest.approx(15.0)

    def test_zless_obs_pools_with_model_shallowest_level(self, tmp_path, monkeypatch):
        """A z-less source (e.g. satellite SST) sharing "cbar_group" with a
        depth-split model must still end up on the same color scale as
        the model's shallowest level -- its own level_key (None) never
        equals the model's ("vlevel", ...) keys, so without
        _merge_zless_into_shallowest they'd never pool at all."""
        monkeypatch.chdir(tmp_path)
        obs_nc = self._write_nc(
            tmp_path / "obs.nc", "sst_obs", np.array([[[20.0, 21.0], [22.0, 23.0]]])
        )
        model_ds = xr.Dataset(
            {"ptemp": (["time", "z", "y", "x"], np.array([[
                [[18.0, 19.0], [20.0, 21.0]],
                [[5.0, 6.0], [7.0, 8.0]],
            ]]))},
            coords={
                "time": pd.date_range("2024-01-01", periods=1),
                "depth": (["z"], [0.0, 100.0]),
                "lon": (["y", "x"], np.array([[0.0, 1.0], [0.0, 1.0]])),
                "lat": (["y", "x"], np.array([[0.0, 0.0], [1.0, 1.0]])),
            },
            attrs={"data_name": "model", "data_type": "ocean_model"},
        )
        model_nc = str(tmp_path / "model.nc")
        model_ds.to_netcdf(model_nc)

        metazones = {
            "mz1": {"vlevel": {"vname": "depth", "levels": [0.0, 100.0]}}
        }
        outputs = {"mapseries": {"otype": "mapseries", "cbar_group": "sst"}}
        processor = OutputProcessor()
        interp_params = processor._prepare_interpolation_params(metazones)

        cbar_ranges = processor._resolve_cbar_ranges(
            [obs_nc, model_nc], metazones, outputs, interp_params
        )

        surface_key = ("mz1", "sst", ("vlevel", "0.0"))
        deep_key = ("mz1", "sst", ("vlevel", "100.0"))
        obs_key = ("mz1", "sst", None)

        # obs (20-23) merged with the model's surface level (18-21).
        assert cbar_ranges[surface_key]["ptemp"] == pytest.approx((18.0, 23.0))
        assert cbar_ranges[obs_key]["ptemp"] == pytest.approx((18.0, 23.0))
        # The deep level (5-8) stays untouched by obs.
        assert cbar_ranges[deep_key]["ptemp"] == pytest.approx((5.0, 8.0))

    def test_climatology_source_excluded_from_pooling(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        model_nc = self._write_nc(
            tmp_path / "model.nc", "model", np.array([[[10.0, 11.0], [12.0, 13.0]]])
        )
        clim_nc = self._write_nc(
            tmp_path / "clim.nc", "woa18", np.array([[[-100.0, 200.0], [0.0, 0.0]]]),
            data_type="woa18",
        )
        metazones = {"mz1": {}}
        outputs = {"mapseries": {"otype": "mapseries", "cbar_group": "sst"}}
        processor = OutputProcessor()
        interp_params = processor._prepare_interpolation_params(metazones)

        cbar_ranges = processor._resolve_cbar_ranges(
            [model_nc, clim_nc], metazones, outputs, interp_params
        )

        vmin, vmax = cbar_ranges[("mz1", "sst", None)]["ptemp"]
        assert vmin == pytest.approx(10.0)
        assert vmax == pytest.approx(13.0)

    def test_no_cbar_group_configured_returns_empty(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        model_nc = self._write_nc(
            tmp_path / "model.nc", "model", np.array([[[10.0, 11.0], [12.0, 13.0]]])
        )
        metazones = {"mz1": {}}
        outputs = {"mapseries": {"otype": "mapseries"}}
        processor = OutputProcessor()
        interp_params = processor._prepare_interpolation_params(metazones)

        cbar_ranges = processor._resolve_cbar_ranges(
            [model_nc], metazones, outputs, interp_params
        )

        assert cbar_ranges == {}


class TestMergeZlessIntoShallowest:
    """Pure-function coverage for the merge helper itself, independent of
    file I/O -- see TestResolveCbarRanges.
    test_zless_obs_pools_with_model_shallowest_level for the end-to-end
    version through _resolve_cbar_ranges."""

    def test_zless_merged_into_shallowest_level(self):
        pooled = {
            ("mz1", "sst", None): {"ptemp": (20.0, 23.0)},
            ("mz1", "sst", ("vlevel", "0.0")): {"ptemp": (18.0, 21.0)},
            ("mz1", "sst", ("vlevel", "100.0")): {"ptemp": (5.0, 8.0)},
        }

        _merge_zless_into_shallowest(pooled, _merge_minmax_dicts)

        assert pooled[("mz1", "sst", ("vlevel", "0.0"))]["ptemp"] == (18.0, 23.0)
        assert pooled[("mz1", "sst", None)]["ptemp"] == (18.0, 23.0)
        assert pooled[("mz1", "sst", ("vlevel", "100.0"))]["ptemp"] == (5.0, 8.0)

    def test_vrange_bins_use_lower_bound_as_depth(self):
        pooled = {
            ("mz1", "g", None): {"v": (1.0, 2.0)},
            ("mz1", "g", ("vrange", "100-500")): {"v": (10.0, 12.0)},
            ("mz1", "g", ("vrange", "0-100")): {"v": (3.0, 4.0)},
        }

        _merge_zless_into_shallowest(pooled, _merge_minmax_dicts)

        assert pooled[("mz1", "g", ("vrange", "0-100"))]["v"] == (1.0, 4.0)
        assert pooled[("mz1", "g", ("vrange", "100-500"))]["v"] == (10.0, 12.0)

    def test_no_op_without_zless_group(self):
        pooled = {
            ("mz1", "sst", ("vlevel", "0.0")): {"ptemp": (18.0, 21.0)},
            ("mz1", "sst", ("vlevel", "100.0")): {"ptemp": (5.0, 8.0)},
        }
        original = {k: dict(v) for k, v in pooled.items()}

        _merge_zless_into_shallowest(pooled, _merge_minmax_dicts)

        assert pooled == original

    def test_no_op_without_depth_resolved_siblings(self):
        pooled = {("mz1", "sst", None): {"ptemp": (18.0, 21.0)}}
        original = {k: dict(v) for k, v in pooled.items()}

        _merge_zless_into_shallowest(pooled, _merge_minmax_dicts)

        assert pooled == original


class TestAttachCbarRange:

    def test_injects_cbar_min_max_attrs_when_configured(self):
        processor = OutputProcessor()
        processor._cbar_ranges = {("mz1", "sst", None): {"ptemp": (8.0, 15.0)}}
        ds = xr.Dataset({"ptemp": ("x", [1.0])})

        processor._attach_cbar_range(ds, "mz1", {"otype": "mapseries", "cbar_group": "sst"})

        assert ds.attrs["cbar_min_ptemp"] == 8.0
        assert ds.attrs["cbar_max_ptemp"] == 15.0

    def test_noop_without_cbar_group(self):
        processor = OutputProcessor()
        processor._cbar_ranges = {("mz1", "sst", None): {"ptemp": (8.0, 15.0)}}
        ds = xr.Dataset({"ptemp": ("x", [1.0])})

        processor._attach_cbar_range(ds, "mz1", {"otype": "mapseries"})

        assert "cbar_min_ptemp" not in ds.attrs
