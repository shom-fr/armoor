"""Colormap resolution: cmocean + matplotlib fallback."""

import logging
from typing import Callable

import numpy as np

logger = logging.getLogger(__name__)

# Cache resolved colormaps so we don't re-import every tile
_cmap_cache: dict = {}


def resolve_colormap(name: str) -> Callable:
    """Return a callable colormap for *name*.

    Supports:
    - ``"cmo.<name>"`` → cmocean
    - Any matplotlib colormap name

    Parameters
    ----------
    name:
        Colormap name string.

    Returns
    -------
    callable
        A function ``cmap(x: np.ndarray) → np.ndarray[uint8, (N,4)]``
        where *x* is in [0, 1].
    """
    if name in _cmap_cache:
        return _cmap_cache[name]

    cmap = _load_cmap(name)
    _cmap_cache[name] = cmap
    return cmap


def _load_cmap(name: str):
    # cmocean: names like "cmo.thermal" or "thermal"
    if name.startswith("cmo."):
        short = name[4:]
        try:
            import cmocean

            cmap = cmocean.cm.cmap_d.get(short)
            if cmap is None:
                raise KeyError(short)
            return cmap
        except Exception as exc:
            logger.warning("cmocean cmap '%s' not found (%s), falling back to viridis", name, exc)
            name = "viridis"

    # matplotlib
    import matplotlib

    try:
        return matplotlib.colormaps[name]
    except KeyError:
        logger.warning("matplotlib cmap '%s' not found, using viridis", name)
        return matplotlib.colormaps["viridis"]


def apply_colormap(
    data: np.ndarray,
    cmap_name: str,
    vmin: float,
    vmax: float,
) -> np.ndarray:
    """Normalise *data* and apply *cmap_name*.

    NaN values become fully transparent (alpha=0).

    Parameters
    ----------
    data:
        2-D float array.
    cmap_name:
        Colormap name.
    vmin, vmax:
        Data range for normalisation.

    Returns
    -------
    np.ndarray, shape (H, W, 4), dtype uint8
        RGBA image array.
    """
    cmap = resolve_colormap(cmap_name)

    nan_mask = np.isnan(data)

    # Normalise to [0, 1]
    span = vmax - vmin
    if span == 0:
        span = 1.0
    norm = np.clip((data - vmin) / span, 0.0, 1.0)

    # Apply colormap → RGBA float [0, 1]
    rgba = cmap(norm)  # shape (H, W, 4)

    # Convert to uint8
    rgba_uint8 = (rgba * 255).astype(np.uint8)

    # Transparent for NaN
    rgba_uint8[nan_mask, 3] = 0

    return rgba_uint8


def colormap_strip(cmap_name: str, n: int = 256) -> np.ndarray:
    """Return a horizontal (1 × n × 4) RGBA strip for legend rendering.

    Parameters
    ----------
    cmap_name:
        Colormap name.
    n:
        Number of colour steps.

    Returns
    -------
    np.ndarray, shape (1, n, 4), dtype uint8
    """
    cmap = resolve_colormap(cmap_name)
    x = np.linspace(0.0, 1.0, n)
    rgba = (cmap(x) * 255).astype(np.uint8)
    return rgba[np.newaxis, :, :]  # (1, n, 4)
