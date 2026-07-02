"""Point value extraction endpoint.

GET /api/datasets/<id>/point
    ?variable=<v>&lon=<>&lat=<>&time_idx=<>&depth_idx=<>

Returns the value of *variable* at the grid point nearest to (lon, lat)
for the selected time step and depth level, together with the physical
coordinates of that nearest point (time label, actual lon/lat, depth in m).
"""

import logging

import numpy as np
from flask import Blueprint, jsonify, request

from armoor.viewer.api._spatial import get_index, nearest_ij
from armoor.viewer.store import store

bp = Blueprint("point", __name__, url_prefix="/api/datasets")
logger = logging.getLogger(__name__)


@bp.route("/<dataset_id>/point", methods=["GET"])
def get_point(dataset_id: str):
    """Extract the value of a variable at the nearest grid point.

    Query parameters
    ----------------
    variable : str
        Name of the data variable to sample.
    lon : float
        Target longitude in degrees.
    lat : float
        Target latitude in degrees.
    time_idx : int, optional
        Time step index (default 0).
    depth_idx : int, optional
        Depth level index (default 0).
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
        return jsonify({"error": "Missing or invalid lon/lat"}), 400

    time_idx = int(args.get("time_idx", 0))
    depth_idx = int(args.get("depth_idx", 0))

    try:
        result = _extract_point(entry, variable, lon, lat, time_idx, depth_idx)
    except Exception as exc:
        logger.exception("Point extraction failed")
        return jsonify({"error": str(exc)}), 500

    return jsonify(result)


# ---------------------------------------------------------------------------


def _extract_point(entry, variable, lon, lat, time_idx, depth_idx) -> dict:
    ds = entry.ds
    da = ds[variable]

    j, i, y_dim, x_dim = nearest_ij(entry, lat, lon)
    _, lat2d, lon2d, _, _ = get_index(entry)

    # Actual grid coordinates
    actual_lon = float(lon2d[j, i])
    actual_lat = float(lat2d[j, i])

    # Extract scalar value — select single point to avoid loading the full 2-D slice
    time_dim = _find_dim(da, ("time",))
    depth_dim = _find_dim(da, ("z", "s_rho", "s_w", "depth", "deptht", "level", "nz", "nz1"))

    isel = {}
    if time_dim:
        isel[time_dim] = time_idx
    if depth_dim:
        isel[depth_dim] = depth_idx
    if y_dim and y_dim in da.dims:
        isel[y_dim] = int(j)
    if x_dim and x_dim in da.dims:
        isel[x_dim] = int(i)

    scalar = da.isel(**isel).squeeze()
    if scalar.ndim == 0:
        value = float(scalar.values)
    else:
        # Fallback for rectilinear grids where lat/lon dims are shared with data dims
        arr = scalar.values.astype(float)
        value = float(arr[j, i]) if arr.ndim == 2 else float(arr.flat[0])
    if np.isnan(value):
        value = None

    # Time label
    time_str = None
    if entry.time_values and time_idx < len(entry.time_values):
        time_str = str(entry.time_values[time_idx])

    # Physical depth at the grid point
    depth_val = _get_depth_val(ds, depth_dim, depth_idx, time_idx, j, i, entry.depth_values)

    return {
        "variable": variable,
        "units": da.attrs.get("units", ""),
        "value": value,
        "lon": actual_lon,
        "lat": actual_lat,
        "time_idx": time_idx,
        "time_str": time_str,
        "depth_idx": depth_idx,
        "depth_val": depth_val,
    }


def _get_depth_val(ds, depth_dim, depth_idx, time_idx, j, i, coord_depths):
    """Return physical depth (m) at grid point (j, i) for z-level depth_idx."""
    if depth_dim is None:
        return None

    # Try well-known 3-D/4-D depth variables
    from armoor.viewer.api.section import _find_depth_data_var

    var_name = _find_depth_data_var(ds, depth_dim)
    if var_name:
        da = ds[var_name]
        time_dim = _find_dim(da, ("time",))
        isel = {depth_dim: depth_idx}
        if time_dim:
            isel[time_dim] = time_idx
        try:
            arr = da.isel(**isel).squeeze().values.astype(float)
            v = float(arr[j, i]) if arr.ndim == 2 else float(arr.flat[0])
            return None if np.isnan(v) else v
        except Exception as exc:  # nosec B110
            logger.debug("Could not extract grid value at (%s, %s): %s", i, j, exc)

    # 1-D coordinate
    if coord_depths and depth_idx < len(coord_depths):
        return float(coord_depths[depth_idx])

    return None


def _find_dim(da, candidates):
    for c in candidates:
        if c in da.dims:
            return c
    return None
