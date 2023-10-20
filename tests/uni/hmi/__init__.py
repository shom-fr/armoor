import os
import shutil
import pathlib
import logging
from datetime import datetime, timezone
from xoa import cfgm
from armoor.hmi.script_tools import create_folder
import armoor.cli.logger_tools as log

rootdir = os.path.abspath(os.path.dirname(__file__))
cfgm_forecaster = cfgm.ConfigManager(os.path.join(rootdir, "..", "..", "tests.ini"))

current_dir = pathlib.Path().resolve()
paths = cfgm_forecaster.load(os.path.join(current_dir, "tests.cfg"))

test_day = datetime.now(timezone.utc).strftime("%Y%m%d")
model = 'hycom3d'
config = 'med'


def change_path(folder_test):
    os.chdir(paths["path_p3"])

    create_folder(os.path.join(paths["path_p3"], folder_test))
    os.chdir(os.path.join(paths["path_p3"], folder_test))

    log.setup_logging()
    logger = logging.getLogger(__name__)

    return os.path.join(paths["path_p3"], folder_test), logger


def copy_test_files():
    copy_empty_data_files('med')
    copy_empty_data_files('manga')
    copy_empty_data_files('indien')


def copy_empty_data_files(local_config):
    source_dir = os.path.join(rootdir, "..", "..", "..", "data", "P3", "empty_data", f"hycom3d_{local_config}_")
    destination_dir = os.path.join(paths["path_p3"], "empty_data", f'hycom3d_{local_config}_{test_day}')
    shutil.copytree(source_dir, destination_dir, dirs_exist_ok=True)


def get_input_folder_path() -> str:
    return os.path.join('..', "empty_data")
