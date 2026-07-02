"""Colormap strip endpoint – used by the legend canvas.

GET /api/colormap-strip?name=<cmap>&n=<steps>
Returns a (1 × n × 4) PNG strip.
"""

import io
import logging

from flask import Blueprint, Response, jsonify, request
from PIL import Image

from armoor.viewer.rendering.colormap import colormap_strip

bp = Blueprint("colormap", __name__, url_prefix="/api")
logger = logging.getLogger(__name__)


@bp.route("/colormap-strip", methods=["GET"])
def get_colormap_strip():
    """Return a horizontal colormap strip as a PNG.

    Query parameters
    ----------------
    name : str
        Colormap name (default ``cmo.thermal``).
    n : int
        Number of colour steps (default 256).
    """
    name = request.args.get("name", "cmo.thermal")
    n = int(request.args.get("n", 256))
    n = max(2, min(n, 2048))

    try:
        strip = colormap_strip(name, n)  # shape (1, n, 4), uint8
    except Exception as exc:
        logger.warning("colormap strip failed for '%s': %s", name, exc)
        return jsonify({"error": str(exc)}), 400

    img = Image.fromarray(strip, mode="RGBA")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return Response(buf.getvalue(), mimetype="image/png")
