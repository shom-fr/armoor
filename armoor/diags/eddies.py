import numpy as np
import xarray as xr

from armoor.data.datatype import DataEddies
from armoor.stats import pdf as spdf


def pdf(ds: xr.Dataset) -> xr.Dataset:
    """Compute per-variable PDFs for cyclonic and anticyclonic eddies.

    Splits `ds` by `eddy_type` (-1 cyclones, +1 anticyclones), computes the
    PDF of each `DataEddies.data_vars` variable in each half, and merges
    the results back as `{var}_A`/`{var}_C` (anticyclones/cyclones).

    Parameters
    ----------
    ds : xarray.Dataset
        Eddy dataset, with an `eddy_type` variable.

    Returns
    -------
    xarray.Dataset
        `ds` augmented with `{var}_A`/`{var}_C` PDF variables.
    """
    ds = ds.compute()

    dsa = ds.where(ds.eddy_type == 1, drop=True)
    dsc = ds.where(ds.eddy_type == -1, drop=True)

    vars = [var for var in DataEddies.data_vars if var in ds.data_vars]
    dsa = spdf(dsa, vars)
    dsc = spdf(dsc, vars)

    dsa = dsa.drop_vars(var for var in dsa.data_vars if 'pdf' not in var)
    dsc = dsc.drop_vars(var for var in dsc.data_vars if 'pdf' not in var)

    ds = ds.assign(
        **{
            **{
                f'{var}_A': dsa[var].assign_attrs({**dsa[var].attrs, 'eddy_type': 'anticyclones'})
                for var in dsa.data_vars
            },
            **{
                f'{var}_C': dsc[var].assign_attrs({**dsc[var].attrs, 'eddy_type': 'cyclones'})
                for var in dsc.data_vars
            }
        }
    )

    return ds


def area2radius(ds: xr.Dataset) -> xr.Dataset:
    """
    Compute the equivalent radius of the vmax contour.

    This function computes the equivalent radius of a circle whose area
    matches that enclosed by the eddy vmax contour.

    Parameters
    ----------
    ds : xarray.Dataset
        Dataset with vmax_area variable.

    Returns
    -------
    xarray.Dataset
        Dataset extended with a new vmax_radius variable.
    """
    vmax_area = ds.vmax_area
    vmax_radius = np.sqrt(vmax_area / np.pi)
    ds['vmax_radius'] = vmax_radius.assign_attrs({
        'comment': 'Radius of the vmax contour from vmax_area',
        'units': 'km'
        })
    return ds


def compute_vars(ds: xr.Dataset) -> xr.Dataset:
    """Add any derivable eddy diagnostic variables missing from `ds`.

    A no-op for non-eddy datasets (checks for `vmax_area` presence).

    Parameters
    ----------
    ds : xarray.Dataset
        Dataset to augment.

    Returns
    -------
    xarray.Dataset
        `ds`, with `vmax_radius` added if derivable and missing.
    """
    if "vmax_area" in ds.data_vars and "vmax_radius" not in ds.data_vars:
        ds = area2radius(ds)

    return ds
