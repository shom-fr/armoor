import os
import shutil
import logging
from xoa import cfgm
from armoor.hmi.script_tools import create_folder
import armoor.cli.logger_tools as log

rootdir = os.path.abspath(os.path.dirname(__file__))
cfgm_forecaster = cfgm.ConfigManager(os.path.join(rootdir, "../../tests.ini"))
paths = cfgm_forecaster.load(os.path.join(rootdir, "../../../config/tests.cfg"))

def change_path(folder_test):
    os.chdir(paths["path_p1"])

    out_path = f'output_{folder_test}/'
    create_folder(f'{paths["path_p1"]}{out_path}')
    os.chdir(f'{paths["path_p1"]}{out_path}')

    log.setup_logging()
    logger = logging.getLogger(__name__)

    return f'{paths["path_p1"]}{out_path}', logger


def copy_test_files(test):
    source_dir = os.path.join(rootdir, "..", "..", "..", "data", "P1", "single_tests", test)
    destination_dir = os.path.join(paths["path_p1"],"single_tests", test)
    shutil.copytree(source_dir, destination_dir, dirs_exist_ok=True)