What's new
##########

Develop
=======

New features
------------

- Added ``armoor-comp-clim``: new comparison tool for 3D model outputs against
  an observed hydrological climatology (WOA18 or Bobyclim) for ``ptemp`` and
  ``sal``.  Colocation uses a new monthly grouping method
  (``TimeColocation.tmonth``) that averages model outputs by calendar month
  before comparing them to the climatology month by month.  Outputs: ``maps``
  and ``timeseries``.

- Added ``armoor.viewer`` subpackage: an interactive web viewer for armoor/xarray
  ocean datasets.  It provides a Flask application
  with 10 REST API blueprints (datasets, tiles, wind, section, timeseries, …),
  an iTowns 3D globe with an offline Blue Marble basemap, and a particle
  animation system for current visualization.  Run with ``armoor-viewer`` after
  installing ``flask``, ``flask-cors``, and ``pillow``.

- ``armoor-viewer`` now supports a 2D render mode (Leaflet planisphere) as an
  alternative to the 3D iTowns globe, for machines without WebGL2 support
  (e.g. headless HPC login nodes with software-only OpenGL).  The mode is
  auto-detected client-side by default, can be forced with
  ``armoor-viewer --render-mode {auto,2d,3d}`` or
  ``$ARMOOR_VIEWER_RENDER_MODE``, and can be switched at runtime from the
  sidebar toggle.

Breaking changes
----------------

- The dependency on ``xoa.cf`` has been replaced by ``xoa.meta``.
  This enables installation via conda-forge. Users relying on internal
  ``xoa.cf`` APIs should migrate to ``xoa.meta``.

Deprecations
------------

Bug fixes
---------

- Fixed a decoding error (``KeyError: 'ptemp'``) in satellite SST and
  other dataset loaders caused by ``xoa.meta`` selecting the wrong
  MetaSpecs during inference. Specs are now applied explicitly with
  ``cfspecs.decode(ds)`` instead of relying on the ``set_meta_specs``
  context manager.

- Fixed ``XoaCoordsError: Coordinate type not found`` when reordering
  dimensions after a curvilinear-to-rectilinear grid transform. Added
  ``axis`` attributes to all coordinate entries in the armoor CF
  configuration files so that ``xoa.meta`` can correctly resolve
  dimension types (X, Y, Z, T).

Documentation
-------------
