import glob
import os

import xarray as xr
from xoa.cfgm import ConfigManager

from armoor.base.calls_from_dict import dict2call
from armoor.tests.uni.__init__ import INI_FILE, SAMPLE_DIR, TMP_DIR

INT_TESTS_DIR = os.path.abspath(os.path.dirname(__file__))

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


def test_href_terms():
    cfg = dict2call(get_cfg(
        os.path.join(
            INT_TESTS_DIR,
            "L4_vs_HyCOM_href_terms.cfg"
        )
    ))

def test_href_intervals():
    cfg = dict2call(get_cfg(
        os.path.join(
            INT_TESTS_DIR,
            "L4_vs_HyCOM_href_intervals.cfg"
        )
    ))


def test_cloud_terms():
    cfg = dict2call(
        get_cfg(os.path.join(INT_TESTS_DIR, "L4_vs_HyCOM_cloud_terms.cfg"))
    )


def test_cloud_intervals():
    cfg = dict2call(
        get_cfg(os.path.join(INT_TESTS_DIR, "L4_vs_HyCOM_cloud_intervals.cfg"))
    )
