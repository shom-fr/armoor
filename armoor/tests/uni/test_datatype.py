"""Unit tests for armoor.data.datatype.

Covers the fmt -> DataType registry lookup (exact match + default fallback)
and the validate_load_params compatibility check, since load.py/output.py/
plot.py have no other automated safety net for this code path.
"""
import pytest

from armoor import ArmoorError
from armoor.data.datatype import DataEddies, DataOceanModel, get_data_type


class TestGetDataType:

    def test_known_ocean_model_fmts(self):
        for fmt in ("hycom", "croco", "croco_xios", "cmems_model"):
            assert isinstance(get_data_type(fmt), DataOceanModel)

    def test_known_eddies_fmts(self):
        for fmt in ("eddy_pet", "eddy_sacso", "eddy_shoot"):
            assert isinstance(get_data_type(fmt), DataEddies)

    def test_unknown_fmt_defaults_to_ocean_model(self):
        assert isinstance(get_data_type("some_future_model_fmt"), DataOceanModel)


class TestValidateLoadParams:

    def test_ocean_model_never_raises(self):
        data_type = get_data_type("hycom")
        metazones = {"mz1": {"tfreq": "1D", "vlevel": [10]}}
        data_type.validate_load_params("hycom", metazones)  # no raise

    def test_eddies_raises_on_forbidden_param(self):
        data_type = get_data_type("eddy_pet")
        metazones = {"mz1": {"vlevel": [10]}}
        with pytest.raises(ArmoorError, match="mz1"):
            data_type.validate_load_params("eddy_pet", metazones)

    def test_eddies_allows_compatible_params(self):
        data_type = get_data_type("eddy_sacso")
        metazones = {"mz1": {"tbound": ["2020-01-01", "2020-01-02"]}}
        data_type.validate_load_params("eddy_sacso", metazones)  # no raise
