from armoor.cli.command_line_interface import command_line_interface
from armoor.base.calls_from_dict import dict2call
from armoor.hmi.script_tools import create_folder
from tests.int.base import change_path, copy_test_files

folder_test = 'test_VA'
copy_test_files(folder_test)


class TestBulletins:

    def test_ticket_32(self):
        out_path, logger = change_path(folder_test)
        logger.info('test_ticket_32')
        parser = command_line_interface(['--cfgfile', f"../single_tests/{folder_test}/ticket_32.ini"])
        parser.update({'output_path': out_path})
        create_folder(f'tmp')
        dict2call(parser)
        assert True

    def test_ticket_31(self):
        out_path, logger = change_path(folder_test)
        logger.info('test_ticket_31')
        parser = command_line_interface(['--cfgfile', f"../single_tests/{folder_test}/ticket_31.ini"])
        parser.update({'output_path': out_path})
        create_folder(f'tmp')
        dict2call(parser)
        assert True

    def test_ticket_25(self):
        out_path, logger = change_path(folder_test)
        logger.info('test_ticket_25')
        parser = command_line_interface(['--cfgfile', f"../single_tests/{folder_test}/ticket_25.ini"])
        parser.update({'output_path': out_path})
        create_folder(f'tmp')
        dict2call(parser)
        assert True
