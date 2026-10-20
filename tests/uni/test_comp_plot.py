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

    def imap_unordered(self, func, iterable):
        return [func(args) for args in iterable]


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


def _make_taylor_datatree(tmp_path):
    """Two products against noisy copies of the same reference, the second
    product being worse and with twice the variance."""
    rng = np.random.default_rng(0)
    time = pd.date_range("2020-01-01", periods=200)
    ref = np.sin(np.arange(200) / 10.0)
    nodes = {}
    for prod_name, noise, scale in (("model1", 0.1, 1.0), ("model2", 0.8, 2.0)):
        for path, values, data_name in (
            ("ref/data", ref, "obs"),
            ("prod/data", scale * ref + noise * rng.standard_normal(200), prod_name),
        ):
            ds = xr.Dataset({"ptemp": (["time"], values)}, coords={"time": time})
            ds.attrs["data_name"] = data_name
            nodes[f"{prod_name}/{path}"] = ds
    path = tmp_path / "taylor.zarr"
    xr.DataTree.from_dict(nodes).to_zarr(path, mode="w")
    return str(path)


class TestTaylor:
    def test_one_diagram_per_variable_with_a_point_per_product(self, tmp_path):
        nc = _make_taylor_datatree(tmp_path)
        dt = xr.open_datatree(nc)
        expected_stds, expected_corrs = [], []
        for prod_name in ("model1", "model2"):
            prod = dt[f"{prod_name}/prod/data"]["ptemp"].values
            ref = dt[f"{prod_name}/ref/data"]["ptemp"].values
            expected_stds.append(prod.std() / ref.std())
            expected_corrs.append(np.corrcoef(prod, ref)[0, 1])
        dt.close()
        plotcomp = PlotComp(nc, "comp_sst", "mz1")
        try:
            with patch.object(plotcomp, "save_figure") as save_figure, \
                 patch("xoa.core.plot.plot_taylor") as plot_taylor:
                plotcomp.taylor()
        finally:
            plotcomp.clean()
        assert save_figure.call_count == 1
        assert save_figure.call_args[0][1].endswith("/taylor_ptemp.png")
        (stds, corrs), kwargs = plot_taylor.call_args
        assert kwargs["labels"] == ["model1", "model2"]
        assert kwargs["ref_label"] == "obs"
        # Standard deviations normalized by the reference
        np.testing.assert_allclose(stds, expected_stds)
        np.testing.assert_allclose(corrs, expected_corrs)

    def test_renders(self, tmp_path):
        plotcomp = PlotComp(_make_taylor_datatree(tmp_path), "comp_sst", "mz1")
        try:
            with patch.object(plotcomp, "save_figure") as save_figure:
                plotcomp.taylor()
        finally:
            plotcomp.clean()
        fig = save_figure.call_args[0][0]
        legend = fig.axes[0].get_legend()
        assert [t.get_text() for t in legend.get_texts()] == ["obs", "model1", "model2"]


class TestMapsCorr:
    def test_corr_map_uses_a_fixed_symmetric_scale(self, tmp_path):
        """The correlation map is drawn between -1 and 1 next to the standard
        deviations."""
        nc = _make_map_datatree(tmp_path)
        dt = xr.open_datatree(nc)
        data = dt["model1/ref/data"].to_dataset()
        nodes = {
            "model1/ref/data": data,
            "model1/ref/std": data,
            "model1/prod/data": dt["model1/prod/data"].to_dataset(),
            "model1/prod/std": dt["model1/prod/data"].to_dataset(),
            "model1/comp/corr": data * 0 + 0.5,
        }
        dt.close()
        path = tmp_path / "corr.zarr"
        xr.DataTree.from_dict(nodes).to_zarr(path, mode="w")
        axes = [MagicMock(), MagicMock(), MagicMock()]
        plotcomp = PlotComp(str(path), "comp_sst", "mz1")
        try:
            with patch("armoor.comp.plot.create_subplots", return_value=(MagicMock(), axes)), \
                 patch.object(plotcomp, "save_figure") as save_figure:
                plotcomp.maps()
        finally:
            plotcomp.clean()
        _, kwargs = axes[2].pcolormesh.call_args
        assert (kwargs["vmin"], kwargs["vmax"], kwargs["cmap"]) == (-1, 1, "cmo.balance")
        assert "/map_ptemp_corr_prod1" in save_figure.call_args[0][1]


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
