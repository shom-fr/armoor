from armoor.cli.command_line_interface import command_line_interface
from armoor.base.calls_from_dict import dict2call
from armoor.hmi.script_tools import create_folder
from tests.int.base import change_path, copy_test_files

folder_test = 'test_f5'
copy_test_files(folder_test)


class TestBulletins:

    def test_map_diff(self):  # OK
        out_path, logger = change_path(folder_test)
        logger.info('test_map_diff')
        parser = command_line_interface(['--cfgfile', f"../single_tests/{folder_test}/map_diff.cfg"])
        parser.update({'output_path': out_path})
        dict2call(parser)
        assert True

    def test_ser_temp_ponct(self):  # OK
        out_path, logger = change_path(folder_test)
        logger.info('test_ser_temp_ponct')
        parser = command_line_interface(['--cfgfile', f"../single_tests/{folder_test}/ser_temp_ponct.cfg"])
        parser.update({'output_path': out_path})
        dict2call(parser)
        assert True

    def test_ser_temp_stats(self):  # OK
        out_path, logger = change_path(folder_test)
        logger.info('test_ser_temp_stats')
        parser = command_line_interface(['--cfgfile', f"../single_tests/{folder_test}/ser_temp_stats.cfg"])
        parser.update({'output_path': out_path})
        dict2call(parser)
        assert True

    def test_ser_temp_ponct_SCA(self):
        out_path, logger = change_path(folder_test)
        logger.info("test_ser_temp_ponct_SCA")
        parser = command_line_interface(
            ['--cfgfile', f"../single_tests/{folder_test}/ser_temp_ponct_SCA.cfg"])
        parser.update({'output_path': out_path})
        dict2call(parser)
        assert True

    def test_ser_temp_stats_SCA(self):
        out_path, logger = change_path(folder_test)
        logger.info("test_ser_temp_stats_SCA")
        parser = command_line_interface(
            ['--cfgfile', f"../single_tests/{folder_test}/ser_temp_stats_SCA.cfg"])
        parser.update({'output_path': out_path})
        create_folder(f'tmp')
        dict2call(parser)
        assert True