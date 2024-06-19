from armoor.cli.command_line_interface import command_line_interface
from armoor.base.calls_from_dict import dict2call
from tests.int.base import change_path, copy_test_files

folder_test = 'test_f9'
copy_test_files(folder_test)


class TestBulletins:

    def test_map_current_db(self):  # OK
        out_path, logger = change_path(folder_test)
        logger.info('test_map_current_DB')
        parser = command_line_interface(['--cfgfile', f"../single_tests/{folder_test}/map_current_DB.cfg"])
        parser.update({'output_path': out_path})
        dict2call(parser)
        assert True

    def test_map_trajectory(self):  # OK
        out_path, logger = change_path(folder_test)
        logger.info('test_map_trajectory')
        parser = command_line_interface(['--cfgfile', f"../single_tests/{folder_test}/map_trajectory.cfg"])
        parser.update({'output_path': out_path})
        dict2call(parser)
        assert True

    def test_map_trajectory_hycom_multi_drifters(self):
        out_path, logger = change_path(folder_test)
        logger.info("test_map_trajectory_hycom_multi_drifters")
        parser = command_line_interface(['--cfgfile', f"../single_tests/{folder_test}/map_trajectory_hycom_multi_drifters.cfg"])
        parser.update({'output_path': out_path})
        dict2call(parser)
        assert True

    def test_map_trajectory_hycom_nemo_multi_drifters(self):
        out_path, logger = change_path(folder_test)
        logger.info("test_map_trajectory_hycom_nemo_multi_drifters")
        parser = command_line_interface(['--cfgfile', f"../single_tests/{folder_test}/map_trajectory_hycom_nemo_multi_drifters.cfg"])
        parser.update({'output_path': out_path})
        dict2call(parser)
        assert True

    def test_map_trajectory_hycom_multi_drifters_current(self):
        out_path, logger = change_path(folder_test)
        logger.info("test_map_trajectory_hycom_multi_drifters_current")
        parser = command_line_interface(['--cfgfile', f"../single_tests/{folder_test}/map_trajectory_hycom_multi_drifters_current.cfg"])
        parser.update({'output_path': out_path})
        dict2call(parser)
        assert True

    def test_plot_diff_traj_distance(self):  # OK
        out_path, logger = change_path(folder_test)
        logger.info('test_plot_diff_traj_distance')
        parser = command_line_interface(['--cfgfile', f"../single_tests/{folder_test}/plot_diff_traj_distance.cfg"])
        parser.update({'output_path': out_path})
        dict2call(parser)
        assert True

    def test_map_trajectory_topaz(self):  # OK
        out_path, logger = change_path(folder_test)
        logger.info('test_map_trajectory_TOPAZ')
        parser = command_line_interface(['--cfgfile', f"../single_tests/{folder_test}/map_trajectory_TOPAZ.cfg"])
        parser.update({'output_path': out_path})
        dict2call(parser)
        assert True
    def test_map_trajectory_hycom(self):
        out_path, logger = change_path(folder_test)
        logger.info("test_map_trajectory_hycom")
        parser = command_line_interface(['--cfgfile', f"../single_tests/{folder_test}/map_trajectory_hycom.cfg"])
        parser.update({'output_path': out_path})
        dict2call(parser)
        assert True

    def test_map_multi_traj(self):
        out_path, logger = change_path(folder_test)
        logger.info("test_map_multi_traj")
        parser = command_line_interface(['--cfgfile', f"../single_tests/{folder_test}/map_multi_traj.cfg"])
        parser.update({'output_path': out_path})
        dict2call(parser)
        assert True