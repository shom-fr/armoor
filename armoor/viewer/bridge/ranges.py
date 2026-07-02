"""Wrappers around armoor range-splitting functions."""

import logging
from typing import List

import xarray as xr

logger = logging.getLogger(__name__)


def process_time_range(ds: xr.Dataset, tfreq: str) -> xr.Dataset:
    """Split dataset into time intervals via armoor.

    Parameters
    ----------
    ds:
        Input dataset.
    tfreq:
        Pandas frequency string (e.g. ``"D"``, ``"M"``, ``"1H"``).
    """
    from armoor.data.range import process_time_range as _ptr

    logger.info("Time range split: tfreq=%s", tfreq)
    return _ptr(ds, tfreq)


def process_vertical_range(
    ds: xr.Dataset,
    vname: str,
    vrange: List[float],
) -> xr.Dataset:
    """Mask dataset outside a vertical range via armoor.

    Parameters
    ----------
    ds:
        Input dataset.
    vname:
        Name of the vertical coordinate variable (e.g. ``"z"``, ``"depth"``).
    vrange:
        ``[vmin, vmax]`` bounds.
    """
    from armoor.data.range import process_vertical_range as _pvr

    logger.info("Vertical range filter: vname=%s, range=%s", vname, vrange)
    return _pvr(ds, vname, vrange)
