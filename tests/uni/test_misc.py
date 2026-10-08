"""Unit tests for armoor.misc.str2bool.

Regression coverage for the `--dask-processes True/False` argparse
footgun: `type=bool` treats any non-empty string (including "False") as
truthy, silently ignoring the value actually typed on the command line.
"""
import pytest

from armoor.misc import str2bool


class TestStr2Bool:

    @pytest.mark.parametrize("value", ["True", "true", "1", "yes", "TRUE"])
    def test_truthy_strings(self, value):
        assert str2bool(value) is True

    @pytest.mark.parametrize("value", ["False", "false", "0", "no", "FALSE"])
    def test_falsy_strings(self, value):
        assert str2bool(value) is False

    def test_plain_bool_passthrough(self):
        assert str2bool(True) is True
        assert str2bool(False) is False

    def test_invalid_string_raises_value_error(self):
        """Must raise ValueError (not ArmoorError) so argparse's own
        "invalid X value" CLI error message fires instead of a raw
        traceback."""
        with pytest.raises(ValueError, match="garbage"):
            str2bool("garbage")
