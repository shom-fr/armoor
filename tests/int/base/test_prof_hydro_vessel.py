from armoor.cli.command_line_interface import command_line_interface
from armoor.base.calls_from_dict import dict2call
from tests.int.base import change_path, copy_test_files

folder_test = 'test_f2'
copy_test_files(folder_test)


class TestBulletins:

    def test_diag_disp(self):  # OK
        out_path, logger = change_path(folder_test)
        logger.info('test_diag_disp')
        parser = command_line_interface(
            ['--cfgfile', f"../single_tests/{folder_test}/diag_disp.cfg"])
        parser.update({'output_path': out_path})
        dict2call(parser)
        assert True

    def test_multi_plot_tranche_intervalle(self):  # OK
        out_path, logger = change_path(folder_test)
        logger.info('test_multi_plot_tranche_intervalle')
        parser = command_line_interface(
            ['--cfgfile', f"../single_tests/{folder_test}/multi_plot_tranche_intervalle.cfg"])
        parser.update({'output_path': out_path})
        dict2call(parser)
        assert True

    def test_diag_theta_s_multi(self):  # OK
        out_path, logger = change_path(folder_test)
        logger.info('test_diag_theta_s_multi')
        parser = command_line_interface(
            ['--cfgfile', f"../single_tests/{folder_test}/diag_theta_s_multi.cfg"])
        parser.update({'output_path': out_path})
        dict2call(parser)
        assert True

    def test_diag_theta_s_multi_dens(self):  # OK
        out_path, logger = change_path(folder_test)
        logger.info('test_diag_theta_s_multi_dens')
        parser = command_line_interface(
            ['--cfgfile', f"../single_tests/{folder_test}/diag_theta_s_multi_dens.cfg"])
        parser.update({'output_path': out_path})
        dict2call(parser)
        assert True

    def test_diag_theta_s_unique(self):  # OK
        out_path, logger = change_path(folder_test)
        logger.info('test_diag_theta_s_unique')
        parser = command_line_interface(
            ['--cfgfile', f"../single_tests/{folder_test}/diag_theta_s_unique.cfg"])
        parser.update({'output_path': out_path})
        dict2call(parser)
        assert True

    def test_map_diff(self):  # OK
        out_path, logger = change_path(folder_test)
        logger.info('test_map_diff')
        parser = command_line_interface(
            ['--cfgfile', f"../single_tests/{folder_test}/map_diff.cfg"])
        parser.update({'output_path': out_path})
        dict2call(parser)
        assert True

    def test_map_diff_intervalles(self):  # OK
        out_path, logger = change_path(folder_test)
        logger.info('test_map_diff_intervalles')
        parser = command_line_interface(
            ['--cfgfile', f"../single_tests/{folder_test}/map_diff_intervalles.cfg"])
        parser.update({'output_path': out_path})
        dict2call(parser)
        assert True

    def test_profil_multi_temp(self):  # OK
        out_path, logger = change_path(folder_test)
        logger.info('test_profil_multi_temp')
        parser = command_line_interface(
            ['--cfgfile', f"../single_tests/{folder_test}/profil_multi_temp.cfg"])
        parser.update({'output_path': out_path})
        dict2call(parser)
        assert True

    def test_profil_unique_temp(self):  # OK
        out_path, logger = change_path(folder_test)
        logger.info('test_profil_unique_temp')
        parser = command_line_interface(
            ['--cfgfile', f"../single_tests/{folder_test}/profil_unique_temp.cfg"])
        parser.update({'output_path': out_path})
        dict2call(parser)
        assert True

    def test_ser_temp_intervalles(self):  # OK
        out_path, logger = change_path(folder_test)
        logger.info('test_ser_temp_intervalles')
        parser = command_line_interface(
            ['--cfgfile', f"../single_tests/{folder_test}/ser_temp_intervalles.cfg"])
        parser.update({'output_path': out_path})
        dict2call(parser)
        assert True

    def test_diag_ts_psy4(self):
        out_path, logger = change_path(folder_test)

        logger.info("test_diag_ts_psy4.cfg")
        parser = command_line_interface(['--cfgfile', f"../single_tests/{folder_test}/diag_ts_psy4.cfg"])
        parser.update({'output_path': out_path})
        dict2call(parser)
        assert True

    def test_diag_ts_multi_cora(self):
        out_path, logger = change_path(folder_test)

        logger.info("test_diag_ts_multi_cora.cfg")
        parser = command_line_interface(['--cfgfile', f"../single_tests/{folder_test}/diag_ts_multi_cora.cfg"])
        parser.update({'output_path': out_path})
        dict2call(parser)
        assert True

    def test_ser_temp_tranches(self):
        out_path, logger = change_path(folder_test)

        logger.info("test_ser_temp_tranches.cfg")
        parser = command_line_interface(
            ['--cfgfile', f"../single_tests/{folder_test}/ser_temp_tranches.cfg"])
        parser.update({'output_path': out_path})
        dict2call(parser)
        assert True

    def test_diag_theta_s_unique_SCA(self):
        out_path, logger = change_path(folder_test)

        logger.info("test_diag_theta_s_unique_SCA.cfg")
        parser = command_line_interface(
            ['--cfgfile', f"../single_tests/{folder_test}/diag_theta_s_unique_SCA.cfg"])
        parser.update({'output_path': out_path})
        dict2call(parser)
        assert True

    def test_map_biais_intervalles_tranches_SCA(self):
        out_path, logger = change_path(folder_test)

        logger.info("test_map_biais_intervalles_tranches_SCA.cfg")
        parser = command_line_interface(['--cfgfile',
                                         f"../single_tests/{folder_test}/map_biais_intervalles_tranches_SCA.cfg"])
        parser.update({'output_path': out_path})
        # create_folder(f'tmp')
        dict2call(parser)
        assert True

    def test_diag_disp_SCA(self):
        out_path, logger = change_path(folder_test)

        logger.info("test_diag_disp_SCA.cfg")
        parser = command_line_interface(
            ['--cfgfile', f"../single_tests/{folder_test}/diag_disp_SCA.cfg"])
        parser.update({'output_path': out_path})
        # create_folder(f'tmp')
        dict2call(parser)
        assert True

    def test_profil_multi_temp_SCA(self):
        out_path, logger = change_path(folder_test)

        logger.info("test_profil_multi_temp_SCA.cfg")
        parser = command_line_interface(
            ['--cfgfile', f"../single_tests/{folder_test}/profil_multi_temp_SCA.cfg"])
        parser.update({'output_path': out_path})
        # create_folder(f'tmp')
        dict2call(parser)
        assert True

    def test_ser_temp_stat_SCA(self):
        out_path, logger = change_path(folder_test)

        logger.info("test_ser_temp_stat_SCA.cfg")
        parser = command_line_interface(
            ['--cfgfile', f"../single_tests/{folder_test}/ser_temp_stat_SCA.cfg"])
        parser.update({'output_path': out_path})
        # create_folder(f'tmp')
        dict2call(parser)
        assert True

    def test_diag_disp_argo(self):
        out_path, logger = change_path(folder_test)

        logger.info("test_diag_disp_argo.cfg")
        parser = command_line_interface(
            ['--cfgfile', f"../single_tests/{folder_test}/diag_disp_argo.cfg"])
        parser.update({'output_path': out_path})
        # create_folder(f'tmp')
        dict2call(parser)
        assert True

    def test_diag_disp_list_flotteurs(self):
        out_path, logger = change_path(folder_test)

        logger.info("test_diag_disp_list_flotteurs.cfg")
        parser = command_line_interface(
            ['--cfgfile', f"../single_tests/{folder_test}/diag_disp_list_flotteurs.cfg"])
        parser.update({'output_path': out_path})
        # create_folder(f'tmp')
        dict2call(parser)
        assert True