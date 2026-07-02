"""Tile rendering endpoint.

GET /api/datasets/<id>/tile
"""

import logging

from flask import Blueprint, Response, jsonify, request

from armoor.viewer import config as cfg
from armoor.viewer.rendering.raster import slice_to_png
from armoor.viewer.store import store

bp = Blueprint("tiles", __name__, url_prefix="/api/datasets")
logger = logging.getLogger(__name__)


@bp.route("/<dataset_id>/tile", methods=["GET"])
def get_tile(dataset_id: str):
    """Render a 2-D slice of a dataset variable as a PNG.

    Query parameters
    ----------------
    variable : str
        Variable name to render.
    time_idx : int, optional
        Time step index (default 0).
    depth_idx : int, optional
        Depth level index (default 0).
    colormap : str, optional
        Colormap name (default ``cmo.thermal``).
    vmin : float, optional
        Colour scale minimum (auto if absent).
    vmax : float, optional
        Colour scale maximum (auto if absent).
    width : int, optional
        Output width in pixels (default from config).
    height : int, optional
        Output height in pixels (default from config).
    land_mask : bool, optional
        If ``1`` / ``true``, land pixels are made transparent (default false).

    Response headers
    ----------------
    X-Bbox-West, X-Bbox-East, X-Bbox-South, X-Bbox-North : float
        Geographic bounding box in degrees.
    X-Vmin, X-Vmax : float
        Actual colour scale bounds used.
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

    time_idx = int(args.get("time_idx", 0))
    depth_idx_raw = args.get("depth_idx")
    depth_idx = int(depth_idx_raw) if depth_idx_raw is not None else None

    colormap = args.get("colormap", "cmo.thermal")

    vmin_raw = args.get("vmin")
    vmax_raw = args.get("vmax")
    vmin = float(vmin_raw) if vmin_raw is not None else None
    vmax = float(vmax_raw) if vmax_raw is not None else None

    width = int(args.get("width", cfg.TILE_WIDTH))
    height = int(args.get("height", cfg.TILE_HEIGHT))

    land_mask_raw = args.get("land_mask", "false").lower()
    apply_land_mask = land_mask_raw in ("1", "true", "yes")

    try:
        png_bytes, used_vmin, used_vmax, bbox = slice_to_png(
            entry.ds,
            variable=variable,
            time_idx=time_idx,
            depth_idx=depth_idx,
            colormap=colormap,
            vmin=vmin,
            vmax=vmax,
            width=width,
            height=height,
            apply_land_mask=apply_land_mask,
        )
    except Exception as exc:
        logger.exception("Tile rendering failed")
        return jsonify({"error": str(exc)}), 500

    mime = "image/png" if png_bytes[:4] == b'\x89PNG' else "image/jpeg"
    headers = {
        "Content-Type": mime,
        "Cache-Control": "no-store",
        "X-Bbox-West": str(bbox["west"]),
        "X-Bbox-East": str(bbox["east"]),
        "X-Bbox-South": str(bbox["south"]),
        "X-Bbox-North": str(bbox["north"]),
        "X-Vmin": str(used_vmin),
        "X-Vmax": str(used_vmax),
        # Allow JS to read custom headers
        "Access-Control-Expose-Headers": (
            "X-Bbox-West, X-Bbox-East, X-Bbox-South, X-Bbox-North, X-Vmin, X-Vmax"
        ),
    }

    return Response(png_bytes, headers=headers)
