"""Open datasets via armoor or directly via xarray for Zarr stores."""

import logging

import xarray as xr

logger = logging.getLogger(__name__)


def register_cf() -> None:
    """Register armoor CF specs (idempotent)."""
    try:
        from armoor.data.open_decode import register_cf as _register_cf

        _register_cf()
    except Exception as exc:
        logger.warning("Could not register armoor CF specs: %s", exc)


def open_dataset(path: str, fmt: str) -> xr.Dataset:
    """Open a dataset, routing zarr to xarray directly and others to armoor.

    Parameters
    ----------
    path:
        Path (or glob) to the data.
    fmt:
        Format string.  ``"zarr"`` is handled natively; all other strings
        are forwarded to ``armoor.data.open_decode.open_decode``.

    Returns
    -------
    xr.Dataset
        Lazy xarray Dataset.
    """
    register_cf()

    if fmt == "zarr":
        logger.info("Opening Zarr store: %s", path)
        ds = xr.open_dataset(path, engine="zarr", chunks="auto", consolidated=True)
        # Normalise depth coordinate name if needed
        if "depth" in ds and "depth" not in ds.coords:
            ds = ds.set_coords("depth")
        return ds

    # Delegate to armoor for all other formats
    logger.info("Opening via armoor (fmt=%s): %s", fmt, path)
    try:
        from armoor.data.open_decode import open_decode

        return open_decode(path, fmt)
    except Exception as exc:
        logger.error("armoor open_decode failed: %s", exc)
        raise
