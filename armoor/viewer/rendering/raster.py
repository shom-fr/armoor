"""Convert an xarray 2-D slice to a PNG byte string."""

import io
import logging
from typing import Optional, Tuple

import numpy as np
import xarray as xr
from PIL import Image

from armoor.viewer.rendering.colormap import apply_colormap

logger = logging.getLogger(__name__)


def slice_to_png(
    ds: xr.Dataset,
    variable: str,
    time_idx: int = 0,
    depth_idx: Optional[int] = None,
    colormap: str = "cmo.thermal",
    vmin: Optional[float] = None,
    vmax: Optional[float] = None,
    width: int = 1024,
    height: int = 512,
    apply_land_mask: bool = False,
) -> Tuple[bytes, float, float, dict]:
    """Extract a 2-D slice from *ds* and render it as a PNG.

    Parameters
    ----------
    ds:
        Dataset containing *variable*.
    variable:
        Name of the data variable to render.
    time_idx:
        Index along the time dimension (ignored if no time dim).
    depth_idx:
        Index along the vertical dimension (ignored if no z/depth dim).
    colormap:
        Colormap name (cmocean or matplotlib).
    vmin, vmax:
        Colour scale bounds.  Auto-computed from finite data if not given.
    width, height:
        Output PNG size in pixels.
    apply_land_mask:
        If ``True``, land pixels are set fully transparent so the base
        imagery shows through.  Uses Natural Earth 110 m data via cartopy.

    Returns
    -------
    png_bytes : bytes
    vmin : float
    vmax : float
    bbox : dict  – { west, south, east, north } in degrees
    """
    da = ds[variable]

    # --- Select time & depth -------------------------------------------------
    isel_kwargs = {}
    time_dim = _find_dim(da, ("time",))
    depth_dim = _find_dim(da, ("z", "depth", "deptht", "level"))

    if time_dim and time_dim in da.dims:
        isel_kwargs[time_dim] = time_idx

    if depth_dim and depth_dim in da.dims:
        if depth_idx is not None:
            isel_kwargs[depth_dim] = depth_idx
        else:
            isel_kwargs[depth_dim] = 0

    if isel_kwargs:
        da = da.isel(**isel_kwargs)

    # Squeeze any remaining size-1 dims
    da = da.squeeze()

    if da.ndim != 2:
        raise ValueError(
            f"After selection, '{variable}' has {da.ndim} dimensions {da.dims}; expected 2"
        )

    # --- Compute -------------------------------------------------------------
    arr = da.values.astype(float)

    # Flip Y axis (lat increases upward in geographic convention)
    arr = np.flipud(arr)

    # --- Auto vmin / vmax ----------------------------------------------------
    finite = arr[np.isfinite(arr)]
    if vmin is None:
        vmin = float(finite.min()) if len(finite) else 0.0
    if vmax is None:
        vmax = float(finite.max()) if len(finite) else 1.0
    if vmin == vmax:
        vmax = vmin + 1.0

    # --- Colormap → RGBA -----------------------------------------------------
    rgba = apply_colormap(arr, colormap, vmin, vmax)

    # --- Land mask -----------------------------------------------------------
    if apply_land_mask:
        bbox_tmp = _extract_bbox(ds, da)
        try:
            from armoor.viewer.rendering.landmask import make_land_mask

            ny_arr, nx_arr = arr.shape
            land = make_land_mask(
                bbox_tmp["west"],
                bbox_tmp["east"],
                bbox_tmp["south"],
                bbox_tmp["north"],
                nx_arr,
                ny_arr,
            )
            # flipud so mask orientation matches the flipped data array
            land_flipped = np.flipud(land)
            rgba[land_flipped, 3] = 0
        except Exception as exc:
            logger.warning("Land mask failed, skipping: %s", exc)

    # --- Resize to (height, width) -------------------------------------------
    img = Image.fromarray(rgba, mode="RGBA")
    if img.size != (width, height):
        img = img.resize((width, height), Image.BILINEAR)

    # Use PNG whenever transparency is needed (NaN pixels or land mask).
    # PNG with compress_level=1 is fast enough; JPEG would destroy alpha.
    has_transparency = apply_land_mask or bool(np.isnan(arr).any())
    buf = io.BytesIO()
    if has_transparency:
        img.save(buf, format="PNG", optimize=False, compress_level=1)
    else:
        img = img.convert("RGB")
        img.save(buf, format="JPEG", quality=90)
    png_bytes = buf.getvalue()

    # --- Bounding box --------------------------------------------------------
    bbox = _extract_bbox(ds, da)

    return png_bytes, float(vmin), float(vmax), bbox


def _find_dim(da: xr.DataArray, candidates: tuple) -> Optional[str]:
    for name in candidates:
        if name in da.dims:
            return name
    return None


def _extract_bbox(ds: xr.Dataset, da: xr.DataArray) -> dict:
    """Try to extract lon/lat bounding box from dataset coordinates."""
    lon_candidates = ("lon", "longitude", "nav_lon", "x")
    lat_candidates = ("lat", "latitude", "nav_lat", "y")

    west = east = south = north = None

    for name in lon_candidates:
        if name in ds.coords:
            vals = ds[name].values.ravel()
            west = float(np.nanmin(vals))
            east = float(np.nanmax(vals))
            break

    for name in lat_candidates:
        if name in ds.coords:
            vals = ds[name].values.ravel()
            south = float(np.nanmin(vals))
            north = float(np.nanmax(vals))
            break

    return {
        "west": west if west is not None else -180.0,
        "east": east if east is not None else 180.0,
        "south": south if south is not None else -90.0,
        "north": north if north is not None else 90.0,
    }
