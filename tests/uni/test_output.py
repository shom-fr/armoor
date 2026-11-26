"""Unit tests for armoor.comp.output.

These tests stub out heavy optional dependencies (xoa, parcels, etc.) so they
can run in environments that only have the core scientific stack installed.
"""
import sys
import types
import unittest.mock as mock

import numpy as np
import pandas as pd
import xarray as xr
import pytest


# ---------------------------------------------------------------------------
# Stub heavy optional deps before any armoor imports
# ---------------------------------------------------------------------------
def _ensure_mock(name):
    """Insert a MagicMock into sys.modules if the real module is absent."""
    if name in sys.modules:
        return
    import importlib
    try:
        importlib.import_module(name)
    except ImportError:
        sys.modules[name] = mock.MagicMock()


# xoa and its sub-packages
for _mod in (
    "xoa", "xoa.geo", "xoa.grid", "xoa.regrid", "xoa.meta",
    "parcels",
):
    _ensure_mock(_mod)

# xr.DataTree (available from xarray >= 2024.10)
if not hasattr(xr, "DataTree"):
    try:
        from xarray.core.datatree import DataTree
        xr.DataTree = DataTree
    except ImportError:
        xr.DataTree = mock.MagicMock()

# Now safe to import armoor modules
from armoor import ArmoorError
from armoor.comp.output import (
    check_output,
    _DRIFTER_OTYPE_REMAP,
    DATA_TYPES,
    OutputProcessor,
)


# ---------------------------------------------------------------------------
# check_output
# ---------------------------------------------------------------------------

class TestCheckOutput:

    def test_non_drifter_passthrough(self):
        outputs = {"o1": {"otype": "timeseries"}}
        result = check_output("comp_sst", outputs)
        assert result["o1"]["otype"] == "timeseries"

    def test_drifter_remaps_timeseries(self):
        outputs = {"o1": {"otype": "timeseries"}}
        result = check_output("comp_drifter", outputs)
        assert result["o1"]["otype"] == "timeseries_drifter"

    def test_drifter_remaps_maps_current(self):
        outputs = {"o1": {"otype": "maps_current"}}
        result = check_output("comp_drifter", outputs)
        assert result["o1"]["otype"] == "maps_current_drifter"

    def test_drifter_remaps_maps_trajectory(self):
        outputs = {"o1": {"otype": "maps_trajectory"}}
        result = check_output("comp_drifter", outputs)
        assert result["o1"]["otype"] == "maps_trajectory_drifter"

    def test_invalid_otype_raises(self):
        outputs = {"o1": {"otype": "nonexistent_type"}}
        with pytest.raises(ArmoorError, match="Not implemented"):
            check_output("comp_sst", outputs)

    def test_multiple_outputs(self):
        outputs = {
            "o1": {"otype": "timeseries"},
            "o2": {"otype": "maps_current"},
        }
        result = check_output("comp_drifter", outputs)
        assert result["o1"]["otype"] == "timeseries_drifter"
        assert result["o2"]["otype"] == "maps_current_drifter"


# ---------------------------------------------------------------------------
# _parse_configuration
# ---------------------------------------------------------------------------

class TestParseConfiguration:

    def setup_method(self):
        self.processor = OutputProcessor(func_comp="comp_sst")

    def test_single_key_dicts(self):
        ocfg = [
            {"atlantic": {"ncins": {}, "key": "val"}},
            {"monthly": {"otype": "timeseries"}},
        ]
        metazone, output, mparams, oparams = self.processor._parse_configuration(ocfg)
        assert metazone == "atlantic"
        assert output == "timeseries"
        assert mparams["key"] == "val"
        assert oparams["otype"] == "timeseries"

    def test_multi_key_dict_returns_first_key(self):
        """next(iter(...)) returns the first key, not a concatenation."""
        ocfg = [
            {"atlantic": {"ncins": {}}, "pacific": {"ncins": {}}},
            {"monthly": {"otype": "timeseries"}},
        ]
        metazone, output, mparams, _ = self.processor._parse_configuration(ocfg)
        assert metazone in ("atlantic", "pacific")
        assert "atlantic" not in metazone or metazone == "atlantic"


# ---------------------------------------------------------------------------
# _validate_output_compatibility
# ---------------------------------------------------------------------------

class TestValidateOutputCompatibility:

    def setup_method(self):
        self.processor = OutputProcessor(func_comp="comp_sst")

    def test_valid_output(self):
        oparams = {"otype": "timeseries"}
        mparams = {"ncins": {}}
        assert self.processor._validate_output_compatibility(
            oparams, mparams, "atlantic", "timeseries"
        )

    def test_invalid_output_type(self):
        oparams = {"otype": "nonexistent"}
        mparams = {}
        assert not self.processor._validate_output_compatibility(
            oparams, mparams, "atlantic", "nonexistent"
        )

    def test_missing_required_params(self):
        """comp_argo maps requires trange_seq and vlevel/vrange."""
        processor = OutputProcessor(func_comp="comp_argo")
        oparams = {"otype": "maps"}
        mparams = {"ncins": {}}
        assert not processor._validate_output_compatibility(
            oparams, mparams, "atlantic", "maps"
        )

    def test_has_required_params(self):
        processor = OutputProcessor(func_comp="comp_argo")
        oparams = {"otype": "maps"}
        mparams = {"ncins": {}, "trange_seq": True, "vlevel": True}
        assert processor._validate_output_compatibility(
            oparams, mparams, "atlantic", "maps"
        )

    def test_conflicting_params(self):
        """comp_argo mvprofiles has mparams_con: vertical: [vlevel]."""
        processor = OutputProcessor(func_comp="comp_argo")
        oparams = {"otype": "mvprofiles"}
        mparams = {"ncins": {}, "trange_seq": True, "vlevel": True}
        assert not processor._validate_output_compatibility(
            oparams, mparams, "atlantic", "mvprofiles"
        )

    def test_drifter_otype_remap_in_validation(self):
        processor = OutputProcessor(func_comp="comp_drifter")
        oparams = {"otype": "timeseries"}
        mparams = {"ncins": {}}
        assert processor._validate_output_compatibility(
            oparams, mparams, "atlantic", "timeseries"
        )


# ---------------------------------------------------------------------------
# _concatenate_time_datasets
# ---------------------------------------------------------------------------

class TestConcatenateTimeDatasets:

    def setup_method(self):
        self.processor = OutputProcessor(func_comp="comp_sst")

    def _make_ds(self, times, values):
        return xr.Dataset(
            {"temp": (["time"], values)},
            coords={"time": times},
        )

    def test_single_time_concat(self):
        ds1 = self._make_ds([0], [1.0])
        ds2 = self._make_ds([1], [2.0])
        result = self.processor._concatenate_time_datasets([ds1, ds2])
        assert result.sizes["time"] == 2
        np.testing.assert_array_equal(result["temp"].values, [1.0, 2.0])

    def test_multi_time_flattening(self):
        ds1 = self._make_ds([0, 1], [1.0, 2.0])
        ds2 = self._make_ds([2, 3], [3.0, 4.0])
        result = self.processor._concatenate_time_datasets([ds1, ds2])
        assert result.sizes["time"] == 4
        np.testing.assert_array_equal(result["temp"].values, [1.0, 2.0, 3.0, 4.0])

    def test_mixed_time_sizes(self):
        """When any dataset has time > 1, all should be split."""
        ds1 = self._make_ds([0, 1], [1.0, 2.0])
        ds2 = self._make_ds([2], [3.0])
        result = self.processor._concatenate_time_datasets([ds1, ds2])
        assert result.sizes["time"] == 3

    def test_vrange_preserved_from_any_dataset(self):
        ds1 = self._make_ds([0], [1.0])
        ds2 = self._make_ds([1], [2.0])
        ds2.attrs["vrange"] = [0, 10]
        result = self.processor._concatenate_time_datasets([ds1, ds2])
        assert "vrange" in result.attrs
        assert result.attrs["vrange"] == [[0, 10]]

    def test_vrange_not_set_when_absent(self):
        ds1 = self._make_ds([0], [1.0])
        ds2 = self._make_ds([1], [2.0])
        result = self.processor._concatenate_time_datasets([ds1, ds2])
        assert "vrange" not in result.attrs

    def test_period_datasets_merged_not_dropped(self):
        """Whole-window (period) datasets, e.g. comp_alti's mke, survive."""
        ds1 = self._make_ds([0, 1], [1.0, 2.0])
        ds_period = xr.Dataset({"mke": (["period"], [5.0])}, coords={"period": [0]})
        result = self.processor._concatenate_time_datasets([ds1, ds_period])
        assert result.sizes["time"] == 2
        assert result.sizes["period"] == 1
        np.testing.assert_array_equal(result["mke"].values, [5.0])

    def test_period_datasets_only(self):
        ds_period = xr.Dataset({"mke": (["period"], [5.0])}, coords={"period": [0]})
        result = self.processor._concatenate_time_datasets([ds_period])
        assert "time" not in result.dims
        np.testing.assert_array_equal(result["mke"].values, [5.0])


# ---------------------------------------------------------------------------
# _concatenate_datasets (None filtering)
# ---------------------------------------------------------------------------

class TestConcatenateDatasets:

    def setup_method(self):
        self.processor = OutputProcessor(func_comp="comp_sst")

    def test_all_none_returns_empty(self):
        result = self.processor._concatenate_datasets([None, None], ["time"])
        assert result == {}

    def test_empty_list_returns_empty(self):
        result = self.processor._concatenate_datasets([], ["time"])
        assert result == {}

    def _make_tree(self, vrange_label=None, trange_label=None):
        ds = xr.Dataset({"temp": (["time"], [1.0])}, coords={"time": [0]})
        if vrange_label is not None:
            ds.attrs["vrange"] = vrange_label
        if trange_label is not None:
            ds.attrs["trange"] = trange_label
        return xr.DataTree.from_dict({"mean": ds})

    def test_multiple_vertical_bins_without_fusion_strategy_raises(self):
        """Regression test for the "Multi-dataset concatenation not
        implemented" error seen in CI (comp_argo, meta2, "maps" output):
        a metazone whose vertical range config has several bins (e.g.
        vrange=[(10,1000), (10,100), (100,500), (500,1000)]) produces one
        dataset per bin. Output types without a "concat" key (like "maps")
        have no fusion strategy for more than one dataset, so this must
        raise rather than silently pick one or drop data.
        """
        trees = [
            self._make_tree(vrange_label=label)
            for label in ("10-1000", "10-100", "100-500", "500-1000")
        ]

        with pytest.raises(ArmoorError, match="Multi-dataset concatenation not implemented"):
            self.processor._concatenate_datasets(trees, concat_dim=None, output="maps")

    def test_multiple_time_bins_without_fusion_strategy_raises(self):
        """Same gap, but triggered by trange_seq (temporal splitting) alone
        instead of vrange/vlevel -- _process_single_product applies
        _apply_time_ranges *then* _apply_vertical_ranges on each result, so
        a multi-bin trange_seq is an equally valid, independent way to end
        up with more than one dataset for a non-fusing output type.
        """
        trees = [
            self._make_tree(trange_label=label)
            for label in ("2026-01-01_2026-01-02", "2026-01-02_2026-01-03")
        ]

        with pytest.raises(ArmoorError, match="Multi-dataset concatenation not implemented"):
            self.processor._concatenate_datasets(trees, concat_dim=None, output="maps")

    def test_uvprofiles_keeps_multiple_datasets_unfused(self):
        """uvprofiles/udiagts are explicitly allowed to keep several
        per-bin datasets unfused (saved as separate numbered files)
        instead of hitting the "not implemented" error above."""
        trees = [self._make_tree(label) for label in ("10-1000", "10-100")]

        result = self.processor._concatenate_datasets(trees, concat_dim=None, output="uvprofiles")

        assert isinstance(result["mean"], list)
        assert len(result["mean"]) == 2

    def test_time_concat_dim_fuses_multiple_datasets(self):
        """When the output declares concat=["time"], multiple datasets are
        fused via _concatenate_time_datasets instead of raising."""
        trees = [self._make_tree(label) for label in ("10-1000", "10-100")]

        result = self.processor._concatenate_datasets(trees, concat_dim=["time"], output="timeseries")

        assert isinstance(result["mean"], xr.Dataset)


# ---------------------------------------------------------------------------
# _process_coloc_pair -- member-resolved vs member-averaged "prod/data"
# ---------------------------------------------------------------------------

class TestProcessColocPairMemberData:
    """For otype=timeseries, "prod/data" must hold the member mean, not the
    raw (time, z, member) product -- keeping the latter for every file of
    every product is what OOMs large comp_argo timeseries runs."""

    def setup_method(self):
        self.processor = OutputProcessor(func_comp="comp_argo")
        time = pd.date_range("2024-01-01", periods=3, freq="D")
        z = [0.0, 10.0]
        member = np.arange(4)
        rng = np.random.default_rng(0)
        self.ds_prod = xr.Dataset(
            {"ptemp": (("time", "z", "member"), rng.random((3, 2, 4)))},
            coords={
                "time": time,
                "z": z,
                "member": member,
                "lon": ("member", [0.0, 0.1, 0.2, 0.3]),
                "lat": ("member", [45.0, 45.1, 45.2, 45.3]),
            },
        )
        self.ds_ref = xr.Dataset(
            {"ptemp": (("time", "z"), rng.random((3, 2)))},
            coords={"time": time, "z": z, "lon": 0.15, "lat": 45.15},
        )
        self.mparams = {"vrange": {"bins_min": [0.0], "bins_max": [2000.0]}}

    def _run(self, output):
        computed = {dt: [] for dt in DATA_TYPES}
        self.processor._process_coloc_pair(
            self.ds_prod, self.ds_ref, self.mparams, {"stat": ["z"]}, output, computed
        )
        return computed["prod"][0]["data"].to_dataset()

    def test_timeseries_stores_member_mean(self):
        ds_data = self._run("timeseries")
        assert "member" not in ds_data.dims
        np.testing.assert_allclose(
            ds_data["ptemp"].values, self.ds_prod["ptemp"].mean("member").values
        )

    def test_other_otypes_keep_members(self):
        ds_data = self._run("diagdisp_glob")
        assert ds_data.sizes["member"] == 4


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

def test_data_types_tuple():
    assert DATA_TYPES == ("prod", "ref", "comp")


def test_drifter_otype_remap_keys():
    assert set(_DRIFTER_OTYPE_REMAP.keys()) == {
        "timeseries", "maps_current", "maps_trajectory"
    }


class TestSharedOutputs:
    """Otypes holding the same data are computed and written once."""

    OTYPES = ("maps", "mvprofiles", "mdiagts", "diagdisp_sel", "uvprofiles", "udiagts")

    @staticmethod
    def _write_pair(path):
        import numpy as np

        paths = []
        for kind in ("prod", "ref"):
            dims = ("time", "z") + (("member",) if kind == "prod" else ())
            shape = (2, 3) + ((4,) if kind == "prod" else ())
            hdims = ("time",) + dims[2:]
            hshape = (2,) + shape[2:]
            rng = np.random.default_rng(0)
            ds = xr.Dataset(
                {v: (dims, rng.random(shape)) for v in ("ptemp", "sal")},
                coords={
                    "time": np.array(["2024-01-02", "2024-01-03"], "datetime64[ns]"),
                    "lon": (hdims, rng.random(hshape)),
                    "lat": (hdims, rng.random(hshape)),
                    "depth": (dims, rng.random(shape)),
                },
                attrs={"data_name": kind},
            )
            name = f"{kind}_2024-01-01T00:00:00_2024-01-16T00:00:00_0.0-10.0.zarr"
            ds.to_zarr(path / name)
            paths.append(str(path / name))
        return paths

    def _run(self, files, otypes):
        from armoor.comp.output import main_output

        mparams = {"trange_seq": {"tfreq": "15D"}, "vrange": {}}
        return main_output(
            {"MZ": {"ARGO": {"mod": files}}},
            {"MZ": mparams},
            {o: {"otype": o} for o in otypes},
            "comp_argo",
        )

    def test_same_as_unshared(self, tmp_path, monkeypatch):
        """Linked outputs hold what would be computed for each otype alone."""
        from pathlib import Path

        files = self._write_pair(tmp_path)
        shared_dir, alone_dir = tmp_path / "shared", tmp_path / "alone"
        shared_dir.mkdir()
        alone_dir.mkdir()
        monkeypatch.chdir(shared_dir)
        shared = self._run(files, self.OTYPES)
        assert set(shared) == set(self.OTYPES)
        linked = {o for o in shared if Path(shared[o]["MZ"][0]).is_symlink()}
        assert linked == {"mdiagts", "diagdisp_sel", "udiagts"}
        monkeypatch.chdir(alone_dir)
        for otype in self.OTYPES:
            alone = self._run(files, [otype])
            assert alone[otype] == shared[otype]
            for path in alone[otype]["MZ"]:
                expected = xr.open_datatree(alone_dir / path, engine="zarr").load()
                result = xr.open_datatree(shared_dir / path, engine="zarr").load()
                assert result.identical(expected)

    def test_rerun_with_other_otypes(self, tmp_path, monkeypatch):
        """Links and stores of a previous run are replaced."""
        from pathlib import Path

        files = self._write_pair(tmp_path)
        monkeypatch.chdir(tmp_path)
        first = self._run(files, ["mvprofiles", "mdiagts"])
        second = self._run(files, ["mdiagts", "mvprofiles"])
        assert Path(first["mvprofiles"]["MZ"][0]).is_symlink()
        path = Path(second["mdiagts"]["MZ"][0])
        assert path.is_dir() and not path.is_symlink()
        assert xr.open_datatree(Path(second["mvprofiles"]["MZ"][0]), engine="zarr").children


def test_hpc_stage_workers():
    """The workers follow the CPUs of the job, unless set by the user."""
    from armoor.cli.hpc import _build_stage_cmd, _ncpus

    assert _ncpus({"ncpus_comp": 8, "ncpus": 2}, "comp") == 8
    assert _ncpus({"ncpus": 2}, "comp") == 2
    args = ("MZ", True, None, None, None)
    cmd = _build_stage_cmd(["armoor-comp-argo", "MZ"], *args, n_workers=8)
    assert cmd[cmd.index("--dask-nworkers") + 1] == "8"
    cmd = _build_stage_cmd(["armoor-comp-argo", "MZ", "--dask-nworkers", "2"], *args, n_workers=8)
    assert cmd.count("--dask-nworkers") == 1 and "8" not in cmd
    assert "--dask-nworkers" not in _build_stage_cmd(["armoor-comp-argo", "MZ"], *args)


class TestConcurrentWrites:
    """The output stores are written several at once, within a global cap."""

    PERIODS = tuple(
        f"2024-01-{d:02d}T00:00:00_2024-01-{d + 1:02d}T00:00:00" for d in range(1, 13)
    )

    @staticmethod
    def _write_pairs(path, periods):
        rng = np.random.default_rng(0)
        files = []
        for period in periods:
            for kind in ("prod", "ref"):
                dims = ("time", "z") + (("member",) if kind == "prod" else ())
                shape = (1, 3) + ((4,) if kind == "prod" else ())
                hdims = ("time",) + dims[2:]
                ds = xr.Dataset(
                    {v: (dims, rng.random(shape)) for v in ("ptemp", "sal")},
                    coords={
                        "time": np.array([period[:10]], "datetime64[ns]"),
                        "lon": (hdims, rng.random((1,) + shape[2:])),
                        "lat": (hdims, rng.random((1,) + shape[2:])),
                        "depth": (dims, rng.random(shape)),
                    },
                    attrs={"data_name": kind},
                )
                name = path / f"{kind}_{period}_0.0-10.0.zarr"
                ds.to_zarr(name)
                files.append(str(name))
        return files

    def test_cap_and_order(self, tmp_path, monkeypatch):
        import threading
        import time

        from armoor.comp import output as comp_output

        files = self._write_pairs(tmp_path, self.PERIODS)
        monkeypatch.chdir(tmp_path)
        mparams = {"MZ": {"trange_seq": {"tfreq": "1D"}, "vrange": {}}}
        otypes = {"diagdisp_sel": {"otype": "diagdisp_sel"}}

        def run():
            return comp_output.main_output(
                {"MZ": {"ARGO": {"mod": files}}}, mparams, otypes, "comp_argo"
            )

        expected = run()["diagdisp_sel"]["MZ"]
        assert len(expected) == len(self.PERIODS)

        write = comp_output.write_datatree_to_zarr
        lock = threading.Lock()
        state = {"running": 0, "max": 0}

        def slow_write(dt, path):
            with lock:
                state["running"] += 1
                state["max"] = max(state["max"], state["running"])
            time.sleep(0.05)
            write(dt, path)
            with lock:
                state["running"] -= 1

        monkeypatch.setattr(comp_output, "write_datatree_to_zarr", slow_write)
        monkeypatch.setattr(comp_output, "_WRITE_SLOTS", threading.BoundedSemaphore(3))
        assert run()["diagdisp_sel"]["MZ"] == expected
        assert state["max"] == 3
