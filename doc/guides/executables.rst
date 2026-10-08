.. _guide-executables:

Command-line executables, in depth
#####################################

:ref:`howtostart` lists every ``armoor-*`` command; :ref:`cliunit` and
:ref:`climeta` document each one's arguments. This guide instead covers
the architecture shared across them: what actually happens between
invoking a command and getting output on disk.

Two families, one plumbing
============================

All ``armoor-*`` console scripts (see the full list in ``pyproject.toml``'s
``[project.scripts]``) are thin wrappers: a ``get_parser_*`` function
builds an ``argparse.ArgumentParser`` (shared building blocks such as
``add_dask_parser_arguments``, ``add_logging_parser_arguments``,
``add_comp_io_parser_arguments``/``add_comp_parser_arguments`` live in
``armoor.cli.io``/``armoor.cli.log``), then a ``main_*`` function parses
``sys.argv`` and runs the actual work. Heavy imports (dask.distributed,
cartopy, scipy, xoa, ...) are deferred into these functions so that
``--help`` and shell completion stay fast even on a slow HPC filesystem.

- **Elementary executables** (:ref:`cliunit`) run a single task on an
  already-decoded input/output file pair, wrapped in
  ``armoor.cli.io.armoor_cli_session`` -- a context manager that sets up
  logging and a local Dask cluster around the call and tears it down
  afterwards. No metazone config is involved; strategies are either passed
  explicitly or auto-detected (:ref:`guide-colocation`'s "unit-level
  auto-detection" section).
- **Metazone-based executables** (:ref:`climeta`) run a whole pipeline,
  once per metazone, driven by the two config files described in
  :ref:`guide-configuration`.

The meta-pipeline stage model
================================

Every metazone-based executable follows the same shape -- open-decode
(:ref:`opendecode`) → filter → [colocate] → range/compute output → plot --
only the colocation stage and the on-disk layout differ between
``armoor-data`` (no reference dataset, so no colocation) and
``armoor-comp-*``/``armoor-bull`` (reference vs. product):

.. list-table::
   :header-rows: 1
   :widths: 30 35 35

   * - Stage
     - ``armoor-data``
     - ``armoor-comp-*``
   * - Filtered input
     - ``./data/metazones/{metazone}/{data.name}/``
     - ``./{comp}/metazones/{metazone}/{data.name}/``
   * - Colocated pair
     - *(n/a)*
     - ``./{comp}/coloc/{metazone}/{ref.name}/{prod.name}/``
   * - Computed output
     - ``./data/output/{metazone}/{data.name}/{otype}/``
     - ``./{comp}/output/{metazone}/{ref.name}/{data.name}/{otype}/``
   * - Plots
     - ``./data/plot/{metazone}/``
     - ``./{comp}/plot/{metazone}/{ref.name}/{otype}/``

Each stage's flag lets you stop the pipeline right after it, to inspect
intermediate zarr files while you iterate on a config:

.. list-table::
   :header-rows: 1
   :widths: 25 75

   * - Flag
     - Effect
   * - ``--filters-only``
     - Stop after filtering (and, for ``armoor-data``, interpolation).
   * - ``--coloc-only``
     - (``armoor-comp-*`` only) Stop after colocation, before computing
       outputs.
   * - ``--no-plot``
     - Run the full pipeline but skip the plot stage.
   * - ``--plot-only OTYPE``
     - Regenerate plots for a single output type from already-computed
       zarr files (requires ``--input-json``, produced by a prior run).

HPC dispatch
=============

``--hosts-cfg PATH`` (pointing at a *woom* ``hosts.cfg``) switches
``armoor-data``/``armoor-comp-*`` from running stages in the foreground to
submitting them as Slurm/PBS jobs, in four waves (Wave 0: per-dataset
load; Wave 1: colocation; Wave 2: output computation; Wave 3: plotting --
implemented in ``armoor.cli.hpc``), with per-stage walltime/queue/cpu
counts read from the ``[hpc]`` section of the data/output ``.cfg``. The
``--load-only``/``--input-zarrs``/``--input-json``/``--jsonfile`` flags
exist purely to hand intermediate state (lists of zarr paths, as JSON)
between waves -- they are what the HPC job scripts pass to themselves, not
something you normally set by hand in an interactive run.

The odd ones out
==================

- ``armoor-bull`` generates bulletins (a fixed report format) rather than
  arbitrary plots/outputs; it shares the metazone/filter/colocation
  machinery but not the ``otype`` output model (:ref:`clibull`).
  ``armoor-diag`` is planned to follow the same shape but is not available
  yet.
- ``armoor-tick-*`` (``authentication``, ``authentication-info``,
  ``create``, ``description``, ``search``) talk to Shom's TICK
  (InfluxDB/Chronograf) stack for bulletin publication and have nothing to
  do with the filter/coloc/output pipeline at all (:ref:`tick`).

Discovering options
=====================

Every entry point supports ``-h``/``--help``; the generated reference for
each one (built from the same ``get_parser_*`` functions via
``sphinx-argparse``) lives under :ref:`cliunit` and :ref:`climeta`. Shell
completion is available via ``armoor-`` + Tab. When a command's behavior
depends on the current metazone/data config rather than on flags (which is
most of the interesting behavior for meta executables), see
:ref:`guide-metazones` and :ref:`guide-configuration` instead of the
``-h`` output.
