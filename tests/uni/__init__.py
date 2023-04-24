import os
import shutil
import logging
from xoa import cfgm
from armoor.hmi.script_tools import create_folder
from armoor.tick.forecaster import Forecaster
import armoor.cli.logger_tools as log

rootdir = os.path.abspath(os.path.dirname(__file__))
cfgm_forecaster = cfgm.ConfigManager(os.path.join(rootdir, "../tests.ini"))
paths = cfgm_forecaster.load(os.path.join(rootdir, "../../config/tests.cfg"))

def copy_p2_forecaster_cfg_file():
    source_file = os.path.join(rootdir, "..", "..", "data", "P2", 'forecaster.cfg')
    destination_dir = os.path.join(paths["path_p2"], 'forecaster.cfg')
    shutil.copyfile(source_file, destination_dir)

def init_status(config_reg, production_time, copy=True):
    logger = change_path_p2()
    source_file = os.path.join(rootdir, "..", "..", "data", "P2", 'data.json')
    create_folder('path_to_front')

    dst = os.path.join('path_to_front', f'{config_reg}_{production_time}')
    create_folder(dst)
    if copy:
        shutil.copyfile(source_file, os.path.join(dst, 'data.json'))
    forecaster = Forecaster()
    return logger, forecaster

def change_path_p2():
    os.chdir(paths["path_p2"])

    log.setup_logging()
    logger = logging.getLogger(__name__)

    return logger



# def change_path(folder_test, poste="path_p1"):
#     os.chdir(paths[poste])
#
#     out_path = f'output_{folder_test}/'
#     create_folder(f'{paths[poste]}{out_path}')
#     os.chdir(f'{paths[poste]}{out_path}')
#
#     log.setup_logging()
#     logger = logging.getLogger(__name__)
#
#     return f'{paths[poste]}{out_path}', logger




# def copy_p2_test_file(test):
#     source_file = os.path.join(rootdir, "..", "..", "..", "data", "P2", test)
#     destination_dir = os.path.join(paths["path_p2"], test)
#     shutil.copyfile(src, dst)
#     shutil.copytree(source_dir, destination_dir, dirs_exist_ok=True)