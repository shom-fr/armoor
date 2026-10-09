import os

_THISDIR = os.path.dirname(__file__)

FILTERS_INI = os.path.join(_THISDIR, "filters.ini")
COMP_INI = os.path.join(_THISDIR, "comp.ini")
DATA_INI = os.path.join(_THISDIR, "data.ini")
METAZONES_INI = os.path.join(_THISDIR, "metazones.ini")
BULL_INI = os.path.join(_THISDIR, "bull.ini")

HPC_DEFAULTS = {
    "queue": "seq",
    "time_orch": "12:00:00",
    "time_load": "02:00:00",
    "time_comp": "02:00:00",
    "time_output": "02:00:00",
    "time_plot": "01:00:00",
    "time_merge": "00:05:00",
    "ncpus": 1,
    "ncpus_load": 8,
}
