import sys
import os
import logging
from armoor.cli.command_line_interface import command_line_interface
from armoor.base.calls_from_dict import dict2call
from armoor.hmi.script_tools import create_folder
from tests.config_path import path_p1 as path
import armoor.cli.logger_tools as log

folder_test = 'test_f6'

def change_path():
    os.chdir(path)

    out_path = f'output_{folder_test}/'
    create_folder(f'{path}{out_path}')
    os.chdir(f'{path}{out_path}')

    log.setup_logging()
    logger = logging.getLogger(__name__)

    return f'{path}{out_path}', logger


class TestBulletins:

    def test_ellipse_courant_et_periode(self):
        out_path, logger = change_path()
        logger.info('test_ellipse_courant_et_periode')
        parser = command_line_interface(['--file', f"../single_tests/{folder_test}/ellipse_courant_et_periode.ini"])
        parser.update({'output_path' : out_path })
        dict2call(parser)
        assert True

    def test_map_current(self):
        out_path, logger = change_path()
        logger.info('test_map_current')
        parser = command_line_interface(['--file', f"../single_tests/{folder_test}/map_current.ini"])
        parser.update({'output_path' : out_path })
        dict2call(parser)
        assert True

    def test_map_current_biais(self):
        out_path, logger = change_path()
        logger.info('test_map_current_biais')
        parser = command_line_interface(['--file', f"../single_tests/{folder_test}/map_current_biais.ini"])
        parser.update({'output_path' : out_path })
        dict2call(parser)
        assert True

    def test_map_current_croco(self):
        out_path, logger = change_path()
        logger.info('test_map_current_croco')
        parser = command_line_interface(['--file', f"../single_tests/{folder_test}/map_current_croco.ini"])
        parser.update({'output_path' : out_path })
        dict2call(parser)
        assert True

    def test_map_current_hycom2det3d(self):
        out_path, logger = change_path()
        logger.info('test_map_current_hycom2Det3D')
        parser = command_line_interface(['--file', f"../single_tests/{folder_test}/map_current_hycom2Det3D.ini"])
        parser.update({'output_path' : out_path })
        dict2call(parser)
        assert True

    def test_map_current_rmse(self):
        out_path, logger = change_path()
        logger.info('test_map_current_RMSE')
        parser = command_line_interface(['--file', f"../single_tests/{folder_test}/map_current_RMSE.ini"])
        parser.update({'output_path' : out_path })
        dict2call(parser)
        assert True

    def test_map_harm_courant(self):
        out_path, logger = change_path()
        logger.info('test_map_harm_courant')
        parser = command_line_interface(['--file', f"../single_tests/{folder_test}/map_harm_courant.ini"])
        parser.update({'output_path' : out_path })
        dict2call(parser)
        assert True

    def test_ser_temp_uv_ponct(self):
        out_path, logger = change_path()
        logger.info('test_ser_temp_uv_ponct')
        parser = command_line_interface(['--file', f"../single_tests/{folder_test}/ser_temp_uv_ponct.ini"])
        parser.update({'output_path' : out_path })
        dict2call(parser)
        assert True

    def test_ser_temp_uv_ponct_intervalles(self):
        out_path, logger = change_path()
        logger.info('test_ser_temp_uv_ponct_intervalles')
        parser = command_line_interface(['--file', f"../single_tests/{folder_test}/ser_temp_uv_ponct_intervalles.ini"])
        parser.update({'output_path' : out_path })
        dict2call(parser)
        assert True

    def test_ser_temp_uv_stat_intervalles(self):
        out_path, logger = change_path()
        logger.info('test_ser_temp_uv_stat_intervalles')
        parser = command_line_interface(['--file', f"../single_tests/{folder_test}/ser_temp_uv_stat_intervalles.ini"])
        parser.update({'output_path' : out_path })
        dict2call(parser)
        assert True