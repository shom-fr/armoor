from armoor.cli.command_line_interface import command_line_interface
from armoor.base.calls_from_dict import dict2call
from tests.int.base import change_path, copy_test_files

folder_test = 'test_f8'
copy_test_files(folder_test)

class TestBulletins:

    def test_graph2d(self):
        out_path, logger = change_path(folder_test)
        logger.info('test_graph2d')
        parser = command_line_interface(['--cfgfile', f"../single_tests/{folder_test}/graph2d.ini"])
        parser.update({'output_path' : out_path })
        dict2call(parser)
        assert True

    def test_graph2d_steps(self):
        out_path, logger = change_path(folder_test)
        logger.info('test_graph2d_steps')
        parser = command_line_interface(['--cfgfile', f"../single_tests/{folder_test}/graph2d_steps.ini"])
        parser.update({'output_path' : out_path })
        dict2call(parser)
        assert True

    def test_stick_plot_vmadcp(self):
        out_path, logger = change_path(folder_test)
        logger.info('test_stick_plot_vmadcp')
        parser = command_line_interface(['--cfgfile', f"../single_tests/{folder_test}/stick_plot_vmadcp.ini"])
        parser.update({'output_path' : out_path })
        dict2call(parser)
        assert True

    def test_stick_plot_vmadcp_hycom_1depth(self):
        out_path, logger = change_path(folder_test)
        logger.info('test_stick_plot_vmadcp_hycom_1depth')
        parser = command_line_interface(['--cfgfile', f"../single_tests/{folder_test}/stick_plot_vmadcp_hycom_1depth.ini"])
        parser.update({'output_path' : out_path })
        dict2call(parser)
        assert True

    def test_stick_plot_vmadcp_hycom_3depths(self):
        out_path, logger = change_path(folder_test)
        logger.info('test_stick_plot_vmadcp_hycom_3depths')
        parser = command_line_interface(['--cfgfile', f"../single_tests/{folder_test}/stick_plot_vmadcp_hycom_3depths.ini"])
        parser.update({'output_path' : out_path })
        dict2call(parser)
        assert True

    def test_stick_plot_vmadcp_steps(self):
        out_path, logger = change_path(folder_test)
        logger.info('test_stick_plot_vmadcp_steps')
        parser = command_line_interface(['--cfgfile', f"../single_tests/{folder_test}/stick_plot_vmadcp_steps.ini"])
        parser.update({'output_path' : out_path })
        dict2call(parser)
        assert True
