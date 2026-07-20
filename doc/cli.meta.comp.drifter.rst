:command:`armoor-comp-drifter`
==============================

Usage
-----

.. code-block:: bash

    armoor-comp-drifter METAZONES CFGFILE PERIOD FREQ [OPTIONS]

.. rubric:: Example

.. code-block:: bash

    armoor-comp-drifter MED comp_drifter.cfg 6h 1h \
        --tbound 2023-05-01 2023-05-31

``METAZONES``
    Comma-separated list of metazone names to process (must exist in
    ``metazones.cfg`` or the file given to ``-m``).

``CFGFILE``
    Path to the comparison configuration file (see :ref:`clicomp`).

``PERIOD``
    Duration of each virtual particle integration step, as a
    `pandas period string <https://pandas.pydata.org/docs/user_guide/timeseries.html#period-aliases>`_.
    This controls how far ahead (or behind) virtual trajectories are
    integrated using model currents.  Typical values: ``1h``, ``6h``,
    ``1d``.

``FREQ``
    Time frequency at which the real drifter position and the virtual
    trajectory are compared, as a pandas frequency string.  Must be
    ≤ ``PERIOD``.  Typical values: ``1h``, ``6h``, ``1d``.

Time bounds (``--tbound``)
--------------------------

``--tbound`` overrides the ``tbound`` parameter defined in the metazone
configuration for the current run only.

.. code-block:: bash

    --tbound 2023-05-01 2023-05-31

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

    - ``cmems_drifter``

metazone parameters
-------------------

    - ``tbound``
    - ``trange_seq``
    - ``tfreq``
    - ``tide``
    - ``tresample``
    - ``tsmooth``
    - ``polygon``
    - ``vars``

    .. note::
       Other given parameters are ignored.

outputs
-------

    - ``timeseries``
    - ``maps_trajectory``
    - ``maps_current``

.. argparse::
    :module: armoor.cli.main
    :func: get_parser_comp_drifter
    :prog: armoor-comp-drifter
    :nosubcommands:
