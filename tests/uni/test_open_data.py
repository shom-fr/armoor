import xarray as xr

from armoor.base.open_data import open_file
from armoor.hmi.script_tools import create_folder
from tests.int.base import change_path

folder_test = 'open_data'

class TestOpenData:

    def test_open_topaz(self):
        out_path, logger = change_path(folder_test)
        logger.info('test_open_topaz')
        path_ds = f"../data/test_f1/MODEL/topaz_dataset-ran-arc-day-myoceanv2-be.nc"
        ds = open_file(path_ds)
        print(isinstance(ds, xr.Dataset))
        assert isinstance(ds, xr.Dataset)

    def test_open_croco(self):
        out_path, logger = change_path(folder_test)
        logger.info('test_open_croco')
        path_ds = f"../data/test_f1/MODEL/CROCO_loire.nc"
        ds = open_file(path_ds)
        print(isinstance(ds, xr.Dataset))
        assert isinstance(ds, xr.Dataset)

    def test_open_croco_3d_currents(self):
        out_path, logger = change_path(folder_test)
        logger.info('test_open_croco_3d_currents')
        path_ds = f"../data/test_f6/MODEL/CROCO_loire.nc"
        ds = open_file(path_ds, type="CROCO_currents")
        print(isinstance(ds, xr.Dataset))
        assert isinstance(ds, xr.Dataset)

    def test_open_hycom_2d(self):
        out_path, logger = change_path(folder_test)
        logger.info('test_open_hycom_2d')
        path_ds = f"../data/test_f1/MODEL/HYCOMsst_2D.nc"
        ds = open_file(path_ds)
        print(isinstance(ds, xr.Dataset))
        assert isinstance(ds, xr.Dataset)

    def test_open_hycom_3d(self):
        out_path, logger = change_path(folder_test)
        logger.info('test_open_hycom_3d')
        path_ds = [f"../data/test_f4/h_3D_med_sub.nc",
                   f"../data/test_f4/saln_3D_med_sub.nc"]
        ds = open_file(path_ds, type="HYCOM_3D")
        print(isinstance(ds, xr.Dataset))
        assert isinstance(ds, xr.Dataset)

    def test_open_hycom_currents(self):
        out_path, logger = change_path(folder_test)
        logger.info('test_open_hycom_currents')
        path_ds = [f"../data/test_f8/MOD/h_3D_med.nc",
                   f"../data/test_f8/MOD/u_3D_med.nc",
                   f"../data/test_f8/MOD/v_3D_med.nc"]
        ds = open_file(path_ds, type="HYCOM_currents")
        print(isinstance(ds, xr.Dataset))
        assert isinstance(ds, xr.Dataset)

    def test_open_insitu_cmems(self):
        out_path, logger = change_path(folder_test)
        logger.info('test_open_insitu_cmems')
        path_ds = f"../data/test_f3/OBS/BO_TS_MO_BrofjordenWR_201901.nc"
        ds = open_file(path_ds)
        print(isinstance(ds, xr.Dataset))
        assert isinstance(ds, xr.Dataset)

    def test_open_radarhf(self):
        out_path, logger = change_path(folder_test)
        logger.info('test_open_radarhf')
        path_ds = f"../data/test_f6/RADARHF_OBS_R1110_IROISE_20210131.nc"
        ds = open_file(path_ds)
        print(isinstance(ds, xr.Dataset))
        assert isinstance(ds, xr.Dataset)

    def test_open_satellite(self):
        out_path, logger = change_path(folder_test)
        logger.info('test_open_satellite')
        path_ds = f"../data/test_f1/OBS/nov_METEOFRANCE-EUR-SST_L3MONOSENSOR_NRT-OBS_V2-AVHRR_METOP_B_FULL_TIME_SERIE_1621503492101_2.nc"
        ds = open_file(path_ds)
        print(isinstance(ds, xr.Dataset))
        assert isinstance(ds, xr.Dataset)

    def test_open_radiales(self):
        out_path, logger = change_path(folder_test)
        logger.info('test_open_radiales')
        path_ds = f"../data/test_f4/GL_PR_GL_64556.nc"
        ds = open_file(path_ds)
        print(isinstance(ds, xr.Dataset))
        assert isinstance(ds, xr.Dataset)

    def test_open_vmadcp(self):
        out_path, logger = change_path(folder_test)
        logger.info('test_open_vmadcp')
        path_ds = f"../data/test_f8/OBS/OS_150_STA_098.txt"
        ds = open_file(path_ds, type='VMADCP')
        print(isinstance(ds, xr.Dataset))
        assert isinstance(ds, xr.Dataset)

    def test_open_ladcp(self):
        out_path, logger = change_path(folder_test)
        logger.info('test_open_ladcp')
        path_ds = f"../data/test_f7/LADCP_PF006.txt"
        ds = open_file(path_ds, type='LADCP')
        print(isinstance(ds, xr.Dataset))
        assert isinstance(ds, xr.Dataset)

    def test_open_woa18(self):
        out_path, logger = change_path(folder_test)
        logger.info('test_open_woa18')
        path_ds = [f"../data/test_f5/climato/mensuel/woa18_decav_s01_5d.nc",
                   f"../data/test_f5/climato/mensuel/woa18_decav_s02_5d.nc",
                   f"../data/test_f5/climato/mensuel/woa18_decav_s03_5d.nc",
                   f"../data/test_f5/climato/mensuel/woa18_decav_s04_5d.nc",
                   f"../data/test_f5/climato/mensuel/woa18_decav_s05_5d.nc",
                   f"../data/test_f5/climato/mensuel/woa18_decav_s06_5d.nc",
                   f"../data/test_f5/climato/mensuel/woa18_decav_s07_5d.nc",
                   f"../data/test_f5/climato/mensuel/woa18_decav_s08_5d.nc",
                   f"../data/test_f5/climato/mensuel/woa18_decav_s09_5d.nc",
                   f"../data/test_f5/climato/mensuel/woa18_decav_s10_5d.nc",
                   f"../data/test_f5/climato/mensuel/woa18_decav_s11_5d.nc",
                   f"../data/test_f5/climato/mensuel/woa18_decav_s12_5d.nc"]
        ds = open_file(path_ds, func="clim_hydro")
        print(isinstance(ds, xr.Dataset))
        assert isinstance(ds, xr.Dataset)

