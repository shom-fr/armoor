"""Serve the Blue Marble base map as local tiles (fully offline).

Tile pipeline:
  1. Check disk cache  <ARMOOR_VIEWER_DATA>/tiles/geo/{z}/{x}/{y}.jpg  → serve immediately.
  2. Compute tile by cropping the Blue Marble image, save to cache.

To get better zoom quality, place a high-res Blue Marble image at the path
given by ``cfg.IMG_PATH`` (default: ``~/.local/share/armoor-viewer/img/earth-blue-marble.jpg``).
Recommended: NASA Blue Marble 21600×10800 — that image gives sharp tiles up
to zoom 6.  You can pre-warm the tile cache with::

    python tools/generate_tiles.py

If the image file is missing, all endpoints return a solid dark tile
(RGB 10,10,24) instead of a 500 error.
"""

import io
import os

from flask import Blueprint, make_response, request
from PIL import Image

Image.MAX_IMAGE_PIXELS = None   # 21600×10800 exceeds PIL's default bomb check

from armoor.viewer import config as cfg

bp = Blueprint("basemap", __name__)

_IMG_PATH  = cfg.IMG_PATH
_CACHE_DIR = cfg.CACHE_DIR

_img_cache: Image.Image | None = None


def _globe_image() -> Image.Image | None:
    """Return cached Blue Marble image, or None if file is missing."""
    global _img_cache
    if _img_cache is None:
        if not os.path.exists(_IMG_PATH):
            return None
        _img_cache = Image.open(_IMG_PATH).convert("RGB")
    return _img_cache


def _dark_tile(width: int = 256, height: int = 256) -> bytes:
    """Return a solid dark JPEG tile (fallback when image is missing).

    Parameters
    ----------
    width : int
        Tile width in pixels.
    height : int
        Tile height in pixels.

    Returns
    -------
    bytes
        JPEG byte string of the dark tile.
    """
    out = Image.new("RGB", (width, height), (10, 10, 24))
    buf = io.BytesIO()
    out.save(buf, format="JPEG", quality=85)
    return buf.getvalue()


def _crop_tile(west: float, south: float, east: float, north: float,
               width: int = 256, height: int = 256) -> bytes:
    """Crop a geographic region from the Blue Marble image and return JPEG bytes.

    Falls back to a solid dark tile if the image file is missing.

    Parameters
    ----------
    west, south, east, north : float
        Geographic bounds in degrees.
    width, height : int
        Output tile size in pixels.

    Returns
    -------
    bytes
        JPEG byte string.
    """
    img = _globe_image()
    if img is None:
        return _dark_tile(width, height)

    W, H = img.size
    x0 = max(0, round((west  + 180) / 360 * W))
    y0 = max(0, round((90   - north) / 180 * H))
    x1 = min(W, round((east  + 180) / 360 * W))
    y1 = min(H, round((90   - south) / 180 * H))
    if x1 <= x0 or y1 <= y0:
        out = Image.new("RGB", (width, height), (10, 10, 24))
    else:
        out = img.crop((x0, y0, x1, y1)).resize((width, height), Image.LANCZOS)
    buf = io.BytesIO()
    out.save(buf, format="JPEG", quality=85)
    return buf.getvalue()


def _cache_path(z: int, x: int, y: int) -> str:
    return os.path.join(_CACHE_DIR, str(z), str(x), f"{y}.jpg")


def _cache_get(z: int, x: int, y: int) -> bytes | None:
    p = _cache_path(z, x, y)
    if os.path.exists(p):
        with open(p, "rb") as f:
            return f.read()
    return None


def _cache_put(z: int, x: int, y: int, data: bytes) -> None:
    p = _cache_path(z, x, y)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "wb") as f:
        f.write(data)


# ── EPSG:4326 geographic tile endpoint ───────────────────────────────────────
# Geographic tile scheme: 2^(z+1) cols × 2^z rows.

@bp.route("/basemap/geo/<int:z>/<int:x>/<int:y>.png")
def tile_geo(z: int, x: int, y: int):
    """Serve an EPSG:4326 basemap tile.

    Parameters
    ----------
    z : int
        Zoom level (0–6).
    x : int
        Tile column.
    y : int
        Tile row.
    """
    if not (0 <= z <= 8):
        return "Invalid zoom", 400
    nx = 2 ** (z + 1)
    ny = 2 ** z
    x  = x % nx
    if not (0 <= y < ny):
        return "Invalid y", 400
    data = _cache_get(z, x, y)
    if data is None:
        west  =  x      / nx * 360 - 180
        east  = (x + 1) / nx * 360 - 180
        north = 90 -  y      / ny * 180
        south = 90 - (y + 1) / ny * 180
        data = _crop_tile(west, south, east, north)
        _cache_put(z, x, y, data)
    resp = make_response(data)
    resp.headers["Content-Type"] = "image/jpeg"
    resp.headers["Cache-Control"] = "public, max-age=86400"
    return resp


# ── WMS endpoint (kept for compatibility) ─────────────────────────────────────

@bp.route("/basemap/wms")
def wms():
    """Serve a WMS-compatible basemap tile.

    Query parameters
    ----------------
    BBOX : str
        Bounding box as ``minLon,minLat,maxLon,maxLat`` (or lat-first for WMS 1.3).
    WIDTH : int
        Output width in pixels.
    HEIGHT : int
        Output height in pixels.
    CRS / SRS : str
        Coordinate reference system.
    VERSION : str
        WMS version (affects axis order for EPSG:4326).
    """
    bbox_str = request.args.get("BBOX") or request.args.get("bbox", "-90,-180,90,180")
    width    = int(request.args.get("WIDTH")  or request.args.get("width",  256))
    height   = int(request.args.get("HEIGHT") or request.args.get("height", 256))
    crs      = (request.args.get("CRS") or request.args.get("SRS") or "EPSG:4326").upper()
    version  = request.args.get("VERSION", "1.3.0")
    vals     = list(map(float, bbox_str.split(",")))
    if "4326" in crs and version.startswith("1.3"):
        south, west, north, east = vals
    else:
        west, south, east, north = vals
    data = _crop_tile(west, south, east, north, width, height)
    resp = make_response(data)
    resp.headers["Content-Type"] = "image/jpeg"
    resp.headers["Cache-Control"] = "public, max-age=3600"
    return resp


# ── Old XYZ endpoint (kept for compatibility) ─────────────────────────────────

@bp.route("/basemap/<int:z>/<int:x>/<int:y>.png")
def tile(z: int, x: int, y: int):
    """Serve an XYZ (Web Mercator) basemap tile.

    Parameters
    ----------
    z : int
        Zoom level (0–8).
    x : int
        Tile column.
    y : int
        Tile row.
    """
    if not (0 <= z <= 8):
        return "Invalid zoom", 400
    n = 2**z
    x = x % n
    if not (0 <= y < n):
        return "Invalid y", 400
    west  =  x      / n * 360 - 180
    east  = (x + 1) / n * 360 - 180
    north = 90 -  y      / n * 180
    south = 90 - (y + 1) / n * 180
    data = _crop_tile(west, south, east, north)
    resp = make_response(data)
    resp.headers["Content-Type"] = "image/jpeg"
    resp.headers["Cache-Control"] = "public, max-age=86400"
    return resp
