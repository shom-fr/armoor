from armoor.cli.command_line_interface import command_line_interface
from armoor.base.calls_from_dict import dict2call
from tests.int.base import change_path, copy_test_files

folder_test = 'test_f6'
copy_test_files(folder_test)


class TestBulletins:

    def test_ellipse_courant_et_periode(self):  # OK
        out_path, logger = change_path(folder_test)
        logger.info('test_ellipse_courant_et_periode')
        parser = command_line_interface(['--cfgfile', f"../single_tests/{folder_test}/ellipse_courant_et_periode.ini"])
        parser.update({'output_path': out_path})
        dict2call(parser)
        assert True

    def test_map_current(self):  # OK
        out_path, logger = change_path(folder_test)
        logger.info('test_map_current')
        parser = command_line_interface(['--cfgfile', f"../single_tests/{folder_test}/map_current.ini"])
        parser.update({'output_path': out_path})
        dict2call(parser)
        assert True

    def test_map_current_biais(self):  # OK
        out_path, logger = change_path(folder_test)
        logger.info('test_map_current_biais')
        parser = command_line_interface(['--cfgfile', f"../single_tests/{folder_test}/map_current_biais.ini"])
        parser.update({'output_path': out_path})
        dict2call(parser)
        assert True

    def test_map_current_croco(self):
        out_path, logger = change_path(folder_test)
        logger.info('test_map_current_croco')
        parser = command_line_interface(['--cfgfile', f"../single_tests/{folder_test}/map_current_croco.ini"])
        parser.update({'output_path': out_path})
        dict2call(parser)
        assert True

    def test_map_current_hycom2det3d(self):
        out_path, logger = change_path(folder_test)
        logger.info('test_map_current_hycom2Det3D')
        parser = command_line_interface(['--cfgfile', f"../single_tests/{folder_test}/map_current_hycom2Det3D.ini"])
        parser.update({'output_path': out_path})
        dict2call(parser)
        assert True

    def test_map_current_rmse(self):  # OK
        out_path, logger = change_path(folder_test)
        logger.info('test_map_current_RMSE')
        parser = command_line_interface(['--cfgfile', f"../single_tests/{folder_test}/map_current_RMSE.ini"])
        parser.update({'output_path': out_path})
        dict2call(parser)
        assert True

    def test_map_harm_courant(self):  # OK
        out_path, logger = change_path(folder_test)
        logger.info('test_map_harm_courant')
        parser = command_line_interface(['--cfgfile', f"../single_tests/{folder_test}/map_harm_courant.ini"])
        parser.update({'output_path': out_path})
        dict2call(parser)
        assert True

    def test_ser_temp_uv_ponct(self):  # OK
        out_path, logger = change_path(folder_test)
        logger.info('test_ser_temp_uv_ponct')
        parser = command_line_interface(['--cfgfile', f"../single_tests/{folder_test}/ser_temp_uv_ponct.ini"])
        parser.update({'output_path': out_path})
        dict2call(parser)
        assert True

    def test_ser_temp_uv_ponct_intervalles(self):  # OK
        out_path, logger = change_path(folder_test)
        logger.info('test_ser_temp_uv_ponct_intervalles')
        parser = command_line_interface(
            ['--cfgfile', f"../single_tests/{folder_test}/ser_temp_uv_ponct_intervalles.ini"])
        parser.update({'output_path': out_path})
        dict2call(parser)
        assert True

    def test_ser_temp_uv_stat_intervalles(self):  # OK
        out_path, logger = change_path(folder_test)
        logger.info('test_ser_temp_uv_stat_intervalles')
        parser = command_line_interface(
            ['--cfgfile', f"../single_tests/{folder_test}/ser_temp_uv_stat_intervalles.ini"])
        parser.update({'output_path': out_path})
        dict2call(parser)
        assert True
