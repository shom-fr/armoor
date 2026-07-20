import os

ROOTDIR = os.path.abspath(os.path.dirname(__file__))

class ArmoorError(Exception):
    pass

import armoor.accessors  # noqa: E402, F401 — registers ds.filters / ds.oceanvars / ds.coloc / ds.stats / ds.plot