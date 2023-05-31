import xarray as xr

from armoor.base import read_sst
from armoor.base.open_decode import open_decode
from armoor.hmi.script_tools import create_folder
from tests.int.base import change_path

folder_test = 'read_var'
out_path, logger = change_path(folder_test)


class TestReadVar:
    def test_sel_sound_speed(self):  # OK
        logger.info('test_sel_sound_speed')
        path_ds = ["../data/test_uni/read_var/nemo_for_sound_speed.nc"]
        ds = open_decode(path_ds)
        sound_speed = ds.read_sst.sel(['sound_speed'])
        assert sound_speed.max() > 1000

    def test_sel_mld(self):  # needs xoa latest version
        logger.info('test_sel_mld')
        path_ds = ["../data/test_uni/read_var/woa18_decav_t03_04.nc"]
        ds = open_decode(path_ds, type='WOA18')
        _ = ds.read_sst.sel(['mld'])
        assert True
