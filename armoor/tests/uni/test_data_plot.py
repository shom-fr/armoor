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
from armoor.__init__ import ArmoorError
from armoor.data.plot import PlotEddies, PlotOceanModel, get_plotter


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
