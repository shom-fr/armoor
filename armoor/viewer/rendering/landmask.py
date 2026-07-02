"""Land mask generation using Natural Earth data via cartopy + shapely 2.

The land geometry is loaded once and cached.  Per-tile masks are also cached
by (west, east, south, north, nx, ny) so repeated requests for the same
viewport are free.
"""

import functools
import logging

import numpy as np

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Land geometry – loaded once at import time (lazy)
# ---------------------------------------------------------------------------

_land_geom = None  # shapely Geometry (MultiPolygon)


def _get_land_geom():
    """Return the cached unified Natural Earth land geometry."""
    global _land_geom
    if _land_geom is None:
        _land_geom = _load_land_geom()
    return _land_geom


def _load_land_geom():
    logger.info("Loading Natural Earth land polygons…")
    try:
        import cartopy.feature as cfeature
        from shapely.ops import unary_union

        # 110 m resolution is fast to load and sufficient for masking
        geometries = list(
            cfeature.NaturalEarthFeature(
                "physical",
                "land",
                "110m",
            ).geometries()
        )
        geom = unary_union(geometries)
        logger.info("Land geometry loaded (%d sub-geometries)", len(geometries))
        return geom
    except Exception as exc:
        logger.error("Could not load land geometry: %s", exc)
        raise


# ---------------------------------------------------------------------------
# Per-tile mask cache
# ---------------------------------------------------------------------------


# Key: (west, east, south, north, nx, ny) all rounded to 4 dp
@functools.lru_cache(maxsize=256)
def _cached_land_mask(
    west: float,
    east: float,
    south: float,
    north: float,
    nx: int,
    ny: int,
) -> np.ndarray:
    """Compute and cache a boolean land mask on a (ny × nx) regular grid.

    Returns
    -------
    np.ndarray, shape (ny, nx), dtype bool
        ``True`` where the grid point is on land.
    """
    import shapely

    land = _get_land_geom()

    lons = np.linspace(west, east, nx)
    lats = np.linspace(south, north, ny)
    lon_g, lat_g = np.meshgrid(lons, lats)

    # Shapely 2.x vectorised point-in-polygon
    pts = shapely.points(lon_g.ravel(), lat_g.ravel())
    mask = shapely.within(pts, land).reshape(ny, nx)
    return mask


def make_land_mask(
    west: float,
    east: float,
    south: float,
    north: float,
    nx: int,
    ny: int,
) -> np.ndarray:
    """Public helper – rounds coordinates before cache lookup.

    Parameters
    ----------
    west, east, south, north:
        Bounding box in degrees.
    nx, ny:
        Grid size (columns × rows).

    Returns
    -------
    np.ndarray, shape (ny, nx), dtype bool
        ``True`` on land.
    """
    return _cached_land_mask(
        round(west, 4),
        round(east, 4),
        round(south, 4),
        round(north, 4),
        int(nx),
        int(ny),
    )
