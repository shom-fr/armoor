import xarray as xr

from armoor.base.open_decode import open_decode
from armoor.hmi.script_tools import create_folder
from tests.int.base import change_path

folder_test = 'open_data'


class TestOpenData:

    def test_open_topaz(self):  # OK
        out_path, logger = change_path(folder_test)
        logger.info('test_open_topaz')
        path_ds = [f"../data/test_uni/topaz.nc"]
        ds = open_decode(path_ds)
        assert isinstance(ds, xr.Dataset)

    def test_open_croco(self):  # OK
        out_path, logger = change_path(folder_test)
        logger.info('test_open_croco')
        path_ds = [f"../data/test_uni/croco.nc"]
        ds = open_decode(path_ds, type='CROCO')
        assert isinstance(ds, xr.Dataset)

    def test_open_croco_3d_currents(self):  # OK
        out_path, logger = change_path(folder_test)
        logger.info('test_open_croco_3d_currents')
        path_ds = [f"../data/test_uni/croco_courant.nc"]
        ds = open_decode(path_ds, type="CROCO_currents")
        assert isinstance(ds, xr.Dataset)

    def test_open_hycom_2d(self):  # OK
        out_path, logger = change_path(folder_test)
        logger.info('test_open_hycom_2d')
        path_ds = [f"../data/test_uni/hycom_2d.nc"]
        ds = open_decode(path_ds)
        assert isinstance(ds, xr.Dataset)

    def test_open_hycom_3d(self):  # OK
        out_path, logger = change_path(folder_test)
        logger.info('test_open_hycom_3d')
        path_ds = [f"../data/test_uni/hycom_h.nc", f"../data/test_uni/hycom_saln.nc"]
        ds = open_decode(path_ds, type="HYCOM_3D")
        assert isinstance(ds, xr.Dataset)

    def test_open_hycom_currents(self):  # OK
        out_path, logger = change_path(folder_test)
        logger.info('test_open_hycom_currents')
        path_ds = [f"../data/test_uni/hycom_h.nc", f"../data/test_uni/hycom_u.nc", f"../data/test_uni/hycom_v.nc"]
        ds = open_decode(path_ds, type="HYCOM_currents")
        assert isinstance(ds, xr.Dataset)

    def test_open_insitu_cmems(self):  # OK
        out_path, logger = change_path(folder_test)
        logger.info('test_open_insitu_cmems')
        path_ds = [f"../data/test_uni/cmems.nc"]
        ds = open_decode(path_ds, type="CMEMS")
        assert isinstance(ds, xr.Dataset)

    def test_open_radarhf(self):  # OK
        out_path, logger = change_path(folder_test)
        logger.info('test_open_radarhf')
        path_ds = [f"../data/test_uni/radarhf.nc"]
        ds = open_decode(path_ds)
        assert isinstance(ds, xr.Dataset)

    def test_open_satellite(self):  # OK
        out_path, logger = change_path(folder_test)
        logger.info('test_open_satellite')
        path_ds = [f"../data/test_uni/satellite.nc"]
        ds = open_decode(path_ds)
        assert isinstance(ds, xr.Dataset)

    def test_open_radiales(self):  # OK
        out_path, logger = change_path(folder_test)
        logger.info('test_open_radiales')
        path_ds = [f"../data/test_uni/radiale.nc"]
        ds = open_decode(path_ds)
        assert isinstance(ds, xr.Dataset)

    def test_open_vmadcp(self):  # OK
        out_path, logger = change_path(folder_test)
        logger.info('test_open_vmadcp')
        path_ds = [f"../data/test_uni/vmadcp.txt"]
        ds = open_decode(path_ds, type='VMADCP')
        assert isinstance(ds, xr.Dataset)

    def test_open_ladcp(self):  # OK
        out_path, logger = change_path(folder_test)
        logger.info('test_open_ladcp')
        path_ds = [f"../data/test_uni/ladcp.txt"]
        ds = open_decode(path_ds, type='LADCP')
        assert isinstance(ds, xr.Dataset)

    def test_open_woa18(self):  # OK
        out_path, logger = change_path(folder_test)
        logger.info('test_open_woa18')
        path_ds = [f"../data/test_uni/woa18_decav_s01_5d.nc", f"../data/test_uni/woa18_decav_s02_5d.nc",
                   f"../data/test_uni/woa18_decav_s03_5d.nc", f"../data/test_uni/woa18_decav_s04_5d.nc",
                   f"../data/test_uni/woa18_decav_s05_5d.nc", f"../data/test_uni/woa18_decav_s06_5d.nc",
                   f"../data/test_uni/woa18_decav_s07_5d.nc", f"../data/test_uni/woa18_decav_s08_5d.nc",
                   f"../data/test_uni/woa18_decav_s09_5d.nc", f"../data/test_uni/woa18_decav_s10_5d.nc",
                   f"../data/test_uni/woa18_decav_s11_5d.nc", f"../data/test_uni/woa18_decav_s12_5d.nc"]
        ds = open_decode(path_ds, type="WOA18")
        assert isinstance(ds, xr.Dataset)

    def test_open_scanfish(self):  # OK
        out_path, logger = change_path(folder_test)
        logger.info('test_open_scanfish')
        path_ds = [f"../data/test_uni/scanfish.txt"]
        ds = open_decode(path_ds, type='scanfish')
        assert isinstance(ds, xr.Dataset)

    def test_open_seasoar(self):  # OK
        out_path, logger = change_path(folder_test)
        logger.info('test_open_seasoar')
        path_ds = [f"../data/test_uni/seasoar.txt"]
        ds = open_decode(path_ds, type='seasoar')
        assert isinstance(ds, xr.Dataset)

    def test_open_mouillage(self):  # OK
        out_path, logger = change_path(folder_test)
        logger.info('test_open_mouillage')
        path_ds = [f"../data/test_uni/mouillage.txt"]
        ds = open_decode(path_ds, type='mouillage')
        assert isinstance(ds, xr.Dataset)

    def test_open_cora(self):  # OK
        out_path, logger = change_path(folder_test)
        logger.info('test_open_cora')
        path_ds = [f"../data/test_uni/cora.nc"]
        ds = open_decode(path_ds, type='CORA')
        assert isinstance(ds, xr.Dataset)
