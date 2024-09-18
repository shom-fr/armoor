from armoor.cli.command_line_interface import command_line_interface
from armoor.base.calls_from_dict import dict2call
from armoor.hmi.script_tools import create_folder
from tests.int.base import change_path, copy_test_files, update_comodo

folder_test = 'test_f6'
copy_test_files(folder_test)


class TestBulletins:

    def test_ellipse_courant_et_periode(self):  # OK
        out_path, logger = change_path(folder_test)
        logger.info('test_ellipse_courant_et_periode')
        parser = command_line_interface(['--cfgfile', f"../single_tests/{folder_test}/ellipse_courant_et_periode.cfg"])
        parser.update({'output_path': out_path})
        parser = update_comodo(parser)
        dict2call(parser)
        assert True

    def test_map_current(self):  # OK
        out_path, logger = change_path(folder_test)
        logger.info('test_map_current')
        parser = command_line_interface(['--cfgfile', f"../single_tests/{folder_test}/map_current.cfg"])
        parser.update({'output_path': out_path})
        dict2call(parser)
        assert True

    def test_map_current_biais(self):  # OK
        out_path, logger = change_path(folder_test)
        logger.info('test_map_current_biais')
        parser = command_line_interface(['--cfgfile', f"../single_tests/{folder_test}/map_current_biais.cfg"])
        parser.update({'output_path': out_path})
        dict2call(parser)
        assert True

    def test_map_current_res_biais(self):  # OK
        out_path, logger = change_path(folder_test)
        logger.info('test_map_current_res_biais')
        parser = command_line_interface(['--cfgfile', f"../single_tests/{folder_test}/map_current_res_biais.cfg"])
        parser.update({'output_path': out_path})
        dict2call(parser)
        assert True

    def test_map_current_croco(self):
        out_path, logger = change_path(folder_test)
        logger.info('test_map_current_croco')
        parser = command_line_interface(['--cfgfile', f"../single_tests/{folder_test}/map_current_croco.cfg"])
        parser.update({'output_path': out_path})
        dict2call(parser)
        assert True

    def test_map_current_hycom2det3d(self):
        out_path, logger = change_path(folder_test)
        logger.info('test_map_current_hycom2Det3D')
        parser = command_line_interface(['--cfgfile', f"../single_tests/{folder_test}/map_current_hycom2Det3D.cfg"])
        parser.update({'output_path': out_path})
        dict2call(parser)
        assert True

    def test_map_current_rmse(self):  # OK
        out_path, logger = change_path(folder_test)
        logger.info('test_map_current_RMSE')
        parser = command_line_interface(['--cfgfile', f"../single_tests/{folder_test}/map_current_RMSE.cfg"])
        parser.update({'output_path': out_path})
        dict2call(parser)
        assert True

    def test_map_harm_courant(self):  # OK
        out_path, logger = change_path(folder_test)
        logger.info('test_map_harm_courant')
        parser = command_line_interface(['--cfgfile', f"../single_tests/{folder_test}/map_harm_courant.cfg"])
        parser.update({'output_path': out_path})
        parser = update_comodo(parser)
        dict2call(parser)
        assert True

    def test_ser_temp_uv_ponct(self):  # OK
        out_path, logger = change_path(folder_test)
        logger.info('test_ser_temp_uv_ponct')
        parser = command_line_interface(['--cfgfile', f"../single_tests/{folder_test}/ser_temp_uv_ponct.cfg"])
        parser.update({'output_path': out_path})
        dict2call(parser)
        assert True

    def test_ser_temp_uv_res_ponct(self):  # OK
        out_path, logger = change_path(folder_test)
        logger.info('test_ser_temp_uv_res_ponct')
        parser = command_line_interface(['--cfgfile', f"../single_tests/{folder_test}/ser_temp_uv_res_ponct.cfg"])
        parser.update({'output_path': out_path})
        dict2call(parser)
        assert True

    def test_ser_temp_uv_ponct_intervalles(self):  # OK
        out_path, logger = change_path(folder_test)
        logger.info('test_ser_temp_uv_ponct_intervalles')
        parser = command_line_interface(
            ['--cfgfile', f"../single_tests/{folder_test}/ser_temp_uv_ponct_intervalles.cfg"])
        parser.update({'output_path': out_path})
        dict2call(parser)
        assert True

    def test_ser_temp_uv_stat_intervalles(self):  # OK
        out_path, logger = change_path(folder_test)
        logger.info('test_ser_temp_uv_stat_intervalles')
        parser = command_line_interface(
            ['--cfgfile', f"../single_tests/{folder_test}/ser_temp_uv_stat_intervalles.cfg"])
        parser.update({'output_path': out_path})
        dict2call(parser)
        assert True
    
    def test_ser_temp_uv_stat_echeances(self):  # OK
        out_path, logger = change_path(folder_test)
        logger.info('test_ser_temp_uv_stat_echeances')
        parser = command_line_interface(
            ['--cfgfile', f"../single_tests/{folder_test}/ser_temp_uv_stat_echeances.cfg"])
        parser.update({'output_path': out_path})
        dict2call(parser)
        assert True
    
    def test_ser_temp_uv_res_stat_intervalles(self):  # OK
        out_path, logger = change_path(folder_test)
        logger.info('test_ser_temp_uv_res_stat_intervalles')
        parser = command_line_interface(
            ['--cfgfile', f"../single_tests/{folder_test}/ser_temp_uv_res_stat_intervalles.cfg"])
        parser.update({'output_path': out_path})
        dict2call(parser)
        assert True

    def test_ellipse_courant_et_periode_ticket154(self):  # OK
        out_path, logger = change_path(folder_test)
        logger.info('test_ellipse_courant_et_periode_ticket154')
        parser = command_line_interface(
            ['--cfgfile', f"../single_tests/{folder_test}/ellipse_courant_et_periode_ticket154.cfg"])
        parser.update({'output_path': out_path})
        dict2call(parser)
        assert True

    def test_map_current_hycom2Det3D_ticket156(self):  # OK
        out_path, logger = change_path(folder_test)
        logger.info('test_map_current_hycom2Det3D_ticket156')
        parser = command_line_interface(
            ['--cfgfile', f"../single_tests/{folder_test}/map_current_hycom2Det3D_ticket156.cfg"])
        parser.update({'output_path': out_path})
        dict2call(parser)
        assert True


    def test_map_harm_current_ticket120(self):  # OK
        out_path, logger = change_path(folder_test)
        logger.info('test_map_harm_current_ticket120')
        parser = command_line_interface(
            ['--cfgfile', f"../single_tests/{folder_test}/map_harm_current_ticket120.cfg"])
        parser.update({'output_path': out_path})
        dict2call(parser)
        assert True

    def test_ser_temp_uv_ponct_intervalle_ticket158(self):  # OK
        out_path, logger = change_path(folder_test)
        logger.info('test_ser_temp_uv_ponct_intervalle_ticket158')
        parser = command_line_interface(
            ['--cfgfile', f"../single_tests/{folder_test}/ser_temp_uv_ponct_intervalle_ticket158.cfg"])
        parser.update({'output_path': out_path})
        dict2call(parser)
        assert True

    def test_ser_temp_uv_ponct_ticket128(self):  # OK
        out_path, logger = change_path(folder_test)
        logger.info('test_test_ser_temp_uv_ponct_ticket128')
        parser = command_line_interface(
            ['--cfgfile', f"../single_tests/{folder_test}/ser_temp_uv_ponct_ticket128.cfg"])
        parser.update({'output_path': out_path})
        dict2call(parser)
        assert True