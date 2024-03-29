from armoor.cli.command_line_interface import command_line_interface
from armoor.base.calls_from_dict import dict2call
from tests.int.base import change_path, copy_test_files

folder_test = 'test_f1'
copy_test_files(folder_test)


class TestBulletins:

    def test_diag_disp_sst(self):  # OK
        out_path, logger = change_path(folder_test)
        logger.info('test_diag_disp_sst')
        parser = command_line_interface(['--cfgfile', f"../single_tests/{folder_test}/diag_disp_sst.cfg"])
        parser.update({'output_path': out_path})
        dict2call(parser)
        assert True

    def test_map_sst_biais(self):  # OK
        out_path, logger = change_path(folder_test)
        logger.info('test_map_sst_biais')
        parser = command_line_interface(['--cfgfile', f"../single_tests/{folder_test}/map_sst_biais.cfg"])
        parser.update({'output_path': out_path})
        dict2call(parser)
        assert True

    def test_map_sst_diff(self):  # OK
        out_path, logger = change_path(folder_test)
        logger.info('test_map_sst_diff')
        parser = command_line_interface(['--cfgfile', f"../single_tests/{folder_test}/map_sst_diff.cfg"])
        parser.update({'output_path': out_path})
        dict2call(parser)
        assert True

    def test_map_sst_diff_seuil_bathy(self):  # OK
        out_path, logger = change_path(folder_test)
        logger.info('test_map_sst_diff_seuil_bathy')
        parser = command_line_interface(['--cfgfile', f"../single_tests/{folder_test}/map_sst_diff_seuil_bathy.cfg"])
        parser.update({'output_path': out_path})
        dict2call(parser)
        assert True

    def test_map_sst_diff_topaz(self):  # OK
        out_path, logger = change_path(folder_test)
        logger.info('test_map_sst_diff_TOPAZ')
        parser = command_line_interface(['--cfgfile', f"../single_tests/{folder_test}/map_sst_diff_TOPAZ.cfg"])
        parser.update({'output_path': out_path})
        dict2call(parser)
        assert True

    def test_map_sst_rmse(self):  # OK
        out_path, logger = change_path(folder_test)
        logger.info('test_map_sst_rmse')
        parser = command_line_interface(['--cfgfile', f"../single_tests/{folder_test}/map_sst_rmse.cfg"])
        parser.update({'output_path': out_path})
        dict2call(parser)
        assert True

    def test_map_sst_rmse_centree(self):  # OK
        out_path, logger = change_path(folder_test)
        logger.info('test_map_sst_rmse_centree')
        parser = command_line_interface(['--cfgfile', f"../single_tests/{folder_test}/map_sst_rmse_centree.cfg"])
        parser.update({'output_path': out_path})
        dict2call(parser)
        assert True

    def test_ser_temp_sst(self):  # OK
        out_path, logger = change_path(folder_test)
        logger.info('test_ser_temp_sst')
        parser = command_line_interface(['--cfgfile', f"../single_tests/{folder_test}/ser_temp_sst.cfg"])
        parser.update({'output_path': out_path})
        dict2call(parser)
        assert True

    def test_ser_temp_sst_ponct_diff(self):  # OK
        out_path, logger = change_path(folder_test)
        logger.info('test_ser_temp_sst_ponct_diff')
        parser = command_line_interface(['--cfgfile', f"../single_tests/{folder_test}/ser_temp_sst_ponct_diff.cfg"])
        parser.update({'output_path': out_path})
        dict2call(parser)
        assert True

    def test_ser_temp_sst_ponct_intervalles(self):  # OK
        out_path, logger = change_path(folder_test)
        logger.info('test_ser_temp_sst_ponct_intervalles')
        parser = command_line_interface(
            ['--cfgfile', f"../single_tests/{folder_test}/ser_temp_sst_ponct_intervalles.cfg"])
        parser.update({'output_path': out_path})
        dict2call(parser)
        assert True

    def test_sst_stats(self):
        out_path, logger = change_path(folder_test)
        logger.info("test_sst_stats")
        parser = command_line_interface(
            ['--cfgfile', f"../single_tests/{folder_test}/sst_stats.cfg"])
        parser.update({'output_path': out_path})
        dict2call(parser)
        assert True

    def test_sst_map_diff_hycom(self):
        out_path, logger = change_path(folder_test)
        logger.info("test_sst_map_diff_hycom")
        parser = command_line_interface(
            ['--cfgfile', f"../single_tests/{folder_test}/sst_map_diff_hycom.cfg"])
        parser.update({'output_path': out_path})
        dict2call(parser)
        assert True

    def test_map_sst_diff_quality(self):
        out_path, logger = change_path(folder_test)
        logger.info("test_map_sst_diff_quality")
        parser = command_line_interface(
            ['--cfgfile', f"../single_tests/{folder_test}/map_sst_diff_quality.cfg"])
        parser.update({'output_path': out_path})
        dict2call(parser)
        assert True

    def test_diag_disp_L4(self):
        out_path, logger = change_path(folder_test)
        logger.info("test_diag_disp_L4")
        parser = command_line_interface(
            ['--cfgfile', f"../single_tests/{folder_test}/diag_disp_L4.cfg"])
        parser.update({'output_path': out_path})
        dict2call(parser)
        assert True

    def test_sst_stats_intervalles(self):
        out_path, logger = change_path(folder_test)
        logger.info("test_sst_stats_intervalles")
        parser = command_line_interface(
            ['--cfgfile', f"../single_tests/{folder_test}/sst_stats_intervalles.cfg"])
        parser.update({'output_path': out_path})
        dict2call(parser)
        assert True

    def test_map_diff_croco(self):
        out_path, logger = change_path(folder_test)
        logger.info("test_map_diff_croco")
        parser = command_line_interface(
            ['--cfgfile', f"../single_tests/{folder_test}/map_diff_croco.cfg"])
        parser.update({'output_path': out_path})
        dict2call(parser)
        assert True