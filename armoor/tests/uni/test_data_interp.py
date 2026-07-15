"""Unit tests for vfreq (vertical-step interpolation), covering the three
places touched by the "vfreq type fix" commit:

- armoor/data/interp.py: VerticalInterpolation.vfreq must cast its step
  argument to float before calling np.arange.
- armoor/data/output.py: validate_interpolation / get_interpolation_params
  must treat vfreq as a vertical-interpolation candidate on par with vlevel.
- armoor/cli/metazones.ini: vfreq is a named [[vfreq]] subsection (vname/step),
  like vlevel/vrange/bathy/trange_seq.
"""

import numpy as np
import pytest
import xarray as xr

from armoor.__init__ import ArmoorError
from armoor.data import INTERP_PARAMS_USER
from armoor.data.interp import VerticalInterpolation, process_vertical_interpolation
from armoor.data.output import get_interpolation_params, validate_interpolation


def _profile_ds(n=50, zmax=490.0):
    """Single-profile dataset with a 'z' dim and a 'depth' vertical coordinate."""
    depth = np.linspace(0, zmax, n).astype(np.float32)
    return xr.Dataset(
        {"temp": (["z"], np.linspace(20, 5, n).astype(np.float32))},
        coords={"z": np.arange(n), "depth": (["z"], depth)},
    )


class TestVerticalInterpolationVfreq:
    """Test suite for VerticalInterpolation.vfreq."""

    def setup_method(self):
        self.ds = _profile_ds()

    def test_string_step_is_accepted(self):
        """Step may arrive as a string; vfreq must cast it rather than pass
        it straight to np.arange."""
        coloc = VerticalInterpolation(self.ds)
        result = coloc.vfreq({"vname": "depth", "step": "25.0"})
        assert result is not None

    def test_string_step_raised_typeerror_before_fix(self):
        """Without the float() cast, np.arange(..., step="25.0") raises TypeError."""
        with pytest.raises(TypeError):
            np.arange(0.0, 490.0, "25.0")

    def test_regular_step_levels(self):
        coloc = VerticalInterpolation(self.ds)
        result = coloc.vfreq({"vname": "depth", "step": "25.0"})
        expected = np.arange(0.0, 490.0, 25.0)
        np.testing.assert_allclose(result["depth"].values, expected)
        assert result.sizes["z"] == len(expected)

    def test_string_and_float_step_are_equivalent(self):
        result_str = VerticalInterpolation(_profile_ds()).vfreq({"vname": "depth", "step": "25.0"})
        result_float = VerticalInterpolation(_profile_ds()).vfreq({"vname": "depth", "step": 25.0})
        np.testing.assert_allclose(
            result_str["depth"].values, result_float["depth"].values
        )

    def test_no_z_dim_returns_none(self):
        ds_flat = xr.Dataset(
            {"temp": 20.0}, coords={"depth": 0.0}
        )
        coloc = VerticalInterpolation(ds_flat)
        assert coloc.vfreq({"vname": "depth", "step": "25.0"}) is None

    def test_process_vertical_interpolation_dispatches_vfreq(self):
        result = process_vertical_interpolation(
            self.ds, ("vfreq", {"vname": "depth", "step": "25.0"})
        )
        expected = np.arange(0.0, 490.0, 25.0)
        assert result.sizes["z"] == len(expected)


class TestValidateInterpolationVfreq:
    """Test suite for validate_interpolation with vfreq."""

    def test_vlevel_and_vfreq_both_set_raises(self):
        metazones = {
            "zone1": {
                "vlevel": {"vname": "depth", "levels": [0, 10, 20]},
                "vfreq": {"vname": "depth", "step": "25.0"},
            }
        }
        with pytest.raises(ArmoorError):
            validate_interpolation(metazones)

    def test_vfreq_alone_is_valid(self):
        metazones = {"zone1": {"vfreq": {"vname": "depth", "step": "25.0"}}}
        result = validate_interpolation(metazones)
        assert result["zone1"] == {"vfreq": {"vname": "depth", "step": "25.0"}}

    def test_neither_vlevel_nor_vfreq_set(self):
        metazones = {"zone1": {}}
        result = validate_interpolation(metazones)
        assert result["zone1"] is None

    def test_does_not_mutate_the_caller_s_metazones_dict(self):
        # Regression test: validate_interpolation (via validate_metazone_params)
        # used to overwrite metazones[mz_name] with None in place when neither
        # vlevel nor vfreq was set. OutputProcessor re-reads the *original*
        # metazones dict later for unrelated per-metazone processing (time/
        # vertical ranges) -- silently replacing it with None there crashed
        # with "TypeError: argument of type 'NoneType' is not iterable".
        original_mz_param = {"tbound": ["2020-01-01", "2020-01-02"]}
        metazones = {"zone1": original_mz_param}
        result = validate_interpolation(metazones)
        assert result["zone1"] is None
        assert metazones["zone1"] is original_mz_param
        assert metazones["zone1"] == {"tbound": ["2020-01-01", "2020-01-02"]}


class TestGetInterpolationParamsVfreq:
    """Test suite for get_interpolation_params with vfreq."""

    def test_vfreq_registered_as_vertical_candidate(self):
        """Core of the fix: without this, get_interpolation_params silently
        ignores a correctly-configured vfreq."""
        assert "vfreq" in INTERP_PARAMS_USER["vertical"]

    def test_vfreq_extracted_as_vertical_param(self):
        metazones = {"zone1": {"vfreq": {"vname": "depth", "step": "25.0"}}}
        result = get_interpolation_params(metazones)
        assert result["zone1"]["vertical"] == ("vfreq", {"vname": "depth", "step": "25.0"})

    def test_vlevel_still_works_alone(self):
        metazones = {"zone1": {"vlevel": {"vname": "depth", "levels": [0, 10, 20]}}}
        result = get_interpolation_params(metazones)
        assert result["zone1"]["vertical"] == ("vlevel", {"vname": "depth", "levels": [0, 10, 20]})


class TestMetazonesIniVfreqSchema:
    """Test suite for the metazones.ini vfreq subsection schema."""

    def test_vfreq_parsed_as_subsection(self, tmp_path):
        from xoa.cfgm import ConfigManager

        from armoor.cli import METAZONES_INI

        cfgfile = tmp_path / "metazones.cfg"
        cfgfile.write_text(
            '[zone1]\nname = "zone1"\n[[vfreq]]\nvname = depth\nstep = 25.0\n'
        )

        metazones = ConfigManager(METAZONES_INI).load(str(cfgfile))

        assert dict(metazones["zone1"]["vfreq"]) == {"vname": "depth", "step": 25.0}
