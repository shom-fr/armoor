"""Unit tests for section (broken-line vertical section) horizontal
interpolation, covering the same three places as vfreq (see
test_data_interp.py):

- armoor/data/interp.py: HorizontalInterpolation.section takes a dict
  ({"dx": ..., <section_name>: {"coords": ...}, ...}) with one or more
  named sections sharing the same "dx", like VerticalInterpolation
  vlevel/vfreq but returning a dict of {section_name: xr.Dataset}.
- armoor/data/output.py: validate_interpolation / get_interpolation_params
  must treat section as a horizontal-interpolation candidate, mutually
  exclusive with cloud.
- armoor/cli/metazones.ini: section is a [[section]] subsection with a
  shared "dx" and one or more named [[[__many__]]] subsections (coords),
  like vlevel/vrange/vfreq/bathy.
"""

import numpy as np
import pandas as pd
import pytest
import xarray as xr

from armoor.__init__ import ArmoorError
from armoor.data import INTERP_PARAMS_USER
from armoor.data.interp import HorizontalInterpolation, process_horizontal_interpolation
from armoor.data.output import get_interpolation_params, validate_interpolation


def _gridded_ds():
    lon = np.linspace(-10, 0, 10)
    lat = np.linspace(40, 50, 10)
    lon_grid, lat_grid = np.meshgrid(lon, lat)
    return xr.Dataset(
        {"temp": (["time", "z", "y", "x"], np.random.rand(2, 3, 10, 10))},
        coords={
            "time": pd.date_range("2023-01-01", periods=2),
            "lat": (["y", "x"], lat_grid),
            "lon": (["y", "x"], lon_grid),
            "z": np.arange(3),
        },
    )


class TestHorizontalInterpolationSection:
    """Test suite for HorizontalInterpolation.section."""

    def setup_method(self):
        self.ds = _gridded_ds()

    def test_dict_args_accepted(self):
        interp = HorizontalInterpolation(self.ds)
        coords = [(45.0, -8.0), (46.0, -5.0), (47.0, -2.0)]
        result = interp.section({"dx": 10, "transect1": {"coords": coords}})
        assert set(result) == {"transect1"}
        assert "npts" in result["transect1"].dims
        assert "distance" in result["transect1"].coords

    def test_multiple_named_sections_share_dx(self):
        interp = HorizontalInterpolation(self.ds)
        result = interp.section({
            "dx": 10,
            "transect1": {"coords": [(45.0, -8.0), (46.0, -5.0)]},
            "transect2": {"coords": [(44.0, -9.0), (47.0, -2.0)]},
            })
        assert set(result) == {"transect1", "transect2"}
        for ds_section in result.values():
            assert "npts" in ds_section.dims
            assert "distance" in ds_section.coords

    def test_process_horizontal_interpolation_dispatches_section(self):
        coords = [(45.0, -8.0), (46.0, -2.0)]
        result = process_horizontal_interpolation(
            self.ds, ("section", {"dx": 10, "transect1": {"coords": coords}})
        )
        assert set(result) == {"transect1"}
        assert "npts" in result["transect1"].dims
        assert "distance" in result["transect1"].coords


class TestValidateInterpolationSection:
    """Test suite for validate_interpolation with section."""

    def test_cloud_and_section_both_set_raises(self):
        metazones = {
            "zone1": {
                "cloud": [(45.0, -8.0)],
                "section": {
                    "dx": 10.0,
                    "transect1": {"coords": [(45.0, -8.0), (46.0, -2.0)]},
                    },
            }
        }
        with pytest.raises(ArmoorError):
            validate_interpolation(metazones)

    def test_section_alone_is_valid(self):
        section = {
            "dx": 10.0,
            "transect1": {"coords": [(45.0, -8.0), (46.0, -2.0)]},
            }
        metazones = {"zone1": {"section": section}}
        result = validate_interpolation(metazones)
        assert result["zone1"] == {"section": section}

    def test_neither_cloud_nor_section_set(self):
        metazones = {"zone1": {}}
        result = validate_interpolation(metazones)
        assert result["zone1"] is None


class TestGetInterpolationParamsSection:
    """Test suite for get_interpolation_params with section."""

    def test_section_registered_as_horizontal_candidate(self):
        assert "section" in INTERP_PARAMS_USER["horizontal"]

    def test_section_extracted_as_horizontal_param(self):
        section = {
            "dx": 10.0,
            "transect1": {"coords": [(45.0, -8.0), (46.0, -2.0)]},
            }
        metazones = {"zone1": {"section": section}}
        result = get_interpolation_params(metazones)
        assert result["zone1"]["horizontal"] == ("section", section)

    def test_cloud_still_works_alone(self):
        metazones = {"zone1": {"cloud": [(45.0, -8.0)]}}
        result = get_interpolation_params(metazones)
        assert result["zone1"]["horizontal"] == ("cloud", [(45.0, -8.0)])


class TestMetazonesIniSectionSchema:
    """Test suite for the metazones.ini section subsection schema."""

    def test_section_parsed_as_subsection(self, tmp_path):
        from xoa.cfgm import ConfigManager, register_validation_functions

        from armoor.misc import parse_coords
        from armoor.cli import METAZONES_INI

        register_validation_functions(coordinates=parse_coords)

        cfgfile = tmp_path / "metazones.cfg"
        cfgfile.write_text(
            '[zone1]\nname = "zone1"\n'
            "[[section]]\n"
            "dx = 5.0\n"
            "    [[[transect1]]]\n"
            "    coords = (45.0,-10.0),(46.0,-8.0),(44.0,-5.0)\n"
        )

        metazones = ConfigManager(METAZONES_INI).load(str(cfgfile))

        assert metazones["zone1"]["section"]["dx"] == 5.0
        assert dict(metazones["zone1"]["section"]["transect1"]) == {
            "coords": [(45.0, -10.0), (46.0, -8.0), (44.0, -5.0)],
        }

    def test_multiple_named_sections_parsed(self, tmp_path):
        from xoa.cfgm import ConfigManager, register_validation_functions

        from armoor.misc import parse_coords
        from armoor.cli import METAZONES_INI

        register_validation_functions(coordinates=parse_coords)

        cfgfile = tmp_path / "metazones.cfg"
        cfgfile.write_text(
            '[zone1]\nname = "zone1"\n'
            "[[section]]\n"
            "dx = 5.0\n"
            "    [[[transect1]]]\n"
            "    coords = (45.0,-10.0),(46.0,-8.0)\n"
            "    [[[transect2]]]\n"
            "    coords = (44.0,-9.0),(47.0,-2.0)\n"
        )

        metazones = ConfigManager(METAZONES_INI).load(str(cfgfile))

        section = metazones["zone1"]["section"]
        assert section["dx"] == 5.0
        assert dict(section["transect1"]) == {"coords": [(45.0, -10.0), (46.0, -8.0)]}
        assert dict(section["transect2"]) == {"coords": [(44.0, -9.0), (47.0, -2.0)]}


class TestCheckMetazonesInSection:
    """Test suite for check_metazones_in's handling of a configured vs.
    unconfigured [[section]] subsection (armoor/cli/main.py:
    _SUBSECTION_PRIMARY_KEY drops subsections configobj.validate()
    auto-materializes with every key defaulted to None -- "dx" is the
    telltale for "section" since it's the only key living directly on
    [[section]] itself, "coords" having moved into the named
    [[[__many__]]] subsections)."""

    def _load(self, tmp_path, cfg_text):
        from xoa.cfgm import ConfigManager, register_validation_functions

        from armoor.misc import parse_coords
        from armoor.cli import METAZONES_INI

        register_validation_functions(coordinates=parse_coords)
        cfgfile = tmp_path / "metazones.cfg"
        cfgfile.write_text(cfg_text)
        return ConfigManager(METAZONES_INI).load(str(cfgfile))

    def test_configured_section_survives(self, tmp_path):
        from armoor.cli.main import check_metazones_in

        metazones = self._load(
            tmp_path,
            '[zone1]\nname = "zone1"\n'
            "[[section]]\n"
            "dx = 5.0\n"
            "    [[[transect1]]]\n"
            "    coords = (45.0,-10.0),(46.0,-8.0)\n"
            "    [[[transect2]]]\n"
            "    coords = (44.0,-9.0),(47.0,-2.0)\n"
        )

        result = check_metazones_in(["zone1"], metazones)

        section = result["zone1"]["section"]
        assert section["dx"] == 5.0
        assert dict(section["transect1"]) == {"coords": [(45.0, -10.0), (46.0, -8.0)]}
        assert dict(section["transect2"]) == {"coords": [(44.0, -9.0), (47.0, -2.0)]}

    def test_unconfigured_section_dropped(self, tmp_path):
        from armoor.cli.main import check_metazones_in

        metazones = self._load(tmp_path, '[zone1]\nname = "zone1"\n')

        result = check_metazones_in(["zone1"], metazones)

        assert "section" not in result["zone1"]
