"""Unit tests for armoor.plot."""

from armoor.plot import format_trange, get_output_vminmax


class TestFormatTrange:

    def test_returns_title_and_suffix(self):
        title, suffix = format_trange("[2020-01-01T00:00:00_2020-01-31T00:00:00[")
        assert title == "[2020-01-01T00:00-2020-01-31T00:00["
        assert suffix == "2020_01_01T00:00_2020_01_31T00:00"

    def test_suffix_has_no_brackets(self):
        _, suffix = format_trange("[2020-01-01T00:00:00_2020-01-02T00:00:00[")
        assert "[" not in suffix and "]" not in suffix


class TestGetOutputVminmax:
    """Regression tests for the CI crash: cfg_outputs is keyed by the
    user-chosen config *section* name, not by otype -- output (from
    ncins/zarr_outputs, always an otype string) must be matched against
    each section's `otype` field, not used to index cfg_outputs directly.

    Real-world trigger (comp_argo.cfg, GitLab CI):
        [outputs]
            [[global_dispersion]]
            otype = diagdisp_glob
    `main_plot` looks up otype "diagdisp_glob"; the old
    `cfg_outputs[output]` raised KeyError since "diagdisp_glob" is not a
    top-level key of cfg_outputs -- "global_dispersion" is.
    """

    def test_section_name_differs_from_otype(self):
        cfg_outputs = {
            "fmt": "png",
            "global_dispersion": {"otype": "diagdisp_glob", "vminmax": {"ptemp": (5.0, 30.0)}},
            "dispersion": {"otype": "diagdisp_sel"},
        }
        assert get_output_vminmax(cfg_outputs, "diagdisp_glob") == {"ptemp": (5.0, 30.0)}

    def test_section_without_vminmax_returns_none(self):
        cfg_outputs = {
            "dispersion": {"otype": "diagdisp_sel"},
        }
        assert get_output_vminmax(cfg_outputs, "diagdisp_sel") is None

    def test_otype_not_found_returns_none_instead_of_raising(self):
        cfg_outputs = {
            "dispersion": {"otype": "diagdisp_sel"},
        }
        assert get_output_vminmax(cfg_outputs, "maps") is None

    def test_fmt_key_with_string_value_is_skipped(self):
        """cfg_outputs also holds a plain 'fmt' string alongside section
        dicts -- must not crash trying to call .get('otype') on it."""
        cfg_outputs = {"fmt": "png,zarr"}
        assert get_output_vminmax(cfg_outputs, "maps") is None

    def test_no_cfg_outputs_returns_none(self):
        assert get_output_vminmax(None, "maps") is None

    def test_section_name_matching_otype_still_works(self):
        """The coincidental case (section name == otype) must keep working."""
        cfg_outputs = {"maps": {"otype": "maps", "vminmax": {"sal": (0.0, 40.0)}}}
        assert get_output_vminmax(cfg_outputs, "maps") == {"sal": (0.0, 40.0)}
