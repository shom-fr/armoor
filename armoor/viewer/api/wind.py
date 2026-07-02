"""Wind / current grid endpoint.

GET /api/datasets/<id>/wind
"""

import logging

from flask import Blueprint, jsonify, request

from armoor.viewer import config as cfg
from armoor.viewer.rendering.wind import extract_wind_native
from armoor.viewer.store import store

bp = Blueprint("wind", __name__, url_prefix="/api/datasets")
logger = logging.getLogger(__name__)


@bp.route("/<dataset_id>/wind", methods=["GET"])
def get_wind(dataset_id: str):
    """Return u/v on the native curvilinear grid (subsampled).

    Query parameters
    ----------------
    u_var : str
        Name of the zonal velocity variable.
    v_var : str
        Name of the meridional velocity variable.
    time_idx : int, optional
        Time step index (default 0).
    depth_idx : int, optional
        Depth level index (default 0).
    nx : int, optional
        Maximum output columns (default from config).
    ny : int, optional
        Maximum output rows (default from config).

    Returns
    -------
    JSON
        ``{ type, u, v, lon, lat, lat_min, lat_max, lon_min, lon_max, ny, nx }``
    """
    try:
        entry = store.get(dataset_id)
    except KeyError:
        return jsonify({"error": f"Dataset not found: {dataset_id}"}), 404

    args = request.args

    u_var = args.get("u_var")
    v_var = args.get("v_var")

    if not u_var or not v_var:
        return jsonify({"error": "Missing query parameters: u_var and v_var"}), 400

    for vname in (u_var, v_var):
        if vname not in entry.ds.data_vars and vname not in entry.ds.coords:
            return jsonify({"error": f"Variable '{vname}' not in dataset"}), 400

    time_idx = int(args.get("time_idx", 0))
    depth_idx_raw = args.get("depth_idx")
    depth_idx = int(depth_idx_raw) if depth_idx_raw is not None else None

    nx = int(args.get("nx", cfg.WIND_NX))
    ny = int(args.get("ny", cfg.WIND_NY))

    try:
        grid = extract_wind_native(
            entry.ds,
            u_var=u_var,
            v_var=v_var,
            time_idx=time_idx,
            depth_idx=depth_idx,
            nx_out=nx,
            ny_out=ny,
        )
    except Exception as exc:
        logger.exception("Wind grid extraction failed")
        return jsonify({"error": str(exc)}), 500

    return jsonify(grid)
