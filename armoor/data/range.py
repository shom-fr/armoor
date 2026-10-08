import logging

import numpy as np
import pandas as pd
import xarray as xr

from armoor.__init__ import ArmoorError

logger = logging.getLogger(__name__)


def process_time_range(ds, tfreq):
    """Process time range by splitting dataset into time intervals.
    
    Splits an xarray dataset into temporal subsets based on a specified frequency
    and concatenates them along a new 'trange' dimension. Each subset is assigned
    a time_range coordinate indicating its temporal bounds.
    
    Parameters
    ----------
    ds : xarray.Dataset
        Input dataset containing a 'time' coordinate.
    tfreq : str
        Frequency string for time intervals (e.g., 'D' for daily, 'M' for monthly,
        'H' for hourly). Follows pandas date_range frequency conventions.
    
    Returns
    -------
    xarray.Dataset
        Combined dataset with subsets concatenated along the 'trange' dimension.
        Each element along 'trange' corresponds to one time interval.
    
    Notes
    -----
    The function creates non-overlapping time intervals using pd.date_range and
    selects data within each interval. The resulting dataset has a new 'trange'
    dimension indexed from 0 to n-1, where n is the number of intervals.
    
    Examples
    --------
    >>> ds = xr.Dataset({'temp': (['time'], [1, 2, 3])},
    ...                 coords={'time': pd.date_range('2020-01-01', periods=3, freq='D')})
    >>> result = process_time_range(ds, 'D')
    >>> result.dims
    Frozen({'trange': 2})
    """
    t_start = ds.time.min().data
    t_end = ds.time.max().data
    time_ranges = pd.date_range(
        start=f"{t_start}",
        end=f"{t_end}",
        freq=tfreq
    )
    subsets = []
    for idate in range(len(time_ranges) - 1):
        t_start = time_ranges[idate]
        t_end = time_ranges[idate + 1]
        sub = ds.sel(time=slice(t_start, t_end))
        sub = sub.expand_dims(dim="trange")
        for var in sub.data_vars:
            if not "time" in ds[var].sizes:
                sub[var] = sub[var].squeeze(dim="trange")
        sub["time_range"] = xr.DataArray(
            [f"{t_start:%Y%m%dT%H%M%S}_to_{t_end:%Y%m%dT%H%M%S}"],
            dims=("trange",)
            )
        subsets.append(sub)
        
    combined = xr.concat(
        subsets,
        dim="trange",
        join="outer",
        data_vars="all",
        # coords="minimal",   # don't try to align all coordinates
        # compat="override",  # allow metadata differences
        # join="override"     # don't merge coordinates by labels
    )
    combined = combined.assign_coords(trange=np.arange(len(subsets)))
    return combined


def process_vertical_range(ds, vname, vrange):
    """Process vertical range by filtering data within specified bounds.
    
    Filters 3D variables in the dataset to retain only values within a specified
    vertical range. 2D variables (without a 'z' dimension) are preserved unchanged.
    
    Parameters
    ----------
    ds : xarray.Dataset
        Input dataset containing variables with or without a 'z' dimension.
    vname : str
        Name of the vertical coordinate variable to use for filtering.
    vrange : tuple or list of length 2
        Vertical range bounds as (minimum, maximum). Data outside this range
        will be masked (set to NaN) for 3D variables.
    
    Returns
    -------
    xarray.Dataset
        Filtered dataset where 3D variables are masked outside the specified
        vertical range, and 2D variables remain unchanged.
    
    Notes
    -----
    The function separates variables into two groups: those with and without
    a 'z' dimension. Only variables with a 'z' dimension are filtered using
    the vertical range mask. The mask is computed before applying to improve
    performance with dask-backed datasets.
    
    Examples
    --------
    >>> ds = xr.Dataset({
    ...     'temp': (['z', 'x'], [[1, 2], [3, 4]]),
    ...     'surface': (['x'], [10, 20])
    ... }, coords={'z': [0, 100]})
    >>> result = process_vertical_range(ds, 'z', (0, 50))
    >>> result['temp'].values
    array([[ 1.,  2.],
           [nan, nan]])
    """
    mask = (ds[vname] >= vrange[0]) & (ds[vname] <= vrange[1])
    mask = mask.compute()
    vars2d = [var for var in ds.data_vars if "z" not in ds[var].dims]
    vars3d = [var for var in ds.data_vars if "z" in ds[var].dims]
    ds = xr.merge([ds[vars2d], ds[vars3d].where(mask)])
    ds = ds.assign_coords(
        vertical_range=f"{vrange[0]}_to_{vrange[1]}",
    )
    return ds