"""armoor-viewer configuration."""
import os

# Static assets bundled with the package
STATIC_FOLDER = os.path.join(os.path.dirname(__file__), "static")

# User data directory (writable: tile cache)
_DATA_DIR = os.environ.get(
    "ARMOOR_VIEWER_DATA",
    os.path.join(os.path.expanduser("~"), ".local", "share", "armoor-viewer"),
)

CACHE_DIR = os.path.join(_DATA_DIR, "tiles", "geo")

# Blue Marble image – searched in order:
#   1. $ARMOOR_VIEWER_DATA/img/  (explicit override or user install)
#   2. ~/.local/share/armoor-viewer/img/  (default user install)
#   3. $CONDA_PREFIX/share/armoor-viewer/img/  (conda env data)
#   4. armoor/viewer/data/earth.jpg  (bundled 2 K fallback, always available)
_BUNDLED_IMG = os.path.join(os.path.dirname(__file__), "data", "earth.jpg")

def _find_img() -> str:
    import sys
    candidates = [
        os.path.join(_DATA_DIR, "img", "earth-blue-marble.jpg"),
    ]
    prefix = os.environ.get("CONDA_PREFIX") or sys.prefix
    if prefix and prefix != "/usr":
        candidates.append(
            os.path.join(prefix, "share", "armoor-viewer", "img",
                         "earth-blue-marble.jpg")
        )
    candidates.append(_BUNDLED_IMG)
    for path in candidates:
        if os.path.exists(path):
            return path
    return candidates[0]  # default write target even if absent

IMG_PATH = _find_img()

TILE_WIDTH  = 1024
TILE_HEIGHT = 512
WIND_NX     = 256
WIND_NY     = 128

SUPPORTED_FORMATS = ["zarr", "armoor", "cmems_model", "hycom", "croco", "croco_xios", "woa18"]

SECRET_KEY = os.environ.get("ARMOOR_VIEWER_SECRET_KEY", "armoor-viewer-dev-key-change-in-prod")

# Frontend render mode: "auto" (client-side WebGL2 detection), "2d" (Leaflet
# planisphere, no WebGL required) or "3d" (iTowns globe, requires WebGL2).
# Useful on headless / no-GPU compute nodes to force "2d" for all users.
RENDER_MODE = os.environ.get("ARMOOR_VIEWER_RENDER_MODE", "auto")
