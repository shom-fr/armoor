from armoor.cli.command_line_interface import command_line_interface
from armoor.base.calls_from_dict import dict2call
from armoor.hmi.script_tools import create_folder
from tests.int.base import change_path, copy_test_files

folder_test = 'test_VA'
copy_test_files(folder_test)


class TestBulletins:

    def test_18_test_plot_ts_metr_stats(self):
        out_path, logger = change_path(folder_test)
        logger.info("test_18_test_plot_ts_metr_stats.ini")
        parser = command_line_interface(
            ['--cfgfile', f"../single_tests/{folder_test}/18_test_plot_ts_metr_stats.ini"])
        parser.update({'output_path': out_path})
        create_folder(f'tmp')
        dict2call(parser)
        assert True

    def test_23_issue_23(self):
        out_path, logger = change_path(folder_test)

        logger.info("test_23_issue_23.ini")
        parser = command_line_interface(
            ['--cfgfile', f"../single_tests/{folder_test}/23_issue_23.ini"])
        parser.update({'output_path': out_path})
        create_folder(f'tmp')
        dict2call(parser)
        assert True

    def test_26_issue_26(self):
        out_path, logger = change_path(folder_test)

        logger.info("test_26_issue_26.ini")
        parser = command_line_interface(
            ['--cfgfile', f"../single_tests/{folder_test}/26_issue_26.ini"])
        parser.update({'output_path': out_path})
        create_folder(f'tmp')
        dict2call(parser)
        assert True

    def test_28_f2(self):
        out_path, logger = change_path(folder_test)

        logger.info("test_28_f2.ini")
        parser = command_line_interface(['--cfgfile', f"../single_tests/{folder_test}/28_f2.ini"])
        parser.update({'output_path': out_path})
        create_folder(f'tmp')
        dict2call(parser)
        assert True

    def test_29_testL3Cquality(self):
        out_path, logger = change_path(folder_test)

        logger.info("test_29_testL3Cquality.ini")
        parser = command_line_interface(
            ['--cfgfile', f"../single_tests/{folder_test}/29_testL3Cquality.ini"])
        parser.update({'output_path': out_path})
        create_folder(f'tmp')
        dict2call(parser)
        assert True

    def test_30_testL4diagdispT(self):
        out_path, logger = change_path(folder_test)

        logger.info("test_30_testL4diagdispT.ini")
        parser = command_line_interface(
            ['--cfgfile', f"../single_tests/{folder_test}/30_testL4diagdispT.ini"])
        parser.update({'output_path': out_path})
        create_folder(f'tmp')
        dict2call(parser)
        assert True

    def test_31_test_plot_ts_metr_stats(self):
        out_path, logger = change_path(folder_test)

        logger.info("test_31_test_plot_ts_metr_stats.ini")
        parser = command_line_interface(
            ['--cfgfile', f"../single_tests/{folder_test}/31_test_plot_ts_metr_stats.ini"])
        parser.update({'output_path': out_path})
        create_folder(f'tmp')
        dict2call(parser)
        assert True

    def test_32_f2(self):
        out_path, logger = change_path(folder_test)

        logger.info("test_32_f2.ini")
        parser = command_line_interface(['--cfgfile', f"../single_tests/{folder_test}/32_f2.ini"])
        parser.update({'output_path': out_path})
        create_folder(f'tmp')
        dict2call(parser)
        assert True

    def test_36_test_sst_nov(self):
        out_path, logger = change_path(folder_test)

        logger.info("test_36_test_sst_nov.ini")
        parser = command_line_interface(
            ['--cfgfile', f"../single_tests/{folder_test}/36_test_sst_nov.ini"])
        parser.update({'output_path': out_path})
        create_folder(f'tmp')
        dict2call(parser)
        assert True

    def test_37_test_sst(self):
        out_path, logger = change_path(folder_test)

        logger.info("test_37_test_sst.ini")
        parser = command_line_interface(
            ['--cfgfile', f"../single_tests/{folder_test}/37_test_sst.ini"])
        parser.update({'output_path': out_path})
        create_folder(f'tmp')
        dict2call(parser)
        assert True

    def test_43_f9(self):
        out_path, logger = change_path(folder_test)

        logger.info("test_43_f9.ini")
        parser = command_line_interface(['--cfgfile', f"../single_tests/{folder_test}/43_f9.ini"])
        parser.update({'output_path': out_path})
        create_folder(f'tmp')
        dict2call(parser)
        assert True

    def test_55_test_map_current(self):
        out_path, logger = change_path(folder_test)

        logger.info("test_55_test_map_current.ini")
        parser = command_line_interface(
            ['--cfgfile', f"../single_tests/{folder_test}/55_test_map_current.ini"])
        parser.update({'output_path': out_path})
        create_folder(f'tmp')
        dict2call(parser)
        assert True

    def test_56_ser_temp_intervalles_PSY4(self):
        out_path, logger = change_path(folder_test)

        logger.info("test_56_ser_temp_intervalles_PSY4.ini")
        parser = command_line_interface(
            ['--cfgfile', f"../single_tests/{folder_test}/56_ser_temp_intervalles_PSY4.ini"])
        parser.update({'output_path': out_path})
        create_folder(f'tmp')
        dict2call(parser)
        assert True

    def test_75_diag_theta_s_unique_SCA(self):
        out_path, logger = change_path(folder_test)

        logger.info("test_75_diag_theta_s_unique_SCA.ini")
        parser = command_line_interface(
            ['--cfgfile', f"../single_tests/{folder_test}/75_diag_theta_s_unique_SCA.ini"])
        parser.update({'output_path': out_path})
        create_folder(f'tmp')
        dict2call(parser)
        assert True

    def test_76_map_biais_intervalles_tranches_SCA(self):
        out_path, logger = change_path(folder_test)

        logger.info("test_76_map_biais_intervalles_tranches_SCA.ini")
        parser = command_line_interface(['--cfgfile',
                                         f"../single_tests/{folder_test}/76_map_biais_intervalles_tranches_SCA.ini"])
        parser.update({'output_path': out_path})
        create_folder(f'tmp')
        dict2call(parser)
        assert True

    def test_77_diag_disp_SCA(self):
        out_path, logger = change_path(folder_test)

        logger.info("test_77_diag_disp_SCA.ini")
        parser = command_line_interface(
            ['--cfgfile', f"../single_tests/{folder_test}/77_diag_disp_SCA.ini"])
        parser.update({'output_path': out_path})
        create_folder(f'tmp')
        dict2call(parser)
        assert True

    def test_78_profil_multi_temp_SCA(self):
        out_path, logger = change_path(folder_test)

        logger.info("test_78_profil_multi_temp_SCA.ini")
        parser = command_line_interface(
            ['--cfgfile', f"../single_tests/{folder_test}/78_profil_multi_temp_SCA.ini"])
        parser.update({'output_path': out_path})
        create_folder(f'tmp')
        dict2call(parser)
        assert True

    def test_79_ser_temp_stat_SCA(self):
        out_path, logger = change_path(folder_test)

        logger.info("test_79_ser_temp_stat_SCA.ini")
        parser = command_line_interface(
            ['--cfgfile', f"../single_tests/{folder_test}/79_ser_temp_stat_SCA.ini"])
        parser.update({'output_path': out_path})
        create_folder(f'tmp')
        dict2call(parser)
        assert True

    def test_80_ellipses_ADCP_CROCO(self):
        out_path, logger = change_path(folder_test)

        logger.info("test_80_ellipses_ADCP_CROCO.ini")
        parser = command_line_interface(
            ['--cfgfile', f"../single_tests/{folder_test}/80_ellipses_ADCP_CROCO.ini"])
        parser.update({'output_path': out_path})
        create_folder(f'tmp')
        dict2call(parser)
        assert True

    def test_82_test_variable_3d_PSY4_SCA(self):
        out_path, logger = change_path(folder_test)

        logger.info("test_82_test_variable_3d_PSY4_SCA.ini")
        parser = command_line_interface(
            ['--cfgfile', f"../single_tests/{folder_test}/82_test_variable_3d_PSY4_SCA.ini"])
        parser.update({'output_path': out_path})
        create_folder(f'tmp')
        dict2call(parser)
        assert True

    def test_82_test_variable_3d_PSY4_SCA_nov(self):
        out_path, logger = change_path(folder_test)

        logger.info("test_82_test_variable_3d_PSY4_SCA_nov.ini")
        parser = command_line_interface(
            ['--cfgfile', f"../single_tests/{folder_test}/82_test_variable_3d_PSY4_SCA.ini"])
        parser.update({'output_path': out_path})
        create_folder(f'tmp')
        dict2call(parser)
        assert True

    def test_83_test_variable_2d_SCA(self):
        out_path, logger = change_path(folder_test)

        logger.info("test_83_test_variable_2d_SCA.ini")
        parser = command_line_interface(
            ['--cfgfile', f"../single_tests/{folder_test}/83_test_variable_2d_SCA.ini"])
        parser.update({'output_path': out_path})
        create_folder(f'tmp')
        dict2call(parser)
        assert True

    def test_87_ser_temp_ponct_SCA(self):
        out_path, logger = change_path(folder_test)

        logger.info("test_87_ser_temp_ponct_SCA.ini")
        parser = command_line_interface(
            ['--cfgfile', f"../single_tests/{folder_test}/87_ser_temp_ponct_SCA.ini"])
        parser.update({'output_path': out_path})
        create_folder(f'tmp')
        dict2call(parser)
        assert True

    def test_88_ser_temp_stats_SCA(self):
        out_path, logger = change_path(folder_test)

        logger.info("test_88_ser_temp_stats_SCA.ini")
        parser = command_line_interface(
            ['--cfgfile', f"../single_tests/{folder_test}/88_ser_temp_stats_SCA.ini"])
        parser.update({'output_path': out_path})
        create_folder(f'tmp')
        dict2call(parser)
        assert True

    def test_94_ser_temp_uv_stat_intervalles_SCA(self):
        out_path, logger = change_path(folder_test)

        logger.info("test_94_ser_temp_uv_stat_intervalles_SCA.ini")
        parser = command_line_interface(
            ['--cfgfile', f"../single_tests/{folder_test}/94_ser_temp_uv_stat_intervalles_SCA.ini"])
        parser.update({'output_path': out_path})
        create_folder(f'tmp')
        dict2call(parser)
        assert True
