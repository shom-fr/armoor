"""Flask application factory for armoor-viewer."""

import argparse
import logging
import os

from flask import Flask
from flask_cors import CORS

from armoor.viewer import config as cfg

logger = logging.getLogger(__name__)


def create_app(test_config=None, render_mode: str | None = None) -> Flask:
    """Create and configure the Flask application.

    Parameters
    ----------
    test_config : dict, optional
        Config overrides (used by the test suite).
    render_mode : str, optional
        Default frontend render mode (``auto`` / ``2d`` / ``3d``).  Falls
        back to ``cfg.RENDER_MODE`` (env var ``ARMOOR_VIEWER_RENDER_MODE``,
        default ``auto``) if not given.

    Returns
    -------
    Flask
        Configured Flask application instance.
    """
    app = Flask(
        __name__,
        static_folder=os.path.abspath(cfg.STATIC_FOLDER),
        static_url_path="",
    )
    app.config["SECRET_KEY"] = cfg.SECRET_KEY
    app.config["RENDER_MODE"] = render_mode or cfg.RENDER_MODE

    if test_config is not None:
        app.config.update(test_config)

    CORS(app, resources={r"/api/*": {"origins": "*"}})

    from armoor.viewer.api.basemap    import bp as basemap_bp
    from armoor.viewer.api.colormap   import bp as colormap_bp
    from armoor.viewer.api.config     import bp as config_bp
    from armoor.viewer.api.datasets   import bp as datasets_bp
    from armoor.viewer.api.grid       import bp as grid_bp
    from armoor.viewer.api.metadata   import bp as metadata_bp
    from armoor.viewer.api.operations import bp as operations_bp
    from armoor.viewer.api.point      import bp as point_bp
    from armoor.viewer.api.section    import bp as section_bp
    from armoor.viewer.api.tiles      import bp as tiles_bp
    from armoor.viewer.api.timeseries import bp as timeseries_bp
    from armoor.viewer.api.wind       import bp as wind_bp

    for blueprint in (
        basemap_bp, config_bp, datasets_bp, grid_bp, metadata_bp, tiles_bp,
        wind_bp, operations_bp, colormap_bp, timeseries_bp, section_bp,
        point_bp,
    ):
        app.register_blueprint(blueprint)

    @app.route("/")
    def index():
        """Serve the viewer's single-page-app entry point."""
        return app.send_static_file("index.html")

    return app


def serve(
    host: str = "127.0.0.1",
    port: int = 5000,
    debug: bool = False,
    render_mode: str | None = None,
) -> None:
    """Start the armoor-viewer development server.

    Parameters
    ----------
    host : str
        Bind address (default ``127.0.0.1``).
    port : int
        TCP port (default ``5000``).
    debug : bool
        Enable Flask debug mode.
    render_mode : str, optional
        Default frontend render mode (``auto`` / ``2d`` / ``3d``).
    """
    app = create_app(render_mode=render_mode)
    logger.info("armoor-viewer listening on http://%s:%d", host, port)
    app.run(host=host, port=port, debug=debug, threaded=True)


def setup_basemap(src: str | None = None) -> None:
    """Copy the Blue Marble image into the active conda environment.

    Parameters
    ----------
    src : str, optional
        Path to the source JPEG.  If omitted, a list of known locations is
        searched (armoor-viewer source tree, user data dir).
    """
    import shutil

    source = src
    if source is None or not os.path.exists(source):
        raise FileNotFoundError(
            "Blue Marble image not found. "
            "Provide the path with --src /path/to/earth-blue-marble.jpg"
        )

    import sys
    conda_prefix = os.environ.get("CONDA_PREFIX") or sys.prefix
    if not conda_prefix or conda_prefix == "/usr":
        raise RuntimeError(
            "Could not determine conda/Python prefix. "
            "Activate your conda environment or set CONDA_PREFIX."
        )

    dest_dir = os.path.join(conda_prefix, "share", "armoor-viewer", "img")
    os.makedirs(dest_dir, exist_ok=True)
    dest = os.path.join(dest_dir, "earth-blue-marble.jpg")
    shutil.copy2(source, dest)
    print(f"Installed: {dest}")


def main() -> None:
    """CLI entry point for ``armoor-viewer``."""
    parser = argparse.ArgumentParser(
        prog="armoor-viewer",
        description="Interactive web viewer for armoor / xarray ocean datasets.",
    )
    parser.add_argument("--host",  default="127.0.0.1", help="Bind address (default 127.0.0.1)")
    parser.add_argument("--port",  default=5000, type=int, help="TCP port (default 5000)")
    parser.add_argument("--debug", action="store_true", help="Enable Flask debug mode")
    parser.add_argument(
        "--render-mode", choices=["auto", "2d", "3d"], default=None,
        help="Frontend render mode: 'auto' (client-side WebGL2 detection, "
             "default), '2d' (Leaflet planisphere, no GPU required), "
             "'3d' (iTowns globe, requires WebGL2). Overrides "
             "$ARMOOR_VIEWER_RENDER_MODE.",
    )
    parser.add_argument(
        "--setup-basemap", action="store_true",
        help="Install the Blue Marble basemap image into the active conda env and exit.",
    )
    parser.add_argument(
        "--src", default=None,
        help="Source path for --setup-basemap (auto-detected if omitted).",
    )
    args = parser.parse_args()

    if args.setup_basemap:
        setup_basemap(args.src)
        return

    serve(host=args.host, port=args.port, debug=args.debug, render_mode=args.render_mode)


if __name__ == "__main__":
    main()
