"""Unit tests for OutputProcessor's data-type awareness in armoor.data.output.

Before this, _validate_output_compatibility/_process_output_type always read
the flat, ocean-model-shaped OUTPUTS_PARAMS dict regardless of the actual
dataset's type. For an eddies dataset, whose outputs_params only defines
"pdf_eddies", this would have incorrectly treated e.g. otype="maps" as
valid (ocean model's own entry), letting eddy data reach stats code that
assumes ptemp/depth. Now it must be skipped (logged forbidden, no crash).
"""
import numpy as np
import xarray as xr

from armoor.data.datatype import DataEddies, DataOceanModel
from armoor.data.output import OutputProcessor, get_datatrees, get_dim_stats


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
