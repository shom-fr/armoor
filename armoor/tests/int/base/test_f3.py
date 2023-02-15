import sys
import os

from armoor.cli.command_line_interface import command_line_interface
from armoor.base.calls_from_dict import dict2call
from armoor.hmi.script_tools import create_folder

import armoor.cli.logger_tools as log
import logging

#TODO Please change this folder to the location of your P1 folder
path = '/mnt/d/1144/P1/'
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