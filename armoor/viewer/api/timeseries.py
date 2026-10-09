"""Time-series extraction endpoint.

GET /api/datasets/<id>/timeseries
    ?variable=<v>&lon=<lon>&lat=<lat>&depth_idx=<d>
"""

import logging

import numpy as np
from flask import Blueprint, jsonify, request

from armoor.viewer.api._spatial import nearest_ij
from armoor.viewer.store import store

bp = Blueprint("timeseries", __name__, url_prefix="/api/datasets")
logger = logging.getLogger(__name__)

# Per-dataset time-series cache: (dataset_id, variable, j, i, depth_idx) → values list.
_ts_cache: dict = {}
_TS_CACHE_SIZE = 64


@bp.route("/<dataset_id>/timeseries", methods=["GET"])
def get_timeseries(dataset_id: str):
    """Flask view for ``GET /api/datasets/<id>/timeseries``.

    Query parameters
    ----------------
    variable : str
        Variable name to extract.
    lon, lat : float
        Point to extract the nearest-grid-point series at.
    depth_idx : int, optional
        Vertical index to select (default 0).

    Returns
    -------
    flask.Response
        JSON time series on success, or a JSON ``{"error": ...}`` with a
        4xx/5xx status on a missing dataset/variable/parameter or an
        extraction failure.
    """
    try:
        entry = store.get(dataset_id)
    except KeyError:
        return jsonify({"error": f"Dataset not found: {dataset_id}"}), 404

    args = request.args
    variable = args.get("variable")
    if not variable:
        return jsonify({"error": "Missing query parameter: variable"}), 400
    if variable not in entry.ds.data_vars:
        return jsonify({"error": f"Variable '{variable}' not in dataset"}), 400

    try:
        lon = float(args.get("lon"))
        lat = float(args.get("lat"))
    except (TypeError, ValueError):
        return jsonify({"error": "Missing or invalid lon/lat parameters"}), 400

    depth_idx = int(args.get("depth_idx", 0))

    try:
        result = _extract_timeseries(entry, variable, lon, lat, depth_idx)
    except Exception as exc:
        logger.exception("Time-series extraction failed")
        return jsonify({"error": str(exc)}), 500

    return jsonify(result)


# ---------------------------------------------------------------------------


def _find_dim(da, candidates):
    for c in candidates:
        if c in da.dims:
            return c
    return None


def _extract_timeseries(entry, variable: str, lon: float, lat: float, depth_idx: int) -> dict:
    ds = entry.ds
    da = ds[variable]

    time_dim = _find_dim(da, ("time",))
    depth_dim = _find_dim(da, ("z", "s_rho", "s_w", "depth", "deptht", "level", "nz", "nz1"))

    j, i, y_dim, x_dim = nearest_ij(entry, lat, lon)

    cache_key = (entry.id, variable, j, i, depth_idx)
    if cache_key in _ts_cache:
        values, time_values = _ts_cache[cache_key]
    else:
        values, time_values = _load_point(
            entry, da, time_dim, depth_dim, depth_idx, y_dim, x_dim, j, i
        )
        if len(_ts_cache) >= _TS_CACHE_SIZE:
            _ts_cache.pop(next(iter(_ts_cache)))
        _ts_cache[cache_key] = (values, time_values)

    depth_val = None
    if entry.depth_values and depth_idx < len(entry.depth_values):
        depth_val = entry.depth_values[depth_idx]

    return {
        "variable": variable,
        "units": da.attrs.get("units", ""),
        "lon": lon,
        "lat": lat,
        "depth_idx": depth_idx,
        "depth_val": depth_val,
        "times": time_values,
        "values": values,
    }


def _load_point(entry, da, time_dim, depth_dim, depth_idx, y_dim, x_dim, j, i):
    """Extract the 1-D time series at (j, i, depth_idx).

    Strategy:
    1. For Zarr stores: use zarr-python directly — reads only the native
       zarr chunks (typically much smaller than xarray's rechunked chunks).
    2. Otherwise: select depth+space lazily, then rechunk the 1-D time
       series to a single chunk before calling compute(), so that Dask can
       read the NT source chunks in parallel with the threaded scheduler.
    """
    # ── Strategy 1: Zarr direct access ─────────────────────────────────────
    if entry.fmt == "zarr":
        arr, t_vals = _zarr_point(entry, da, time_dim, depth_dim, depth_idx, y_dim, x_dim, j, i)
        if arr is not None:
            return _to_values(arr), t_vals

    # ── Strategy 2: Dask with threaded scheduler ────────────────────────────
    isel = {}
    if depth_dim and depth_dim in da.dims:
        isel[depth_dim] = depth_idx
    if y_dim and y_dim in da.dims:
        isel[y_dim] = j
    if x_dim and x_dim in da.dims:
        isel[x_dim] = i

    series_da = da.isel(**isel).squeeze()

    if time_dim and time_dim in series_da.dims:
        arr = _compute_1d(series_da, time_dim)
    else:
        arr = np.array([float(series_da.values)])

    # Fallback if spatial dims were not in isel
    if arr.ndim == 2:
        arr = arr[:, i] if arr.shape[1] > 1 else arr[:, 0]
    elif arr.ndim == 3:
        arr = arr[:, j, i]

    t_vals = entry.time_values if entry.time_values else list(range(len(arr)))
    return _to_values(arr), t_vals


def _zarr_point(entry, da, time_dim, depth_dim, depth_idx, y_dim, x_dim, j, i):
    """Read one point's time series directly from a Zarr store.

    Uses zarr-python's native chunked I/O, which reads only the chunks that
    overlap the requested indices.  xarray's Dask chunks (set by open_decode)
    can be much larger than the store's native chunks, so bypassing Dask can
    dramatically reduce the amount of data read from disk.
    """
    try:
        import zarr

        store_obj = zarr.open_consolidated(entry.path, mode="r")
        if da.name not in store_obj:
            return None, None

        z = store_obj[da.name]

        # Build an index tuple matching the xarray dimension order
        idx = [slice(None)] * z.ndim
        for dim_pos, dim in enumerate(da.dims):
            if dim == depth_dim:
                idx[dim_pos] = depth_idx
            elif dim == y_dim:
                idx[dim_pos] = j
            elif dim == x_dim:
                idx[dim_pos] = i

        arr = np.asarray(z[tuple(idx)]).squeeze().astype(float)

        # Build matching time labels
        if time_dim and time_dim in da.dims:
            t_pos = list(da.dims).index(time_dim)
            n = z.shape[t_pos]
            t_vals = entry.time_values[:n] if entry.time_values else list(range(n))
        else:
            t_vals = entry.time_values or []

        return arr, t_vals
    except Exception as exc:
        logger.debug("Zarr direct read failed, falling back to Dask: %s", exc)
        return None, None


def _compute_1d(series_da, time_dim):
    """Compute a 1-D Dask time series using the threaded scheduler.

    Rechunking to a single time chunk first tells Dask to load all NT
    source chunks in parallel (threads), then concatenate in memory.
    """
    try:
        import dask.array as dsa

        if isinstance(series_da.data, dsa.Array):
            rechunked = series_da.chunk({time_dim: -1})
            return rechunked.compute(scheduler="threads").values.astype(float)
    except Exception:  # nosec B110
        pass
    return series_da.values.astype(float)


def _to_values(arr):
    return [None if np.isnan(v) else float(v) for v in arr.ravel()]
