import os, glob
import xarray as xr
from armoor.__init__ import ROOTDIR
from armoor.base.open_decode import open_decode

samples_dir = os.path.join(ROOTDIR, "_samples")

class TestCmemsFormat:

    def test_argo(self):   
        ncins = glob.glob(
            os.path.join(samples_dir, "GL_PR_PF_*.nc")
        )
        ds = open_decode(
            ncins,
            platform="argo",
            fmt="cmems_insitu"
        )
        assert isinstance(ds, xr.Dataset)
        assert set(["z", "time"]).issubset(ds.dims)
        assert set(["depth", "lon", "lat", "time"]).issubset(ds.coords)
        assert ds.lon.dims == ("time",)
        assert ds.lat.dims == ("time",)
        assert ds.depth.dims == ("time", "z")
    
    def test_mooring(self):
        ncins = glob.glob(
            os.path.join(samples_dir, "GL_TS_MO_*.nc")
        )
        dss = open_decode(
            ncins,
            platform="mooring",
            fmt="cmems_insitu"
        )
        assert isinstance(dss, list)
        assert all([isinstance(ds, xr.Dataset) for ds in dss])
        assert all([set(["z", "time"]).issubset(ds.dims) for ds in dss])
        assert all([set(
            ["depth", "lon", "lat", "time"]
        ).issubset(ds.coords) for ds in dss])
        assert all(["time" not in ds.lon.dims for ds in dss])
        assert all(["time" not in ds.lat.dims for ds in dss])
        
    def test_drifter(self):
        ncins = glob.glob(
            os.path.join(samples_dir, "GL_TS_DB_*.nc")
        )
        dss = open_decode(
            ncins,
            platform="drifter",
            fmt="cmems_insitu"
        )
        assert isinstance(dss, list)
        assert all([isinstance(ds, xr.Dataset) for ds in dss])
        assert all([set(["z", "time"]).issubset(ds.dims) for ds in dss])
        assert all([set(
            ["depth", "lon", "lat", "time"]
        ).issubset(ds.coords) for ds in dss])
        assert all(["time" in ds.lon.dims for ds in dss])
        assert all(["time" in ds.lat.dims for ds in dss])
        assert all(["z" in ds.depth.dims for ds in dss])
        
    def test_glider(self):
        ncins = glob.glob(
            os.path.join(samples_dir, "GL_TS_GL_*.nc")
        )
        dss = open_decode(
            ncins,
            platform="glider",
            fmt="cmems_insitu"
        )
        assert isinstance(dss, list)
        assert all([isinstance(ds, xr.Dataset) for ds in dss])
        assert all([set(["z", "time"]).issubset(ds.dims) for ds in dss])
        assert all([set(
            ["depth", "lon", "lat", "time"]
        ).issubset(ds.coords) for ds in dss])
        assert all(["time" in ds.lon.dims for ds in dss])
        assert all(["time" in ds.lat.dims for ds in dss])
        assert all(["z" in ds.depth.dims for ds in dss])

class TestModel:
    
    def test_cmems_model(self):   
        ncins = [os.path.join(samples_dir, "cmems_glo12.nc")]
        ds = open_decode(
            ncins,
            fmt="cmems_model",
        )
        assert isinstance(ds, xr.Dataset)
        assert set(["z", "time", "x", "y"]).issubset(ds.dims)
        assert set(["depth", "time", "lon", "lat"]).issubset(ds.coords)
        
    def test_hycom_model(self):   
        ncins = glob.glob(
            os.path.join(samples_dir, "hycom_*.nc")
        )
        ds = open_decode(
            ncins,
            fmt="hycom",
        )
        assert isinstance(ds, xr.Dataset)
        assert set(["z", "time", "x", "y"]).issubset(ds.dims)
        assert set(["depth", "time", "lon", "lat"]).issubset(ds.coords)
        

        
    '''
    def test_open_topaz(self):  # OK
        logger.info('test_open_topaz')
        path_ds = ["../data/test_uni/open_decode/topaz.nc"]
        ds = open_decode(path_ds)
        assert isinstance(ds, xr.Dataset)

    def test_open_croco(self):  # OK
        logger.info('test_open_croco')
        path_ds = ["../data/test_uni/open_decode/croco.nc"]
        ds = open_decode(path_ds, type='CROCO')
        assert isinstance(ds, xr.Dataset)

    def test_open_croco_3d_currents(self):  # OK
        logger.info('test_open_croco_3d_currents')
        path_ds = ["../data/test_uni/open_decode/croco_courant.nc"]
        ds = open_decode(path_ds, type="CROCO_currents")
        assert isinstance(ds, xr.Dataset)

    def test_open_hycom_2d(self):  # OK
        logger.info('test_open_hycom_2d')
        path_ds = ["../data/test_uni/open_decode/hycom_2d.nc"]
        ds = open_decode(path_ds)
        assert isinstance(ds, xr.Dataset)

    def test_open_hycom_3d(self):  # OK
        logger.info('test_open_hycom_3d')
        path_ds = ["../data/test_uni/open_decode/hycom_h.nc", "../data/test_uni/open_decode/hycom_saln.nc"]
        ds = open_decode(path_ds, type="HYCOM_3D")
        assert isinstance(ds, xr.Dataset)

    def test_open_hycom_currents(self):  # OK
        logger.info('test_open_hycom_currents')
        path_ds = ["../data/test_uni/open_decode/hycom_h.nc", "../data/test_uni/open_decode/hycom_u.nc",
                   "../data/test_uni/open_decode/hycom_v.nc"]
        ds = open_decode(path_ds, type="HYCOM_currents")
        assert isinstance(ds, xr.Dataset)

    def test_open_insitu_cmems(self):  # OK
        logger.info('test_open_insitu_cmems')
        path_ds = ["../data/test_uni/open_decode/cmems.nc"]
        ds = open_decode(path_ds, type="CMEMS")
        assert isinstance(ds, xr.Dataset)

    def test_open_radarhf(self):  # OK
        logger.info('test_open_radarhf')
        path_ds = ["../data/test_uni/open_decode/radarhf.nc"]
        ds = open_decode(path_ds)
        assert isinstance(ds, xr.Dataset)

    def test_open_satellite(self):  # OK
        logger.info('test_open_satellite')
        path_ds = ["../data/test_uni/open_decode/satellite.nc"]
        ds = open_decode(path_ds)
        assert isinstance(ds, xr.Dataset)

    def test_open_radiales(self):  # OK
        logger.info('test_open_radiales')
        path_ds = ["../data/test_uni/open_decode/radiale.nc"]
        ds = open_decode(path_ds)
        assert isinstance(ds, xr.Dataset)

    def test_open_vmadcp(self):  # OK
        logger.info('test_open_vmadcp')
        path_ds = ["../data/test_uni/open_decode/vmadcp.txt"]
        ds = open_decode(path_ds, type='VMADCP')
        assert isinstance(ds, xr.Dataset)

    def test_open_ladcp(self):  # OK
        logger.info('test_open_ladcp')
        path_ds = ["../data/test_uni/open_decode/ladcp.txt"]
        ds = open_decode(path_ds, type='LADCP')
        assert isinstance(ds, xr.Dataset)

    def test_open_woa18(self):  # OK
        logger.info('test_open_woa18')
        path_ds = ["../data/test_uni/open_decode/woa18_decav_s01_5d.nc",
                   "../data/test_uni/open_decode/woa18_decav_s02_5d.nc",
                   "../data/test_uni/open_decode/woa18_decav_s03_5d.nc",
                   "../data/test_uni/open_decode/woa18_decav_s04_5d.nc",
                   "../data/test_uni/open_decode/woa18_decav_s05_5d.nc",
                   "../data/test_uni/open_decode/woa18_decav_s06_5d.nc",
                   "../data/test_uni/open_decode/woa18_decav_s07_5d.nc",
                   "../data/test_uni/open_decode/woa18_decav_s08_5d.nc",
                   "../data/test_uni/open_decode/woa18_decav_s09_5d.nc",
                   "../data/test_uni/open_decode/woa18_decav_s10_5d.nc",
                   "../data/test_uni/open_decode/woa18_decav_s11_5d.nc",
                   "../data/test_uni/open_decode/woa18_decav_s12_5d.nc"]
        ds = open_decode(path_ds, type="WOA18")
        assert isinstance(ds, xr.Dataset)

    def test_open_scanfish(self):  # OK
        logger.info('test_open_scanfish')
        path_ds = ["../data/test_uni/open_decode/scanfish.txt"]
        ds = open_decode(path_ds, type='scanfish')
        assert isinstance(ds, xr.Dataset)

    def test_open_seasoar(self):  # OK
        logger.info('test_open_seasoar')
        path_ds = ["../data/test_uni/open_decode/seasoar.txt"]
        ds = open_decode(path_ds, type='seasoar')
        assert isinstance(ds, xr.Dataset)

    def test_open_mouillage(self):  # OK
        logger.info('test_open_mouillage')
        path_ds = ["../data/test_uni/open_decode/mouillage.txt"]
        ds = open_decode(path_ds, type='mouillage')
        assert isinstance(ds, xr.Dataset)

    def test_open_cora(self):  # OK
        logger.info('test_open_cora')
        path_ds = ["../data/test_uni/open_decode/cora.nc"]
        ds = open_decode(path_ds, type='CORA')
        assert isinstance(ds, xr.Dataset)
    '''