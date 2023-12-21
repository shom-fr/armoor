from armoor.cli.command_line_interface import command_line_interface
from armoor.base.calls_from_dict import dict2call
from armoor.hmi.script_tools import create_folder
from tests.int.base import change_path, copy_test_files

folder_test = 'test_VA_2'
copy_test_files(folder_test)


class TestBulletins:
    def test_120_map_harm_courant_mini_nov(self):
        out_path, logger = change_path(folder_test)
        logger.info("test_120_map_harm_courant_mini_nov.cfg")
        parser = command_line_interface(
            ['--cfgfile', f"../single_tests/{folder_test}/120_map_harm_courant_mini_nov.cfg"])
        parser.update({'output_path': out_path})
        create_folder(f'tmp')
        dict2call(parser)
        assert True

    def test_127_stats_nov(self):
        out_path, logger = change_path(folder_test)
        logger.info("test_127_stats_nov.ini")
        parser = command_line_interface(
            ['--cfgfile', f"../single_tests/{folder_test}/127_stats_nov.ini"])
        parser.update({'output_path': out_path})
        create_folder(f'tmp')
        dict2call(parser)
        assert True

    def test_132_section_nov(self):
        out_path, logger = change_path(folder_test)
        logger.info("test_132_section_nov.ini")
        parser = command_line_interface(
            ['--cfgfile', f"../single_tests/{folder_test}/132_section_nov.ini"])
        parser.update({'output_path': out_path})
        create_folder(f'tmp')
        dict2call(parser)
        assert True

    def test_142_map_diff_nov(self):
        out_path, logger = change_path(folder_test)
        logger.info("test_142_map_diff_nov.cfg")
        parser = command_line_interface(
            ['--cfgfile', f"../single_tests/{folder_test}/142_map_diff_nov.cfg"])
        parser.update({'output_path': out_path})
        create_folder(f'tmp')
        dict2call(parser)
        assert True

    def test_156_map_current_hycom2Det3D(self):
        out_path, logger = change_path(folder_test)
        logger.info("test_156_map_current_hycom2Det3D.cfg")
        parser = command_line_interface(
            ['--cfgfile', f"../single_tests/{folder_test}/156_map_current_hycom2Det3D.cfg"])
        parser.update({'output_path': out_path})
        create_folder(f'tmp')
        dict2call(parser)
        assert True

    def test_121_diagramme_dispersion(self):
        out_path, logger = change_path(folder_test)
        logger.info("test_121_diagramme_dispersion.ini")
        parser = command_line_interface(
            ['--cfgfile', f"../single_tests/{folder_test}/121_diagramme_dispersion.ini"])
        parser.update({'output_path': out_path})
        create_folder(f'tmp')
        dict2call(parser)
        assert True

    def test_128_ser_temp_uv_ponct_mini_nov(self):
        out_path, logger = change_path(folder_test)
        logger.info("test_128_ser_temp_uv_ponct_mini_nov.cfg")
        parser = command_line_interface(
            ['--cfgfile', f"../single_tests/{folder_test}/128_ser_temp_uv_ponct_mini_nov.cfg"])
        parser.update({'output_path': out_path})
        create_folder(f'tmp')
        dict2call(parser)
        assert True

    def test_135_ellipse_courant_utide_FROMVEUR(self):
        out_path, logger = change_path(folder_test)
        logger.info("test_135_ellipse_courant_utide_FROMVEUR.cfg")
        parser = command_line_interface(
            ['--cfgfile', f"../single_tests/{folder_test}/135_ellipse_courant_utide_FROMVEUR.cfg"])
        parser.update({'output_path': out_path})
        create_folder(f'tmp')
        dict2call(parser)
        assert True

    def test_143_ser_temp_ponct(self):
        out_path, logger = change_path(folder_test)
        logger.info("test_143_ser_temp_ponct.cfg")
        parser = command_line_interface(
            ['--cfgfile', f"../single_tests/{folder_test}/143_ser_temp_ponct.cfg"])
        parser.update({'output_path': out_path})
        create_folder(f'tmp')
        dict2call(parser)
        assert True

    # def test_pasdedata145_diag_disp_argo(self):
    #     out_path, logger = change_path(folder_test)
    #     logger.info("test_pasdedata145_diag_disp_argo.ini")
    #     parser = command_line_interface(
    #         ['--cfgfile', f"../single_tests/{folder_test}/pasdedata145_diag_disp_argo.ini"])
    #     parser.update({'output_path': out_path})
    #     create_folder(f'tmp')
    #     dict2call(parser)
    #     assert True

    def test_123_harmonic_table_ADCP_CROCO(self):
        out_path, logger = change_path(folder_test)
        logger.info("test_123_harmonic_table_ADCP_CROCO.ini")
        parser = command_line_interface(
            ['--cfgfile', f"../single_tests/{folder_test}/123_harmonic_table_ADCP_CROCO.ini"])
        parser.update({'output_path': out_path})
        create_folder(f'tmp')
        dict2call(parser)
        assert True

    def test_129_glider(self):
        out_path, logger = change_path(folder_test)
        logger.info("test_129_glider.ini")
        parser = command_line_interface(
            ['--cfgfile', f"../single_tests/{folder_test}/129_glider.ini"])
        parser.update({'output_path': out_path})
        create_folder(f'tmp')
        dict2call(parser)
        assert True

    def test_137_hovmoller_FROMVEUR(self):
        out_path, logger = change_path(folder_test)
        logger.info("test_137_hovmoller_FROMVEUR.cfg")
        parser = command_line_interface(
            ['--cfgfile', f"../single_tests/{folder_test}/137_hovmoller_FROMVEUR.cfg"])
        parser.update({'output_path': out_path})
        create_folder(f'tmp')
        dict2call(parser)
        assert True

    def test_144_ser_temp_stats_nov(self):
        out_path, logger = change_path(folder_test)
        logger.info("test_144_ser_temp_stats_nov.cfg")
        parser = command_line_interface(
            ['--cfgfile', f"../single_tests/{folder_test}/144_ser_temp_stats_nov.cfg"])
        parser.update({'output_path': out_path})
        create_folder(f'tmp')
        dict2call(parser)
        assert True

    def test_124_ellipses_ADCP_CROCO(self):
        out_path, logger = change_path(folder_test)
        logger.info("test_124_ellipses_ADCP_CROCO.ini")
        parser = command_line_interface(
            ['--cfgfile', f"../single_tests/{folder_test}/124_ellipses_ADCP_CROCO.ini"])
        parser.update({'output_path': out_path})
        create_folder(f'tmp')
        dict2call(parser)
        assert True

    def test_130_map_nov(self):
        out_path, logger = change_path(folder_test)
        logger.info("test_130_map_nov.ini")
        parser = command_line_interface(
            ['--cfgfile', f"../single_tests/{folder_test}/130_map_nov.ini"])
        parser.update({'output_path': out_path})
        create_folder(f'tmp')
        dict2call(parser)
        assert True

    def test_138_harmonic_table_FROMVEUR(self):
        out_path, logger = change_path(folder_test)
        logger.info("test_138_harmonic_table_FROMVEUR.cfg")
        parser = command_line_interface(
            ['--cfgfile', f"../single_tests/{folder_test}/138_harmonic_table_FROMVEUR.cfg"])
        parser.update({'output_path': out_path})
        create_folder(f'tmp')
        dict2call(parser)
        assert True

    def test_146_diag_ts_unique(self):
        out_path, logger = change_path(folder_test)
        logger.info("test_146_diag_ts_unique.ini")
        parser = command_line_interface(
            ['--cfgfile', f"../single_tests/{folder_test}/146_diag_ts_unique.ini"])
        parser.update({'output_path': out_path})
        create_folder(f'tmp')
        dict2call(parser)
        assert True

    def test_125_harmonic_table_ADCP_CROCO_test_lecture(self):
        out_path, logger = change_path(folder_test)
        logger.info("test_125_harmonic_table_ADCP_CROCO_test_lecture.ini")
        parser = command_line_interface(['--cfgfile',
                                         f"../single_tests/{folder_test}/125_harmonic_table_ADCP_CROCO_test_lecture.ini"])
        parser.update({'output_path': out_path})
        create_folder(f'tmp')
        dict2call(parser)
        assert True

    def test_131_map_trajectory_nov(self):
        out_path, logger = change_path(folder_test)
        logger.info("test_131_map_trajectory_nov.ini")
        parser = command_line_interface(
            ['--cfgfile', f"../single_tests/{folder_test}/131_map_trajectory_nov.ini"])
        parser.update({'output_path': out_path})
        create_folder(f'tmp')
        dict2call(parser)
        assert True

    def test_140_map_sst_hycomglo12_rms_nov(self):
        out_path, logger = change_path(folder_test)
        logger.info("test_140_map_sst_hycomglo12_rms_nov.ini")
        parser = command_line_interface(
            ['--cfgfile', f"../single_tests/{folder_test}/140_map_sst_hycomglo12_rms_nov.ini"])
        parser.update({'output_path': out_path})
        create_folder(f'tmp')
        dict2call(parser)
        assert True

    def test_154_ellipse_courant_et_periode(self):
        out_path, logger = change_path(folder_test)
        logger.info("test_154_ellipse_courant_et_periode.cfg")
        parser = command_line_interface(
            ['--cfgfile', f"../single_tests/{folder_test}/154_ellipse_courant_et_periode.cfg"])
        parser.update({'output_path': out_path})
        create_folder(f'tmp')
        dict2call(parser)
        assert True
