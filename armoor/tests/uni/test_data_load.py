"""Unit tests for the data_type plumbing added to armoor.data.load.

Covers the two places flagged as sharp edges when threading `data_type`
through the pipeline: process_single_combination's full attrs overwrite,
and load_datasets' early validate_load_params gate.
"""
import numpy as np
import pandas as pd
import pytest
import xarray as xr

from armoor import ArmoorError
from armoor.data.load import load_datasets, process_single_combination


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
