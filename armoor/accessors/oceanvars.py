"""ds.oceanvars accessor — re-registers OceanVars under the same name.

The OceanVars class methods call ``self.ds.oceanvars.*`` internally, so the
accessor name must stay "oceanvars".  We just move the registration here so
that importing ``armoor.accessors`` is the single authoritative trigger.
"""

import xarray as xr

from armoor.oceanvars import OceanVars

# Register OceanVars directly — keeps all internal self.ds.oceanvars.* calls
# working without any wrapper layer.
xr.register_dataset_accessor("oceanvars")(OceanVars)
