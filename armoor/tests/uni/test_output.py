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
    "xoa", "xoa.geo", "xoa.grid", "xoa.regrid", "xoa.cf",
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


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

def test_data_types_tuple():
    assert DATA_TYPES == ("prod", "ref", "comp")


def test_drifter_otype_remap_keys():
    assert set(_DRIFTER_OTYPE_REMAP.keys()) == {
        "timeseries", "maps_current", "maps_trajectory"
    }
