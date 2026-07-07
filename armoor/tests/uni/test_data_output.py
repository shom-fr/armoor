"""Unit tests for OutputProcessor's data-type awareness in armoor.data.output.

Before this, _validate_output_compatibility/_process_output_type always read
the flat, ocean-model-shaped OUTPUTS_PARAMS dict regardless of the actual
dataset's type. For an eddies dataset (DataEddies.outputs_params == {}),
this would have incorrectly treated e.g. otype="maps" as valid (ocean
model's own entry), letting eddy data reach stats code that assumes
ptemp/depth. Now it must be skipped (logged forbidden, no crash).
"""
import numpy as np
import xarray as xr

from armoor.data.datatype import DataEddies, DataOceanModel
from armoor.data.output import OutputProcessor


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


class TestProcessDatasetsMparamsNotCorrupted:
    """Regression test for the mparams=None crash.

    _prepare_interpolation_params used to mutate the caller's metazones dict
    in place (via validate_metazone_params) to signal "no interpolation
    needed" for a metazone missing both vlevel and vfreq. _process_metazone
    then re-read that *same*, now-corrupted metazones[metazone] as mparams
    for unrelated time/vertical range processing, crashing with
    "TypeError: argument of type 'NoneType' is not iterable" the moment a
    metazone had no interpolation params configured at all -- an entirely
    ordinary case (see REFACTOR_PLAN_DATA_DATATYPE.md follow-up).
    """

    def test_metazone_without_interpolation_params_does_not_crash(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        ds = xr.Dataset(
            {"ptemp": (("time",), np.random.rand(3).astype("float32"))},
            coords={"time": np.arange(3), "lon": 10.0, "lat": 40.0},
        )
        ds.attrs["data_name"] = "model1"
        ds.attrs["data_ref"] = "False"
        ds.attrs["data_type"] = "ocean_model"
        nc = tmp_path / "model1.nc"
        ds.to_netcdf(nc)

        # No vlevel/vfreq at all -- exactly the case that used to null out
        # this same metazone dict before _apply_range_processing read it.
        metazones = {"mz1": {}}
        processor = OutputProcessor()
        result = processor.process_datasets([str(nc)], metazones, {})

        assert result == {}
        # The caller's own metazones dict must come out exactly as it went in.
        assert metazones == {"mz1": {}}
