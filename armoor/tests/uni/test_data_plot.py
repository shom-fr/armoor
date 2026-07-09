"""Unit tests for the PlotOceanModel/PlotEddies split in armoor.data.plot.

get_plotter dispatches on the data_type attr carried by the zarr datatree
(see armoor.data.load), reusing the same MethodRegistry dispatch idiom as
armoor.comp.plot.PlotComp. PlotEddies has no methods yet, so calling any
plot method on it must raise a clear error rather than crash or silently
do nothing -- this is the "for free" behavior the hierarchy is meant to
provide until eddy plotting is actually designed.
"""
import numpy as np
import pytest
import xarray as xr

# base/dispatch.py's call() raises this specific ArmoorError family --
# see armoor/base/dispatch.py's own import, and the dual-class landmine
# documented in REFACTOR_PLAN_BASE_EXTRACTION.md.
from unittest.mock import MagicMock, patch

from armoor.__init__ import ArmoorError
from armoor.data.plot import PlotEddies, PlotOceanModel, get_plotter, _plot_task, main_plot


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


def _write_datatree(tmp_path, data_type, name="ds"):
    ds = xr.Dataset({"var1": (("obs",), np.random.rand(5))})
    ds.attrs["data_name"] = name
    if data_type is not None:
        ds.attrs["data_type"] = data_type
    dt = xr.DataTree.from_dict({"data": ds})
    path = tmp_path / f"{name}.zarr"
    dt.to_zarr(path, mode="w")
    return str(path)


class TestGetPlotter:

    def test_ocean_model_data_type(self, tmp_path):
        nc = _write_datatree(tmp_path, "ocean_model")
        plotter = get_plotter(nc, "mz1")
        try:
            assert isinstance(plotter, PlotOceanModel)
        finally:
            plotter.clean()

    def test_eddies_data_type(self, tmp_path):
        nc = _write_datatree(tmp_path, "eddies")
        plotter = get_plotter(nc, "mz1")
        try:
            assert isinstance(plotter, PlotEddies)
        finally:
            plotter.clean()

    def test_missing_data_type_defaults_to_ocean_model(self, tmp_path):
        nc = _write_datatree(tmp_path, None)
        plotter = get_plotter(nc, "mz1")
        try:
            assert isinstance(plotter, PlotOceanModel)
        finally:
            plotter.clean()

    def test_unknown_data_type_defaults_to_ocean_model(self, tmp_path):
        nc = _write_datatree(tmp_path, "some_future_type")
        plotter = get_plotter(nc, "mz1")
        try:
            assert isinstance(plotter, PlotOceanModel)
        finally:
            plotter.clean()


class TestPlotEddiesNotImplemented:

    def test_calling_any_method_raises(self, tmp_path):
        nc = _write_datatree(tmp_path, "eddies")
        plotter = get_plotter(nc, "mz1")
        try:
            with pytest.raises(ArmoorError, match="mdiagts"):
                plotter.call("mdiagts")
        finally:
            plotter.clean()


class TestPlotOceanModelRegistersMethods:

    def test_known_methods_registered(self, tmp_path):
        nc = _write_datatree(tmp_path, "ocean_model")
        plotter = get_plotter(nc, "mz1")
        try:
            for method_name in ("mdiagts", "udiagts", "mvprofiles", "uvprofiles", "timeseries", "maps"):
                assert method_name in plotter.methods
        finally:
            plotter.clean()


class TestSaveFigureTracksSavedFiles:
    """save_figure must append to self.saved_files so _plot_task can report
    generated paths back, mirroring armoor.comp.plot.PlotComp."""

    def test_saved_files_starts_empty(self, tmp_path):
        nc = _write_datatree(tmp_path, "ocean_model")
        plotter = get_plotter(nc, "mz1")
        try:
            assert plotter.saved_files == []
        finally:
            plotter.clean()

    def test_save_figure_appends_resolved_path(self, tmp_path):
        import matplotlib.pyplot as plt

        nc = _write_datatree(tmp_path, "ocean_model")
        plotter = get_plotter(nc, "mz1")
        try:
            fig = plt.figure()
            out = tmp_path / "sub" / "fig.png"
            plotter.save_figure(fig, out)
            assert plotter.saved_files == [str(out.resolve())]
        finally:
            plotter.clean()


class TestPlotTaskForwardsVminmax:
    """_plot_task must be module-level (spawn-pickling) and forward
    vminmax to get_plotter, mirroring armoor.comp.plot._plot_task."""

    def test_plot_task_forwards_vminmax_to_get_plotter(self, tmp_path):
        nc = _write_datatree(tmp_path, "ocean_model")
        with patch("armoor.data.plot.get_plotter") as mock_get_plotter:
            _plot_task(nc, "mz1", "maps", vminmax={"ptemp": (1.0, 2.0)})
        mock_get_plotter.assert_called_once_with(nc, "mz1", {"ptemp": (1.0, 2.0)})


class TestMainPlotExtractsVminmaxFromCfgOutputs:
    """main_plot flattens {output: {metazone: [paths]}} into a list of
    task tuples and calls _plot_task sequentially for each, mirroring
    armoor.comp.plot.main_plot."""

    def test_vminmax_extracted_per_output_and_forwarded(self, tmp_path):
        nc = _write_datatree(tmp_path, "ocean_model")
        ncins = {"maps": {"mz1": [nc]}}
        cfg_outputs = {"maps": {"otype": "maps", "vminmax": {"ptemp": (5.0, 30.0)}}}

        with patch("multiprocessing.get_context", side_effect=_fake_get_context), \
             patch("armoor.data.plot._plot_task", return_value=["out.png"]) as mock_task:
            png_paths = main_plot(ncins, ["mz1"], cfg_outputs=cfg_outputs)

        mock_task.assert_called_once_with(nc, "mz1", "maps", {"ptemp": (5.0, 30.0)})
        assert png_paths == ["out.png"]

    def test_no_cfg_outputs_passes_none_vminmax(self, tmp_path):
        nc = _write_datatree(tmp_path, "ocean_model")
        ncins = {"maps": {"mz1": [nc]}}

        with patch("multiprocessing.get_context", side_effect=_fake_get_context), \
             patch("armoor.data.plot._plot_task", return_value=["out.png"]) as mock_task:
            main_plot(ncins, ["mz1"])

        mock_task.assert_called_once_with(nc, "mz1", "maps", None)

    def test_metazone_not_requested_is_skipped(self, tmp_path):
        nc = _write_datatree(tmp_path, "ocean_model")
        ncins = {"maps": {"mz1": [nc]}}

        with patch("armoor.data.plot._plot_task") as mock_task:
            png_paths = main_plot(ncins, ["other_mz"])

        mock_task.assert_not_called()
        assert png_paths == []

    def test_num_workers_capped_by_task_count(self, tmp_path):
        """kw_dask requests more workers than there are tasks -- num_workers
        should be capped, matching armoor.comp.plot.main_plot."""
        nc = _write_datatree(tmp_path, "ocean_model")
        ncins = {"maps": {"mz1": [nc]}}

        with patch("multiprocessing.get_context", side_effect=_fake_get_context), \
             patch("armoor.data.plot._plot_task", return_value=[]):
            png_paths = main_plot(ncins, ["mz1"], kw_dask=(8, False, None, None, None))

        assert png_paths == []
