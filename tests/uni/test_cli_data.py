"""End-to-end test for main_data_pipeline's HPC wave modes (load_only,
input_zarrs, plot_only, no_plot), added alongside HPC support for
armoor-data. Mirrors tests/uni/test_data_pipeline.py's real-sample setup."""
import json

import pytest

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
def data_cfg_files(tmp_path_factory):
    tmp_path = tmp_path_factory.mktemp("cli_data_run")
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
    return tmp_path, cfgfile, metafile


def test_load_only_writes_metazone_paths_json(data_cfg_files):
    """--load-only (HPC Wave 0) loads a single dataset key for all
    metazones and writes {metazone: [zarr_paths]}."""
    from armoor.cli.main import _init_heavy, main_data_pipeline
    _init_heavy()

    tmp_path, cfgfile, metafile = data_cfg_files
    jsonfile = tmp_path / "wave0.json"
    import os
    cwd = os.getcwd()
    os.chdir(tmp_path)
    try:
        main_data_pipeline(
            cfgfile, metafile, ["datazone"], jsonfile,
            ofilter=False, no_plot=True, plot_only=None, input_json=None,
            kw_dask=(1, None, None), data_args={"tbound": None}, load_only="glo12",
        )
    finally:
        os.chdir(cwd)

    with open(jsonfile) as f:
        wave0 = json.load(f)
    assert list(wave0.keys()) == ["datazone"]
    assert wave0["datazone"]


def test_input_zarrs_skips_load_and_produces_output(data_cfg_files):
    """--input-zarrs (HPC Wave 1) reuses a Wave-0 JSON instead of calling
    load_datasets, and produces the same nested {otype: {mz: [paths]}}
    shape as the normal pipeline with no_plot=True."""
    from armoor.cli.main import _init_heavy, main_data_pipeline
    _init_heavy()

    tmp_path, cfgfile, metafile = data_cfg_files
    wave0_json = tmp_path / "wave0_reuse.json"
    wave1_json = tmp_path / "wave1.json"
    import os
    cwd = os.getcwd()
    os.chdir(tmp_path)
    try:
        main_data_pipeline(
            cfgfile, metafile, ["datazone"], wave0_json,
            ofilter=False, no_plot=True, plot_only=None, input_json=None,
            kw_dask=(1, None, None), data_args={"tbound": None}, load_only="glo12",
        )
        main_data_pipeline(
            cfgfile, metafile, ["datazone"], wave1_json,
            ofilter=False, no_plot=True, plot_only=None, input_json=None,
            kw_dask=(1, None, None), data_args={"tbound": None},
            input_zarrs=[str(wave0_json)],
        )
    finally:
        os.chdir(cwd)

    with open(wave1_json) as f:
        wave1 = json.load(f)
    assert list(wave1.keys()) == ["timeseries"]
    assert "datazone" in wave1["timeseries"]


def test_plot_only_writes_png_paths(data_cfg_files):
    """--plot-only (HPC Wave 3) reads a merged output JSON and renders
    plots, writing their paths to --jsonfile -- regression test for the
    bug where main_data() used to discard PlotOceanModel's return value,
    leaving --jsonfile unwritten for png-only outputs."""
    from armoor.cli.main import _init_heavy, main_data_pipeline
    _init_heavy()

    tmp_path, cfgfile, metafile = data_cfg_files
    wave1_json = tmp_path / "wave1_for_plot.json"
    plot_json = tmp_path / "plot.json"
    import os
    cwd = os.getcwd()
    os.chdir(tmp_path)
    try:
        main_data_pipeline(
            cfgfile, metafile, ["datazone"], wave1_json,
            ofilter=False, no_plot=True, plot_only=None, input_json=None,
            kw_dask=(1, None, None), data_args={"tbound": None},
        )
        main_data_pipeline(
            cfgfile, metafile, ["datazone"], plot_json,
            ofilter=False, no_plot=False, plot_only="timeseries", input_json=wave1_json,
            kw_dask=(1, None, None), data_args={"tbound": None},
        )
    finally:
        os.chdir(cwd)

    with open(plot_json) as f:
        png_paths = json.load(f)
    assert png_paths
    from pathlib import Path
    for p in png_paths:
        assert Path(p).stat().st_size > 0
