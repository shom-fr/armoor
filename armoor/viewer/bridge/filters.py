"""Wrapper around armoor's FiltersAccessor.apply_combined_filters."""

import logging

import xarray as xr

logger = logging.getLogger(__name__)


def apply_combined_filters(ds: xr.Dataset, filters_config: dict) -> xr.Dataset:
    """Apply armoor combined filters to *ds*.

    Requires the ``armoorfilters`` accessor to be registered.  This is done
    by importing ``armoor.filters`` (the import itself registers the
    accessor).

    Parameters
    ----------
    ds:
        Input dataset.
    filters_config:
        Filter configuration dict as expected by
        ``ArmoorFilters.apply_combined_filters``.

    Returns
    -------
    xr.Dataset
        Filtered dataset.
    """
    try:
        import armoor  # noqa: F401 – side-effect: registers ds.filters accessor
    except ImportError as exc:
        raise RuntimeError("armoor is not installed") from exc

    result = ds.filters.combined(filters_config)
    if result is None:
        # apply_combined_filters can return None when polygon filter finds no data
        logger.warning("apply_combined_filters returned None; returning original dataset")
        return ds
    return result
