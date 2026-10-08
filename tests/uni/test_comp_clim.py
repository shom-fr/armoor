"""End-to-end test for the comp_clim pipeline: the real woa18 climatology
samples against the real cmems_glo12 model sample, driven through
armoor.cli.main.main_comp like test_comp_hydrosection.py."""
import pytest
import xarray as xr

from armoor import ROOTDIR
from armoor.data.open_decode import register_cf

SAMPLES_DIR = ROOTDIR + "/_samples"


@pytest.fixture(scope="module", autouse=True)
def register_and_reset_cf():
    import xoa.meta as xmeta
    register_cf()
    yield
    xmeta.reset_cache(memory=True)


@pytest.fixture(scope="module")
def comp_clim_run(tmp_path_factory):
    """Run the real comp_clim load->coloc->output pipeline once and return
    the path to the produced "timeseries" output zarr. The real
    cmems_glo12_[temp,sal].nc sample covers June/July 2026, which overlaps
    2 of the 3 available woa18 climatology months (05, 06, 07)."""
    from armoor.cli.main import main_comp, _init_heavy
    _init_heavy()

    tmp_path = tmp_path_factory.mktemp("comp_clim_run")
    cfgfile = tmp_path / "comp_clim.cfg"
    cfgfile.write_text(f"""
[data]
    [[woa18]]
    name=woa18clim
    path="{SAMPLES_DIR}/woa18_decav_*.nc"
    fmt=woa18
    ref=True
    [[glo12]]
    name=glo12
    path="{SAMPLES_DIR}/cmems_glo12_[temp,sal].nc"
    fmt=cmems_model
[outputs]
    fmt=png
    [[timeseries]]
    otype=timeseries
""")

    metafile = tmp_path / "metazones.cfg"
    metafile.write_text("""
[climzone]
    name=climzone
    tbound=2026-06-15,2026-07-08
    href=reference
    polygon=(45.0,-14.0),(49,-14),(49,-7.0),(45,-7.0)
    [[vlevel]]
        vname=depth
        levels=10
""")

    import os
    cwd = os.getcwd()
    os.chdir(tmp_path)
    try:
        main_comp(
            cfgfile=cfgfile,
            metafile=metafile,
            metazones=["climzone"],
            func_comp="comp_clim",
            jsonfile=tmp_path / "out.json",
            ofilter=False,
            ocoloc=False,
            no_plot=True,
            plot_only=None,
            input_json=None,
            kw_dask=(1, None, None),
            comp_args={"tbound": None},
        )
        zarr_path = (
            tmp_path / "comp_clim" / "output" / "climzone" /
            "woa18clim" / "timeseries" / "10.0" / "all.zarr"
        )
        assert zarr_path.exists(), f"expected output not found: {zarr_path}"
        return zarr_path
    finally:
        os.chdir(cwd)


def test_pipeline_produces_ref_prod_comp_groups(comp_clim_run):
    """ref/prod (data/mean/std) and comp (bias/rmse/rmsec) must all carry
    both ptemp and sal."""
    dt = xr.open_datatree(comp_clim_run)
    model = dt["glo12"]
    for branch, subgroups in (
        ("ref", ("data", "mean", "std")),
        ("prod", ("data", "mean", "std")),
        ("comp", ("bias", "rmse", "rmsec")),
    ):
        for sub in subgroups:
            data_vars = model[branch][sub].to_dataset().data_vars
            assert "ptemp" in data_vars
            assert "sal" in data_vars
    dt.close()


def test_pipeline_colocates_on_overlapping_months(comp_clim_run):
    """tmonth() colocation must keep only the 2 calendar months (June, July)
    common to the woa18 climatology and the model sample, and every bias
    value must be finite."""
    dt = xr.open_datatree(comp_clim_run)
    model = dt["glo12"]
    assert list(model["ref"]["data"].to_dataset()["time"].values) == [6, 7]
    bias = model["comp"]["bias"].to_dataset()
    assert bool(bias["ptemp"].notnull().all())
    assert bool(bias["sal"].notnull().all())
    dt.close()


def test_timeseries_plot_renders(comp_clim_run):
    """PlotComp.timeseries() must render one stats PNG per comp_var
    (ptemp, sal), suffixed with the single vlevel (10.0)."""
    from pathlib import Path

    from armoor.comp.plot import PlotComp

    pc = PlotComp(str(comp_clim_run), "comp_clim", "climzone")
    pc.call("timeseries")
    pc.clean()

    names = {Path(f).name for f in pc.saved_files}
    assert names == {"timeseries_stats_ptemp_10.0.png", "timeseries_stats_sal_10.0.png"}
    for f in pc.saved_files:
        assert Path(f).stat().st_size > 0
