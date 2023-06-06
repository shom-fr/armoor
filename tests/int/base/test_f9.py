from armoor.cli.command_line_interface import command_line_interface
from armoor.base.calls_from_dict import dict2call
from armoor.hmi.script_tools import create_folder
from tests.int.base import change_path, copy_test_files

folder_test = 'test_f9'
copy_test_files(folder_test)


class TestBulletins:

    def test_map_current_db(self):  # OK
        out_path, logger = change_path(folder_test)
        logger.info('test_map_current_DB')
        parser = command_line_interface(['--cfgfile', f"../single_tests/{folder_test}/map_current_DB.ini"])
        parser.update({'output_path': out_path})
        dict2call(parser)
        assert True

    def test_map_trajectory(self):  # OK
        out_path, logger = change_path(folder_test)
        logger.info('test_map_trajectory')
        parser = command_line_interface(['--cfgfile', f"../single_tests/{folder_test}/map_trajectory.ini"])
        parser.update({'output_path': out_path})
        dict2call(parser)
        assert True

    def test_plot_diff_traj_distance(self):  # OK
        out_path, logger = change_path(folder_test)
        logger.info('test_plot_diff_traj_distance')
        parser = command_line_interface(['--cfgfile', f"../single_tests/{folder_test}/plot_diff_traj_distance.ini"])
        parser.update({'output_path': out_path})
        dict2call(parser)
        assert True

    def test_map_trajectory_topaz(self):  # OK
        out_path, logger = change_path(folder_test)
        logger.info('test_map_trajectory_TOPAZ')
        parser = command_line_interface(['--cfgfile', f"../single_tests/{folder_test}/map_trajectory_TOPAZ.ini"])
        parser.update({'output_path': out_path})
        dict2call(parser)
        assert True
