"""Unit tests for OutputProcessor's data-type awareness in armoor.data.output.

Before this, _validate_output_compatibility/_process_output_type always read
the flat, ocean-model-shaped OUTPUTS_PARAMS dict regardless of the actual
dataset's type. For an eddies dataset (DataEddies.outputs_params == {}),
this would have incorrectly treated e.g. otype="maps" as valid (ocean
model's own entry), letting eddy data reach stats code that assumes
ptemp/depth. Now it must be skipped (logged forbidden, no crash).
"""
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
