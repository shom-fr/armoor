"""End-to-end test for the armoor-data pipeline (no ref/prod comparison,
unlike comp_*): the real cmems_glo12 model sample loaded and reduced over
one metazone/vlevel, driven through the same internal calls main_data()
itself makes (load_datasets -> output_data), since main_data() only exposes
an argparse entrypoint."""
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
def data_pipeline_run(tmp_path_factory):
    """Run the real armoor-data load->output pipeline once and return the
    path to the produced "timeseries" output zarr."""
    from xoa.cfgm import ConfigManager

    from armoor.cli import DATA_INI, METAZONES_INI
    from armoor.cli.main import _init_heavy, check_metazones_in
    from armoor.data.load import load_datasets
    from armoor.data.output import main_output as output_data
    _init_heavy()

    tmp_path = tmp_path_factory.mktemp("data_pipeline_run")
    cfgfile = tmp_path / "data.cfg"
    cfgfile.write_text(f"""
[data]
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
[datazone]
    name=datazone
    tbound=2026-06-15,2026-07-08
    tfreq=1d
    polygon=(45.0,-14.0),(49,-14),(49,-7.0),(45,-7.0)
    [[vlevel]]
        vname=depth
        levels=10
""")

    import os
    cwd = os.getcwd()
    os.chdir(tmp_path)
    try:
        cfg = ConfigManager(DATA_INI).load(str(cfgfile))
        metazones_cfg = ConfigManager(METAZONES_INI).load(str(metafile))
        metazones = check_metazones_in(["datazone"], metazones_cfg, tbound=None)
        zarrs = load_datasets(cfg["data"], metazones, "data")
        output_data(zarrs, metazones, cfg.get("outputs", {}).copy())

        zarr_path = tmp_path / "data" / "output" / "datazone" / "timeseries" / "10.0" / "glo12.zarr"
        assert zarr_path.exists(), f"expected output not found: {zarr_path}"
        return zarr_path
    finally:
        os.chdir(cwd)


def test_pipeline_produces_data_mean_std_groups(data_pipeline_run):
    """Unlike comp_*, there's no reference to diff against: the output is a
    flat data/mean/std tree (no per-source subgroup), both ptemp and sal
    present and fully finite (a real, gap-free model grid, unlike the
    satellite/in-situ samples used by the comp_* tests)."""
    dt = xr.open_datatree(data_pipeline_run)
    for group in ("data", "mean", "std"):
        ds = dt[group].to_dataset()
        assert "ptemp" in ds.data_vars
        assert "sal" in ds.data_vars
        assert bool(ds["ptemp"].notnull().all())
        assert bool(ds["sal"].notnull().all())
    dt.close()


def test_timeseries_plot_renders(data_pipeline_run):
    """PlotOceanModel.timeseries() must render one PNG per variable
    (ptemp, sal), suffixed with the single configured vlevel (10.0)."""
    from pathlib import Path

    from armoor.data.plot import PlotOceanModel

    dt = xr.open_datatree(data_pipeline_run)
    pc = PlotOceanModel(dt, "datazone")
    pc.call("timeseries")
    pc.clean()

    names = {Path(f).name for f in pc.saved_files}
    assert names == {"timeseries_glo12_ptemp_10.0.png", "timeseries_glo12_sal_10.0.png"}
    for f in pc.saved_files:
        assert Path(f).stat().st_size > 0
