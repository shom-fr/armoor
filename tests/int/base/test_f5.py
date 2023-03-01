from armoor.cli.command_line_interface import command_line_interface
from armoor.base.calls_from_dict import dict2call
from tests.int.base import change_path

folder_test = 'test_f5'

class TestBulletins:

    def test_map_diff(self):
        out_path, logger = change_path(folder_test)
        logger.info('test_map_diff')
        parser = command_line_interface(['--cfgfile', f"../single_tests/{folder_test}/map_diff.ini"])
        parser.update({'output_path' : out_path })
        dict2call(parser)
        assert True

    def test_ser_temp_ponct(self):
        out_path, logger = change_path(folder_test)
        logger.info('test_ser_temp_ponct')
        parser = command_line_interface(['--cfgfile', f"../single_tests/{folder_test}/ser_temp_ponct.ini"])
        parser.update({'output_path' : out_path })
        dict2call(parser)
        assert True

    def test_ser_temp_stats(self):
        out_path, logger = change_path(folder_test)
        logger.info('test_ser_temp_stats')
        parser = command_line_interface(['--cfgfile', f"../single_tests/{folder_test}/ser_temp_stats.ini"])
        parser.update({'output_path' : out_path })
        dict2call(parser)
        assert True
