import sys
import os
import logging
from armoor.cli.command_line_interface import command_line_interface
from armoor.base.calls_from_dict import dict2call
from armoor.hmi.script_tools import create_folder
from armoor.tests.config_path import path_p1 as path
import armoor.cli.logger_tools as log

folder_test = 'test_f3'

def change_path():
    os.chdir(path)

    out_path = f'output_{folder_test}/'
    create_folder(f'{path}{out_path}')
    os.chdir(f'{path}{out_path}')

    log.setup_logging()
    logger = logging.getLogger(__name__)

    return f'{path}{out_path}', logger


class TestBulletins:

    def test_ser_temp_stat(self):
        out_path, logger = change_path()
        logger.info('test_ser_temp_stat')
        parser = command_line_interface(['--file', f"../single_tests/{folder_test}/ser_temp_stat.ini"])
        parser.update({'output_path' : out_path })
        dict2call(parser)
        assert True