"""Shared KDTree spatial index, cached per dataset (keyed by id(ds))."""

import numpy as np
from scipy.spatial import KDTree

_cache: dict = {}


def get_index(entry):
    """Return (tree, lat2d, lon2d, y_dim, x_dim), built once per dataset."""
    key = id(entry.ds)
    if key not in _cache:
        _cache[key] = _build(entry.ds)
    return _cache[key]


def nearest_ij(entry, lat: float, lon: float):
    """Return (j, i, y_dim, x_dim) for the nearest grid point."""
    tree, lat2d, lon2d, y_dim, x_dim = get_index(entry)
    _, flat = tree.query([[lat, lon]])
    j, i = np.unravel_index(flat[0], lat2d.shape)
    return int(j), int(i), y_dim, x_dim


def _build(ds):
    lat_arr, lon_arr = _get_latlon(ds)
    if lat_arr is None:
        raise ValueError("No lat/lon coordinates in dataset")
    y_dim = x_dim = None
    if lat_arr.ndim == 1:
        lon2d, lat2d = np.meshgrid(lon_arr, lat_arr)
    else:
        lat2d, lon2d = lat_arr, lon_arr
        for name in ("lat", "latitude", "nav_lat"):
            if name in ds.coords and len(ds[name].dims) == 2:
                y_dim, x_dim = ds[name].dims
                break
    tree = KDTree(np.column_stack([lat2d.ravel(), lon2d.ravel()]))
    return tree, lat2d, lon2d, y_dim, x_dim


def _get_latlon(ds):
    for lat_name in ("lat", "latitude", "nav_lat"):
        for lon_name in ("lon", "longitude", "nav_lon"):
            if lat_name in ds.coords and lon_name in ds.coords:
                return (
                    ds[lat_name].values.astype(float),
                    ds[lon_name].values.astype(float),
                )
    return None, None
