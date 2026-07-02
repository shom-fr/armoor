"""armoor-viewer – interactive web viewer for armoor/xarray datasets.

Quick start::

    armoor-viewer                          # open empty viewer on port 5000
    armoor-viewer --port 8080              # different port

Environment variables
---------------------
ARMOOR_VIEWER_DATA
    Directory for the Blue Marble image and tile cache.
    Defaults to ``~/.local/share/armoor-viewer``.
ARMOOR_VIEWER_SECRET_KEY
    Flask secret key for session security.
"""

from armoor.viewer.app import create_app, serve  # noqa: F401
