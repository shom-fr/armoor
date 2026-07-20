"""Extract u/v components on the native curvilinear grid for the particle system."""

import logging
from typing import Optional, Tuple

import numpy as np
import xarray as xr

logger = logging.getLogger(__name__)

_LON_NAMES = ("lon", "longitude", "nav_lon", "x")
_LAT_NAMES = ("lat", "latitude", "nav_lat", "y")


def extract_wind_native(
    ds: xr.Dataset,
    u_var: str,
    v_var: str,
    time_idx: int = 0,
    depth_idx: Optional[int] = None,
    nx_out: int = 256,
    ny_out: int = 128,
) -> dict:
    """Extract u/v on the native grid, subsampled to ≤ nx_out × ny_out.

    Parameters
    ----------
    ds:
        Dataset containing *u_var* and *v_var*.
    u_var, v_var:
        Names of the zonal / meridional velocity variables.
    time_idx:
        Time step index.
    depth_idx:
        Depth level index (defaults to surface = 0).
    nx_out, ny_out:
        Maximum output grid size; the native grid is strided if larger.

    Returns
    -------
    dict with keys:
        ``type``    : "native"
        ``u``, ``v``: list[list[float]] – native 2-D values (ny × nx)
        ``lon``, ``lat``: list[list[float]] – native 2-D coordinates
        ``lat_min``, ``lat_max``, ``lon_min``, ``lon_max``: float
        ``ny``, ``nx``: int
    """
    u_arr, lons, lats = _select_2d(ds, u_var, time_idx, depth_idx)
    v_arr, _, _ = _select_2d(ds, v_var, time_idx, depth_idx)

    ny_src, nx_src = u_arr.shape

    # Subsample so the payload stays manageable
    j_step = max(1, ny_src // ny_out)
    i_step = max(1, nx_src // nx_out)

    u_sub = u_arr[::j_step, ::i_step]
    v_sub = v_arr[::j_step, ::i_step]
    lon_sub = lons[::j_step, ::i_step]
    lat_sub = lats[::j_step, ::i_step]

    ny_actual, nx_actual = u_sub.shape

    return {
        "type": "native",
        "u": np.nan_to_num(u_sub, nan=0.0).tolist(),
        "v": np.nan_to_num(v_sub, nan=0.0).tolist(),
        "lon": lon_sub.tolist(),
        "lat": lat_sub.tolist(),
        "ny": ny_actual,
        "nx": nx_actual,
        "lat_min": float(np.nanmin(lat_sub)),
        "lat_max": float(np.nanmax(lat_sub)),
        "lon_min": float(np.nanmin(lon_sub)),
        "lon_max": float(np.nanmax(lon_sub)),
    }


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _select_2d(
    ds: xr.Dataset,
    var: str,
    time_idx: int,
    depth_idx: Optional[int],
) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Select a 2-D slice and return (data, lons_2d, lats_2d)."""
    da = ds[var]

    isel_kw = {}
    time_dim = _find_dim(da, ("time",))
    depth_dim = _find_dim(da, ("z", "depth", "deptht", "level"))

    if time_dim and time_dim in da.dims:
        isel_kw[time_dim] = time_idx
    if depth_dim and depth_dim in da.dims:
        isel_kw[depth_dim] = depth_idx if depth_idx is not None else 0

    if isel_kw:
        da = da.isel(**isel_kw)

    da = da.squeeze()

    if da.ndim != 2:
        raise ValueError(f"'{var}' is {da.ndim}-D after selection; expected 2-D")

    arr = da.values.astype(float)

    lons = lats = None
    for name in _LON_NAMES:
        if name in ds.coords:
            lons = ds[name].values
            break
    for name in _LAT_NAMES:
        if name in ds.coords:
            lats = ds[name].values
            break

    if lons is None or lats is None:
        ny, nx = arr.shape
        lons, lats = np.meshgrid(np.linspace(-180, 180, nx), np.linspace(-90, 90, ny))
        return arr, lons, lats

    # Always work with 2-D coordinate arrays
    if lons.ndim == 1 or lats.ndim == 1:
        if lons.ndim == 1 and lats.ndim == 1:
            lons, lats = np.meshgrid(lons, lats)
        elif lons.ndim == 1:
            lons = np.broadcast_to(lons[np.newaxis, :], arr.shape).copy()
        else:
            lats = np.broadcast_to(lats[:, np.newaxis], arr.shape).copy()

    return arr, lons, lats


def _find_dim(da: xr.DataArray, candidates: tuple):
    for name in candidates:
        if name in da.dims:
            return name
    return None
