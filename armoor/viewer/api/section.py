"""Vertical section extraction endpoint.

GET /api/datasets/<id>/section
    ?variable=<v>&lon1=<>&lat1=<>&lon2=<>&lat2=<>&time_idx=<>&n_points=<>
    &depth_var=<optional: name of the 3-D depth variable>

Extracts *variable* along the straight path (lon1,lat1)→(lon2,lat2)
for every depth level at the selected time step, using nearest-neighbor
lookup (works for both regular and curvilinear grids).

Depths on the Y-axis are resolved in this order:
  1. The variable named by *depth_var* (if supplied explicitly).
  2. Any data variable in the dataset whose dimensions include the Z dim
     AND at least one horizontal (y/x) dim – i.e. a 3-D depth field such
     as CROCO's z_rho or NEMO's gdept_0.  Its values are sampled along the
     section path and averaged horizontally for each Z level.
  3. A 1-D depth *coordinate* attached to the Z dimension (e.g. deptht).
  4. Fall-back: integer Z-level indices [0, 1, 2, …].

Returns a JSON object ready for canvas rendering.
"""

import logging

import numpy as np
from flask import Blueprint, jsonify, request

from armoor.viewer.api._spatial import get_index
from armoor.viewer.store import store

bp = Blueprint("section", __name__, url_prefix="/api/datasets")
logger = logging.getLogger(__name__)

R_EARTH_KM = 6371.0

# Dimension names recognised as horizontal spatial dims
_SPATIAL_DIMS = frozenset(
    {
        "x",
        "xi_rho",
        "xi_u",
        "xi_v",
        "xi_psi",
        "y",
        "eta_rho",
        "eta_u",
        "eta_v",
        "eta_psi",
        "lon",
        "longitude",
        "nav_lon",
        "lat",
        "latitude",
        "nav_lat",
    }
)

# Well-known names for 3-D depth variables (checked in priority order)
_DEPTH_VAR_NAMES = [
    "z_rho",
    "z_w",
    "z_u",
    "z_v",  # CROCO / ROMS sigma levels
    "gdept_0",
    "gdepw_0",
    "gdept_rho",  # NEMO
    "depth_rho",
    "depth_w",
]


@bp.route("/<dataset_id>/section", methods=["GET"])
def get_section(dataset_id: str):
    """Extract a vertical section along a straight path.

    Query parameters
    ----------------
    variable : str
        Name of the data variable to sample.
    lon1, lat1 : float
        Start point coordinates in degrees.
    lon2, lat2 : float
        End point coordinates in degrees.
    time_idx : int, optional
        Time step index (default 0).
    n_points : int, optional
        Number of points along the section (default 100, clamped to 10–500).
    depth_var : str, optional
        Explicit name of the 3-D depth variable.
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

    # Accept either lons/lats (multi-waypoint) or legacy lon1/lat1/lon2/lat2.
    lons_raw = args.get("lons")
    lats_raw = args.get("lats")
    if lons_raw and lats_raw:
        try:
            waypoint_lons = [float(x) for x in lons_raw.split(",")]
            waypoint_lats = [float(x) for x in lats_raw.split(",")]
        except ValueError:
            return jsonify({"error": "Invalid lons/lats values"}), 400
        if len(waypoint_lons) < 2 or len(waypoint_lons) != len(waypoint_lats):
            return jsonify({"error": "lons and lats must have the same length ≥ 2"}), 400
    else:
        try:
            waypoint_lons = [float(args.get("lon1")), float(args.get("lon2"))]
            waypoint_lats = [float(args.get("lat1")), float(args.get("lat2"))]
        except (TypeError, ValueError):
            return jsonify({"error": "Missing or invalid section endpoint coordinates"}), 400

    time_idx = int(args.get("time_idx", 0))
    n_points = max(10, min(int(args.get("n_points", 100)), 500))
    depth_var = args.get("depth_var")  # optional explicit override

    try:
        result = _extract_section(
            entry, variable, waypoint_lons, waypoint_lats, time_idx, n_points, depth_var
        )
    except Exception as exc:
        logger.exception("Section extraction failed")
        return jsonify({"error": str(exc)}), 500

    return jsonify(result)


# ---------------------------------------------------------------------------
# Internals
# ---------------------------------------------------------------------------


def _extract_section(
    entry, variable, waypoint_lons, waypoint_lats, time_idx, n_points, depth_var_name=None
) -> dict:
    ds = entry.ds
    da = ds[variable]

    time_dim = _find_dim(da, ("time",))
    depth_dim = _find_dim(da, ("z", "s_rho", "s_w", "depth", "deptht", "level", "nz", "nz1"))

    # Cached KD-tree (shared with point/timeseries endpoints)
    tree, lat2d, lon2d, _, _ = get_index(entry)
    grid_shape = lat2d.shape

    # Build multi-segment path, allocating points proportionally to segment length.
    seg_dists = [
        _haversine_km(
            waypoint_lons[i], waypoint_lats[i], waypoint_lons[i + 1], waypoint_lats[i + 1]
        )
        for i in range(len(waypoint_lons) - 1)
    ]
    total_dist = sum(seg_dists) or 1.0

    path_lon_list, path_lat_list, dist_list = [], [], []
    cum_dist = 0.0
    for i, (lo1, la1, lo2, la2, seg_d) in enumerate(
        zip(waypoint_lons, waypoint_lats, waypoint_lons[1:], waypoint_lats[1:], seg_dists)
    ):
        seg_n = max(2, round(n_points * seg_d / total_dist))
        seg_lons = np.linspace(lo1, lo2, seg_n)
        seg_lats = np.linspace(la1, la2, seg_n)
        start = 0 if i == 0 else 1  # avoid duplicate junction point
        for k in range(start, seg_n):
            path_lon_list.append(seg_lons[k])
            path_lat_list.append(seg_lats[k])
            dist_list.append(cum_dist + _haversine_km(lo1, la1, seg_lons[k], seg_lats[k]))
        cum_dist += seg_d

    path_lons = np.array(path_lon_list)
    path_lats = np.array(path_lat_list)
    distances = dist_list

    # Query nearest grid indices for all path points at once
    query_pts = np.column_stack([path_lats, path_lons])
    _, flat_idx = tree.query(query_pts)
    j_arr, i_arr = np.unravel_index(flat_idx, grid_shape)

    n_depths = ds.sizes.get(depth_dim, 1) if depth_dim else 1

    # ── Resolve depth values (2-D: depths[d][p]) ────────────────────────────
    depths = _resolve_depths(
        ds,
        depth_dim,
        j_arr,
        i_arr,
        n_depths,
        time_idx,
        entry.depth_values,
        depth_var_name,
        n_points,
    )

    # ── Extract variable along section ──────────────────────────────────────
    # Load all depth levels in one shot, then index spatially
    isel_t = {time_dim: time_idx} if time_dim else {}
    slab = da.isel(**isel_t).squeeze().values.astype(float)  # (n_depths, ny, nx) or (ny, nx)
    if slab.ndim == 2:
        slab = slab[np.newaxis]  # treat as single depth level
    values = [
        [None if np.isnan(v) else float(v) for v in slab[d, j_arr, i_arr]] for d in range(n_depths)
    ]

    # Colour scale from section data
    flat = [v for row in values for v in row if v is not None]
    vmin = float(np.nanmin(flat)) if flat else 0.0
    vmax = float(np.nanmax(flat)) if flat else 1.0
    if vmin == vmax:
        vmax = vmin + 1.0

    return {
        "variable": variable,
        "units": da.attrs.get("units", ""),
        "values": values,  # n_depths × n_points
        "depths": depths,  # n_depths × n_points floats (metres)
        "distances": distances,  # km from first point
        "lons": path_lons.tolist(),
        "lats": path_lats.tolist(),
        "vmin": vmin,
        "vmax": vmax,
        "time_idx": time_idx,
    }


# ---------------------------------------------------------------------------
# Depth resolution
# ---------------------------------------------------------------------------


def _resolve_depths(
    ds, depth_dim, j_arr, i_arr, n_depths, time_idx, coord_depths, depth_var_name, n_points
):
    """Return a 2-D array depths[d][p] of depth values (floats, metres).

    Each row d gives the physical depth at each section point p for that
    z-level — exactly as matplotlib's pcolormesh expects the Y coordinate.

    Priority:
      1. Explicit depth_var_name supplied by the caller.
      2. Auto-detected 3-D/4-D depth variable (has depth_dim + spatial dims).
      3. 1-D depth coordinate already extracted at load time (coord_depths).
      4. Integer indices [0 … n_depths-1].
    """
    # 1 & 2 – try to sample a depth variable along the section
    var_name = depth_var_name or _find_depth_data_var(ds, depth_dim)
    if var_name:
        result = _sample_depth_var(ds, var_name, depth_dim, j_arr, i_arr, n_depths, time_idx)
        if result is not None:
            logger.debug("Depth from variable '%s'", var_name)
            return result

    # 3 – 1-D coordinate (e.g. NEMO's deptht): broadcast to 2-D
    if coord_depths:
        logger.debug("Depth from coordinate (%d values)", len(coord_depths))
        return [[float(coord_depths[d])] * n_points for d in range(n_depths)]

    # 4 – fall back to indices: broadcast to 2-D
    logger.debug("Depth: falling back to Z-level indices")
    return [[float(d)] * n_points for d in range(n_depths)]


def _find_depth_data_var(ds, depth_dim):
    """Auto-detect a data variable that encodes physical depth at each z-level."""
    if depth_dim is None:
        return None

    # Priority 1: well-known names in data_vars
    for name in _DEPTH_VAR_NAMES:
        if name in ds.data_vars and depth_dim in ds[name].dims:
            return name

    # Priority 2: well-known names in coords (e.g. CROCO z_rho stored as coord)
    for name in _DEPTH_VAR_NAMES:
        if name in ds.coords and depth_dim in ds[name].dims:
            return name

    # Priority 3: generic scan — only accept variables whose units or name clearly
    # indicate a depth/altitude field.  This avoids accidentally returning the
    # variable being visualised (e.g. temperature in °C or salinity in psu).
    _DEPTH_UNITS = {"m", "meter", "meters", "metre", "metres"}
    for collection in (ds.data_vars, ds.coords):
        for name, da in collection.items():
            if depth_dim not in da.dims:
                continue
            if not any(d in _SPATIAL_DIMS for d in da.dims):
                continue
            units = da.attrs.get("units", "").lower().strip()
            lname = (
                da.attrs.get("long_name", "") + " " + da.attrs.get("standard_name", "")
            ).lower()
            name_l = name.lower()
            if (
                units in _DEPTH_UNITS
                or "depth" in name_l
                or "depth" in lname
                or "altitude" in lname
                or "elevation" in lname
            ):
                return name

    return None


def _sample_depth_var(ds, var_name, depth_dim, j_arr, i_arr, n_depths, time_idx):
    """Sample a 4-D depth variable (time, z, y, x) along the section.

    Mirrors exactly what _extract_section does for the main variable:
      1. isel(time=time_idx) to drop the time dimension.
      2. For each z-level: isel(depth_dim=d) → 2-D (y, x) array.
      3. Sample at the section points (j_arr, i_arr).

    Returns a 2-D list depths[d][p], or None on any failure.
    """
    if var_name not in ds.data_vars and var_name not in ds.coords:
        return None

    da = ds[var_name]

    if depth_dim not in da.dims:
        return None

    # Strip time (same pattern as the main variable)
    time_dim = _find_dim(da, ("time",))
    if time_dim:
        da = da.isel({time_dim: time_idx})

    # Load all depth levels at once
    try:
        slab = da.values.astype(float)  # (n_depths, ny, nx)
    except Exception:
        return None

    if slab.ndim != 3 or slab.shape[0] != n_depths:
        return None

    depths_2d = []
    for d in range(n_depths):
        row = slab[d, j_arr, i_arr]
        row = np.where(np.isnan(row), float(d), row)
        depths_2d.append(row.tolist())

    return depths_2d


def _haversine_km(lon1, lat1, lon2, lat2) -> float:
    phi1, phi2 = np.radians(lat1), np.radians(lat2)
    dphi = np.radians(lat2 - lat1)
    dlam = np.radians(lon2 - lon1)
    a = np.sin(dphi / 2) ** 2 + np.cos(phi1) * np.cos(phi2) * np.sin(dlam / 2) ** 2
    return float(2 * R_EARTH_KM * np.arcsin(np.sqrt(a)))


def _find_dim(da, candidates):
    for c in candidates:
        if c in da.dims:
            return c
    return None
