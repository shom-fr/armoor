"""End-to-end test for the comp_argo pipeline: the real argo profile
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
def comp_argo_run(tmp_path_factory):
    """Run the real comp_argo load->coloc->output pipeline once (both real
    argo platforms, 1902796 and 2901943) and return the path to the
    produced "timeseries" output root (one zarr per vlevel)."""
    from armoor.cli.main import main_comp, _init_heavy
    _init_heavy()

    tmp_path = tmp_path_factory.mktemp("comp_argo_run")
    cfgfile = tmp_path / "comp_argo.cfg"
    cfgfile.write_text(f"""
[data]
    [[glo12]]
    name=glo12
    path="{SAMPLES_DIR}/cmems_glo12_[temp,sal].nc"
    fmt=cmems_model
    [[argo]]
    name=argoprofiles
    path={SAMPLES_DIR}/*_PR_PF_*.nc
    fmt=cmems_insitu
    platform=argo
    ref=True
[outputs]
    fmt=png
    [[timeseries]]
    otype=timeseries
""")

    metafile = tmp_path / "metazones.cfg"
    metafile.write_text("""
[argozone]
    name=argozone
    tbound=2026-06-15,2026-07-08
    polygon=(45.0,-14.0),(49,-14),(49,-7.0),(45,-7.0)
    [[trange_seq]]
        tfreq=1d
        tref=reference
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
            metazones=["argozone"],
            func_comp="comp_argo",
            jsonfile=tmp_path / "out.json",
            ofilter=False,
            ocoloc=False,
            no_plot=True,
            plot_only=None,
            input_json=None,
            kw_dask=(1, None, None),
            comp_args={"radius": 20.0, "qc": None, "tbound": None},
        )
        output_root = tmp_path / "comp_argo" / "output" / "argozone" / "argoprofiles" / "timeseries"
        assert output_root.is_dir(), f"expected output not found: {output_root}"
        return output_root
    finally:
        os.chdir(cwd)


def test_pipeline_produces_two_signature_groups(comp_argo_run):
    """The z-resolved group (ptemp/sal/pdens/temp/sndspeed, at the single
    configured vlevel=10.0) and the z-less "mld" group must land as two
    distinct all.zarr files."""
    dt_z = xr.open_datatree(comp_argo_run / "10.0" / "all.zarr")
    dt_none = xr.open_datatree(comp_argo_run / "None" / "all.zarr")
    z_vars = set(dt_z["glo12"]["ref"]["data"].to_dataset().data_vars)
    none_vars = set(dt_none["glo12"]["ref"]["data"].to_dataset().data_vars)
    assert z_vars == {"ptemp", "sal", "pdens", "temp", "sndspeed"}
    assert none_vars == {"mld"}
    dt_z.close()
    dt_none.close()


def test_pipeline_bias_finite_for_z_resolved_vars(comp_argo_run):
    """Every z-resolved comp_var's bias must be finite at every colocated
    time (radius=20km around each real argo profile)."""
    dt = xr.open_datatree(comp_argo_run / "10.0" / "all.zarr")
    bias = dt["glo12"]["comp"]["bias"].to_dataset()
    for var in ("ptemp", "sal", "pdens", "temp", "sndspeed"):
        assert bool(bias[var].notnull().all())
    dt.close()


def test_timeseries_plot_renders(comp_argo_run):
    """PlotComp.timeseries() must render one stats PNG per z-resolved
    comp_var (suffixed _10.0) plus one for mld (no vlevel suffix), and must
    not crash on mld's real all-NaN values (no mixed-layer computable from
    a single-instant argo profile)."""
    from pathlib import Path

    from armoor.comp.plot import PlotComp

    saved = []
    for tag in ("10.0", "None"):
        pc = PlotComp(str(comp_argo_run / tag / "all.zarr"), "comp_argo", "argozone")
        pc.call("timeseries")
        pc.clean()
        saved += pc.saved_files

    names = {Path(f).name for f in saved}
    assert names == {
        "timeseries_stats_ptemp_10.0.png", "timeseries_stats_sal_10.0.png",
        "timeseries_stats_pdens_10.0.png", "timeseries_stats_temp_10.0.png",
        "timeseries_stats_sndspeed_10.0.png", "timeseries_stats_mld.png",
    }
    for f in saved:
        assert Path(f).stat().st_size > 0
