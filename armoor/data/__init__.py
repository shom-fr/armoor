INTERP_PARAMS_USER = {
    "time": ("tfreq",),
    "horizontal": ("cloud",),
    "vertical": ("vlevel","vfreq"),
    }

# Kept for backward compatibility with call sites still importing this dict
# directly; the source of truth is now DataOceanModel.outputs_params
# (armoor.data.datatype) — see the per-data-type hierarchy there.
from armoor.data.datatype import DataOceanModel

OUTPUTS_PARAMS = DataOceanModel().outputs_params