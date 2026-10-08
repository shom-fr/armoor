.. _guide-metazones:

Metazones, in depth
####################

A **metazone** is a named bundle of spatio-temporal-vertical selection
criteria and processing directives. It is armoor's central concept for
metazone-based executables (:ref:`climeta`): every such executable
(``armoor-filters``, ``armoor-data``, ``armoor-comp-*``, ``armoor-bull``)
loops over one or more metazones and repeats its *entire* pipeline once per
metazone, so that the same input data can be reduced to several
region/period/depth-range combinations in a single run.

This guide explains what a metazone parameter actually configures --
which, perhaps surprisingly, depends on *which stage of the pipeline reads
it*, not just on the key's name.

The metazones configuration file
=================================

Metazones are declared in a ``metazones.cfg`` file (see
:download:`metazones.cfg <../examples/configs/metazones.cfg>` for a worked
example), validated and type-coerced against the schema shipped as
:download:`armoor/cli/metazones.ini <../../armoor/cli/metazones.ini>`. See
:ref:`guide-configuration` for how that validation mechanism works in
general; this section only covers what is specific to metazones.

The schema's ``[__many__]`` top section means *any* section name is
accepted -- each one becomes one metazone, keyed by its section name. A
single ``metazones.cfg`` typically defines several:

.. literalinclude:: ../examples/configs/metazones.cfg
   :language: ini
   :caption: metazones.cfg
   :linenos:

A metazone-based executable is always invoked with **three** pieces of
information, not just the metazones file:

.. code-block:: console

   $ armoor-comp-argo meta1,meta3 comp_argo.cfg -m metazones.cfg 25 --qc ptemp,1,7

- the comma-separated list of metazone **names to actually run** (a
  positional argument -- ``meta1,meta3`` here; a metazones.cfg can define
  more metazones than you run in a given invocation),
- the data/output configuration file (:ref:`guide-configuration`),
- ``-m/--metazonesfile`` pointing at the metazones.cfg (defaults to
  ``metazones.cfg`` in the current directory).

The three roles of a metazone parameter
========================================

This is the part that is easy to miss: a metazone is read by *three*
independent stages of the pipeline, and most parameters only matter to
exactly one of them.

1. Pre-filtering (every executable)
------------------------------------

Right after open-decode (:ref:`opendecode`), every metazone-based
executable filters each input dataset once, before anything else happens.
``armoor.data.load.build_filters_config`` turns the metazone dict into a
``filters_config`` dict consumed by ``ds.filters.combined`` (the
:ref:`accessor-filters` accessor, backed by ``armoor.filters.ArmoorFilters``):

.. list-table::
   :header-rows: 1
   :widths: 20 30 50

   * - Metazone key
     - ``filters_config`` key
     - Effect
   * - ``tbound``
     - ``time_selection``
     - Keep only ``[date_min, date_max]``.
   * - ``thours``
     - ``hours_selection``
     - Keep only ``[hour_min, hour_max]`` of day (wraps past midnight).
   * - ``tide``
     - ``tide``
     - Apply a tidal filter (``demerliac``, ``godin`` or ``mean``).
   * - ``tresample``
     - ``tresample``
     - Resample in time at the given pandas frequency.
   * - ``tsmooth``
     - ``tsmooth``
     - Smooth in time over the given window.
   * - ``bathy``
     - ``bathy``
     - Keep points where a bathymetry file's depth falls within ``[min, max]``.
   * - ``qc``
     - ``quality``
     - Keep points passing a quality-flag threshold, ``(qname, qmin, qmax)``.
   * - ``polygon``
     - ``polygon``
     - Keep points inside the ``(lat, lon)`` polygon.
   * - ``oceanvars``
     - ``oceanvars``
     - Keep (or derive) only the listed ocean variables.

These filters are all combined into a single mask operation
(``apply_combined_filters``) to avoid materializing one intermediate copy
of the dataset per filter.

2. Colocation (``armoor-comp-*`` only)
----------------------------------------

Filtering happens on *each* dataset independently. Colocation instead
aligns a **reference** (observation) and a **product** (model) dataset onto
a shared support -- see :ref:`guide-colocation` for the mechanism. Only a
subset of metazone keys drive this stage: ``href``, ``cloud``, ``radius``,
``track`` (horizontal); ``trange_seq``, ``tfreq``, ``tmonth`` (time);
``vlevel``, ``vrange`` (vertical).

Crucially, **not every comparison type looks at the same keys**, and some
of those keys don't even come from ``metazones.cfg`` at all: ``radius``
and ``qc`` are CLI options of ``armoor-comp-argo``/``armoor-comp-mooring``
(e.g. ``--qc ptemp,1,7`` above) that ``check_metazones_in`` merges into
every selected metazone's parameter dict before colocation runs, purely so
the same lookup machinery can treat them like any other metazone
parameter. See :ref:`guide-colocation` for the full per-comparison-type
table of which keys apply and their defaults.

3. Output ranging (``armoor-comp-*`` and ``armoor-data``)
------------------------------------------------------------

After colocation, ``trange_seq``/``tfreq`` and ``vlevel``/``vrange`` are
read *a second time*, with a different purpose: splitting the already
time/depth-aligned pair into one sub-dataset per time bin or depth bin,
each written to its own output file. This is where ``vrange``'s
``bins_min``/``bins_max`` actually matter -- during colocation, only
``vref``/``vname`` are used (the pair is interpolated onto one shared
axis); the bin bounds only come into play afterwards, when carving that
aligned pair into per-bin outputs (``armoor.ranges.vrange``/
``trange_seq``).

Parameter reference
====================

- ``name``: name of the metazone (redundant with the section name, kept
  for readability).
- ``tbound``: ``[date_min, date_max]``.
- ``thours``: ``[hour_min, hour_max]`` (24h clock; a range that wraps past
  midnight, e.g. ``[22, 4]``, is handled).
- ``tide``: ``demerliac``, ``godin`` or ``mean``.
- ``tfreq``: a pandas offset alias (``1D``, ``1Y``, ...) defining a regular
  series of terms both datasets are resampled onto.
- ``trange_seq``: subsection interpolating one dataset onto the other's
  *native* time axis before ranging::

      [[trange_seq]]
          tfreq = 1D          # size of each output time bin
          tref = reference    # axis to interpolate onto: reference or product
          method = linear     # optional interpolation method (default: linear)

- ``tresample`` / ``tsmooth``: pre-filtering time resampling/smoothing
  (distinct from ``tfreq``/``trange_seq``, which act at the colocation and
  ranging stages).
- ``polygon``: ``(lat, lon)`` vertices of a filtering polygon.
- ``cloud``: ``(lat, lon)`` points to horizontally interpolate the product
  onto (colocation stage; mutually exclusive with ``href``).
- ``href``: ``reference`` or ``product`` -- which grid to regrid the other
  dataset onto.
- ``bathy``: subsection filtering on bathymetry::

      [[bathy]]
          path = /local/misc/data/bathy_indien.nc
          fmt = hycom
          min = 0.0
          max = 1000.0

- ``vlevel``: subsection interpolating both datasets onto a fixed list of
  vertical levels::

      [[vlevel]]
          vname = depth
          levels = 50, 100, 400, 500

- ``vrange``: subsection colocating vertically onto one dataset's native
  axis, then splitting into vertical bins for output::

      [[vrange]]
          vref = reference                 # axis to interpolate onto
          vname = depth
          bins_min = 50, 400, 800          # only used for output ranging
          bins_max = 100, 500, 1000

- ``vfreq``: subsection interpolating onto a regular vertical step::

      [[vfreq]]
          vname = depth
          step = 25.0

- ``oceanvars``: list of ocean variables (:ref:`Armoor conventions
  <varconventions>`) to keep.

Incompatible combinations
==========================

``check_metazones_in`` (``armoor.cli.main``) rejects a metazone at parse
time if:

- both ``tfreq`` and ``thours`` are set,
- ``trange_seq`` is set without ``tbound``.

``get_colocation_params`` additionally treats some pairs as *candidates*
for the same colocation slot -- e.g. a comparison type declaring
``"horizontal": ("href", "cloud")`` picks whichever one is actually set in
the metazone; setting both is meaningless (only one is looked up, in
declaration order) rather than a hard error, so double-check your config
if you expect a specific one to win.

Two silent behaviors worth knowing about
==========================================

- **Unused keys are dropped with a warning, not an error.** Each
  comparison type declares a ``metazone_params`` whitelist (see
  :ref:`guide-colocation`). If your ``metazones.cfg`` sets a key that
  ``armoor-comp-sst`` (say) doesn't use, it is silently removed from that
  run's parameter dict with a logged warning ("... is removed to run this
  functionality") rather than raising -- convenient for sharing one
  ``metazones.cfg`` across several ``armoor-comp-*`` commands, but it means
  a typo'd key name fails silently instead of erroring.
- **Empty subsections are dropped based on a "primary key".** configobj's
  ``validate()`` always materializes every declared subsection
  (``trange_seq``, ``vlevel``, ``vrange``, ``vfreq``, ``bathy``,
  ``section``) with all sub-keys set to ``None``, even when you never wrote
  it in the ``.cfg``. ``check_metazones_in`` treats a subsection as "not
  configured" only if its *primary key* is ``None``:

  .. list-table::
     :header-rows: 1
     :widths: 30 30

     * - Subsection
       - Primary key
     * - ``trange_seq``
       - ``tfreq``
     * - ``vlevel`` / ``vrange`` / ``vfreq``
       - ``vname``
     * - ``bathy``
       - ``path``
     * - ``section``
       - ``dx``

  In practice this means a half-filled subsection (e.g. a ``[[vrange]]``
  with ``vname`` set but ``vref``/``bins_min``/``bins_max`` left out) is
  *not* dropped -- it is passed through with ``None`` sub-keys, which will
  surface later as a confusing ``KeyError``/``TypeError`` rather than a
  clear "missing parameter" message. Set the primary key's sibling
  parameters together, or not at all.

See also :ref:`guide-configuration` for the configobj/validate mechanism
underneath ``metazones.ini``, and :ref:`examples` for more complete,
copy-pasteable ``metazones.cfg`` examples.
