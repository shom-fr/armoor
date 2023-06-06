import os
import shutil
import pathlib
import logging
from xoa import cfgm
from armoor.hmi.script_tools import create_folder
import armoor.cli.logger_tools as log
from pprint import pprint

rootdir = os.path.abspath(os.path.dirname(__file__))
cfgm_forecaster = cfgm.ConfigManager(os.path.join(rootdir, "..", "..", "tests.ini"))

current_dir = pathlib.Path().resolve()
paths = cfgm_forecaster.load(os.path.join(current_dir, "tests.cfg"))

def change_path(folder_test):
    os.chdir(paths["path_p1"])

    out_path = f'output_{folder_test}/'
    create_folder(os.path.join(paths["path_p1"], out_path))
    os.chdir(os.path.join(paths["path_p1"], out_path))

    log.setup_logging()
    logger = logging.getLogger(__name__)

    return os.path.join(paths["path_p1"], out_path), logger


def copy_test_files(test):
    source_dir = os.path.join(rootdir, "..", "..", "..", "data", "P1", "single_tests", test)
    destination_dir = os.path.join(paths["path_p1"],"single_tests", test)
    shutil.copytree(source_dir, destination_dir, dirs_exist_ok=True)



def change_path_bull(test):
    os.chdir(paths["path_p1"])

    out_path = f"bull_{test}"
    create_folder(os.path.join(paths["path_p1"], out_path))
    os.chdir(os.path.join(paths["path_p1"], out_path))

    log.setup_logging()
    logger = logging.getLogger(__name__)

    return os.path.join(paths["path_p1"], out_path), logger


def copy_bull_test_files(test):
    source_dir = os.path.join(rootdir, "..", "..", "..", "data", "P1", "bull", test)
    destination_dir = os.path.join(paths["path_p1"],f"bull_{test}")
    shutil.copytree(source_dir, destination_dir, dirs_exist_ok=True)

def update_comodo(parser:dict) -> dict:
    outputs = parser.pop('outputs')
    new_outputs = []

    for output in outputs:
        output.update({'env_comodo' : paths["env_comodo"]})
        output.update({'path_comodo' : paths["path_comodo"]})
        new_outputs.append(output)

    parser.update({'outputs': new_outputs})
    return parser