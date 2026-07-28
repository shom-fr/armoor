What's new
##########

Develop
=======

New features
------------

- Added a ``mapseries`` otype to ``armoor-data``: renders one map per native
  time step (instead of a single aggregated map), with the color scale fixed
  once over the whole series, current/wind vectors overlaid via quiver or
  barbs, and an optional climatology min/max reference row. New ``[outputs]``
  options: ``nstd``, ``vector_style``, ``vector_scale``, ``rarification``,
  ``barbs_length``, ``barbs_linewidth``, ``quiver_scale``, ``clim`` and
  ``cbar_group``. ``armoor-data`` also now accepts ``woa18``, ``bobyclim``,
  ``cmems_sst_l4``, ``cmems_sst_l3``, ``cersat_sst_l3`` and ``arpege_insta``
  input formats.

- Added a ``vsections`` otype to ``armoor-data``: extracts and plots vertical
  sections (distance vs depth) along a broken-line transect, using the same
  geodesic, multi-segment interpolation as ``armoor-interp-horizontal
  --section``. Metazones now accept a ``[[section]]`` subsection, mutually
  exclusive with ``cloud``, with a shared ``dx`` and one or more named
  ``[[[transect_name]]]`` subsections (each with its own ``coords``) to
  extract several sections from the same metazone.

- Re-added ``armoor-tick`` (dropped during the ``cli/main.py`` refactor):
  ``armoor-tick-create``/``search``/``description``/``authentication``/
  ``authentication-info`` manage GitLab issues used to report and track
  anomalies, ported onto the current ``get_parser_X``/``main_X`` CLI pattern.

Breaking changes
----------------

Deprecations
------------

Bug fixes
---------

- Fixed ``armoor-data`` output dispatch using the user-chosen ``[outputs]``
  section name instead of ``otype`` to select the plot method, which made
  plotting fail (e.g. ``Data plot 'vsection' not found``) unless a section
  happened to be named exactly like its ``otype``.

- Fixed ``update_auth_cfg`` (``armoor-tick-authentication``) writing empty
  nested sections (e.g. ``proxies``) as a bare string, which made the
  resulting ``auth.cfg`` fail re-validation on the very next run.

Documentation
-------------

- Added the ``nbsphinx`` dependency to the ``doc`` extra: ``doc/conf.py`` has
  used the extension for a while, but ``make html`` failed with
  ``Could not import extension nbsphinx`` on any environment that only
  installs ``.[doc]`` (e.g. CI).

2026.7.0
========

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

- Added mixed layer depth (MLD) as a computable ocean variable.

- Added horizontal coarsening support.

- Added the ``sloop`` input format, with 4D depth broadcast.

- Added a ``vminmax`` color-scale override for ``armoor-comp`` and
  ``armoor-data`` map/section outputs.

- Integrated eddy-detection decoding and diagnostics: ``eddy_pet``,
  ``eddy_sacso`` and ``eddy_shoot`` decoders, divergence/Okubo-Weiss/
  vorticity oceanvars, and a ``stats.pdf`` / ``diags.eddies`` module.

- Vertical interpolation (``vinterp``) now supports isopycnal levels on
  potential density (``pdens``), in addition to ``depth``/``dens``.

- ``open_decode_croco`` now supports CROCO output with an embedded grid
  (no separate grid file required).

Breaking changes
----------------

- The dependency on ``xoa.cf`` has been replaced by ``xoa.meta``.
  This enables installation via conda-forge. Users relying on internal
  ``xoa.cf`` APIs should migrate to ``xoa.meta``.

- ``metazones.cfg``'s ``vlevel``/``vrange``/``vfreq``/``bathy``/``trange_seq``
  are no longer flat strings parsed positionally; they are now named
  configobj subsections (e.g. ``[[vlevel]] vname=... levels=...``,
  ``[[vrange]] vref=... vname=... bins_min=... bins_max=...``). Existing
  ``metazones.cfg`` files must be migrated to the new subsection syntax.

Deprecations
------------

Refactoring
-----------

- Introduced a ``Comparison`` class hierarchy backing ``armoor-comp-*``,
  replacing the previous ad hoc per-comparison logic.

- Introduced a ``DataType`` hierarchy for ``armoor-data`` sources, with
  ``OutputProcessor`` and the plotter/climatology dispatch now routed
  through it (``DataType.outputs_params``).

- Generalized ``StagedDataset`` into a pipeline-context object, now
  carrying ``vlevel``/``vrange``/``trange``/``time`` alongside the data.

- ``open_decode``'s per-format ``elif`` chain was replaced by a
  ``Decoder`` registry (one class per input format, self-registering).

- Extracted ``output_suffix`` and exposed ``time``/``trange``/``vlevel``/
  ``vrange`` on ``ds.range``.

- Extracted a shared dispatch idiom and metazone-parameter validation
  used across ``armoor-comp``/``armoor-data``.

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

- Fixed non-deterministic ``XoaMetaError: Search failed`` errors: per-format
  CF configs (e.g. ``cf_hycom.cfg``) were registered without inheriting the
  default xoa meta specs, so an incomplete spec could be picked for
  unrelated datasets depending on filesystem glob order.

- Fixed ``validate_metazone_params`` mutating its input ``metazones`` dict
  in place, which corrupted later reads of the same dict in
  ``OutputProcessor`` and crashed with ``TypeError: argument of type
  'NoneType' is not iterable`` for any metazone without ``vlevel``/
  ``vfreq`` configured.

- Fixed three colocation/stats bugs surfaced by running comparisons
  against real (rather than synthetic) sample data: a stray ``npts1``
  dimension leaking from radius colocation for scalar references, a
  leftover singleton ``z`` dimension after single-level vertical
  colocation breaking the dims-signature match, and ``StatsComp``'s
  time-mean fallback silently dropping a drifter's time-varying lat/lon
  instead of averaging them.

- Fixed ``armoor-data`` crashing with an opaque
  ``'NoneType' object has no attribute 'to_dataset'`` on unresolvable
  ``oceanvars`` filter requests; now raises a clear error naming the
  offending variable.

- Fixed ``armoor-data`` crashing when a ``metazones.cfg`` section had no
  ``[outputs]`` (closes #258).

- Fixed incorrect handling of ``vfreq`` in ``metazones.cfg`` for
  ``armoor-data``.

- Fixed missing ``data_vars`` on ``maps``/``timeseries`` outputs when
  ``trange`` was configured (closes #253).

- Fixed a suffix collision in ``extract_suffix_from_filename`` where the
  ``z`` capture group was read from the wrong regex group and silently
  equaled ``time``, collapsing distinct ``vrange``/``vlevel`` bins into a
  single sort key and causing "Multi-dataset concatenation not
  implemented" errors.

- Fixed ``KeyError`` in ``get_output_vminmax`` when a config section name
  differs from its ``otype``.

- Fixed degenerate ESMF cells in the regridder: they are now ignored and
  unmapped points are set to ``NaN`` instead of producing garbage values.

- Fixed ``0``/``-999`` fill values in CROCO ``u``/``v`` leaking into the
  ``x_u``/``y_v`` grid shift and corrupting interpolated rho-grid values.

- Fixed HPC job logging: stdout and stderr are no longer merged, so
  ``job.out``/``job.err`` now reflect actual stdout/stderr instead of
  mixing routine logging with tracebacks.

- ``armoor-viewer``: fixed 2D scalar overlay misalignment on curvilinear/
  rotated grids (HYCOM/NEMO) by warping tiles onto their true per-vertex
  geography instead of stretching them across a straight lon/lat bbox.

- ``armoor-viewer``: fixed visible seams and blending artifacts between
  mesh triangles in the 2D scalar overlay.

- Dropped the ``copernicusmarine`` test dependency: the ``woom`` integration
  test workflow now fetches its bathymetry sample from the bundled
  ``_samples/`` data instead of calling the CMEMS API, removing the need for
  network access and CMEMS credentials in CI.

- Silenced a noisy ``argopy`` log line (``Using OFFLINE Argo Float
  implementation``) emitted whenever xarray built its backend registry,
  unrelated to the file actually being opened.

- Pinned ``xoa`` to its conda-forge release instead of an unpinned git
  dependency, avoiding CI resolving a different ``xoa`` commit than the
  local dev environment on every rebuild.

Documentation
-------------

- Added numpy-style English docstrings to the modules touched by the
  ``comp``/``data`` refactoring.
