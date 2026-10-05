import os

ROOTDIR = os.path.abspath(os.path.dirname(__file__))


class ArmoorError(Exception):
    pass


LINE_COLORS = [
    '#1f77b4',
    '#ff7f0e',
    '#2ca02c',
    '#d62728',
    '#9467bd',
    '#8c564b',
    '#e377c2',
    '#7f7f7f',
    '#bcbd22',
    '#17becf',
]

CMAP_VARS = {
    "ptemp": "cmo.thermal",
    "temp": "cmo.thermal",
    "sal": "cmo.haline",
    "pdens": "cmo.dense",
    "sndspeed": "cmo.speed",
    "mld": "cmo.deep",
    "depth": "cmo.deep",
    "ssh": "cmo.delta",
    "sla": "cmo.delta",
    "eke": "viridis",
    "mke": "viridis",
    "u": "cmo.delta",
    "v": "cmo.delta",
    "cgeo": "cmo.delta",
    "cspeed": "cmo.speed",
    "t2m": "cmo.thermal",
    "si10": "cmo.speed",
    "r2": "cmo.rain",
    "prmsl": "cmo.dense",
}

MINMAX_VARS = {
    "ptemp": "pos",
    "temp": "pos",
    "sal": "pos",
    "pdens": "pos",
    "sndspeed": "pos",
    "mld": "pos",
    "depth": "pos",
    "ssh": "rel",
    "sla": "rel",
    "eke": "pos",
    "mke": "pos",
    "u": "rel",
    "v": "rel",
    "cgeo": "rel",
    "cspeed": "pos",
    "t2m": "pos",
    "si10": "pos",
    "r2": "pos",
    "prmsl": "pos",
}

import armoor.accessors  # noqa: E402, F401 — registers ds.filters / ds.oceanvars / ds.coloc / ds.stats / ds.plot
