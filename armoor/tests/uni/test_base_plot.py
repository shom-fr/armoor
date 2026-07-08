"""Unit tests for armoor.base.plot."""

from armoor.base.plot import format_trange


class TestFormatTrange:

    def test_returns_title_and_suffix(self):
        title, suffix = format_trange("[2020-01-01T00:00:00_2020-01-31T00:00:00[")
        assert title == "[2020-01-01T00:00-2020-01-31T00:00["
        assert suffix == "2020_01_01T00:00_2020_01_31T00:00"

    def test_suffix_has_no_brackets(self):
        _, suffix = format_trange("[2020-01-01T00:00:00_2020-01-02T00:00:00[")
        assert "[" not in suffix and "]" not in suffix
