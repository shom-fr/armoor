import os
from xoa.cfgm import register_validation_functions

from armoor.cli.cli_tools import int_or_string_configobj, coords_config_obj, format_cofig_obj2dict
from armoor.__init__ import ROOTDIR

SAMPLE_DIR = os.path.join(ROOTDIR, "_samples")
INI_FILE = os.path.join(ROOTDIR, "cli", "cli.ini")

if "TMPDIR" not in os.environ:
    TMP_DIR = os.path.join(os.getenv("HOME"), 'tmp', 'armoor', 'uni')
    if not os.path.exists(TMP_DIR):
        os.makedirs(TMP_DIR)
else:
    TMP_DIR = os.environ["TMPDIR"]
    
register_validation_functions(absolute_or_relative_time=int_or_string_configobj)
register_validation_functions(coordinates=coords_config_obj)
'''
import os
import shutil
import pathlib
import logging
from xoa import cfgm
from armoor.hmi.script_tools import create_folder
from armoor.tick.forecaster import Forecaster
import armoor.cli.logger_tools as log

rootdir = os.path.abspath(os.path.dirname(__file__))
cfgm_forecaster = cfgm.ConfigManager(os.path.join(rootdir, "..", "tests.ini"))

current_dir = pathlib.Path().resolve()
paths = cfgm_forecaster.load(os.path.join(current_dir, "tests.cfg"))

cfgm_auth = cfgm.ConfigManager(os.path.join(rootdir, "..", "..", "armoor", "tick", 'auth.ini'))

def get_auth_spec():
    return cfgm_auth

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
'''