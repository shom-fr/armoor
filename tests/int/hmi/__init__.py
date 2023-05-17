import os
import shutil
import pathlib
import logging
from xoa import cfgm
from armoor.hmi.script_tools import create_folder
import armoor.cli.logger_tools as log

rootdir = os.path.abspath(os.path.dirname(__file__))
cfgm_forecaster = cfgm.ConfigManager(os.path.join(rootdir, "..", "..", "tests.ini"))

current_dir = pathlib.Path().resolve()
paths = cfgm_forecaster.load(os.path.join(current_dir, "tests.cfg"))

def change_path(folder_test):
    os.chdir(paths["path_p3"])

    create_folder(os.path.join(paths["path_p3"], 'out', folder_test))
    os.chdir(os.path.join(paths["path_p3"], 'out', folder_test))

    log.setup_logging()
    logger = logging.getLogger(__name__)

    return os.path.join(paths["path_p3"], 'out', folder_test), logger


def copy_test_files():
    source_dir = os.path.join(rootdir, "..", "..", "..", "data", "P3", "config")
    destination_dir = os.path.join(paths["path_p3"],"config")
    shutil.copytree(source_dir, destination_dir, dirs_exist_ok=True)