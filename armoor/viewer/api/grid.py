"""Grid mesh endpoint – returns geographic vertex coordinates.

GET /api/datasets/<id>/grid?nx=64&ny=32
"""

import numpy as np
from flask import Blueprint, jsonify, request

from armoor.viewer.store import store

bp = Blueprint("grid", __name__, url_prefix="/api/datasets")

_LON_NAMES = ("lon", "longitude", "nav_lon", "x")
_LAT_NAMES = ("lat", "latitude", "nav_lat", "y")


@bp.route("/<dataset_id>/grid", methods=["GET"])
def get_grid(dataset_id: str):
    """Geographic vertex grid for the scalar overlay mesh.

    Returns (ny+1)×(nx+1) lon/lat arrays sampled from the dataset
    coordinates, so the Three.js mesh follows the actual grid geometry
    without any data regridding.

    Query parameters
    ----------------
    nx : int, optional  (default 64)
    ny : int, optional  (default 32)
    """
    try:
        entry = store.get(dataset_id)
    except KeyError:
        return jsonify({"error": f"Dataset not found: {dataset_id}"}), 404

    nx = int(request.args.get("nx", 64))
    ny = int(request.args.get("ny", 32))
    ds = entry.ds

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
        return jsonify({"error": "No lon/lat coordinates found"}), 400

    if lons.ndim == 2 and lats.ndim == 2:
        ny_src, nx_src = lons.shape
        j_idx = np.round(np.linspace(0, ny_src - 1, ny + 1)).astype(int)
        i_idx = np.round(np.linspace(0, nx_src - 1, nx + 1)).astype(int)
        lons_mesh = lons[np.ix_(j_idx, i_idx)]
        lats_mesh = lats[np.ix_(j_idx, i_idx)]
    else:
        lons_1d = np.atleast_1d(lons).ravel()
        lats_1d = np.atleast_1d(lats).ravel()
        i_idx = np.round(np.linspace(0, len(lons_1d) - 1, nx + 1)).astype(int)
        j_idx = np.round(np.linspace(0, len(lats_1d) - 1, ny + 1)).astype(int)
        lons_mesh, lats_mesh = np.meshgrid(lons_1d[i_idx], lats_1d[j_idx])

    return jsonify(
        {
            "lons": lons_mesh.tolist(),
            "lats": lats_mesh.tolist(),
            "nx": nx,
            "ny": ny,
        }
    )
