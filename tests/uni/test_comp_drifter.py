"""End-to-end test for the comp_drifter pipeline: a real drifter sample vs
a real oceanparcels particle-tracking simulation driven by the real
cmems_glo12 current sample, through armoor.cli.main.main_comp like
test_comp_hydrosection.py. Unlike the other comp_* pipelines, comp_drifter
doesn't diff comp_vars directly -- it releases a virtual particle at the
drifter's start position/time and compares its simulated trajectory
(oceanparcels) against the real drifter track."""
import pytest
import xarray as xr

from armoor import ROOTDIR
from armoor.data.open_decode import register_cf

SAMPLES_DIR = ROOTDIR + "/_samples"
DRIFTER_SAMPLE = SAMPLES_DIR + "/GL_TS_DB_1301782_20260703_20260708.nc"


@pytest.fixture(scope="module", autouse=True)
def register_and_reset_cf():
    import xoa.meta as xmeta
    register_cf()
    yield
    xmeta.reset_cache(memory=True)


@pytest.fixture(scope="module")
def comp_drifter_run(tmp_path_factory):
    """Run the real comp_drifter load->coloc->preproc(parcels)->output
    pipeline once and return the path to the produced output zarr. cfg's
    otype=timeseries gets remapped internally to timeseries_drifter (see
    CompDrifter.otype_remap), landing at .../timeseries_drifter/None/all.zarr."""
    from armoor.cli.main import main_comp, _init_heavy
    _init_heavy()

    tmp_path = tmp_path_factory.mktemp("comp_drifter_run")
    cfgfile = tmp_path / "comp_drifter.cfg"
    cfgfile.write_text(f"""
[data]
    [[glo12]]
    name=glo12
    path="{SAMPLES_DIR}/cmems_glo12_[temp,curr].nc"
    fmt=cmems_model
    [[drifter]]
    name=drifter
    path={DRIFTER_SAMPLE}
    fmt=cmems_insitu
    platform=drifter
    ref=True
[outputs]
    fmt=png
    [[timeseries]]
    otype=timeseries
""")

    metafile = tmp_path / "metazones.cfg"
    metafile.write_text("""
[driftzone]
    name=driftzone
    tbound=2026-07-03,2026-07-08
    polygon=(45.0,-14.0),(49,-14),(49,-7.0),(45,-7.0)
""")

    import os
    cwd = os.getcwd()
    os.chdir(tmp_path)
    try:
        main_comp(
            cfgfile=cfgfile,
            metafile=metafile,
            metazones=["driftzone"],
            func_comp="comp_drifter",
            jsonfile=tmp_path / "out.json",
            ofilter=False,
            ocoloc=False,
            no_plot=True,
            plot_only=None,
            input_json=None,
            kw_dask=(1, None, None),
            comp_args={"period_drift": "5d", "freq_drift": "1h", "tbound": None},
        )
        zarr_path = (
            tmp_path / "comp_drifter" / "output" / "driftzone" /
            "drifter" / "timeseries_drifter" / "None" / "all.zarr"
        )
        assert zarr_path.exists(), f"expected output not found: {zarr_path}"
        return zarr_path
    finally:
        os.chdir(cwd)


def test_pipeline_produces_finite_distance_and_direction(comp_drifter_run):
    """The simulated particle's drift away from the real drifter track must
    be finite at every hourly step over the 5-day period (120 steps), and
    must start at distance 0 (particle released at the drifter's own first
    position)."""
    dt = xr.open_datatree(comp_drifter_run)
    diff = dt["glo12"]["comp"]["diff"].to_dataset()
    assert diff.sizes["time"] == 120
    assert bool(diff["distance"].notnull().all())
    assert bool(diff["direction"].notnull().all())
    assert diff["distance"].values[0] == 0.0
    dt.close()


def test_pipeline_distance_grows_over_time(comp_drifter_run):
    """A regression guard on the parcels integration actually running
    forward in time: cumulative drift distance from the real track should
    trend upward, not stay pinned near 0 (which would indicate a
    degenerate/zero current field or a broken integration)."""
    dt = xr.open_datatree(comp_drifter_run)
    distance = dt["glo12"]["comp"]["diff"].to_dataset()["distance"].values
    assert distance[-1] > distance[len(distance) // 2] > distance[10]
    dt.close()


def test_timeseries_drifter_plot_renders(comp_drifter_run):
    """PlotComp must be called with the remapped otype "timeseries_drifter"
    (not the generic "timeseries" -- that dispatches to timeseries_sel/
    timeseries_stats, which don't understand distance/direction and raise
    KeyError on "temp")."""
    from pathlib import Path

    from armoor.comp.plot import PlotComp

    pc = PlotComp(str(comp_drifter_run), "comp_drifter", "driftzone")
    pc.call("timeseries_drifter")
    pc.clean()

    assert len(pc.saved_files) == 1
    f = Path(pc.saved_files[0])
    assert f.name == "timeseries_drifter.png"
    assert f.stat().st_size > 0
