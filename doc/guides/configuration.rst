.. _guide-configuration:

Configuration files, in depth
###############################

Every metazone-based executable (:ref:`climeta`) is driven by **two**
configuration files, plus one internal decoding schema you normally never
need to touch:

- a **metazones file** (usually ``metazones.cfg``): spatio-temporal-vertical
  selection criteria, shared across executables (:ref:`guide-metazones`);
- a **data/output file** (its name is up to you, e.g. ``comp_argo.cfg``):
  which input datasets to use and which outputs to produce, specific to
  one executable;
- the **CF decoding config** (``armoor/data/*.cfg``, e.g.
  ``cf_cmems_argo.cfg``): how to map a given data format's variable/dim
  names onto armoor's pivot conventions (:ref:`opendecode` /
  :ref:`Armoor conventions <varconventions>`). Shipped with armoor; you
  only write your own if you add support for a new input format.

This guide is about the mechanism common to the first two: how a ``.cfg``
file is validated and turned into the Python dict the pipeline actually
consumes.

configobj + validate
=====================

Armoor uses `configobj <https://configobj.readthedocs.io/>`_ together with
its ``validate`` companion. Every ``.ini`` file shipped under
``armoor/cli/`` (``metazones.ini``, ``data.ini``, ``comp.ini``,
``filters.ini``, ``bull.ini``) is a **configspec** -- a schema, not a
config -- loaded by ``armoor.cli.io.ConfigManager`` and used to validate
*and type-coerce* the ``.cfg`` file you actually write.

A configspec line has the shape ``key = type(args..., default=...)``.
Armoor's schemas use:

.. list-table::
   :header-rows: 1
   :widths: 20 80

   * - Type
     - Meaning
   * - ``string()``
     - Free text.
   * - ``option(a, b, ..., default=...)``
     - One of a fixed set of choices.
   * - ``boolean(default=...)``
     - ``True``/``False``.
   * - ``integer()`` / ``float()``
     - Numeric, coerced from the ``.cfg``'s string.
   * - ``force_list(default=...)``
     - Always returns a Python list, even for a single value with no comma.
   * - ``float_list(default=...)``
     - Like ``force_list``, coerced element-wise to ``float``.
   * - ``path()``
     - A filesystem path (glob patterns allowed for input files).
   * - ``coordinates(default=...)``
     - Armoor-specific: parses a ``(lat, lon), (lat, lon), ...`` string
       into a list of float tuples (registered as a custom validator,
       ``armoor.misc.parse_coords``, via
       ``xoa.cfgm.register_validation_functions`` -- this is why coordinate
       lists parse correctly even though ``configobj`` has no built-in
       notion of tuples).
   * - ``minmax(default=...)``
     - Armoor-specific: parses a ``(min, max)`` pair (used for
       ``vminmax``).

Subsections use ``[[name]]`` (and ``[[[name]]]`` one level deeper); a
literal ``[__many__]`` / ``[[__many__]]`` section name means "any
user-chosen name is accepted here, validated against the same spec" --
this is how ``metazones.ini`` accepts an arbitrary number of differently
named metazones, and how ``data.ini``/``comp.ini`` accept an arbitrary
number of differently named datasets and output blocks.

Worked example: ``comp.ini`` vs. ``comp_argo.cfg``
===================================================

The schema (``armoor/cli/comp.ini``):

.. literalinclude:: ../../armoor/cli/comp.ini
   :language: ini
   :caption: comp.ini (schema)

and a real config validated against it (see :download:`comp_argo.cfg
<../examples/configs/comp_argo.cfg>`):

.. literalinclude:: ../examples/configs/comp_argo.cfg
   :language: ini
   :caption: comp_argo.cfg

Reading them side by side: ``[data]``'s ``[[__many__]]`` block lets you
name each dataset freely (``argo``, ``glo12``, ``hycom`` above); each must
supply ``name``/``path``/``fmt`` (``fmt`` restricted to the ``option(...)``
list of supported formats) and may set ``platform`` and ``ref`` (exactly
one dataset should have ``ref=True`` -- it becomes the colocation
reference, see :ref:`guide-colocation`). ``[outputs]``'s top-level ``fmt``
picks the artifact kinds to write (any of ``netcdf``/``zarr``/``png``);
each ``[[__many__]]`` block underneath then picks ``otype`` (one of the
`option(...)`` choices) and can override per-variable colorbar bounds via
``[[[vminmax]]]``.

Where user ``.cfg`` files are passed
=====================================

Every ``armoor-comp-*``/``armoor-data``/``armoor-filters`` invocation takes
the metazones-to-run list, the data/output ``.cfg`` path, and
``-m/--metazonesfile`` as its first three arguments -- see the exact
signature and the full per-command flag reference in :ref:`climeta`, and
:ref:`guide-metazones` for what "metazones-to-run" means. Use the
:ref:`examples` gallery and the :ref:`tutorials` (which write and run real
``.cfg`` files against bundled sample data) as copy-paste starting points
rather than writing one from the schema alone.

Common pitfalls
================

- **A half-filled subsection is not the same as an absent one.** configobj
  always materializes every declared subsection with ``None`` sub-keys,
  even when you never wrote it. Whether that then counts as "not
  configured" downstream depends on which one sub-key the caller checks
  (armoor calls it that section's "primary key" -- see
  :ref:`guide-metazones` for the exact table). Setting only *some* of a
  subsection's keys usually doesn't raise at parse time; it surfaces later
  as a confusing error once the pipeline reaches a ``None`` it didn't
  expect.
- **``force_list``/``float_list`` always return a list.** A single
  bathymetry threshold or a single vertical level still needs to be
  readable as ``levels[0]`` downstream -- don't special-case "a single
  value" in a config you write by hand, it already comes back as a
  one-element list.
- **Coordinates need the exact ``(lat, lon), (lat, lon)`` tuple syntax.**
  ``polygon``/``cloud`` are parsed by a dedicated validator
  (``parse_coords``); a plain flat list of numbers will fail to parse as
  tuples.
- **Unknown keys don't always error.** Some CLI-level options (e.g.
  ``armoor-comp-argo``'s ``radius``/``qc``) are *not* part of any
  ``.cfg`` schema at all -- they are merged into each running metazone's
  parameter dict by ``check_metazones_in`` from the command line instead
  (see :ref:`guide-metazones`). Conversely, a key that a schema *does*
  accept but the current comparison type doesn't use is silently dropped
  with a warning, not an error -- so a typo in a key name can fail
  silently rather than loudly.
- **No dedicated "validate only" / dry-run flag exists today.** A
  malformed ``.cfg`` surfaces as an ``ArmoorError`` (or occasionally a
  less friendly exception) once the corresponding executable actually
  starts parsing it. When iterating on a new config, narrow ``tbound`` to
  a tiny window and/or use ``--filters-only``/``--coloc-only`` (see
  :ref:`guide-executables`) to fail fast and inspect intermediate zarr
  output before running the full pipeline.
