"""End-to-end test for the comp_hydrosection pipeline against a real glider
sample (`_samples/GL_PR_GL_8901067_20240816.nc`, a full glider mission --
several profiles at their own (time, lon, lat)) and a small synthetic
gridded model product covering its domain/time window.

Exercises the real load -> coloc -> output -> plot chain (same call path as
``armoor-comp-hydrosection``, driven directly through
``armoor.cli.main.main_comp`` like the other ``armoor-comp-*`` CLIs) rather
than mocking any of `track`/`grid2track`/the forced vertical colocation --
those are exactly the parts new to this comparison type and most likely to
break silently. Plotting is exercised by calling `PlotComp` directly instead
of `armoor.comp.plot.main_plot` (which spawns a multiprocessing pool and
pre-warms cartopy's naturalearth cache -- unnecessary and slow/networked for
a single-file test).
"""
import numpy as np
import pandas as pd
import pytest
import xarray as xr

from armoor import ROOTDIR
from armoor.data.open_decode import register_cf

SAMPLES_DIR = ROOTDIR + "/_samples"
GLIDER_SAMPLE = SAMPLES_DIR + "/GL_PR_GL_8901067_20240816.nc"
SEASOAR_SAMPLE = SAMPLES_DIR + "/seasoar.nc"


@pytest.fixture(scope="module", autouse=True)
def register_and_reset_cf():
    """Register armoor CF specs for the module and reset xoa.meta registry on teardown."""
    import xoa.meta as xmeta
    register_cf()
    yield
    xmeta.reset_cache(memory=True)


@pytest.fixture(scope="module")
def synth_model_files(tmp_path_factory):
    """A small gridded (thetao/so) product covering the glider sample's own
    domain (lon ~-1.14, lat ~56.6) and time window (2024-08-16)."""
    outdir = tmp_path_factory.mktemp("synth_model")

    lon = np.linspace(-1.3, -0.9, 6).astype("float32")
    lat = np.linspace(56.4, 56.8, 6).astype("float32")
    depth = np.array([0.5, 5., 10., 20., 40., 60., 100.], dtype="float32")
    time = pd.date_range("2024-08-15", "2024-08-17", freq="6h")

    rng = np.random.default_rng(1)
    thetao = (15 + rng.normal(0, 0.5, size=(len(time), len(depth), len(lat), len(lon)))).astype("float32")
    so = (35 + rng.normal(0, 0.2, size=(len(time), len(depth), len(lat), len(lon)))).astype("float32")

    def make(varname, data):
        return xr.Dataset(
            {varname: (("time", "depth", "latitude", "longitude"), data)},
            coords={"time": time, "depth": depth, "latitude": lat, "longitude": lon},
        )

    temp_nc = outdir / "synth_model_temp.nc"
    sal_nc = outdir / "synth_model_sal.nc"
    make("thetao", thetao).to_netcdf(temp_nc)
    make("so", so).to_netcdf(sal_nc)
    return outdir


@pytest.fixture(scope="module")
def comp_hydrosection_run(tmp_path_factory, synth_model_files):
    """Run the real comp_hydrosection load->coloc->output pipeline once
    (module-scoped: the load+coloc stages take ~1 min against real data)
    and return the path to the produced "sections" output zarr."""
    from armoor.cli.main import main_comp, _init_heavy
    _init_heavy()

    tmp_path = tmp_path_factory.mktemp("comp_hydrosection_run")
    cfgfile = tmp_path / "comp_hydrosection.cfg"
    cfgfile.write_text(f"""
[data]
    [[model]]
    name=synthmodel
    path="{synth_model_files}/synth_model_[temp,sal].nc"
    fmt=cmems_model
    [[glider]]
    name=glider mission
    path={GLIDER_SAMPLE}
    fmt=cmems_insitu
    platform=glider
    ref=True
[outputs]
    fmt=png
    [[hydrosections]]
    otype=sections
""")

    metafile = tmp_path / "metazones.cfg"
    metafile.write_text("""
[hydro]
    name=hydro
    tbound=2024-08-15,2024-08-17
    polygon=(56.4,-1.3),(56.8,-1.3),(56.8,-0.9),(56.4,-0.9)
""")

    import os
    cwd = os.getcwd()
    os.chdir(tmp_path)
    try:
        main_comp(
            cfgfile=cfgfile,
            metafile=metafile,
            metazones=["hydro"],
            func_comp="comp_hydrosection",
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
            tmp_path / "comp_hydrosection" / "output" / "hydro" /
            "glider mission" / "sections" / "None" / "all.zarr"
        )
        assert zarr_path.exists(), f"expected output not found: {zarr_path}"
        return zarr_path
    finally:
        os.chdir(cwd)


@pytest.fixture(scope="module")
def synth_model_files_seasoar(tmp_path_factory):
    """A small gridded (thetao/so) product covering the real seasoar
    sample's own domain (lon ~-9.6/-8.5, lat ~46.5/46.8) and time window
    (2026-07-12/13)."""
    outdir = tmp_path_factory.mktemp("synth_model_seasoar")

    lon = np.linspace(-9.6, -8.5, 6).astype("float32")
    lat = np.linspace(46.5, 46.8, 6).astype("float32")
    depth = np.array([0.5, 5., 10., 20., 40., 60., 100., 150., 200., 300.], dtype="float32")
    time = pd.date_range("2026-07-12", "2026-07-13", freq="3h")

    rng = np.random.default_rng(2)
    thetao = (16 + rng.normal(0, 1.0, size=(len(time), len(depth), len(lat), len(lon)))).astype("float32")
    so = (35.4 + rng.normal(0, 0.1, size=(len(time), len(depth), len(lat), len(lon)))).astype("float32")

    def make(varname, data):
        return xr.Dataset(
            {varname: (("time", "depth", "latitude", "longitude"), data)},
            coords={"time": time, "depth": depth, "latitude": lat, "longitude": lon},
        )

    temp_nc = outdir / "synth_model_temp.nc"
    sal_nc = outdir / "synth_model_sal.nc"
    make("thetao", thetao).to_netcdf(temp_nc)
    make("so", so).to_netcdf(sal_nc)
    return outdir


@pytest.fixture(scope="module")
def comp_hydrosection_run_seasoar(tmp_path_factory, synth_model_files_seasoar):
    """Run the real comp_hydrosection pipeline against the real seasoar.nc
    sample (``fmt=odar``, no ``platform=``): a towed-CTD section with only
    raw conductivity, no ready-made salinity -- exercises the
    conductivity-to-salinity oceanvars fallback end-to-end, not just the
    glider-decoding path already covered by `comp_hydrosection_run`."""
    from armoor.cli.main import main_comp, _init_heavy
    _init_heavy()

    tmp_path = tmp_path_factory.mktemp("comp_hydrosection_run_seasoar")
    cfgfile = tmp_path / "comp_hydrosection.cfg"
    cfgfile.write_text(f"""
[data]
    [[model]]
    name=synthmodel
    path="{synth_model_files_seasoar}/synth_model_[temp,sal].nc"
    fmt=cmems_model
    [[seasoar]]
    name=seasoar section
    path={SEASOAR_SAMPLE}
    fmt=odar
    ref=True
[outputs]
    fmt=png
    [[hydrosections]]
    otype=sections
""")

    metafile = tmp_path / "metazones.cfg"
    metafile.write_text("""
[hydro]
    name=hydro
    tbound=2026-07-12,2026-07-13
    polygon=(46.5,-9.6),(46.8,-9.6),(46.8,-8.5),(46.5,-8.5)
""")

    import os
    cwd = os.getcwd()
    os.chdir(tmp_path)
    try:
        main_comp(
            cfgfile=cfgfile,
            metafile=metafile,
            metazones=["hydro"],
            func_comp="comp_hydrosection",
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
            tmp_path / "comp_hydrosection" / "output" / "hydro" /
            "seasoar section" / "sections" / "None" / "all.zarr"
        )
        assert zarr_path.exists(), f"expected output not found: {zarr_path}"
        return zarr_path
    finally:
        os.chdir(cwd)


def test_seasoar_salinity_derived_from_conductivity(comp_hydrosection_run_seasoar):
    """The real seasoar file only carries raw conductivity -- "sal" must
    still show up in the coloc'd output, derived via
    `armoor.oceanvars.OceanVarsAccessor.sel_sal`'s conductivity
    fallback, with physically plausible open-ocean values."""
    dt = xr.open_datatree(comp_hydrosection_run_seasoar)
    ref_ds = dt["synthmodel"]["ref"]["data"]["0"].to_dataset()
    assert "sal" in ref_ds.data_vars
    assert "ptemp" in ref_ds.data_vars
    sal_valid = ref_ds.sal.values[~np.isnan(ref_ds.sal.values)]
    assert sal_valid.size > 0
    assert np.all((sal_valid > 30) & (sal_valid < 40))
    dt.close()


def test_seasoar_sections_plot_renders_all_variables(comp_hydrosection_run_seasoar):
    """PlotComp.sections() must render for the odar/seasoar-decoded section
    too, not just glider -- same otype, different decode path."""
    from armoor.comp.plot import PlotComp

    pc = PlotComp(str(comp_hydrosection_run_seasoar), "comp_hydrosection", "hydro")
    pc.call("sections")
    pc.clean()

    saved_vars = {
        f.split("sections_")[1].split("_synthmodel")[0] for f in pc.saved_files
    }
    assert {"ptemp", "sal", "pdens", "temp", "sndspeed", "cgeo"}.issubset(saved_vars)


def test_pipeline_produces_three_signature_groups(comp_hydrosection_run):
    """The z-resolved group (ptemp/sal/pdens/temp/sndspeed), the z-less
    "mld" group, and the "cgeo" (pair, z) group must land as three
    distinct, non-colliding coloc files -- regression test for the
    filename-collision bug where two "z"-having groups shared the same
    vlevel tag ("profile") and the second write silently clobbered the
    first; the tag is now derived from each group's own variable names."""
    dt = xr.open_datatree(comp_hydrosection_run)
    ref_data = dt["synthmodel"]["ref"]["data"]
    groups = {frozenset(ref_data[c].to_dataset().data_vars) for c in ref_data.children}
    assert frozenset({"ptemp", "sal", "pdens", "temp", "sndspeed"}) in groups
    assert frozenset({"mld"}) in groups
    assert frozenset({"cgeo"}) in groups
    dt.close()


def test_pipeline_cgeo_has_pair_dim(comp_hydrosection_run):
    """The geostrophic-velocity group must be indexed by "pair" (one value
    per pair of consecutive glider profiles), not "time", with one fewer
    point than the number of stations, and carry its own lon_pair/lat_pair/
    depth_pair coordinates (renamed on merge to avoid colliding with the
    per-station lon/lat/depth -- see CompHydrosection.compute_oceanvars)."""
    dt = xr.open_datatree(comp_hydrosection_run)
    ref_data = dt["synthmodel"]["ref"]["data"]
    cgeo_ds = next(
        ref_data[c].to_dataset() for c in ref_data.children
        if frozenset(ref_data[c].to_dataset().data_vars) == frozenset({"cgeo"})
    )
    assert cgeo_ds.cgeo.dims == ("pair", "z")
    assert cgeo_ds.sizes["pair"] == 5  # 6 glider profiles -> 5 pairs
    assert "lon_pair" in cgeo_ds.coords
    assert "lat_pair" in cgeo_ds.coords
    assert "depth_pair" in cgeo_ds.coords
    dt.close()


def test_pipeline_aligns_product_onto_reference_depth(comp_hydrosection_run):
    """The product's depth-resolved group must be vinterp'd onto the
    reference's own (per-profile) depth levels -- same "z" size on both
    sides, matching the real glider sample's 29 depth bins."""
    dt = xr.open_datatree(comp_hydrosection_run)
    ref_ds = dt["synthmodel"]["ref"]["data"]["0"].to_dataset()
    prod_ds = dt["synthmodel"]["prod"]["data"]["0"].to_dataset()
    assert ref_ds.sizes["time"] == 6
    assert ref_ds.sizes["z"] == prod_ds.sizes["z"] == 29
    dt.close()


def test_pipeline_diff_is_finite_where_expected(comp_hydrosection_run):
    """Real dive profiles (indices 3-5) must produce finite diffs; the
    all-NaN surface-only profiles (indices 0-2, no CTD depth data on the
    real glider sample) must stay NaN, not crash the pipeline."""
    dt = xr.open_datatree(comp_hydrosection_run)
    diff = dt["synthmodel"]["comp"]["diff"]["0"].to_dataset()["ptemp"]
    assert bool(diff.isel(time=slice(0, 3)).isnull().all())
    assert bool(diff.isel(time=slice(3, 6)).notnull().any())
    dt.close()


def test_sections_plot_renders_all_variables(comp_hydrosection_run):
    """PlotComp.sections() must render one PNG per comp_var actually
    present (5 depth-resolved pcolormesh panels + 1 mld curve), without
    crashing on the NaN-depth surface segments."""
    from armoor.comp.plot import PlotComp

    pc = PlotComp(str(comp_hydrosection_run), "comp_hydrosection", "hydro")
    pc.call("sections")
    pc.clean()

    saved_vars = {
        f.split("sections_")[1].split("_synthmodel")[0] for f in pc.saved_files
    }
    assert saved_vars == {"ptemp", "sal", "pdens", "temp", "sndspeed", "mld", "cgeo"}
    for f in pc.saved_files:
        from pathlib import Path
        assert Path(f).stat().st_size > 0
