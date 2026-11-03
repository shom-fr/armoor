"""End-to-end test for the comp_alti pipeline: a synthetic gridded model
product (zos/uo/vo) against the real cmems_duacs_l4 sample, driven through
armoor.cli.main.main_comp like test_comp_sst.py.

It checks the whole load->coloc->output chain and the plots of the four
otypes, with a focus on the comp_alti specifics:

- DUACS sla/ugos/vgos are ignored: sla and the geostrophic currents are
  recomputed from adt, as for the model;
- ke/mke (total current) are not compared, since DUACS has no total current;
- mke_geos is averaged over the whole tbound window (``period`` dimension),
  written in its own ``*_period_*`` coloc files, and only used by maps and
  diagdisp_glob.
"""

import os
import numpy as np
import pandas as pd
import pytest
import xarray as xr

from armoor import ROOTDIR
from armoor.data.open_decode import register_cf

DUACS_SAMPLE = ROOTDIR + "/_samples/cmems_duacs_l4.nc"

ZONE = "altizone"
REF = "duacs"
PROD = "synthmodel"
PERIOD = "period_2024-01-01T00:00:00_2024-01-03T00:00:00"
DAYS = ["2024-01-01T00:00:00", "2024-01-02T00:00:00", "2024-01-03T00:00:00"]
COMPARED = {"sla", "ssh", "ke_geos", "eke"}


@pytest.fixture(scope="module", autouse=True)
def register_and_reset_cf():
    import xoa.meta as xmeta

    register_cf()
    yield
    xmeta.reset_cache(memory=True)


@pytest.fixture(scope="module")
def synth_model_file(tmp_path_factory):
    """A small surface model product covering the DUACS sample's domain
    (lon 48.38/49.12, lat 12.12/12.88) and time window (2024-01-01/03)."""
    outdir = tmp_path_factory.mktemp("synth_model_alti")

    lon = np.linspace(48.2, 49.3, 12).astype("float32")
    lat = np.linspace(11.9, 13.1, 13).astype("float32")
    time = pd.date_range("2024-01-01", "2024-01-03", freq="6h")
    shape = (len(time), len(lat), len(lon))

    rng = np.random.default_rng(0)
    xx, yy = np.meshgrid(lon, lat)
    zos = 0.5 + 0.1 * (np.sin(xx) * np.cos(yy))[None] + rng.normal(0, 0.02, shape)
    uo = rng.normal(0.1, 0.05, shape)
    vo = rng.normal(0.0, 0.05, shape)

    dims = ("time", "latitude", "longitude")
    ds = xr.Dataset(
        {
            "zos": (dims, zos.astype("float32")),
            "uo": (dims, uo.astype("float32")),
            "vo": (dims, vo.astype("float32")),
        },
        coords={"time": time, "latitude": lat, "longitude": lon},
    )
    path = outdir / "synth_model_ssh.nc"
    ds.to_netcdf(path)
    return path


@pytest.fixture(scope="module")
def comp_alti_run(tmp_path_factory, synth_model_file):
    """Run the real comp_alti load->coloc->output pipeline once (daily
    trange) and return the ``comp_alti`` working directory."""
    from armoor.cli.main import _init_heavy, main_comp

    _init_heavy()

    tmp_path = tmp_path_factory.mktemp("comp_alti_run")
    cfgfile = tmp_path / "comp_alti.cfg"
    cfgfile.write_text(f"""
[data]
    [[duacs]]
    name={REF}
    path={DUACS_SAMPLE}
    fmt=cmems_alti_duacs
    ref=True
    [[model]]
    name={PROD}
    path={synth_model_file}
    fmt=cmems_model
[outputs]
    fmt=png
    [[timeseries]]
    otype=timeseries
    [[maps]]
    otype=maps
    [[dispersion]]
    otype=diagdisp_sel
    [[global_dispersion]]
    otype=diagdisp_glob
""")

    metafile = tmp_path / "metazones.cfg"
    metafile.write_text(f"""
[{ZONE}]
    name={ZONE}
    tbound=2024-01-01,2024-01-03
    href=reference
    tfreq=1d
    polygon=(12.0,48.3),(13.0,48.3),(13.0,49.2),(12.0,49.2)
""")

    cwd = os.getcwd()
    os.chdir(tmp_path)
    try:
        main_comp(
            cfgfile=cfgfile,
            metafile=metafile,
            metazones=[ZONE],
            func_comp="comp_alti",
            jsonfile=tmp_path / "out.json",
            ofilter=False,
            ocoloc=False,
            no_plot=True,
            plot_only=None,
            input_json=None,
            kw_dask=(1, None, None),
            comp_args={"tbound": None},
        )
    finally:
        os.chdir(cwd)
    rundir = tmp_path / "comp_alti"
    assert rundir.exists()
    return rundir


def _coloc_dir(rundir):
    return rundir / "coloc" / ZONE / REF / PROD


def _output_zarr(rundir, otype, sub, name=PROD):
    return rundir / "output" / ZONE / REF / otype / sub / f"{name}.zarr"


def _group_vars(zarr_path, branch, sub):
    dt = xr.open_datatree(zarr_path)
    try:
        return set(dt[PROD][branch][sub].to_dataset().data_vars)
    finally:
        dt.close()


# --- coloc ------------------------------------------------------------------


def test_coloc_files(comp_alti_run):
    """One file per day for ref and prod, plus one whole-window period file
    each: the period file must not overwrite a daily one."""
    names = {p.name for p in _coloc_dir(comp_alti_run).glob("*.zarr")}
    expected = {f"{side}_{day}.zarr" for side in ("ref", "prod") for day in DAYS}
    expected |= {f"ref_{PERIOD}.zarr", f"prod_{PERIOD}.zarr"}
    assert names == expected


@pytest.mark.parametrize("side", ["ref", "prod"])
def test_coloc_daily_files_content(comp_alti_run, side):
    """Daily files hold the time-dependent compared variables, never the
    total-current energies (DUACS has no total current) nor mke_geos."""
    for day in DAYS:
        ds = xr.open_zarr(_coloc_dir(comp_alti_run) / f"{side}_{day}.zarr")
        assert ds.sizes["time"] == 1
        assert "period" not in ds.dims
        assert COMPARED <= set(ds.data_vars)
        assert not {"ke", "mke", "mke_geos"} & set(ds.data_vars)
        # ref and prod hold the same variables: the model raw u/v are dropped
        assert set(ds.data_vars) == COMPARED
        # intermediates are not stored
        assert not {"ugos", "vgos", "ugosa", "vgosa"} & set(ds.data_vars)


@pytest.mark.parametrize("side", ["ref", "prod"])
def test_coloc_period_file_content(comp_alti_run, side):
    """The period file only holds mke_geos, on a size-1 period dimension,
    tagged with the whole tbound window."""
    ds = xr.open_zarr(_coloc_dir(comp_alti_run) / f"{side}_{PERIOD}.zarr")
    assert set(ds.data_vars) == {"mke_geos"}
    assert ds.sizes["period"] == 1
    assert "time" not in ds.dims
    assert ds.attrs["period"] == PERIOD.removeprefix("period_")
    assert "time" not in ds.attrs
    assert bool(ds["mke_geos"].notnull().all())
    assert bool((ds["mke_geos"] >= 0).all())


def test_ref_duacs_products_are_ignored(comp_alti_run):
    """The reference sla is the anomaly of adt over the colocated window,
    not the DUACS sla (referenced to 1993-2012)."""
    ref = xr.concat(
        [xr.open_zarr(_coloc_dir(comp_alti_run) / f"ref_{day}.zarr") for day in DAYS],
        "time",
    )
    expected = ref["ssh"] - ref["ssh"].mean("time")
    np.testing.assert_allclose(ref["sla"], expected, atol=1e-6)

    raw = xr.open_dataset(DUACS_SAMPLE)
    assert not np.allclose(ref["sla"].values, raw["sla"].values, atol=1e-3)
    # the adt is passed as is
    np.testing.assert_allclose(ref["ssh"].values, raw["adt"].values, atol=1e-6)


def test_ref_energies_from_adt(comp_alti_run):
    """ke_geos, eke and mke_geos of the reference are consistent with the
    geostrophic currents computed from adt and sla."""
    from shoot.dyn import get_geos

    ref = xr.concat(
        [xr.open_zarr(_coloc_dir(comp_alti_run) / f"ref_{day}.zarr") for day in DAYS],
        "time",
    ).compute()

    ugos, vgos = get_geos(ref["ssh"])
    np.testing.assert_allclose(ref["ke_geos"], 0.5 * (ugos**2 + vgos**2), rtol=1e-5)

    ugosa, vgosa = get_geos(ref["sla"])
    np.testing.assert_allclose(ref["eke"], 0.5 * (ugosa**2 + vgosa**2), rtol=1e-5)

    period = xr.open_zarr(_coloc_dir(comp_alti_run) / f"ref_{PERIOD}.zarr")
    mke = 0.5 * (ugos.mean("time") ** 2 + vgos.mean("time") ** 2)
    np.testing.assert_allclose(period["mke_geos"].isel(period=0), mke, rtol=1e-5)


# --- output -----------------------------------------------------------------


def test_timeseries_output(comp_alti_run):
    """Timeseries stats cover the time-dependent compared variables only."""
    path = comp_alti_run / "output" / ZONE / REF / "timeseries" / "None" / "all.zarr"
    for sub in ("bias", "rmse", "rmsec"):
        assert _group_vars(path, "comp", sub) == COMPARED
    dt = xr.open_datatree(path)
    bias = dt[PROD]["comp"]["bias"].to_dataset()
    assert bias.sizes["time"] == 3
    assert "period" not in bias.dims
    assert bool(bias["sla"].notnull().all())
    dt.close()


def test_maps_outputs(comp_alti_run):
    """maps: one output per day without mke_geos, and one for the period
    with mke_geos only."""
    otype_dir = comp_alti_run / "output" / ZONE / REF / "maps"
    assert {p.name for p in otype_dir.iterdir()} == set(DAYS) | {PERIOD}

    for day in DAYS:
        path = _output_zarr(comp_alti_run, "maps", day)
        assert _group_vars(path, "comp", "diff") == COMPARED

    path = _output_zarr(comp_alti_run, "maps", PERIOD)
    for branch, sub in (("ref", "data"), ("prod", "data"), ("comp", "diff")):
        assert _group_vars(path, branch, sub) == {"mke_geos"}
    dt = xr.open_datatree(path)
    diff = dt[PROD]["comp"]["diff"].to_dataset()["mke_geos"]
    ref = dt[PROD]["ref"]["data"].to_dataset()["mke_geos"]
    prod = dt[PROD]["prod"]["data"].to_dataset()["mke_geos"]
    assert diff.sizes["period"] == 1
    np.testing.assert_allclose(diff, prod - ref, rtol=1e-5, atol=1e-10)
    dt.close()


def test_diagdisp_sel_skips_period(comp_alti_run):
    """diagdisp_sel has no sense for a whole-window mean: no period output."""
    otype_dir = comp_alti_run / "output" / ZONE / REF / "diagdisp_sel"
    assert {p.name for p in otype_dir.iterdir()} == set(DAYS)
    for day in DAYS:
        path = _output_zarr(comp_alti_run, "diagdisp_sel", day)
        assert "mke_geos" not in _group_vars(path, "comp", "diff")


def test_diagdisp_glob_merges_period(comp_alti_run):
    """diagdisp_glob merges the time-concatenated variables with mke_geos."""
    path = _output_zarr(comp_alti_run, "diagdisp_glob", "None")
    for branch, sub in (("ref", "data"), ("comp", "diff")):
        assert _group_vars(path, branch, sub) == COMPARED | {"mke_geos"}
    dt = xr.open_datatree(path)
    diff = dt[PROD]["comp"]["diff"].to_dataset()
    assert diff.sizes["time"] == 3
    assert diff["mke_geos"].dims[0] == "period"
    assert "time" not in diff["mke_geos"].dims
    dt.close()


# --- plots ------------------------------------------------------------------


def _plot(zarr_path, otype, rundir):
    """Plot one output zarr from the run directory (figures are written
    relative to the current directory) and return the saved files."""
    from armoor.comp.plot import PlotComp

    cwd = os.getcwd()
    os.chdir(rundir.parent)
    try:
        pc = PlotComp(str(zarr_path), "comp_alti", ZONE)
        pc.call(otype)
        pc.clean()
    finally:
        os.chdir(cwd)
    files = [rundir.parent / f for f in pc.saved_files]
    assert files
    assert all(f.stat().st_size > 0 for f in files)
    return files


def test_plot_timeseries(comp_alti_run):
    path = comp_alti_run / "output" / ZONE / REF / "timeseries" / "None" / "all.zarr"
    files = _plot(path, "timeseries", comp_alti_run)
    assert {f.name for f in files} == {f"timeseries_stats_{v}.png" for v in COMPARED}


@pytest.mark.parametrize("otype", ["maps", "diagdisp_sel"])
def test_plot_daily(comp_alti_run, otype):
    """One figure per day and compared variable, without mke_geos: the
    daily figures must not overwrite each other."""
    names = []
    for day in DAYS:
        files = _plot(_output_zarr(comp_alti_run, otype, day), otype, comp_alti_run)
        names += [f.name for f in files]
        assert all(f.name.endswith(f"_{day}.png") for f in files)
    assert len(names) == len(set(names))
    assert not any("mke_geos" in name for name in names)
    for var in COMPARED:
        assert sum(f"_{var}_" in name for name in names) == len(DAYS)


def test_plot_maps_period(comp_alti_run):
    files = _plot(_output_zarr(comp_alti_run, "maps", PERIOD), "maps", comp_alti_run)
    assert files
    assert all("mke_geos" in f.name and "_period_" in f.name for f in files)


def test_plot_diagdisp_glob(comp_alti_run):
    path = _output_zarr(comp_alti_run, "diagdisp_glob", "None")
    files = _plot(path, "diagdisp_glob", comp_alti_run)
    assert {f.name for f in files} == {
        f"diagdisp_glob_{v}_{PROD}.png" for v in COMPARED | {"mke_geos"}
    }
