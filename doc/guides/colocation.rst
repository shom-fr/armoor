.. _guide-colocation:

Colocation, in depth
#####################

Colocation is the step that brings a **reference** dataset (an
observation: Argo, a mooring, a satellite product, a climatology, ...) and
a **product** dataset (typically a model) onto a shared time / horizontal /
vertical support, so that a pointwise comparison (bias, RMSE, difference
map, ...) is actually meaningful. Filtering (see :ref:`guide-metazones`)
reduces each dataset on its own; colocation is the only step that looks at
*both* datasets together.

Two ways to run it
===================

- **Interactively / in the Python API**: the :ref:`accessor-coloc`
  accessor, ``ds_prod.coloc.with_ref(ds_ref)``, returning a chainable
  ``ColocSession``. This is what the tutorials use, and what
  ``armoor-coloc-time``/``-horizontal``/``-vertical`` call under the hood
  for a single, ad-hoc reference/product pair.
- **Metazone-driven, for a whole pipeline**: ``armoor-comp-*`` (see
  :ref:`clicomp`), which decides *which* colocation strategy to apply from
  the metazone configuration (:ref:`guide-metazones`) and the comparison
  type being run, for every metazone × reference × product combination.

Both paths ultimately call the same three functions in
``armoor.comp.coloc``: ``process_time_colocation``,
``process_horizontal_colocation``, ``process_vertical_colocation``, each
dispatching on a ``(strategy_name, args)`` pair to a method of
``TimeColocation``, ``HorizontalColocation`` or ``VerticalColocation``.

The strategies
===============

Time
----

.. list-table::
   :header-rows: 1
   :widths: 20 80

   * - Strategy
     - Effect
   * - ``tfreq``
     - Resample *both* datasets onto a new regular time axis at the given
       frequency (``pandas.date_range`` + interpolation).
   * - ``trange_seq``
     - Interpolate one dataset's time axis onto the *other's own* native
       time values (``tref: reference`` or ``product``; ``method``,
       default ``linear``). Used both as the colocation strategy and later
       to define the output time bins (:ref:`guide-metazones`).
   * - ``tmonth``
     - Climatological colocation: group the product by calendar month,
       average, and align on the shared 1-12 month index of a monthly
       reference climatology. Not user-selectable via a metazone key --
       it is ``comp_clim``'s hardcoded default (see below).

Horizontal
----------

.. list-table::
   :header-rows: 1
   :widths: 20 80

   * - Strategy
     - Effect
   * - ``href``
     - Regrid one dataset onto the other's grid (``reference`` or
       ``product``); the source-grid ``mask`` variable, if present, is
       applied and dropped first.
   * - ``cloud``
     - Interpolate (grid-to-location) at a fixed list of ``(lat, lon)``
       points.
   * - ``track``
     - Interpolate the product onto the reference's own *moving* track
       (one point per reference profile/timestep, e.g. a glider mission),
       instead of a fixed point list. Requires the time colocation step to
       have already aligned both "time" axes.
   * - ``radius``
     - Keep product members (a stacked (lon, lat) dimension, ``member``)
       within a geographic radius (km) of each reference point. Handles
       both a fixed reference point and a *time-varying* one (e.g. a
       drifting buoy), the latter via a vectorized per-timestep distance
       computation that also compacts out members that fall outside the
       radius at every timestep, or whose ocean data is all-NaN (masked
       land/coastal cells).
   * - ``coarsen``
     - Degrade one or both datasets' spatial resolution by block-averaging
       (or median/min/max) -- not colocation per se, but available on the
       same session for resolution-sensitivity studies.

Vertical
--------

.. list-table::
   :header-rows: 1
   :widths: 20 80

   * - Strategy
     - Effect
   * - ``vlevel``
     - Interpolate both datasets onto a fixed list of vertical levels.
       When only one side actually has a ``z`` dimension (e.g. a
       full-depth model vs. a surface-only satellite) and a single level
       is requested, the resulting singleton ``z`` dimension is squeezed
       away on that side to keep both datasets' dimension signatures
       comparable.
   * - ``vrange``
     - Interpolate one dataset's vertical axis onto the *other's* native
       axis (``vref: reference`` or ``product``); the bin bounds
       (``bins_min``/``bins_max``) aren't used here at all -- they only
       matter for the output-ranging step that follows colocation.

Which strategy applies to which comparison type
================================================

Not every ``armoor-comp-*`` command accepts every metazone key. Each
comparison type (``armoor.comp.comparison.Comparison`` subclass) declares
``colocation_params_user`` (candidate metazone keys, tried in order, per
colocation kind) and ``colocation_params_default`` (used when nothing user
-configured is found -- or unconditionally, for a strategy that isn't
user-selectable at all):

.. list-table::
   :header-rows: 1
   :widths: 18 20 20 20 22

   * - Comparison
     - time
     - horizontal
     - vertical
     - notes
   * - ``comp_sst``
     - ``trange_seq``, ``tfreq``
     - ``href``, ``cloud``
     - *(default:* ``vlevel`` @ 0m *)*
     - surface-only: no vertical ranging
   * - ``comp_argo``
     - ``trange_seq`` *(default: nearest, "*")*
     - ``radius``
     - ``vrange``, ``vlevel``
     - ``radius``/``qc`` come from CLI flags, not the ``.cfg``
   * - ``comp_mooring``
     - ``trange_seq``, ``tfreq``
     - ``radius``
     - *(default:* ``vrange`` on ``depth`` *)*
     - always ranges on ``depth`` regardless of config (see below)
   * - ``comp_drifter``
     - *(none user-selectable)*
     - *(none -- see below)*
     - *(default:* ``vrange`` on ``depth`` *)*
     - always ranges on ``depth``; spatial matching deferred to OceanParcels
   * - ``comp_models``
     - ``trange_seq``, ``tfreq``
     - ``href``, ``cloud``
     - ``vrange``, ``vlevel``
     - product vs. product; no forced defaults
   * - ``comp_clim``
     - *(default, always:* ``tmonth`` *)*
     - ``href``
     - ``vlevel``
     - climatological monthly colocation is the only option
   * - ``comp_hydrosection``
     - *(default, always: nearest to reference, "*")*
     - *(default, always:* ``track`` *)*
     - *(default, always:* ``vrange`` *on* ``depth`` *)*
     - fully forced: none of the three is user-configurable

Two patterns recur here and are worth internalizing:

- **A comparison type can hardcode a strategy.** ``comp_clim`` always uses
  ``tmonth``, ``comp_hydrosection`` always uses nearest-time/track/vrange
  regardless of what the metazone sets. This isn't a bug to work around --
  it reflects that, e.g., comparing against a climatology only ever makes
  sense month-by-month.
- **``comp_mooring``/``comp_drifter`` always range vertically on**
  ``depth``, never on whatever ``vlevel``/``vrange`` would otherwise
  select (``_ForcedDepthVLevelMixin``). If you configure ``vlevel`` for a
  metazone shared with ``comp_argo``, don't expect ``comp_mooring`` to
  honor it.
- **``comp_drifter`` has no horizontal colocation stage at all** -- unlike
  every other comparison type, spatial matching between the drifter and
  the model happens later, via an OceanParcels simulation
  (``preproc_comp_drifter``), not through ``HorizontalColocation``.

Order of operations in the meta pipeline
=========================================

Within ``armoor.comp.coloc._apply_colocations``, the three stages always
run in a fixed order -- **time, then horizontal, then vertical** --
regardless of the order keys appear in the ``.cfg`` file:

1. **Colocate** time → horizontal → vertical (``_apply_colocations``).
2. **Split by dimension signature** (``_split_by_dims`` /
   ``select_vars_by_dims``): variables with different dimension sets
   (e.g. a 2D ``mld`` next to 3D ``ptemp``) are separated into independent
   sub-datasets so that ranging and output don't try to merge
   incompatible shapes. A product group with no matching reference-side
   dimension signature is simply skipped.
3. **Range** each sub-dataset in time (``_apply_time_ranges``, using
   ``tfreq``/``trange_seq``) and, if a ``z`` dimension is present, in depth
   (``_apply_vertical_ranges``, using ``vlevel``/``vrange`` -- this is
   where ``vrange``'s ``bins_min``/``bins_max`` are finally used). This
   step can turn one (ref, prod) pair into several -- one per time/depth
   bin.
4. **Save** each ranged (ref, prod) pair as a pair of zarr stores under
   ``{comp_name}/coloc/{metazone}/{ref.name}/{prod.name}/`` (see
   :ref:`clicomp`'s workflow section for the full directory layout).

Unit-level auto-detection
==========================

``armoor-coloc-time``/``-horizontal``/``-vertical`` (:ref:`cliunit`) work
on a single, already-decoded reference/product pair with no metazone
config at all, so they *infer* the strategy instead of reading it from a
``.cfg``:

- **horizontal**: ``href`` if the reference has ``(x, y)`` grid dims,
  ``cloud`` (using the reference's own points) if it is a point cloud or
  track (``npts`` or ``time`` dims) -- otherwise an ``ArmoorError`` is
  raised.
- **vertical**: picks ``depth`` if present on both sides, else ``pdens``;
  if the vertical coordinate varies over more than one dimension, it
  checks whether it is actually constant in time/space (and uses a single
  vertical profile if so) or whether both datasets already share the exact
  same ``(time, lon, lat)`` (and uses the full varying coordinate
  otherwise) -- raising if neither holds.

Practical notes
================

- ``href`` and ``cloud`` are mutually exclusive for the same metazone
  (:ref:`guide-metazones`); ``trange_seq`` requires ``tbound`` to be set.
- Colocation always loads data into memory per reference/product pair
  (``_prepare_dataset`` calls ``.load()`` after trimming to only the raw
  variables actually needed, derived variables are computed afterwards on
  the small colocated result) -- keep per-metazone extents reasonable on
  large domains.
- See :ref:`accessor-coloc` for the plain Python API (useful for
  prototyping a colocation strategy in a notebook before wiring it into a
  ``metazones.cfg``).
