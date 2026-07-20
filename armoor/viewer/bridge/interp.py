"""Wrappers around armoor interpolation functions."""

import logging
from typing import Any, Tuple

import xarray as xr

logger = logging.getLogger(__name__)


def process_time_interpolation(ds: xr.Dataset, param: Tuple, tbound=None) -> xr.Dataset:
    """Temporal interpolation via armoor.

    Parameters
    ----------
    ds:
        Input dataset.
    param:
        Tuple forwarded to ``armoor.data.interp.process_time_interpolation``.
        Typically ``("tfreq", "1H")``.
    tbound:
        Optional time bounds; defaults to ``(ds.time.min(), ds.time.max())``.
    """
    from armoor.data.interp import process_time_interpolation as _pti

    if tbound is None and "time" in ds:
        t = ds.time.values
        tbound = (t[0], t[-1])

    logger.info("Temporal interpolation: param=%s", param)
    return _pti(ds, param, tbound)


def process_horizontal_interpolation(ds: xr.Dataset, param: Any) -> xr.Dataset:
    """Horizontal interpolation via armoor.

    Parameters
    ----------
    ds:
        Input dataset.
    param:
        Parameter forwarded to armoor (dict or tuple, format-dependent).
    """
    from armoor.data.interp import process_horizontal_interpolation as _phi

    logger.info("Horizontal interpolation: param=%s", param)
    return _phi(ds, param)


def process_vertical_interpolation(ds: xr.Dataset, param: Any) -> xr.Dataset:
    """Vertical interpolation via armoor.

    Parameters
    ----------
    ds:
        Input dataset.
    param:
        Tuple like ``(method, args)`` forwarded to armoor.
    """
    from armoor.data.interp import process_vertical_interpolation as _pvi

    logger.info("Vertical interpolation: param=%s", param)
    return _pvi(ds, param)
