import glob
import os

import xarray as xr
from xoa.cfgm import ConfigManager

from armoor.__init__ import ROOTDIR
from armoor.base.calls_from_dict import dict2call, get_observation_models_meta
from armoor.tests.uni.__init__ import INI_FILE, SAMPLE_DIR, TMP_DIR

INT_TESTS_DIR = os.path.join(ROOTDIR, "tests", "uni", "test_section_hydro")


def get_cfg(cfg):

    cfg = ConfigManager(INI_FILE).load(cfg)
    cfg["output_path"] = cfg["output_path"].format(tmpdir=TMP_DIR)
    cfg["observation"]["path"] = [
        path.format(sample_dir=SAMPLE_DIR)
        for path in cfg["observation"]["path"]
    ]
    for model in cfg["models"]:
        cfg["models"][model]["path"] = [
            path.format(sample_dir=SAMPLE_DIR)
            for path in cfg["models"][model]["path"]
        ]

    return cfg


def test():
    cfg = get_observation_models_meta(
        get_cfg(os.path.join(INT_TESTS_DIR, "cmems_vs_HyCOM.cfg"))
    )
