"""Unit tests for the data_type plumbing added to armoor.data.load.

Covers the two places flagged as sharp edges when threading `data_type`
through the pipeline: process_single_combination's full attrs overwrite,
and load_datasets' early validate_load_params gate.
"""
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
import xarray as xr

from armoor import ArmoorError
from armoor.data.load import StagedDataset, load_datasets, process_single_combination


@pytest.fixture
def sample_ds():
    ds = xr.Dataset(
        {
            "ptemp": (("time", "z"), np.random.rand(3, 4).astype("float32")),
            "sal": (("time", "z"), np.random.rand(3, 4).astype("float32")),
            "depth": (("time", "z"), np.tile(np.arange(4) * 1.0, (3, 1))),
        },
        coords={
            "time": pd.date_range("2020-01-01", periods=3, freq="D"),
            "lon": 10.0,
            "lat": 40.0,
        },
    )
    ds.attrs["data_name"] = "testdata"
    ds.attrs["data_ref"] = "False"
    ds.attrs["data_type"] = "ocean_model"
    return ds


class TestProcessSingleCombinationDataType:

    def test_data_type_survives_attrs_overwrite(self, sample_ds):
        out = process_single_combination(sample_ds, "mz_test", {})
        assert out is not None
        assert out.attrs["data_type"] == "ocean_model"

    def test_missing_data_type_stays_none(self, sample_ds):
        del sample_ds.attrs["data_type"]
        out = process_single_combination(sample_ds, "mz_test", {})
        assert out is not None
        assert out.attrs["data_type"] is None


class TestLoadDatasetsValidateLoadParamsGate:

    def test_eddies_forbidden_param_raises_before_touching_disk(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        data_cfg = {
            "eddy1": {
                "name": "eddy1",
                # Nonexistent path -- must never be opened, since the
                # forbidden-param check must fire first.
                "path": str(tmp_path / "does_not_exist.nc"),
                "fmt": "eddy_pet",
            }
        }
        metazones = {"mz1": {"vlevel": [10]}}
        with pytest.raises(ArmoorError, match="mz1"):
            load_datasets(data_cfg, metazones, "data")

    def test_ocean_model_no_forbidden_params_check(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        # hycom has no forbidden_params -- validate_load_params must be a
        # no-op regardless of metazone content, so this must fail later
        # (on the nonexistent path via open_decode), not on validation.
        data_cfg = {
            "model1": {
                "name": "model1",
                "path": str(tmp_path / "does_not_exist.nc"),
                "fmt": "hycom",
            }
        }
        metazones = {"mz1": {"vlevel": [10]}}
        # open_decode failures for a missing file are caught internally and
        # logged as a skip (see load_datasets' per-dataset try/except), so
        # this must complete without raising and return no outputs.
        result = load_datasets(data_cfg, metazones, "data")
        assert result == []


class TestStagedDataset:
    """Unit tests for StagedDataset -- the lightweight pipeline-context
    object that rides a zarr path across stages/processes without carrying
    the actual xr.Dataset in memory (see REFACTOR_PLAN_STAGED_DATASET.md).
    """

    def test_behaves_like_a_plain_path(self):
        sd = StagedDataset("p/q.zarr", metazone="med", comp_func="comp_sst")
        assert isinstance(sd, str)
        assert sd == "p/q.zarr"
        assert json.dumps([sd]) == '["p/q.zarr"]'

    def test_attributes_readable(self):
        sd = StagedDataset("p/q.zarr", metazone="med", comp_func="comp_sst", stage="coloc")
        assert sd.metazone == "med"
        assert sd.comp_func == "comp_sst"
        assert sd.stage == "coloc"

    def test_defaults_are_none(self):
        sd = StagedDataset("p/q.zarr")
        assert sd.metazone is None
        assert sd.comp_func is None
        assert sd.stage is None
        assert sd.fmt is None
        assert sd.platform is None

    def test_operations_returning_a_plain_str_drop_attributes(self):
        """Documents the boundary the HPC JSON round-trip fix depends on:
        any operation returning a *new* str loses the extra attributes.
        """
        sd = StagedDataset("p/q.zarr", metazone="med", comp_func="comp_sst")
        reloaded = json.loads(json.dumps(sd))
        assert not hasattr(reloaded, "metazone")
        assert not hasattr(str(sd), "metazone")

    def test_output_dir_matches_pre_refactor_conventions(self):
        """Locks in byte-for-byte parity with the f-string conventions
        previously duplicated in coloc.py/output.py/plot.py -- these are
        on-disk path contracts and must not silently drift.
        """
        sd = StagedDataset("", metazone="med", comp_func="comp_sst")

        assert sd.output_dir("coloc", ref_name="argo", prod_name="hycom") == \
            Path("comp_sst/coloc/med/argo/hycom")
        assert sd.output_dir("output", ref_name="argo", output="maps") == \
            Path("comp_sst/output/med/argo/maps")
        assert sd.output_dir("plot", ref_name="argo") == \
            Path("comp_sst/plot/med/argo")

    def test_output_dir_omits_missing_parts(self):
        sd = StagedDataset("", metazone="med", comp_func=None)
        assert sd.output_dir("coloc", ref_name="argo") == Path("coloc/med/argo")

    def test_hpc_json_round_trip_rewrap(self):
        """Simulates the Wave 0 -> Wave 1 HPC boundary: a {metazone: [paths]}
        dict is dumped to JSON, reloaded (paths come back as plain strings),
        then re-wrapped as StagedDataset -- the fix applied at
        cli/main.py's input_zarrs handling.
        """
        mz_name = "med"
        original = {mz_name: ["a/ref.zarr", "a/prod.zarr"]}
        dumped = json.dumps(original)
        paths = json.loads(dumped)

        rewrapped = [
            StagedDataset(p, metazone=mz_name, comp_func="comp_sst", stage="load")
            for p in paths.get(mz_name, [])
        ]

        assert all(isinstance(p, StagedDataset) for p in rewrapped)
        assert [str(p) for p in rewrapped] == original[mz_name]
        assert all(p.metazone == mz_name and p.comp_func == "comp_sst" for p in rewrapped)

    def test_with_range_carries_forward_metazone_and_comp_func(self):
        sd = StagedDataset("old/path.zarr", metazone="med", comp_func="comp_sst")
        ds = xr.Dataset({"temp": ("time", [1.0])}, coords={"time": [0]})

        new_sd = sd.with_range(ds)

        assert new_sd.metazone == "med"
        assert new_sd.comp_func == "comp_sst"
        assert str(new_sd) == "old/path.zarr"

    def test_with_range_reads_vlevel_vrange_trange_time_from_dataset(self):
        sd = StagedDataset("path.zarr", metazone="med", comp_func="comp_sst")
        ds = xr.Dataset({"temp": ("time", [1.0])}, coords={"time": [0]})
        ds.attrs = {
            "vlevel": "10.0",
            "vrange": "0-50",
            "trange": "[2020-01-01T00:00:00_2020-01-31T00:00:00[",
            "time": "2020-01-01T00:00:00",
        }

        new_sd = sd.with_range(ds)

        assert new_sd.vlevel == "10.0"
        assert new_sd.vrange == "0-50"
        assert new_sd.trange == "[2020-01-01T00:00:00_2020-01-31T00:00:00["
        assert new_sd.time == "2020-01-01T00:00:00"

    def test_with_range_overrides_path_and_stage(self):
        sd = StagedDataset("old.zarr", metazone="med", comp_func="comp_sst", stage="load")
        ds = xr.Dataset({"temp": ("time", [1.0])}, coords={"time": [0]})

        new_sd = sd.with_range(ds, path="new.zarr", stage="coloc")

        assert str(new_sd) == "new.zarr"
        assert new_sd.stage == "coloc"

    def test_with_range_returns_none_fields_when_dataset_has_no_range_attrs(self):
        sd = StagedDataset("path.zarr", metazone="med", comp_func="comp_sst")
        ds = xr.Dataset({"temp": ("time", [1.0])}, coords={"time": [0]})

        new_sd = sd.with_range(ds)

        assert new_sd.vlevel is None
        assert new_sd.vrange is None
        assert new_sd.trange is None
        assert new_sd.time is None
