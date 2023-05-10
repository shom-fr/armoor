from armoor.cli.command_line_interface import command_line_interface
from armoor.base.calls_from_dict import dict2call
from tests.int.base import change_path, copy_test_files

folder_test = 'test_f4'
copy_test_files(folder_test)

class TestBulletins:

    def test_variable_2d(self):
        out_path, logger = change_path(folder_test)
        logger.info('test_variable_2d')
        parser = command_line_interface(['--cfgfile', f"../single_tests/{folder_test}/variable_2d.ini"])
        parser.update({'output_path' : out_path })
        dict2call(parser)
        assert True

    def test_variable_2d_seasor(self):
        out_path, logger = change_path(folder_test)
        logger.info('test_variable_2d_seasor')
        parser = command_line_interface(['--cfgfile', f"../single_tests/{folder_test}/variable_2d_seasor.ini"])
        parser.update({'output_path' : out_path })
        dict2call(parser)
        assert True

    def test_variable_2d_scanfish(self):
        out_path, logger = change_path(folder_test)
        logger.info('test_variable_2d_scanfish')
        parser = command_line_interface(['--cfgfile', f"../single_tests/{folder_test}/variable_2d_scanfish.ini"])
        parser.update({'output_path' : out_path })
        dict2call(parser)
        assert True

    def test_variable_3d(self):
        out_path, logger = change_path(folder_test)
        logger.info('test_variable_3d')
        parser = command_line_interface(['--cfgfile', f"../single_tests/{folder_test}/variable_3d.ini"])
        parser.update({'output_path' : out_path })
        dict2call(parser)
        assert True

    def test_variable_3d_hycom(self):
        out_path, logger = change_path(folder_test)
        logger.info('test_variable_3d_hycom')
        parser = command_line_interface(['--cfgfile', f"../single_tests/{folder_test}/variable_3d_hycom.ini"])
        parser.update({'output_path' : out_path })
        dict2call(parser)
        assert True

    def test_variable_3d_steps(self):
        out_path, logger = change_path(folder_test)
        logger.info('test_variable_3d_steps')
        parser = command_line_interface(['--cfgfile', f"../single_tests/{folder_test}/variable_3d_steps.ini"])
        parser.update({'output_path' : out_path })
        dict2call(parser)
        assert True