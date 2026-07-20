"""Armoor xarray accessor plugins.

Importing this module registers the following accessors on xr.Dataset:
  - ds.filters   : data filtering (time, polygon, quality, bathy, oceanvars, ...)
  - ds.oceanvars : ocean variable selection / computation
  - ds.coloc     : colocation with a reference dataset
  - ds.stats     : statistical comparison metrics
  - ds.interp    : temporal, horizontal, vertical interpolation
  - ds.range     : temporal and vertical range / splitting
  - ds.plot      : extended plot accessor (superset of xarray's built-in)
"""

from armoor.accessors import filters    # noqa: F401
from armoor.accessors import oceanvars  # noqa: F401
from armoor.accessors import coloc      # noqa: F401
from armoor.accessors import stats      # noqa: F401
from armoor.accessors import interp     # noqa: F401
from armoor.accessors import range      # noqa: F401
from armoor.accessors import plot       # noqa: F401
