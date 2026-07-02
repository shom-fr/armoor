"""Dataset management endpoints.

POST   /api/datasets        – load a dataset
GET    /api/datasets        – list loaded datasets
DELETE /api/datasets/<id>   – unload a dataset
"""

import logging

from flask import Blueprint, jsonify, request

from armoor.viewer.store import store

bp = Blueprint("datasets", __name__, url_prefix="/api/datasets")
logger = logging.getLogger(__name__)


@bp.route("", methods=["POST"])
def load_dataset():
    """Load a dataset from disk.

    JSON body
    ---------
    ``{ "path": "/path/to/store.zarr", "fmt": "zarr" }``

    Returns
    -------
    JSON with dataset id and summary metadata.
    """
    body = request.get_json(force=True, silent=True) or {}
    path = body.get("path")
    fmt = body.get("fmt", "zarr")

    if not path:
        return jsonify({"error": "Missing required field: path"}), 400

    job_id = store.submit_load(path, fmt)
    return jsonify({"job_id": job_id, "status": "loading"}), 202


@bp.route("/jobs/<job_id>", methods=["GET"])
def get_job_status(job_id: str):
    """Poll the status of an async dataset-load job."""
    try:
        job = store.get_job(job_id)
    except KeyError:
        return jsonify({"error": f"Job not found: {job_id}"}), 404

    if job["status"] == "ready":
        try:
            entry = store.get(job["dataset_id"])
            return jsonify({**job, **_entry_summary(entry)})
        except KeyError:
            return jsonify({"status": "error", "error": "Dataset disappeared after load"}), 500

    return jsonify(job)


@bp.route("", methods=["GET"])
def list_datasets():
    """List all loaded datasets (summary only)."""
    entries = store.list_entries()
    return jsonify([_entry_summary(e) for e in entries])


@bp.route("/<dataset_id>", methods=["DELETE"])
def close_dataset(dataset_id: str):
    """Unload a dataset and release resources."""
    try:
        store.get(dataset_id)
    except KeyError:
        return jsonify({"error": f"Dataset not found: {dataset_id}"}), 404
    store.close(dataset_id)
    return jsonify({"status": "closed", "id": dataset_id})


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------


def _entry_summary(entry) -> dict:
    return {
        "id": entry.id,
        "path": entry.path,
        "fmt": entry.fmt,
        "variables": entry.variables,
        "time_count": len(entry.time_values),
        "depth_count": len(entry.depth_values),
        "lon_range": entry.lon_range,
        "lat_range": entry.lat_range,
        "dims": entry.dims,
    }
