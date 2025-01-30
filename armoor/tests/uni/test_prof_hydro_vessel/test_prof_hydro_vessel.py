import glob
import os

import xarray as xr
from xoa.cfgm import ConfigManager

from armoor.__init__ import ROOTDIR
from armoor.base.calls_from_dict import dict2call
from armoor.tests.uni.__init__ import INI_FILE, SAMPLE_DIR, TMP_DIR

INT_TESTS_DIR = os.path.join(ROOTDIR, "tests", "uni", "test_prof_hydro_vessel")


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
    cfg = dict2call(get_cfg(os.path.join(INT_TESTS_DIR, "cmems_vs_HyCOM.cfg")))

def test_immersions():
    cfg = dict2call(
        get_cfg(os.path.join(INT_TESTS_DIR, "cmems_vs_HyCOM_immersions.cfg"))
    )

def test_immersions_intervals():
    cfg = dict2call(
        get_cfg(
            os.path.join(
                INT_TESTS_DIR, "cmems_vs_HyCOM_immersions_intervals.cfg"
            )
        )
    )

def test_intervals():
    cfg = dict2call(
        get_cfg(os.path.join(INT_TESTS_DIR, "cmems_vs_HyCOM_intervals.cfg"))
    )


def test_layers():
    cfg = dict2call(
        get_cfg(os.path.join(INT_TESTS_DIR, "cmems_vs_HyCOM_layers.cfg"))
    )


def test_layers_intervals():
    cfg = dict2call(
        get_cfg(
            os.path.join(INT_TESTS_DIR, "cmems_vs_HyCOM_layers_intervals.cfg")
        )
    )
