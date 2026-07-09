"""Unit tests for armoor.comp.plot -- focus on the vminmax color-scale
override wired for GitLab work item #260 (armoor-comp side of "Add
vminmax option into armoor-comp and armoor-data").
"""
from unittest.mock import MagicMock, patch

import numpy as np
import pandas as pd
import pytest
import xarray as xr

from armoor.comp.plot import PlotComp, _plot_task, main_plot


class _FakePool:
    """Runs starmap in-process instead of spawning real subprocesses, so
    tests can mock _plot_task without hitting multiprocessing's pickling
    (a mocked/MagicMock function isn't picklable)."""

    def __init__(self, *a, **kw):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def starmap(self, func, iterable):
        return [func(*args) for args in iterable]


def _fake_get_context(method):
    ctx = MagicMock()
    ctx.Pool.side_effect = _FakePool
    return ctx


def _make_map_datatree(tmp_path, var="ptemp", prod_name="model1", ny=3, nx=4):
    """Minimal datatree matching what `PlotComp.maps` expects: one product
    node with ref/data, prod/data and comp/diff children, on a structured
    (y, x) lon/lat grid."""
    lon2d, lat2d = np.meshgrid(np.linspace(0.0, 3.0, nx), np.linspace(40.0, 42.0, ny))
    coords = {
        "lon": (["y", "x"], lon2d.astype("float32")),
        "lat": (["y", "x"], lat2d.astype("float32")),
        "time": pd.date_range("2020-01-01", periods=1),
    }

    def _ds(value, data_name):
        ds = xr.Dataset(
            {var: (["time", "y", "x"], np.full((1, ny, nx), value, dtype="float32"))},
            coords=coords,
        )
        ds.attrs["data_name"] = data_name
        return ds

    dt = xr.DataTree.from_dict({
        f"{prod_name}/ref/data": _ds(10.0, "ref1"),
        f"{prod_name}/prod/data": _ds(12.0, "prod1"),
        f"{prod_name}/comp/diff": _ds(2.0, "diff"),
    })
    path = tmp_path / "out.zarr"
    dt.to_zarr(path, mode="w")
    return str(path)


class TestPlotCompConstruction:

    def test_vminmax_stored_on_instance(self, tmp_path):
        nc = _make_map_datatree(tmp_path)
        plotcomp = PlotComp(nc, "comp_sst", "mz1", vminmax={"ptemp": (5.0, 30.0)})
        try:
            assert plotcomp.vminmax == {"ptemp": (5.0, 30.0)}
        finally:
            plotcomp.clean()

    def test_vminmax_defaults_to_none(self, tmp_path):
        nc = _make_map_datatree(tmp_path)
        plotcomp = PlotComp(nc, "comp_sst", "mz1")
        try:
            assert plotcomp.vminmax is None
        finally:
            plotcomp.clean()


class TestMapsVminmaxOverride:
    """maps() must use a configured vminmax entry for a variable's color
    scale instead of computing it from the data, but only for variables
    it actually covers -- other variables keep the dynamic computation."""

    def setup_method(self):
        self.mock_axes = [MagicMock(), MagicMock(), MagicMock()]
        self.mock_fig = MagicMock()

    def _run_maps(self, tmp_path, vminmax):
        nc = _make_map_datatree(tmp_path)
        plotcomp = PlotComp(nc, "comp_sst", "mz1", vminmax=vminmax)
        try:
            with patch("armoor.comp.plot.create_subplots", return_value=(self.mock_fig, self.mock_axes)), \
                 patch.object(plotcomp, "save_figure"):
                plotcomp.maps()
        finally:
            plotcomp.clean()
        return self.mock_axes

    def test_configured_variable_uses_vminmax(self, tmp_path):
        axes = self._run_maps(tmp_path, vminmax={"ptemp": (5.0, 30.0)})
        _, kwargs = axes[0].pcolormesh.call_args
        assert (kwargs["vmin"], kwargs["vmax"]) == (5.0, 30.0)

    def test_unconfigured_variable_keeps_dynamic_computation(self, tmp_path):
        axes = self._run_maps(tmp_path, vminmax={"sal": (0.0, 1.0)})
        _, kwargs = axes[0].pcolormesh.call_args
        assert (kwargs["vmin"], kwargs["vmax"]) != (0.0, 1.0)

    def test_no_vminmax_keeps_dynamic_computation(self, tmp_path):
        axes = self._run_maps(tmp_path, vminmax=None)
        _, kwargs = axes[0].pcolormesh.call_args
        assert kwargs["vmin"] is not None and kwargs["vmax"] is not None


class TestPlotTaskThreadsVminmax:

    def test_plot_task_forwards_vminmax_to_plotcomp(self, tmp_path):
        nc = _make_map_datatree(tmp_path)
        with patch("armoor.comp.plot.PlotComp") as mock_cls:
            mock_instance = mock_cls.return_value
            mock_instance.saved_files = []
            _plot_task(nc, "comp_sst", "mz1", "maps", vminmax={"ptemp": (1.0, 2.0)})
        mock_cls.assert_called_once_with(nc, "comp_sst", "mz1", vminmax={"ptemp": (1.0, 2.0)})


class TestMainPlotExtractsVminmaxFromCfgOutputs:

    def test_vminmax_extracted_per_output_and_forwarded(self, tmp_path):
        nc = _make_map_datatree(tmp_path)
        ncins = {"maps": {"mz1": [nc]}}
        cfg_outputs = {"maps": {"otype": "maps", "vminmax": {"ptemp": (5.0, 30.0)}}}

        with patch("multiprocessing.get_context", side_effect=_fake_get_context), \
             patch("armoor.comp.plot._plot_task", return_value=["out.png"]) as mock_task:
            png_paths = main_plot(ncins, ["mz1"], "comp_sst", cfg_outputs=cfg_outputs)

        mock_task.assert_called_once_with(nc, "comp_sst", "mz1", "maps", {"ptemp": (5.0, 30.0)})
        assert png_paths == ["out.png"]

    def test_no_cfg_outputs_passes_none_vminmax(self, tmp_path):
        nc = _make_map_datatree(tmp_path)
        ncins = {"maps": {"mz1": [nc]}}

        with patch("multiprocessing.get_context", side_effect=_fake_get_context), \
             patch("armoor.comp.plot._plot_task", return_value=["out.png"]) as mock_task:
            main_plot(ncins, ["mz1"], "comp_sst")

        mock_task.assert_called_once_with(nc, "comp_sst", "mz1", "maps", None)
