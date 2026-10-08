"""
Unit tests for open_decode_* functions.

This test suite uses pytest and numpy-style docstrings to test all the 
open_decode_* functions with sample data files stored in the library's 
test data directory.
"""

import pytest
import xarray as xr
import numpy as np
import pandas as pd
from pathlib import Path
import tempfile
import netCDF4 as nc4
from datetime import datetime

from armoor import ROOTDIR, ArmoorError
from armoor.data.open_decode import (
    open_decode,
    open_decode_arpege_insta,
    open_decode_sst_satellite,
    open_decode_cmems_model,
    open_decode_hycom,
    open_decode_woa18,
    open_decode_bobyclim,
    open_decode_cora_insitu,
    open_decode_cmems_insitu,
    open_decode_odar,
    open_decode_croco,
    open_decode_eddy_pet,
    open_decode_eddy_sacso,
    open_decode_eddy_shoot,
    get_paths,
    register_cf,
    get_decoder,
    ArmoorDecoder,
    ArpegeInstaDecoder,
    BobyclimDecoder,
    CmemsInsituDecoder,
    CmemsModelDecoder,
    CoraInsituDecoder,
    CrocoDecoder,
    EddyPetDecoder,
    EddySacsoDecoder,
    EddyShootDecoder,
    HycomDecoder,
    OdarDecoder,
    SloopDecoder,
    SstSatelliteDecoder,
    Woa18Decoder,
)

# Test data directory
TEST_DATA_DIR = Path(ROOTDIR) / "_samples"


@pytest.fixture(scope="module", autouse=True)
def register_and_reset_cf():
    """Register armoor CF specs for the module and reset xoa.meta registry on teardown."""
    import xoa.meta as xmeta
    register_cf()
    yield
    xmeta.reset_cache(memory=True)


@pytest.fixture(scope="module")
def setup_test_data():
    """
    Create test data directory and sample files for testing.
    
    Returns
    -------
    dict
        Dictionary containing paths to test files for each format.
    """    
    test_files = {}
    
    # Create sample NetCDF files for different formats
    test_files['cmems_model'] = TEST_DATA_DIR / "cmems_glo12_*.nc"
    test_files['hycom'] = TEST_DATA_DIR / "hycom_*.nc"
    test_files['woa18'] = TEST_DATA_DIR / "woa18_*.nc"
    test_files['cmems_sst_l4'] = TEST_DATA_DIR / "cmems_sst_l4.nc"
    test_files['cmems_sst_l3'] = TEST_DATA_DIR / "cmems_sst_l3.nc"
    test_files['cersat_sst_l3'] = TEST_DATA_DIR / "20210623-IFR-L3C_GHRSST-SSTsubskin-ODYSSEA-GLOB_010_adjusted-v2.0-fv1.0.nc"
    test_files['cmems_insitu_argo'] = TEST_DATA_DIR / "*_PR_PF_*.nc"
    test_files['cmems_insitu_glider'] = TEST_DATA_DIR / "*_PR_GL_*.nc"
    test_files['cmems_insitu_mooring'] = TEST_DATA_DIR / "*_TS_MO_*.nc"
    test_files['cmems_insitu_drifter'] = TEST_DATA_DIR / "*_TS_DB_*.nc"
    test_files['odar_seasoar'] = TEST_DATA_DIR / "seasoar.nc"
    test_files['croco'] = TEST_DATA_DIR / "croco_his.nc"
    test_files['croco_v1'] = TEST_DATA_DIR / "croco_v1.3.nc"
    test_files['eddies_pet'] = TEST_DATA_DIR / "eddy-sample_py-eddy-tracker*"
    test_files['eddies_sacso'] = TEST_DATA_DIR / "eddy-sample_sacso.txt"
    test_files['eddies_shoot'] = TEST_DATA_DIR / "eddy-sample_shoot.nc"

    yield test_files
    
    # Cleanup is handled by pytest tmpdir fixture if needed


# ============================================================================
# Test get_paths function
# ============================================================================

class TestGetPaths:
    """Tests for the get_paths function."""
    
    def test_get_paths_simple_glob(self, tmp_path):
        """
        Test get_paths with simple glob pattern.
        
        Parameters
        ----------
        tmp_path : Path
            Pytest fixture for temporary directory.
        """
        # Create test files
        for i in range(3):
            (tmp_path / f"test_{i}.nc").touch()
        
        pattern = str(tmp_path / "test_*.nc")
        result = get_paths(pattern)
        
        assert len(result) == 3
        assert all(Path(p).exists() for p in result)
    
    def test_get_paths_list_expansion(self, tmp_path):
        """
        Test get_paths with list expansion syntax.
        
        Parameters
        ----------
        tmp_path : Path
            Pytest fixture for temporary directory.
        """
        # Create test files
        (tmp_path / "test_a.nc").touch()
        (tmp_path / "test_b.nc").touch()
        
        pattern = str(tmp_path / "test_[a,b].nc")
        result = get_paths(pattern)
        
        assert len(result) == 2
        assert all(Path(p).exists() for p in result)
    
    def test_get_paths_comma_separated(self, tmp_path):
        """
        Test get_paths with comma-separated paths.
        
        Parameters
        ----------
        tmp_path : Path
            Pytest fixture for temporary directory.
        """
        file1 = tmp_path / "test1.nc"
        file2 = tmp_path / "test2.nc"
        file1.touch()
        file2.touch()
        
        pattern = f"{file1},{file2}"
        result = get_paths(pattern)
        
        assert len(result) == 2
    
    def test_get_paths_empty_pattern(self):
        """Test get_paths raises error for empty pattern."""
        with pytest.raises(Exception):  # Should raise ArmoorError
            get_paths("")
    
    def test_get_paths_not_found(self, tmp_path):
        """Test get_paths raises error when no files found."""
        pattern = str(tmp_path / "nonexistent_*.nc")
        with pytest.raises(Exception):  # Should raise ArmoorError
            get_paths(pattern)
            

class TestOpenDecodeSST:
    """Tests for open_decode_cmems_model function."""
    
    def test_open_decode_cmems_sst_l4(self, setup_test_data):
        """
        Test basic functionality of open_decode_cmems_model.
        
        Parameters
        ----------
        setup_test_data : dict
            Fixture containing test file paths.
        """
        filepath = setup_test_data['cmems_sst_l4']
        result = open_decode_sst_satellite([filepath], fmt="cmems_sst_l4")
        
        assert isinstance(result, xr.Dataset)
        assert 'x' in result.dims
        assert 'y' in result.dims
        assert 'time' in result.dims
        
    def test_open_decode_cmems_sst_l3(self, setup_test_data):
        """
        Test basic functionality of open_decode_cmems_model.
        
        Parameters
        ----------
        setup_test_data : dict
            Fixture containing test file paths.
        """
        filepath = setup_test_data['cmems_sst_l3']
        result = open_decode_sst_satellite([filepath], fmt="cmems_sst_l3")
        
        assert isinstance(result, xr.Dataset)
        assert 'x' in result.dims
        assert 'y' in result.dims
        assert 'time' in result.dims
        
    def test_open_decode_cersat_sst_l3(self, setup_test_data):
        """
        Test basic functionality of open_decode_cmems_model.
        
        Parameters
        ----------
        setup_test_data : dict
            Fixture containing test file paths.
        """
        filepath = setup_test_data['cersat_sst_l3']
        result = open_decode_sst_satellite([filepath], fmt="cersat_sst_l3")
        
        assert isinstance(result, xr.Dataset)
        assert 'x' in result.dims
        assert 'y' in result.dims
        assert 'time' in result.dims

# ============================================================================
# Test open_decode_cmems_model
# ============================================================================

class TestOpenDecodeCmemsModel:
    """Tests for open_decode_cmems_model function."""
    
    def test_open_decode_cmems_model_basic(self, setup_test_data):
        """
        Test basic functionality of open_decode_cmems_model.
        
        Parameters
        ----------
        setup_test_data : dict
            Fixture containing test file paths.
        """
        filepath = setup_test_data['cmems_model']
        result = open_decode_cmems_model(get_paths(str(filepath)))
        
        assert isinstance(result, xr.Dataset)
        assert 'x' in result.dims
        assert 'y' in result.dims
        assert 'z' in result.dims
        assert 'time' in result.dims
    
    def test_open_decode_cmems_model_coordinates(self, setup_test_data):
        """
        Test coordinate swapping in open_decode_cmems_model.
        
        Parameters
        ----------
        setup_test_data : dict
            Fixture containing test file paths.
        """
        filepath = setup_test_data['cmems_model']
        result = open_decode_cmems_model(get_paths(str(filepath)))
        
        assert 'lon' in result.coords
        assert 'lat' in result.coords
        assert 'time' in result.coords
        assert len(result.lon.dims) == 2
        assert len(result.lat.dims) == 2
        assert set(('y', 'x')).issubset(result.lon.dims)
        assert set(('y', 'x')).issubset(result.lat.dims)
    
    def test_open_decode_cmems_model_depth_broadcast(self, setup_test_data):
        """
        Test depth broadcasting in open_decode_cmems_model.
        
        Parameters
        ----------
        setup_test_data : dict
            Fixture containing test file paths.
        """
        filepath = setup_test_data['cmems_model']
        result = open_decode_cmems_model(get_paths(str(filepath)))
        
        if 'depth' in result:
            # Depth should be reset to coords
            assert 'depth' in result.coords
            assert len(result.depth.dims) == 4


# ============================================================================
# Test open_decode_hycom
# ============================================================================

class TestOpenDecodeHycom:
    """Tests for open_decode_hycom function."""
    
    def test_open_decode_hycom_basic(self, setup_test_data):
        """
        Test basic functionality of open_decode_hycom.
        
        Parameters
        ----------
        setup_test_data : dict
            Fixture containing test file paths.
        """
        filepath = setup_test_data['hycom']
        result = open_decode_hycom(get_paths(str(filepath)))
        
        assert isinstance(result, xr.Dataset)
        assert 'x' in result.dims
        assert 'y' in result.dims
        assert 'z' in result.dims
        assert 'time' in result.dims
    
    def test_open_decode_hycom_velocity_shift(self, setup_test_data):
        """
        Test velocity field shifting in open_decode_hycom.
        
        Parameters
        ----------
        setup_test_data : dict
            Fixture containing test file paths.
        """
        filepath = setup_test_data['hycom']
        result = open_decode_hycom(get_paths(str(filepath)))
        
        assert result['u'].dims == result['ptemp'].dims
        assert 'z' in result['u'].dims
    
    def test_open_decode_hycom_duplicate_times(self, setup_test_data):
        """
        Test removal of duplicate times in open_decode_hycom.
        
        Parameters
        ----------
        setup_test_data : dict
            Fixture containing test file paths.
        """
        filepath = setup_test_data['hycom']
        result = open_decode_hycom(get_paths(str(filepath)))
        
        # Check no duplicate times
        assert len(result.time) == len(np.unique(result.time))

    def test_open_decode_hycom_sorts_time_across_groups(self, tmp_path):
        """Regression test: per-variable files are grouped by their exact
        time range (_time_key) and concatenated group-by-group in
        `_groups` insertion order, which follows `sorted_paths` (alphabetical
        filename order) -- not chronological order. Naming the
        chronologically later group's files so they sort first (a real
        pattern seen on an actual HYCOM run) used to produce a
        non-monotonic "time" axis, since the post-merge dedup
        (`ds.sel(time=~...duplicated())`) preserves this pre-existing
        order instead of sorting it."""
        src_dir = TEST_DATA_DIR
        n_first = 30
        for var in ("h", "saln", "temp", "u", "v"):
            ds = xr.open_dataset(src_dir / f"hycom_{var}_3D.nc", decode_times=False)
            # Alphabetically-first prefix ("aaa_") gets the chronologically
            # LATER half of the time series; alphabetically-last ("zzz_")
            # gets the EARLIER half -- inverted on purpose.
            ds.isel(time=slice(n_first, None)).to_netcdf(tmp_path / f"aaa_hycom_{var}_3D.nc")
            ds.isel(time=slice(0, n_first)).to_netcdf(tmp_path / f"zzz_hycom_{var}_3D.nc")
            ds.close()

        result = open_decode_hycom(get_paths(str(tmp_path / "*_hycom_*_3D.nc")))

        time_index = pd.DatetimeIndex(result["time"].values)
        assert time_index.is_monotonic_increasing

    def test_open_decode_hycom_model_coordinates(self, setup_test_data):
        """
        Test coordinate swapping in open_decode_hycom.
        
        Parameters
        ----------
        setup_test_data : dict
            Fixture containing test file paths.
        """
        filepath = setup_test_data['hycom']
        result = open_decode_hycom(get_paths(str(filepath)))
        
        assert 'lon' in result.coords
        assert 'lat' in result.coords
        assert 'time' in result.coords
        assert len(result.lon.dims) == 2
        assert len(result.lat.dims) == 2
        assert set(('y', 'x')).issubset(result.lon.dims)
        assert set(('y', 'x')).issubset(result.lat.dims)
        
    def test_open_decode_hycom_model_depth(self, setup_test_data):
        """
        Test depth broadcasting in open_decode_hycom.
        
        Parameters
        ----------
        setup_test_data : dict
            Fixture containing test file paths.
        """
        filepath = setup_test_data['hycom']
        result = open_decode_hycom(get_paths(str(filepath)))
        
        if 'depth' in result:
            # Depth should be reset to coords
            assert 'depth' in result.coords
            assert len(result.depth.dims) == 4
            assert set(('time', 'z', 'y', 'x')).issubset(result.depth.dims)

# ============================================================================
# Test open_decode_woa18
# ============================================================================

class TestOpenDecodeWoa18:
    """Tests for open_decode_woa18 function."""
    
    def test_open_decode_woa18_basic(self, setup_test_data):
        """
        Test basic functionality of open_decode_woa18.
        
        Parameters
        ----------
        setup_test_data : dict
            Fixture containing test file paths.
        """
        filepath = setup_test_data['woa18']
        result = open_decode_woa18(get_paths(str(filepath)))
        
        assert 'x' in result.dims
        assert 'y' in result.dims
        assert 'z' in result.dims
        assert 'time' in result.dims
    
    def test_open_decode_woa18_variable_renaming(self, setup_test_data):
        """
        Test variable renaming in open_decode_woa18.
        
        Parameters
        ----------
        setup_test_data : dict
            Fixture containing test file paths.
        """
        filepath = setup_test_data['woa18']
        result = open_decode_woa18(get_paths(str(filepath)))
        assert 'sal' in result 
        assert 'temp' in result
    
    def test_open_decode_woa18_coordinates(self, setup_test_data):
        """
        Test coordinate swapping in open_decode_hycom.
        
        Parameters
        ----------
        setup_test_data : dict
            Fixture containing test file paths.
        """
        filepath = setup_test_data['woa18']
        result = open_decode_woa18(get_paths(str(filepath)))

        assert 'lon' in result.coords
        assert 'lat' in result.coords
        assert 'time' in result.coords
        assert len(result.lon.dims) == 2
        assert len(result.lat.dims) == 2
        assert set(('y', 'x')).issubset(result.lon.dims)
        assert set(('y', 'x')).issubset(result.lat.dims)
    
    def test_open_decode_woa18_lon_conversion(self, setup_test_data):
        """
        Test longitude conversion in open_decode_woa18.
        
        Parameters
        ----------
        setup_test_data : dict
            Fixture containing test file paths.
        """
        filepath = setup_test_data['woa18']
        result = open_decode_woa18(get_paths(str(filepath)))
        
        # Check that longitudes are in [-180, 180] range
        if 'lon' in result.coords:
            assert result.lon.min() >= -180
            assert result.lon.max() <= 180

    def test_open_decode_woa18_time_survives_netcdf_roundtrip(self, setup_test_data, tmp_path):
        """Regression test: the raw "months since 1955-01-01" units/calendar
        attrs used to survive the ceil/trunc arithmetic that turns "time"
        into a plain 1-12 month index, so saving this dataset to netcdf
        and reopening it (as armoor.data.output does for every
        intermediate file) crashed with "'months since' units only
        allowed for '360_day' calendar" -- the stale attrs must be
        cleared so a plain numeric roundtrip works."""
        filepath = setup_test_data['woa18']
        result = open_decode_woa18(get_paths(str(filepath)))

        assert result["time"].attrs == {}

        nc_path = tmp_path / "woa18_roundtrip.nc"
        result.to_netcdf(nc_path)
        reopened = xr.open_dataset(nc_path)
        assert reopened["time"].values.tolist() == result["time"].values.tolist()

    def test_open_decode_woa18_derives_materialized_ptemp(self, setup_test_data):
        """ptemp must be derived (not left as "temp") and materialized
        (not dask-backed) -- deriving it lazily previously corrupted the
        dask graph once this dataset was later wrapped in further
        dask.delayed/compute calls downstream."""
        filepath = setup_test_data['woa18']
        result = open_decode_woa18(get_paths(str(filepath)))

        assert "ptemp" in result
        assert not result["ptemp"].chunks
        assert "pres" not in result


# ============================================================================
# Test open_decode_cmems_insitu
# ============================================================================

class TestOpenDecodeCmemsInsitu:
    """Tests for open_decode_cmems_insitu function."""
    
    def test_open_decode_cmems_insitu_argo(self, setup_test_data):
        """
        Test open_decode_cmems_insitu with Argo platform.
        
        Parameters
        ----------
        setup_test_data : dict
            Fixture containing test file paths.
        """
        filepath = setup_test_data['cmems_insitu_argo']
        result = open_decode_cmems_insitu(get_paths(str(filepath)), platform='argo')
        
        assert isinstance(result, xr.Dataset)
        assert 'time' in result.dims
        assert 'z' in result.dims
        assert ('time', ) == result.lon.dims
        assert ('time', ) == result.lat.dims
        assert 'depth' in result.coords
        assert set(('time', 'z')).issubset(result.depth.dims)
        
    def test_open_decode_cmems_insitu_glider(self, setup_test_data):
        """
        Test open_decode_cmems_insitu with glider platform.
        
        Parameters
        ----------
        setup_test_data : dict
            Fixture containing test file paths.
        """
        filepath = setup_test_data['cmems_insitu_glider']
        result = open_decode_cmems_insitu(get_paths(str(filepath)), platform='glider')
        
        assert isinstance(result, list)
        assert all(isinstance(ds, xr.Dataset) for ds in result)
        assert all('lon' in ds.coords for ds in result)
        assert all('lat' in ds.coords for ds in result)
        assert all(('time', ) == ds.lon.dims for ds in result)
        assert all(('time', ) == ds.lat.dims for ds in result)
        assert all('depth' in ds.coords for ds in result)
        assert all(set(('time', 'z')).issubset(ds.depth.dims) for ds in result)
        
    def test_open_decode_cmems_insitu_mooring(self, setup_test_data):
        """
        Test open_decode_cmems_insitu with glider platform.
        
        Parameters
        ----------
        setup_test_data : dict
            Fixture containing test file paths.
        """
        filepath = setup_test_data['cmems_insitu_mooring']
        result = open_decode_cmems_insitu(get_paths(str(filepath)), platform='mooring')
        assert isinstance(result, list)
        assert all(isinstance(ds, xr.Dataset) for ds in result)
        assert all('lon' in ds.coords for ds in result)
        assert all('lat' in ds.coords for ds in result)
        assert all(np.float32 == ds.lon.dtype for ds in result)
        assert all(np.float32 == ds.lat.dtype for ds in result)
        assert all('depth' in ds.coords for ds in result)
        # Real moorings vary: some report a fixed position (scalar lon/lat),
        # others a slightly drifting one ((time,) lon/lat) -- both are valid.
        assert all(ds.lon.dims in ((), ('time',)) for ds in result)
        assert all(ds.lat.dims in ((), ('time',)) for ds in result)
        assert all(('z', ) == ds.depth.dims for ds in result)
        
    def test_open_decode_cmems_insitu_drifter(self, setup_test_data):
        """
        Test open_decode_cmems_insitu with glider platform.
        
        Parameters
        ----------
        setup_test_data : dict
            Fixture containing test file paths.
        """
        filepath = setup_test_data['cmems_insitu_drifter']
        result = open_decode_cmems_insitu(get_paths(str(filepath)), platform='drifter')
        assert isinstance(result, list)
        assert all(isinstance(ds, xr.Dataset) for ds in result)
        assert all('lon' in ds.coords for ds in result)
        assert all('lat' in ds.coords for ds in result)
        assert all(np.float32 == ds.lon.dtype for ds in result)
        assert all(np.float32 == ds.lat.dtype for ds in result)
        assert all('depth' in ds.coords for ds in result)
        assert all(('time',) == ds.lon.dims for ds in result)
        assert all(('time',) == ds.lat.dims for ds in result)
        assert all(('z', ) == ds.depth.dims for ds in result)


# ============================================================================
# Test open_decode_odar
# ============================================================================

class TestOpenDecodeOdar:
    """Tests for open_decode_odar function, against the real seasoar.nc
    sample (an ODAR-processed towed-CTD section, no CMEMS/CORA involved)."""

    def test_open_decode_odar_seasoar(self, setup_test_data):
        """
        Test open_decode_odar against a real seasoar section.

        Parameters
        ----------
        setup_test_data : dict
            Fixture containing test file paths.
        """
        filepath = setup_test_data['odar_seasoar']
        result = open_decode_odar(get_paths(str(filepath)))

        assert isinstance(result, list)
        assert len(result) == 1
        ds = result[0]
        assert isinstance(ds, xr.Dataset)
        assert 'time' in ds.dims
        assert 'z' in ds.dims
        assert 'depth' not in ds.dims  # renamed to "z", kept as a coordinate
        assert ('time',) == ds.lon.dims
        assert ('time',) == ds.lat.dims
        assert 'depth' in ds.coords
        assert ('z',) == ds.depth.dims
        # Raw sensor output, not yet derived -- oceanvars.sel_sal() does that
        # lazily downstream (see TestOceanVars in test_oceanvars.py).
        assert 'conduct' in ds.data_vars
        assert 'sal' not in ds.data_vars
        assert np.issubdtype(ds.time.dtype, np.datetime64)
        assert ds.attrs.get('ODAR_DATASET_TYPE') == 'seasoar'


# ============================================================================
# Test open_decode_croco
# ============================================================================

class TestOpenDecodeCroco:
    """Tests for open_decode_croco function."""
    
    def test_open_decode_croco_basic(self, setup_test_data):
        """
        Test basic functionality of open_decode_croco.
        
        Parameters
        ----------
        setup_test_data : dict
            Fixture containing test file paths.
        """
        filepath = setup_test_data['croco']
        result = open_decode_croco([filepath])
        
        assert isinstance(result, xr.Dataset)
        assert set(('time', 'z', 'y', 'x')).issubset(result.dims)
        assert 'lon' in result.coords
        assert 'lat' in result.coords
        assert 'time' in result.coords
        assert len(result.lon.dims) == 2
        assert len(result.lat.dims) == 2
        assert set(('y', 'x')).issubset(result.lon.dims)
        assert set(('y', 'x')).issubset(result.lat.dims)
        
    def test_open_decode_croco_v1(self, setup_test_data):
        """
        Test basic functionality of open_decode_croco.
        
        Parameters
        ----------
        setup_test_data : dict
            Fixture containing test file paths.
        """
        filepath = setup_test_data['croco_v1']
        result = open_decode_croco([filepath])
        
        assert isinstance(result, xr.Dataset)
        assert set(('time', 'z', 'y', 'x')).issubset(result.dims)
        assert 'lon' in result.coords
        assert 'lat' in result.coords
        assert 'time' in result.coords
        assert len(result.lon.dims) == 2
        assert len(result.lat.dims) == 2
        assert set(('y', 'x')).issubset(result.lon.dims)
        assert set(('y', 'x')).issubset(result.lat.dims)
        
    
    def test_open_decode_croco_sigma_decode(self, setup_test_data):
        """
        Test sigma coordinate decoding in open_decode_croco.
        
        Parameters
        ----------
        setup_test_data : dict
            Fixture containing test file paths.
        """
        filepath = setup_test_data['croco']
        result = open_decode_croco([filepath])
        
        # Sigma coordinates should be removed after decoding
        assert 'sig_rho' not in result.dims
        assert 'sig_w' not in result.dims
        assert 'z' in result.dims
        assert 'depth' in result.coords
        assert set(('time', 'z', 'y', 'x')).issubset(result.depth.dims)
    
    def test_open_decode_croco_velocity_stagger(self, setup_test_data):
        """
        Test velocity field destaggering in open_decode_croco.
        
        Parameters
        ----------
        setup_test_data : dict
            Fixture containing test file paths.
        """
        filepath = setup_test_data['croco']
        result = open_decode_croco([filepath])
        
        if 'u' in result and 'v' in result:
            # After relocation, u and v should be on same grid
            assert 'x_u' not in result.dims
            assert 'y_v' not in result.dims
    
    def test_open_decode_croco_rotation(self, setup_test_data):
        """
        Test velocity rotation in open_decode_croco.
        
        Parameters
        ----------
        setup_test_data : dict
            Fixture containing test file paths.
        """
        filepath = setup_test_data['croco']
        result = open_decode_croco([filepath])
        
        # Angle should be removed after rotation
        assert 'angle' not in result


# ============================================================================
# Test open_decode_eddies
# ============================================================================

class TestOpenDecodeEddies:
    """Tests for the open_decode_eddy_* functions."""

    def test_open_decode_eddies_pet(self, setup_test_data):
        """
        Test open_decode with py-eddy-tracker format.

        Parameters
        ----------
        setup_test_data : dict
            Fixture containing test file paths.
        """
        filepath = setup_test_data['eddies_pet']
        ds = open_decode_eddy_pet(get_paths(str(filepath)))

        assert isinstance(ds, xr.Dataset)
        assert set(["obs", "nb_sample"]).issubset(ds.dims)
        assert set(["time", "nb_sample"]).issubset(ds.coords)
        assert ds.time.dims == ("obs",)
        assert ds.nb_sample.dims == ("nb_sample",)
        assert "eddy_type" in ds.data_vars
        assert "contour_lon" in ds.data_vars
        assert "contour_lat" in ds.data_vars
        assert "center_lon" in ds.data_vars
        assert "center_lat" in ds.data_vars
        assert "vmax_area" in ds.data_vars

    def test_open_decode_eddies_sacso(self, setup_test_data):
        """
        Test open_decode with sacso format.

        Parameters
        ----------
        setup_test_data : dict
            Fixture containing test file paths.
        """
        filepath = setup_test_data['eddies_sacso']
        ds = open_decode_eddy_sacso(get_paths(str(filepath)))

        assert isinstance(ds, xr.Dataset)
        assert set(["obs", "nb_sample"]).issubset(ds.dims)
        assert set(["time", "nb_sample"]).issubset(ds.coords)
        assert ds.time.dims == ("obs",)
        assert ds.nb_sample.dims == ("nb_sample",)
        assert "eddy_type" in ds.data_vars
        assert "contour_lon" in ds.data_vars
        assert "contour_lat" in ds.data_vars
        assert "center_lon" in ds.data_vars
        assert "center_lat" in ds.data_vars
        assert "vmax_area" in ds.data_vars

    def test_open_decode_eddies_shoot(self, setup_test_data):
        """
        Test open_decode with shoot format.

        Parameters
        ----------
        setup_test_data : dict
            Fixture containing test file paths.
        """
        filepath = setup_test_data['eddies_shoot']
        ds = open_decode_eddy_shoot(get_paths(str(filepath)))

        assert isinstance(ds, xr.Dataset)
        assert set(["obs", "nb_sample"]).issubset(ds.dims)
        assert set(["time", "nb_sample"]).issubset(ds.coords)
        assert ds.time.dims == ("obs",)
        assert ds.nb_sample.dims == ("nb_sample",)
        assert "eddy_type" in ds.data_vars
        assert "contour_lon" in ds.data_vars
        assert "contour_lat" in ds.data_vars
        assert "center_lon" in ds.data_vars
        assert "center_lat" in ds.data_vars
        assert "vmax_area" in ds.data_vars


# ============================================================================
# Test open_decode main dispatcher
# ============================================================================

class TestOpenDecode:
    """Tests for the main open_decode dispatcher function."""
    
    def test_open_decode_cmems_model(self, setup_test_data):
        """
        Test open_decode with cmems_model format.
        
        Parameters
        ----------
        setup_test_data : dict
            Fixture containing test file paths.
        """
        filepath = setup_test_data['cmems_model']
        result = open_decode(str(filepath), fmt='cmems_model')
        
        assert isinstance(result, xr.Dataset)
    
    def test_open_decode_hycom(self, setup_test_data):
        """
        Test open_decode with hycom format.
        
        Parameters
        ----------
        setup_test_data : dict
            Fixture containing test file paths.
        """
        filepath = setup_test_data['hycom']
        result = open_decode(str(filepath), fmt='hycom')
        
        assert isinstance(result, xr.Dataset)
    
    def test_open_decode_odar(self, setup_test_data):
        """
        Test open_decode with odar format.

        Parameters
        ----------
        setup_test_data : dict
            Fixture containing test file paths.
        """
        filepath = setup_test_data['odar_seasoar']
        result = open_decode(str(filepath), fmt='odar')

        assert isinstance(result, list)
        assert len(result) == 1

    def test_open_decode_unknown_format(self, setup_test_data):
        """
        Test open_decode raises error for unknown format.
        
        Parameters
        ----------
        setup_test_data : dict
            Fixture containing test file paths.
        """
        filepath = setup_test_data['croco']
        with pytest.raises(Exception):
            open_decode(str(filepath), fmt='unknown_format')

    def test_get_decoder_raises_armoor_error_for_unknown_fmt(self):
        """get_decoder itself must raise a clear ArmoorError, not the old
        broken `raise logger.error(...)` (which actually raised a TypeError
        with no useful message)."""
        with pytest.raises(ArmoorError, match="unknown_format"):
            get_decoder("unknown_format")

    @pytest.mark.parametrize("fmt,decoder_cls", [
        ("cmems_insitu", CmemsInsituDecoder),
        ("cora_insitu", CoraInsituDecoder),
        ("cmems_model", CmemsModelDecoder),
        ("armoor", ArmoorDecoder),
        ("cmems_sst_l4", SstSatelliteDecoder),
        ("cmems_sst_l3", SstSatelliteDecoder),
        ("cersat_sst_l3", SstSatelliteDecoder),
        ("hycom", HycomDecoder),
        ("hycom3d", HycomDecoder),
        ("croco", CrocoDecoder),
        ("croco_xios", CrocoDecoder),
        ("sloop", SloopDecoder),
        ("arpege_insta", ArpegeInstaDecoder),
        ("woa18", Woa18Decoder),
        ("bobyclim", BobyclimDecoder),
        ("odar", OdarDecoder),
    ])
    def test_get_decoder_registry_completeness(self, fmt, decoder_cls):
        """Every reachable fmt (including hycom/hycom3d and croco/croco_xios
        aliases) must resolve to its expected Decoder class."""
        assert isinstance(get_decoder(fmt), decoder_cls)

    @pytest.mark.parametrize("fmt,platform", [
        ('cmems_insitu', 'argo'),
        ('cmems_insitu', 'glider'),
        ('cmems_insitu', 'mooring'),
        ('cmems_insitu', 'drifter'),
    ])
    def test_open_decode_insitu_platforms(self, setup_test_data, fmt, platform):
        """
        Test open_decode with different in-situ platforms.
        
        Parameters
        ----------
        setup_test_data : dict
            Fixture containing test file paths.
        fmt : str
            Format name.
        platform : str
            Platform type.
        """
        if platform == 'argo':
            filepath = setup_test_data['cmems_insitu_argo']
        elif platform == 'glider':
            filepath = setup_test_data['cmems_insitu_glider']
        elif platform == 'mooring':
            filepath = setup_test_data['cmems_insitu_mooring']
        elif platform == 'drifter':
            filepath = setup_test_data['cmems_insitu_drifter']
        
        result = open_decode(str(filepath), fmt=fmt, platform=platform)
        
        assert result is not None


# ============================================================================
# Test open_decode_bobyclim
# ============================================================================

def _write_bobyclim_nc(path, time_values, time_dtype="datetime"):
    """Write a minimal synthetic Bobyclim-like netCDF file."""
    lon = np.linspace(-10., 0., 5)
    lat = np.linspace(40., 50., 4)
    depth = np.array([10., 50., 100.])
    nz, ny, nx = len(depth), len(lat), len(lon)
    nt = len(time_values)

    with nc4.Dataset(path, "w") as ds:
        ds.createDimension("time", nt)
        ds.createDimension("depth", nz)
        ds.createDimension("lat", ny)
        ds.createDimension("lon", nx)

        t_var = ds.createVariable("time", "f4", ("time",))
        if time_dtype == "datetime":
            t_var.units = "days since 2000-01-01"
            t_var.calendar = "standard"
            t_var[:] = time_values
        else:
            t_var[:] = time_values

        lon_var = ds.createVariable("lon", "f4", ("lon",))
        lon_var[:] = lon
        lat_var = ds.createVariable("lat", "f4", ("lat",))
        lat_var[:] = lat
        d_var = ds.createVariable("depth", "f4", ("depth",))
        d_var[:] = depth

        t_data = ds.createVariable("votemper", "f4", ("time", "depth", "lat", "lon"))
        t_data[:] = np.random.rand(nt, nz, ny, nx) * 20 + 5
        s_data = ds.createVariable("vosaline", "f4", ("time", "depth", "lat", "lon"))
        s_data[:] = np.random.rand(nt, nz, ny, nx) * 5 + 33


class TestOpenDecodeBobyclim:
    """Tests for open_decode_bobyclim.

    NOTE: these tests use synthetic netCDF files — open_decode_bobyclim has
    NOT been validated against real Bobyclim files.
    """

    def test_emits_user_warning(self, tmp_path):
        """open_decode_bobyclim must emit a UserWarning on every call."""
        nc_file = tmp_path / "bobyclim.nc"
        _write_bobyclim_nc(nc_file, time_values=[0., 31., 59.])

        with pytest.warns(UserWarning, match="not been tested"):
            open_decode_bobyclim([str(nc_file)])

    def test_output_is_dataset(self, tmp_path):
        """open_decode_bobyclim must return an xarray.Dataset."""
        nc_file = tmp_path / "bobyclim.nc"
        _write_bobyclim_nc(nc_file, time_values=[0., 31., 59.])

        import warnings
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", UserWarning)
            result = open_decode_bobyclim([str(nc_file)])

        assert isinstance(result, xr.Dataset)

    def test_variable_renaming(self, tmp_path):
        """votemper/vosaline must be renamed to temp/sal."""
        nc_file = tmp_path / "bobyclim.nc"
        _write_bobyclim_nc(nc_file, time_values=[0., 31., 59.])

        import warnings
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", UserWarning)
            result = open_decode_bobyclim([str(nc_file)])

        assert "temp" in result
        assert "sal" in result
        assert "votemper" not in result
        assert "vosaline" not in result

    def test_2d_grid_construction(self, tmp_path):
        """1D lon/lat must be promoted to 2D (y, x) grid."""
        nc_file = tmp_path / "bobyclim.nc"
        _write_bobyclim_nc(nc_file, time_values=[0., 31., 59.])

        import warnings
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", UserWarning)
            result = open_decode_bobyclim([str(nc_file)])

        assert "lon" in result.coords
        assert "lat" in result.coords
        assert result["lon"].ndim == 2
        assert result["lat"].ndim == 2
        assert set(("y", "x")).issubset(result["lon"].dims)

    def test_time_normalised_to_monthly_indices(self, tmp_path):
        """Time axis must be normalised to integer monthly indices 1–12."""
        nc_file = tmp_path / "bobyclim.nc"
        # datetime-encoded: Jan, Apr, Jul → months 1, 4, 7
        time_values = [0., 90., 181.]  # approx days-since-2000 for Jan/Apr/Jul
        _write_bobyclim_nc(nc_file, time_values=time_values)

        import warnings
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", UserWarning)
            result = open_decode_bobyclim([str(nc_file)])

        t = result["time"].values
        assert t.dtype in (np.int32, np.int64, np.float32, np.float64)
        assert np.all(t >= 1)
        assert np.all(t <= 12)

    def test_dispatcher_routes_to_bobyclim(self, tmp_path):
        """open_decode with fmt='bobyclim' must call open_decode_bobyclim."""
        nc_file = tmp_path / "bobyclim.nc"
        _write_bobyclim_nc(nc_file, time_values=[0., 31., 59.])

        import warnings
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", UserWarning)
            result = open_decode(str(nc_file), fmt="bobyclim")

        assert isinstance(result, xr.Dataset)


# ============================================================================
# Parametrized tests for robustness
# ============================================================================

@pytest.mark.parametrize("sort_results", [True, False])
def test_get_paths_sorting(tmp_path, sort_results):
    """
    Test get_paths with different sorting options.
    
    Parameters
    ----------
    tmp_path : Path
        Pytest fixture for temporary directory.
    sort_results : bool
        Whether to sort results.
    """
    # Create files in non-alphabetical order
    for name in ['c.nc', 'a.nc', 'b.nc']:
        (tmp_path / name).touch()
    
    pattern = str(tmp_path / "*.nc")
    result = get_paths(pattern, sort_results=sort_results)
    
    assert len(result) == 3
    if sort_results:
        assert result == sorted(result)


class TestDecoderFixedLevels:
    """Decoder.fixed_levels declares whether a format's native "z"
    indices are at fixed depths -- used by armoor-data's native-level
    fallback instead of inspecting the depth field."""

    @pytest.mark.parametrize("fmt", ["croco", "croco_xios", "hycom", "hycom3d"])
    def test_terrain_following_formats(self, fmt):
        from armoor.data.open_decode import get_decoder
        assert get_decoder(fmt).fixed_levels is False

    @pytest.mark.parametrize("fmt", ["cmems_model", "cmems_insitu", "armoor"])
    def test_fixed_level_formats(self, fmt):
        from armoor.data.open_decode import get_decoder
        assert get_decoder(fmt).fixed_levels is True
