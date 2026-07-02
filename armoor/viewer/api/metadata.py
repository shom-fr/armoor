"""Metadata endpoint.

GET /api/datasets/<id>/metadata
"""

import logging

import numpy as np
from flask import Blueprint, jsonify

from armoor.viewer.store import store

bp = Blueprint("metadata", __name__, url_prefix="/api/datasets")
logger = logging.getLogger(__name__)


@bp.route("/<dataset_id>/metadata", methods=["GET"])
def get_metadata(dataset_id: str):
    """Return full metadata for a loaded dataset."""
    try:
        entry = store.get(dataset_id)
    except KeyError:
        return jsonify({"error": f"Dataset not found: {dataset_id}"}), 404

    ds = entry.ds

    # Per-variable info
    var_info = {}
    for vname in entry.variables:
        da = ds[vname]
        var_info[vname] = {
            "dims": list(da.dims),
            "shape": list(da.shape),
            "attrs": {k: _json_safe(v) for k, v in da.attrs.items()},
            "dtype": str(da.dtype),
        }

    return jsonify(
        {
            "id": entry.id,
            "path": entry.path,
            "fmt": entry.fmt,
            "variables": entry.variables,
            "var_info": var_info,
            "time_values": entry.time_values,
            "depth_values": entry.depth_values,
            "lon_range": entry.lon_range,
            "lat_range": entry.lat_range,
            "dims": entry.dims,
            "global_attrs": {k: _json_safe(v) for k, v in ds.attrs.items()},
        }
    )


def _json_safe(v):
    """Convert numpy scalars / arrays to JSON-serialisable Python types."""
    if isinstance(v, np.ndarray):
        return v.tolist()
    if isinstance(v, (np.integer,)):
        return int(v)
    if isinstance(v, (np.floating,)):
        return float(v)
    return v
