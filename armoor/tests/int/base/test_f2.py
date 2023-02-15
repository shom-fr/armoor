import sys
import os

from armoor.cli.command_line_interface import command_line_interface
from armoor.base.calls_from_dict import dict2call
from armoor.hmi.script_tools import create_folder

import armoor.cli.logger_tools as log
import logging

#TODO Please change this folder to the location of your P1 folder
path = '/mnt/d/1144/P1/'
folder_test = 'test_f2'

def change_path():
    os.chdir(path)

    out_path = f'output_{folder_test}/'
    create_folder(f'{path}{out_path}')
    os.chdir(f'{path}{out_path}')

    log.setup_logging()
    logger = logging.getLogger(__name__)

    return f'{path}{out_path}', logger


class TestBulletins:

    def test_diag_disp(self):
        out_path, logger = change_path()
        logger.info('test_diag_disp')
        parser = command_line_interface(['--file', f"../single_tests/{folder_test}/diag_disp.ini"])
        parser.update({'output_path' : out_path })
        dict2call(parser)
        assert True

    def test_multi_plot_tranche_intervalle(self):
        out_path, logger = change_path()
        logger.info('test_multi_plot_tranche_intervalle')
        parser = command_line_interface(['--file', f"../single_tests/{folder_test}/multi_plot_tranche_intervalle.ini"])
        parser.update({'output_path' : out_path })
        dict2call(parser)
        assert True

    def test_diag_theta_s_multi(self):
        out_path, logger = change_path()
        logger.info('test_diag_theta_s_multi')
        parser = command_line_interface(['--file', f"../single_tests/{folder_test}/diag_theta_s_multi.ini"])
        parser.update({'output_path' : out_path })
        dict2call(parser)
        assert True

    def test_diag_theta_s_unique(self):
        out_path, logger = change_path()
        logger.info('test_diag_theta_s_unique')
        parser = command_line_interface(['--file', f"../single_tests/{folder_test}/diag_theta_s_unique.ini"])
        parser.update({'output_path' : out_path })
        dict2call(parser)
        assert True

    def test_map_biais_intervalles_tranches_test(self):
        out_path, logger = change_path()
        logger.info('test_map_biais_intervalles_tranches_test')
        parser = command_line_interface(['--file', f"../single_tests/{folder_test}/map_biais_intervalles_tranches_test.ini"])
        parser.update({'output_path' : out_path })
        dict2call(parser)
        assert True

    def test_map_diff(self):
        out_path, logger = change_path()
        logger.info('test_map_diff')
        parser = command_line_interface(['--file', f"../single_tests/{folder_test}/map_diff.ini"])
        parser.update({'output_path' : out_path })
        dict2call(parser)
        assert True

    def test_map_diff_intervalles(self):
        out_path, logger = change_path()
        logger.info('test_map_diff_intervalles')
        parser = command_line_interface(['--file', f"../single_tests/{folder_test}/map_diff_intervalles.ini"])
        parser.update({'output_path' : out_path })
        dict2call(parser)
        assert True

    def test_profil_multi_temp(self):
        out_path, logger = change_path()
        logger.info('test_profil_multi_temp')
        parser = command_line_interface(['--file', f"../single_tests/{folder_test}/profil_multi_temp.ini"])
        parser.update({'output_path' : out_path })
        dict2call(parser)
        assert True

    def test_profil_unique_temp(self):
        out_path, logger = change_path()
        logger.info('test_profil_unique_temp')
        parser = command_line_interface(['--file', f"../single_tests/{folder_test}/profil_unique_temp.ini"])
        parser.update({'output_path' : out_path })
        dict2call(parser)
        assert True

    def test_ser_temp_intervalles(self):
        out_path, logger = change_path()
        logger.info('test_ser_temp_intervalles')
        parser = command_line_interface(['--file', f"../single_tests/{folder_test}/ser_temp_intervalles.ini"])
        parser.update({'output_path' : out_path })
        dict2call(parser)
        assert True

    def test_ser_temp_tranches(self):
        out_path, logger = change_path()
        logger.info('test_ser_temp_tranches')
        parser = command_line_interface(['--file', f"../single_tests/{folder_test}/ser_temp_tranches.ini"])
        parser.update({'output_path' : out_path })
        dict2call(parser)
        assert True