from armoor.cli.command_line_interface import command_line_interface
from armoor.base.calls_from_dict import dict2call
from tests.int.base import change_path, copy_test_files

folder_test = 'test_f3'
copy_test_files(folder_test)


class TestBulletins:

    def test_ser_temp_stat(self):  # OK
        out_path, logger = change_path(folder_test)
        logger.info('test_ser_temp_stat')
        parser = command_line_interface(['--cfgfile', f"../single_tests/{folder_test}/ser_temp_stat.cfg"])
        parser.update({'output_path': out_path})
        dict2call(parser)
        assert True
