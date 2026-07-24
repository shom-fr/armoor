"""Unit tests for armoor.data.datatype.

Covers the fmt -> DataType registry lookup (exact match + default fallback)
and the validate_load_params compatibility check, since load.py/output.py/
plot.py have no other automated safety net for this code path.
"""
import pytest

from armoor import ArmoorError
from armoor.data.datatype import (
    DataBobyclim, DataEddies, DataMeteo, DataOceanModel, DataSstSatellite,
    DataWoa18, get_data_type, get_data_type_by_name,
)


class TestGetDataType:

    def test_known_ocean_model_fmts(self):
        for fmt in ("hycom", "croco", "croco_xios", "cmems_model"):
            assert isinstance(get_data_type(fmt), DataOceanModel)
            assert get_data_type(fmt).is_climatology is False

    def test_known_eddies_fmts(self):
        for fmt in ("eddy_pet", "eddy_sacso", "eddy_shoot"):
            assert isinstance(get_data_type(fmt), DataEddies)

    def test_unknown_fmt_defaults_to_ocean_model(self):
        assert isinstance(get_data_type("some_future_model_fmt"), DataOceanModel)

    def test_climatology_fmts_are_ocean_model_shaped_but_flagged(self):
        woa18 = get_data_type("woa18")
        bobyclim = get_data_type("bobyclim")
        assert isinstance(woa18, DataWoa18)
        assert isinstance(bobyclim, DataBobyclim)
        # Subclass DataOceanModel: same outputs_params/plotter_cls, just flagged.
        assert isinstance(woa18, DataOceanModel)
        assert isinstance(bobyclim, DataOceanModel)
        assert woa18.is_climatology is True
        assert bobyclim.is_climatology is True
        assert woa18.outputs_params == get_data_type("hycom").outputs_params

    def test_sst_satellite_fmts_are_ocean_model_shaped(self):
        for fmt in ("cmems_sst_l4", "cmems_sst_l3", "cersat_sst_l3"):
            data_type = get_data_type(fmt)
            assert isinstance(data_type, DataSstSatellite)
            assert isinstance(data_type, DataOceanModel)
            assert data_type.is_climatology is False
            assert data_type.outputs_params == get_data_type("hycom").outputs_params

    def test_meteo_fmt_is_ocean_model_shaped_but_otype_restricted(self):
        """meteo is ocean-model-shaped (same DataOceanModel plumbing) but
        deliberately restricted to timeseries/maps/mapseries -- the
        vertical-profile/theta-saln otypes make no sense for a
        surface-only, non-oceanographic source."""
        data_type = get_data_type("arpege_insta")
        assert isinstance(data_type, DataMeteo)
        assert isinstance(data_type, DataOceanModel)
        assert data_type.is_climatology is False
        assert set(data_type.outputs_params.keys()) == {"timeseries", "maps", "mapseries"}
        hycom_params = get_data_type("hycom").outputs_params
        for otype in ("timeseries", "maps", "mapseries"):
            assert data_type.outputs_params[otype] == hycom_params[otype]

    def test_mapseries_outputs_params(self):
        """mapseries has no "stat" key (no mean/std aggregation) and is
        shared identically by ocean_model and climatology data types --
        the climatology-specific exclusion lives in output.py's
        _validate_output_compatibility, not in this static table."""
        for fmt in ("hycom", "woa18", "bobyclim"):
            oparams = get_data_type(fmt).outputs_params["mapseries"]
            assert "stat" not in oparams
            assert oparams["sort"] == ["time", "z"]
            assert "concat" not in oparams

    def test_get_data_type_by_name_resolves_climatology_flag(self):
        assert get_data_type_by_name("woa18").is_climatology is True
        assert get_data_type_by_name("bobyclim").is_climatology is True
        assert get_data_type_by_name("ocean_model").is_climatology is False
        assert get_data_type_by_name(None).is_climatology is False


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

    def test_sst_satellite_ignores_vlevel_and_vrange(self):
        """vlevel/vrange configured on a metazone shared with a
        depth-resolved source must not be rejected for SST -- it's
        silently ignored instead (see OutputProcessor's "z" dimension
        guards in _apply_interpolations/_apply_range_processing)."""
        data_type = get_data_type("cmems_sst_l4")
        metazones = {"mz1": {"vlevel": [10]}, "mz2": {"vrange": {"vname": "depth"}}}
        data_type.validate_load_params("cmems_sst_l4", metazones)  # no raise

    def test_sst_satellite_allows_horizontal_and_time_params(self):
        data_type = get_data_type("cersat_sst_l3")
        metazones = {"mz1": {"tfreq": "1D", "cloud": [(45.0, -10.0)]}}
        data_type.validate_load_params("cersat_sst_l3", metazones)  # no raise

    def test_meteo_ignores_vlevel_and_vfreq(self):
        """Same "ignore, don't reject" rule as SST: vlevel/vfreq configured
        for the sake of a depth-resolved sibling (e.g. the ocean model
        this data forces) must not be rejected for meteo."""
        data_type = get_data_type("arpege_insta")
        metazones = {"mz1": {"vlevel": [10]}, "mz2": {"vfreq": 25.0}}
        data_type.validate_load_params("arpege_insta", metazones)  # no raise

    def test_meteo_allows_horizontal_and_time_params(self):
        data_type = get_data_type("arpege_insta")
        metazones = {"mz1": {"tfreq": "1D", "cloud": [(45.0, -10.0)]}}
        data_type.validate_load_params("arpege_insta", metazones)  # no raise
