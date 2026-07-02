"""Frontend configuration endpoint.

GET /api/config
"""

from flask import Blueprint, current_app, jsonify

bp = Blueprint("config", __name__, url_prefix="/api")


@bp.route("/config", methods=["GET"])
def get_config():
    """Return frontend-relevant server configuration.

    Currently exposes the deployment's default render mode
    (``auto`` / ``2d`` / ``3d``) so the client can decide whether to load
    the iTowns 3D globe or the Leaflet 2D planisphere.
    """
    return jsonify({"render_mode": current_app.config["RENDER_MODE"]})
