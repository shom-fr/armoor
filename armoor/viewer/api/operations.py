"""Operations endpoint – apply armoor transformations.

POST /api/datasets/<id>/operations
"""

import logging
import uuid

from flask import Blueprint, jsonify, request

from armoor.viewer.store import store

bp = Blueprint("operations", __name__, url_prefix="/api/datasets")
logger = logging.getLogger(__name__)


@bp.route("/<dataset_id>/operations", methods=["POST"])
def apply_operation(dataset_id: str):
    """Apply an armoor operation to a loaded dataset.

    The transformed dataset is registered under a **new** UUID and the old
    dataset is NOT removed (the caller can DELETE it explicitly).

    JSON body
    ---------
    ::

        {
            "operation": "<operation_name>",
            "params":    { … }
        }

    Supported operations
    --------------------
    filter
        Apply combined armoor filters.
        ``params`` = filters_config dict (see armoor docs).

    interp_time
        Temporal interpolation.
        ``params`` = ``{ "tfreq": "1H" }``

    interp_horizontal
        Horizontal interpolation.
        ``params`` = dict forwarded directly as the ``param`` argument.

    interp_vertical
        Vertical interpolation.
        ``params`` = ``{ "method": "<method>", "args": […] }``

    range_time
        Split into time intervals.
        ``params`` = ``{ "tfreq": "D" }``

    range_vertical
        Mask outside vertical range.
        ``params`` = ``{ "vname": "z", "vmin": 0, "vmax": 500 }``

    Returns
    -------
    JSON
        ``{ "new_id": "…", "variables": […], … }``
    """
    try:
        entry = store.get(dataset_id)
    except KeyError:
        return jsonify({"error": f"Dataset not found: {dataset_id}"}), 404

    body = request.get_json(force=True, silent=True) or {}
    operation = body.get("operation")
    params = body.get("params", {})

    if not operation:
        return jsonify({"error": "Missing field: operation"}), 400

    ds = entry.ds

    try:
        new_ds = _dispatch(operation, ds, params)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    except Exception as exc:
        logger.exception("Operation '%s' failed", operation)
        return jsonify({"error": str(exc)}), 500

    # Register the transformed dataset under a new id
    new_id = str(uuid.uuid4())
    from armoor.viewer.store import _build_entry
    from armoor.viewer.store import store as _store

    new_entry = _build_entry(entry.path, entry.fmt, new_ds, existing_id=new_id)
    with _store._lock:
        _store._store[new_id] = new_entry

    return jsonify(
        {
            "new_id": new_id,
            "operation": operation,
            "variables": new_entry.variables,
            "time_count": len(new_entry.time_values),
            "depth_count": len(new_entry.depth_values),
            "dims": new_entry.dims,
        }
    ), 201


# ---------------------------------------------------------------------------
# Operation dispatcher
# ---------------------------------------------------------------------------


def _dispatch(operation: str, ds, params: dict):
    if operation == "filter":
        from armoor.viewer.bridge.filters import apply_combined_filters

        return apply_combined_filters(ds, params)

    elif operation == "interp_time":
        from armoor.viewer.bridge.interp import process_time_interpolation

        tfreq = params.get("tfreq")
        if not tfreq:
            raise ValueError("interp_time requires params.tfreq")
        return process_time_interpolation(ds, ("tfreq", tfreq))

    elif operation == "interp_horizontal":
        from armoor.viewer.bridge.interp import process_horizontal_interpolation

        return process_horizontal_interpolation(ds, params)

    elif operation == "interp_vertical":
        from armoor.viewer.bridge.interp import process_vertical_interpolation

        method = params.get("method", "linear")
        args = params.get("args", [])
        return process_vertical_interpolation(ds, (method, args))

    elif operation == "range_time":
        from armoor.viewer.bridge.ranges import process_time_range

        tfreq = params.get("tfreq")
        if not tfreq:
            raise ValueError("range_time requires params.tfreq")
        return process_time_range(ds, tfreq)

    elif operation == "range_vertical":
        from armoor.viewer.bridge.ranges import process_vertical_range

        vname = params.get("vname", "z")
        vmin = params.get("vmin", 0)
        vmax = params.get("vmax", 0)
        return process_vertical_range(ds, vname, [vmin, vmax])

    else:
        raise ValueError(f"Unknown operation: '{operation}'")
