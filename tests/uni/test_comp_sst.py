"""End-to-end test for the comp_sst pipeline: a synthetic gridded model
product against the real cmems_sst_l3 sample, driven through
armoor.cli.main.main_comp like test_comp_hydrosection.py."""
import numpy as np
import pandas as pd
import pytest
import xarray as xr

from armoor import ROOTDIR
from armoor.data.open_decode import register_cf

SAMPLES_DIR = ROOTDIR + "/_samples"
SST_L3_SAMPLE = SAMPLES_DIR + "/cmems_sst_l3.nc"


@pytest.fixture(scope="module", autouse=True)
def register_and_reset_cf():
    import xoa.meta as xmeta
    register_cf()
    yield
    xmeta.reset_cache(memory=True)


@pytest.fixture(scope="module")
def synth_model_file(tmp_path_factory):
    """A small gridded thetao product covering the real sst_l3 sample's own
    domain (lon ~-13.95/-13.05, lat ~45.05/45.95) and time window
    (2026-07-03/08)."""
    outdir = tmp_path_factory.mktemp("synth_model_sst")

    lon = np.linspace(-14.1, -12.9, 6).astype("float32")
    lat = np.linspace(44.9, 46.1, 6).astype("float32")
    depth = np.array([0.5, 5., 10.], dtype="float32")
    time = pd.date_range("2026-07-02", "2026-07-09", freq="6h")

    rng = np.random.default_rng(3)
    thetao = (18 + rng.normal(0, 0.5, size=(len(time), len(depth), len(lat), len(lon)))).astype("float32")

    ds = xr.Dataset(
        {"thetao": (("time", "depth", "latitude", "longitude"), thetao)},
        coords={"time": time, "depth": depth, "latitude": lat, "longitude": lon},
    )
    temp_nc = outdir / "synth_model_temp.nc"
    ds.to_netcdf(temp_nc)
    return temp_nc


@pytest.fixture(scope="module")
def comp_sst_run(tmp_path_factory, synth_model_file):
    """Run the real comp_sst load->coloc->output pipeline once and return
    the path to the produced "timeseries" output zarr."""
    from armoor.cli.main import main_comp, _init_heavy
    _init_heavy()

    tmp_path = tmp_path_factory.mktemp("comp_sst_run")
    cfgfile = tmp_path / "comp_sst.cfg"
    cfgfile.write_text(f"""
[data]
    [[model]]
    name=synthmodel
    path={synth_model_file}
    fmt=cmems_model
    [[sstobs]]
    name=sstobs
    path={SST_L3_SAMPLE}
    fmt=cmems_sst_l3
    ref=True
[outputs]
    fmt=png
    [[timeseries]]
    otype=timeseries
""")

    metafile = tmp_path / "metazones.cfg"
    metafile.write_text("""
[sstzone]
    name=sstzone
    tbound=2026-07-03,2026-07-08
    href=reference
    tfreq=1d
    polygon=(44.9,-14.1),(46.1,-14.1),(46.1,-12.9),(44.9,-12.9)
""")

    import os
    cwd = os.getcwd()
    os.chdir(tmp_path)
    try:
        main_comp(
            cfgfile=cfgfile,
            metafile=metafile,
            metazones=["sstzone"],
            func_comp="comp_sst",
            jsonfile=tmp_path / "out.json",
            ofilter=False,
            ocoloc=False,
            no_plot=True,
            plot_only=None,
            input_json=None,
            kw_dask=(1, None, None),
            comp_args={"qc": None, "tbound": None},
        )
        zarr_path = (
            tmp_path / "comp_sst" / "output" / "sstzone" /
            "sstobs" / "timeseries" / "None" / "all.zarr"
        )
        assert zarr_path.exists(), f"expected output not found: {zarr_path}"
        return zarr_path
    finally:
        os.chdir(cwd)


def test_pipeline_produces_ref_prod_comp_groups(comp_sst_run):
    """ref/prod (data/mean/std) and comp (bias/rmse/rmsec) must all carry ptemp."""
    dt = xr.open_datatree(comp_sst_run)
    model = dt["synthmodel"]
    for branch, subgroups in (
        ("ref", ("data", "mean", "std")),
        ("prod", ("data", "mean", "std")),
        ("comp", ("bias", "rmse", "rmsec")),
    ):
        for sub in subgroups:
            assert "ptemp" in model[branch][sub].to_dataset().data_vars
    dt.close()


def test_pipeline_bias_finite_despite_ref_nan_gaps(comp_sst_run):
    """The real cmems_sst_l3 sample has masked (NaN) pixels; the per-timestep
    spatial bias/rmse must still be finite everywhere."""
    dt = xr.open_datatree(comp_sst_run)
    model = dt["synthmodel"]
    ref_ptemp = model["ref"]["data"].to_dataset()["ptemp"]
    assert bool(ref_ptemp.isnull().any())
    bias = model["comp"]["bias"].to_dataset()["ptemp"]
    rmse = model["comp"]["rmse"].to_dataset()["ptemp"]
    assert bool(bias.notnull().all())
    assert bool((rmse >= 0).all())
    dt.close()


def test_timeseries_plot_renders(comp_sst_run):
    """PlotComp.timeseries() must dispatch to the stats variant (a "bias"
    group is present) and render the single ptemp comp_var."""
    from pathlib import Path

    from armoor.comp.plot import PlotComp

    pc = PlotComp(str(comp_sst_run), "comp_sst", "sstzone")
    pc.call("timeseries")
    pc.clean()

    assert len(pc.saved_files) == 1
    f = Path(pc.saved_files[0])
    assert f.name == "timeseries_stats_ptemp.png"
    assert f.stat().st_size > 0
