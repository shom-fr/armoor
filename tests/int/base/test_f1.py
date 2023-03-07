from armoor.cli.command_line_interface import command_line_interface
from armoor.base.calls_from_dict import dict2call
from tests.int.base import change_path

folder_test = 'test_f1'

class TestBulletins:

    def test_diag_disp_sst(self):
        out_path, logger = change_path(folder_test)
        logger.info('test_diag_disp_sst')
        parser = command_line_interface(['--cfgfile', f"../single_tests/{folder_test}/diag_disp_sst.ini"])
        parser.update({'output_path' : out_path })
        dict2call(parser)
        assert True

    def test_map_sst_biais(self):
        out_path, logger = change_path(folder_test)
        logger.info('test_map_sst_biais')
        parser = command_line_interface(['--cfgfile', f"../single_tests/{folder_test}/map_sst_biais.ini"])
        parser.update({'output_path' : out_path })
        dict2call(parser)
        assert True

    def test_map_sst_diff(self):
        out_path, logger = change_path(folder_test)
        logger.info('test_map_sst_diff')
        parser = command_line_interface(['--cfgfile', f"../single_tests/{folder_test}/map_sst_diff.ini"])
        parser.update({'output_path' : out_path })
        dict2call(parser)
        assert True

    def test_map_sst_diff_seuil_bathy(self):
        out_path, logger = change_path(folder_test)
        logger.info('test_map_sst_diff_seuil_bathy')
        print(f"../single_tests/{folder_test}/map_sst_diff_seuil_bathy.ini")
        parser = command_line_interface(['--cfgfile', f"../single_tests/{folder_test}/map_sst_diff_seuil_bathy.ini"])
        parser.update({'output_path' : out_path })
        dict2call(parser)
        assert True

    def test_map_sst_diff_topaz(self):
        out_path, logger = change_path(folder_test)
        logger.info('test_map_sst_diff_TOPAZ')
        parser = command_line_interface(['--cfgfile', f"../single_tests/{folder_test}/map_sst_diff_TOPAZ.ini"])
        parser.update({'output_path' : out_path })
        dict2call(parser)
        assert True

    def test_map_sst_rmse(self):
        out_path, logger = change_path(folder_test)
        logger.info('test_map_sst_rmse')
        parser = command_line_interface(['--cfgfile', f"../single_tests/{folder_test}/map_sst_rmse.ini"])
        parser.update({'output_path' : out_path })
        dict2call(parser)
        assert True

    def test_map_sst_rmse_centree(self):
        out_path, logger = change_path(folder_test)
        logger.info('test_map_sst_rmse_centree')
        parser = command_line_interface(['--cfgfile', f"../single_tests/{folder_test}/map_sst_rmse_centree.ini"])
        parser.update({'output_path' : out_path })
        dict2call(parser)
        assert True

    def test_ser_temp_sst(self):
        out_path, logger = change_path(folder_test)
        logger.info('test_ser_temp_sst')
        parser = command_line_interface(['--cfgfile', f"../single_tests/{folder_test}/ser_temp_sst.ini"])
        parser.update({'output_path' : out_path })
        dict2call(parser)
        assert True

    def test_ser_temp_sst_ponct_diff(self):
        out_path, logger = change_path(folder_test)
        logger.info('test_ser_temp_sst_ponct_diff')
        parser = command_line_interface(['--cfgfile', f"../single_tests/{folder_test}/ser_temp_sst_ponct_diff.ini"])
        parser.update({'output_path' : out_path })
        dict2call(parser)
        assert True

    def test_ser_temp_sst_ponct_intervalles(self):
        out_path, logger = change_path(folder_test)
        logger.info('test_ser_temp_sst_ponct_intervalles')
        parser = command_line_interface(['--cfgfile', f"../single_tests/{folder_test}/ser_temp_sst_ponct_intervalles.ini"])
        parser.update({'output_path' : out_path })
        dict2call(parser)
        assert True