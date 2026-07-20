"""Unit tests for armoor.cli.interp — focus on the coarsen option."""

import sys
from unittest.mock import MagicMock, patch

import numpy as np
import pandas as pd
import pytest
import xarray as xr

import armoor  # noqa: F401 — registers ds.interp accessor
from armoor.cli.interp import (
    InterpError,
    get_parser_interp_horizontal,
    main_interp_horizontal,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _gridded_ds(ny=6, nx=8, nt=2):
    """Small (time, y, x) dataset usable as a mock model output."""
    lon2d, lat2d = np.meshgrid(np.linspace(0.0, 7.0, nx), np.linspace(40.0, 45.0, ny))
    return xr.Dataset(
        {"temp": (["time", "y", "x"], np.ones((nt, ny, nx), dtype=np.float32))},
        coords={
            "time": pd.date_range("2023-01-01", periods=nt),
            "lon": (["y", "x"], lon2d.astype(np.float32)),
            "lat": (["y", "x"], lat2d.astype(np.float32)),
        },
    )


def _argv(*extra):
    """Build a minimal sys.argv for armoor-interp-horizontal."""
    return ["armoor-interp-horizontal", "input.zarr", "output.zarr", "--ifmt", "armoor", *extra]


def _mock_dask():
    """Return (mock_cluster, mock_client) that work as context managers."""
    cluster = MagicMock()
    client = MagicMock()
    return cluster, client


# ---------------------------------------------------------------------------
# Parser tests — no I/O, no mocks
# ---------------------------------------------------------------------------

class TestParserCoarsen:
    """Verify --coarsen-factor and companions are correctly declared."""

    def test_coarsen_factor_is_parsed_as_int(self):
        args = get_parser_interp_horizontal().parse_args(
            ["fin", "fout", "--coarsen-factor", "4"]
        )
        assert args.coarsen_factor == 4

    def test_coarsen_factor_absent_by_default(self):
        args = get_parser_interp_horizontal().parse_args(["fin", "fout", "--cloud", "(45.,2.)"])
        assert args.coarsen_factor is None

    def test_coarsen_boundary_default_is_trim(self):
        args = get_parser_interp_horizontal().parse_args(
            ["fin", "fout", "--coarsen-factor", "4"]
        )
        assert args.coarsen_boundary == "trim"

    def test_coarsen_boundary_pad_accepted(self):
        args = get_parser_interp_horizontal().parse_args(
            ["fin", "fout", "--coarsen-factor", "4", "--coarsen-boundary", "pad"]
        )
        assert args.coarsen_boundary == "pad"

    def test_coarsen_method_default_is_mean(self):
        args = get_parser_interp_horizontal().parse_args(
            ["fin", "fout", "--coarsen-factor", "4"]
        )
        assert args.coarsen_method == "mean"

    @pytest.mark.parametrize("method", ["mean", "median", "min", "max"])
    def test_coarsen_method_all_values_accepted(self, method):
        args = get_parser_interp_horizontal().parse_args(
            ["fin", "fout", "--coarsen-factor", "4", "--coarsen-method", method]
        )
        assert args.coarsen_method == method

    def test_coarsen_boundary_invalid_rejected(self):
        with pytest.raises(SystemExit):
            get_parser_interp_horizontal().parse_args(
                ["fin", "fout", "--coarsen-factor", "4", "--coarsen-boundary", "drop"]
            )


# ---------------------------------------------------------------------------
# Dispatch tests — mock I/O, verify coarsen is called correctly
# ---------------------------------------------------------------------------

class TestDispatchCoarsen:
    """Verify that main_interp_horizontal dispatches --coarsen-factor correctly."""

    def setup_method(self):
        self.ds = _gridded_ds()
        self.mock_cluster, self.mock_client = _mock_dask()

    def _run(self, *extra_argv):
        with patch("sys.argv", _argv(*extra_argv)), \
             patch("dask.distributed.LocalCluster", return_value=self.mock_cluster), \
             patch("dask.distributed.Client", return_value=self.mock_client), \
             patch("armoor.data.open_decode.open_decode", return_value=self.ds), \
             patch("armoor.data.open_decode.register_cf"), \
             patch("armoor.cli.interp.save_output") as mock_save:
            main_interp_horizontal()
        return mock_save

    def test_output_dims_coarsened_by_factor(self):
        mock_save = self._run("--coarsen-factor", "2")
        saved_ds = mock_save.call_args[0][0]
        assert saved_ds.sizes["x"] == 4   # 8 / 2
        assert saved_ds.sizes["y"] == 3   # 6 / 2

    def test_time_dim_unchanged(self):
        mock_save = self._run("--coarsen-factor", "2")
        saved_ds = mock_save.call_args[0][0]
        assert saved_ds.sizes["time"] == self.ds.sizes["time"]

    def test_coarsen_boundary_pad_forwarded(self):
        mock_save = self._run("--coarsen-factor", "3", "--coarsen-boundary", "pad")
        saved_ds = mock_save.call_args[0][0]
        # y=6 divisible by 3 → 2; x=8, pad → ceil(8/3)=3
        assert saved_ds.sizes["y"] == 2
        assert saved_ds.sizes["x"] == 3

    def test_coarsen_boundary_trim_forwarded(self):
        mock_save = self._run("--coarsen-factor", "3", "--coarsen-boundary", "trim")
        saved_ds = mock_save.call_args[0][0]
        # x=8, trim → floor(8/3)=2
        assert saved_ds.sizes["x"] == 2

    def test_coarsen_method_median_forwarded(self):
        """Median on a uniform field returns the same value as mean."""
        mock_save = self._run("--coarsen-factor", "2", "--coarsen-method", "median")
        saved_ds = mock_save.call_args[0][0]
        np.testing.assert_allclose(saved_ds["temp"].values, 1.0)

    def test_save_output_called_once(self):
        mock_save = self._run("--coarsen-factor", "2")
        mock_save.assert_called_once()


# ---------------------------------------------------------------------------
# Mutual-exclusion tests
# ---------------------------------------------------------------------------

class TestCoarsenMutualExclusion:
    """--coarsen-factor must not be combinable with other interpolation options."""

    def setup_method(self):
        self.ds = _gridded_ds()
        self.mock_cluster, self.mock_client = _mock_dask()

    def _run_raises(self, *extra_argv):
        with patch("sys.argv", _argv(*extra_argv)), \
             patch("dask.distributed.LocalCluster", return_value=self.mock_cluster), \
             patch("dask.distributed.Client", return_value=self.mock_client), \
             patch("armoor.data.open_decode.open_decode", return_value=self.ds), \
             patch("armoor.data.open_decode.register_cf"), \
             patch("armoor.cli.interp.save_output"):
            with pytest.raises(InterpError):
                main_interp_horizontal()

    def test_exclusive_with_cloud(self):
        self._run_raises("--coarsen-factor", "2", "--cloud", "(45.,2.)")

    def test_exclusive_with_section(self):
        self._run_raises("--coarsen-factor", "2", "--section", "45.", "2.", "46.", "3.", "10.")

    def test_exclusive_with_lon_grid(self):
        # Use non-negative values: argparse mistakes leading '-' for a flag.
        self._run_raises(
            "--coarsen-factor", "2",
            "--lon-grid", "0.", "10.", "0.1",
            "--lat-grid", "40.", "50.", "0.1",
        )

    def test_exclusive_with_ncgrid(self):
        self._run_raises("--coarsen-factor", "2", "--ncgrid", "grid.nc")

    def test_no_option_raises(self):
        """Calling with no interpolation option must raise InterpError."""
        with patch("sys.argv", _argv()), \
             patch("dask.distributed.LocalCluster", return_value=self.mock_cluster), \
             patch("dask.distributed.Client", return_value=self.mock_client), \
             patch("armoor.data.open_decode.open_decode", return_value=self.ds), \
             patch("armoor.cli.interp.save_output"):
            with pytest.raises(InterpError):
                main_interp_horizontal()
