"""Interpolation candidate params and per-otype output params for armoor-data.

See `armoor.data.datatype` for the per-data-type hierarchy that now backs
`OUTPUTS_PARAMS`.
"""
INTERP_PARAMS_USER = {
    "time": ("tfreq",),
    "horizontal": ("cloud", "section"),
    "vertical": ("vlevel","vfreq"),
    }

# Kept for backward compatibility with call sites still importing this dict
# directly; the source of truth is now DataOceanModel.outputs_params
# (armoor.data.datatype) — see the per-data-type hierarchy there.
from armoor.data.datatype import DataOceanModel

OUTPUTS_PARAMS = DataOceanModel().outputs_params