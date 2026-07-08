"""Unit tests for armoor.base.io."""

from armoor.base.io import output_suffix


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
