"""Unit tests for armoor.base.io."""

from armoor.base.io import extract_suffix_from_filename, output_suffix, sort_ncs_by_suffix
from armoor.data.load import StagedDataset


class TestOutputSuffix:

    def test_no_attrs_gives_empty_suffix(self):
        assert output_suffix({}) == ""

    def test_time_alone(self):
        assert output_suffix({"time": "2020-01-01"}) == "_2020-01-01"

    def test_trange_alone(self):
        assert output_suffix({"trange": "2020-01-01_to_2020-01-02"}) == "_2020-01-01_to_2020-01-02"

    def test_time_takes_priority_over_trange(self):
        attrs = {"time": "2020-01-01", "trange": "2020-01-01_to_2020-01-02"}
        assert output_suffix(attrs) == "_2020-01-01"

    def test_vlevel_takes_priority_over_vrange(self):
        attrs = {"vlevel": "10.0", "vrange": "0-50"}
        assert output_suffix(attrs) == "_10.0"

    def test_time_and_vlevel_combine(self):
        attrs = {"time": "2020-01-01", "vlevel": "10.0"}
        assert output_suffix(attrs) == "_2020-01-01_10.0"

    def test_trange_and_vrange_combine(self):
        attrs = {"trange": "2020-01-01_to_2020-01-02", "vrange": "0-50"}
        assert output_suffix(attrs) == "_2020-01-01_to_2020-01-02_0-50"


class TestSortNcsBySuffix:
    """sort_ncs_by_suffix should prefer a StagedDataset's own time/vlevel-like
    attrs over regex-parsing the filename, when they're present."""

    def test_staged_dataset_with_time_and_vlevel_sorted_without_filename_parsing(self):
        nc = StagedDataset("some/opaque/path.zarr", time="2020-01-01T00:00:00", vlevel="10.0")

        result = sort_ncs_by_suffix([nc])

        assert "2020-01-01T00:00:00_10.0" in result
        assert result["2020-01-01T00:00:00_10.0"] == [nc]

    def test_staged_dataset_trange_is_bracket_stripped(self):
        nc = StagedDataset("some/opaque/path.zarr", trange="[2020-01-01T00:00:00_2020-01-31T00:00:00[")

        result = sort_ncs_by_suffix([nc], sort_dim=["time"])

        assert "2020-01-01T00:00:00_2020-01-31T00:00:00" in result

    def test_staged_dataset_without_range_attrs_falls_back_to_filename(self):
        """No time/trange/vlevel/vrange set -> same result as a plain string
        (i.e. the filename gets regex-parsed, same as before this change)."""
        filename = "ref_2020-01-01T00:00:00_10.0.zarr"
        expected = sort_ncs_by_suffix([filename])

        nc = StagedDataset(filename)
        result = sort_ncs_by_suffix([nc])

        assert list(result.keys()) == list(expected.keys())

    def test_plain_string_uses_filename_parsing(self):
        filename = "ref_2020-01-01T00:00:00_10.0.zarr"
        res = extract_suffix_from_filename(filename)

        result = sort_ncs_by_suffix([filename])

        expected_key = f"{res['time']}_{res['z']}" if res.get("time") and res.get("z") else "None"
        assert expected_key in result
