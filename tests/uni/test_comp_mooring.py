"""End-to-end test for the comp_mooring pipeline: the two real mooring
station samples against the real cmems_glo12 model sample, driven through
armoor.cli.main.main_comp like test_comp_hydrosection.py."""
import pytest
import xarray as xr

from armoor import ROOTDIR
from armoor.data.open_decode import register_cf

SAMPLES_DIR = ROOTDIR + "/_samples"

STATIONS = {"mooring_6200029": "1.0", "mooring_6200163": "0.5"}


@pytest.fixture(scope="module", autouse=True)
def register_and_reset_cf():
    import xoa.meta as xmeta
    register_cf()
    yield
    xmeta.reset_cache(memory=True)


@pytest.fixture(scope="module")
def comp_mooring_run(tmp_path_factory):
    """Run the real comp_mooring load->coloc->output pipeline once (both
    real mooring stations, 6200029 and 6200163 -- each gets its own
    ref_name output directory) and return the output root."""
    from armoor.cli.main import main_comp, _init_heavy
    _init_heavy()

    tmp_path = tmp_path_factory.mktemp("comp_mooring_run")
    cfgfile = tmp_path / "comp_mooring.cfg"
    cfgfile.write_text(f"""
[data]
    [[glo12]]
    name=glo12
    path="{SAMPLES_DIR}/cmems_glo12_[temp,sal].nc"
    fmt=cmems_model
    [[mooring]]
    name=mooring
    path={SAMPLES_DIR}/*_TS_MO_*.nc
    fmt=cmems_insitu
    platform=mooring
    ref=True
[outputs]
    fmt=png
    [[timeseries]]
    otype=timeseries
""")

    metafile = tmp_path / "metazones.cfg"
    metafile.write_text("""
[moorzone]
    name=moorzone
    tbound=2026-06-15,2026-07-08
    polygon=(45.0,-14.0),(49,-14),(49,-7.0),(45,-7.0)
    [[trange_seq]]
        tfreq=1d
        tref=reference
""")

    import os
    cwd = os.getcwd()
    os.chdir(tmp_path)
    try:
        main_comp(
            cfgfile=cfgfile,
            metafile=metafile,
            metazones=["moorzone"],
            func_comp="comp_mooring",
            jsonfile=tmp_path / "out.json",
            ofilter=False,
            ocoloc=False,
            no_plot=True,
            plot_only=None,
            input_json=None,
            kw_dask=(1, None, None),
            comp_args={"radius": 20.0, "qc": None, "tbound": None},
        )
        output_root = tmp_path / "comp_mooring" / "output" / "moorzone"
        assert output_root.is_dir(), f"expected output not found: {output_root}"
        return output_root
    finally:
        os.chdir(cwd)


def _zarr(output_root, station):
    return output_root / station / "timeseries" / STATIONS[station] / "all.zarr"


def test_pipeline_produces_one_output_per_station(comp_mooring_run):
    """Each real mooring station is a distinct fixed platform -- the
    pipeline must not merge them, unlike comp_argo's moving-profile
    concatenation into a single ref_name."""
    for station in STATIONS:
        assert _zarr(comp_mooring_run, station).exists()


def test_pipeline_bias_finite_temp_only(comp_mooring_run):
    """Neither real mooring sample carries salinity, so only "temp" (not
    ptemp/sal/pdens/sndspeed) can be compared; its bias must be finite."""
    for station in STATIONS:
        dt = xr.open_datatree(_zarr(comp_mooring_run, station))
        model = dt["glo12"]
        assert set(model["ref"]["data"].to_dataset().data_vars) == {"temp"}
        bias = model["comp"]["bias"].to_dataset()["temp"]
        assert bool(bias.notnull().all())
        dt.close()


def test_timeseries_plot_renders(comp_mooring_run):
    """PlotComp.timeseries() must render one stats PNG per station,
    suffixed with that station's own single retained depth level."""
    from pathlib import Path

    from armoor.comp.plot import PlotComp

    for station, vlevel in STATIONS.items():
        pc = PlotComp(str(_zarr(comp_mooring_run, station)), "comp_mooring", "moorzone")
        pc.call("timeseries")
        pc.clean()

        assert len(pc.saved_files) == 1
        f = Path(pc.saved_files[0])
        assert f.name == f"timeseries_stats_temp_{vlevel}.png"
        assert f.stat().st_size > 0
