:command:`armoor-comp-clim`
===========================

Usage
-----

.. code-block:: bash

    armoor-comp-clim METAZONES CFGFILE [OPTIONS]

.. rubric:: Example

.. code-block:: bash

    armoor-comp-clim MANCHE,GASCOGNE comp_clim.cfg \
        --tbound 2023-01-01 2023-12-31

``METAZONES``
    Comma-separated list of metazone names to process (must exist in
    ``metazones.cfg`` or the file given to ``-m``).

``CFGFILE``
    Path to the comparison configuration file (see :ref:`clicomp`).

Time bounds (``--tbound``)
--------------------------

``--tbound`` overrides the ``tbound`` parameter defined in the metazone
configuration for the current run only.

.. code-block:: bash

    --tbound 2023-01-01 2023-12-31

The model outputs are grouped by calendar month over the full ``tbound``
period and averaged into monthly means (indices 1–12) before being compared
to the climatology.  If ``tbound`` spans multiple years, all same-month
values are averaged together.

Pipeline control
----------------

By default all four pipeline stages run in sequence:
*load → coloc → output → plot*.
Each flag short-circuits the pipeline after the named stage:

.. list-table::
   :header-rows: 1
   :widths: 30 70

   * - Flag
     - Effect
   * - ``--filters-only``
     - Stop after loading and filtering.  Zarr files are written to
       ``{comp_name}/metazones/{metazone}/{data}/``.
   * - ``--coloc-only``
     - Stop after colocation.  Zarr files are written to
       ``{comp_name}/coloc/{metazone}/{ref}/{data}/``.
   * - ``--no-plot``
     - Run load + coloc + output computation but skip the plot stage.
   * - ``--plot-only OTYPE``
     - Regenerate plots for a single output type from existing zarr files.
       Requires ``--input-json``.

HPC options
-----------

``--hosts-cfg PATH``
    Path to a *woom* ``hosts.cfg`` file.  When provided, armoor submits
    pipeline stages as Slurm jobs (Wave 0 → Wave 3) instead of running
    them in the foreground.

``--load-only DATASET_KEY``
    *Internal — used by HPC Wave 0 jobs.*  Load a single dataset for all
    metazones and write zarr paths to ``--jsonfile``.

``--input-zarrs JSON,...``
    *Internal — used by HPC Wave 1+ jobs.*  Comma-separated list of
    zarr-paths JSON files produced by Wave 0.  When provided, the load
    stage is skipped.

data formats
------------

    - ``woa18``
    - ``bobyclim``

    .. note::
       The reference dataset must carry ``ref=True`` in the ``[data]``
       section.  Its ``time`` coordinate is expected to contain monthly
       indices 1–12.

       ``bobyclim`` support is experimental and has not been validated on
       real files.  A ``UserWarning`` is emitted at runtime.

metazone parameters
-------------------

    - ``tbound``
    - ``polygon``
    - ``href``
    - ``vlevel``
    - ``vars``

    .. note::
       Other given parameters are ignored.

outputs
-------

    - ``maps``
    - ``timeseries``


.. argparse::
    :module: armoor.cli.main
    :func: get_parser_comp_clim
    :prog: armoor-comp-clim
    :nosubcommands:
