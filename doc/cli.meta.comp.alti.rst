:command:`armoor-comp-alti`
==========================

Usage
-----

.. code-block:: bash

    armoor-comp-alti METAZONES CFGFILE [OPTIONS]

.. rubric:: Example

.. code-block:: bash

    armoor-comp-alti MANCHE,GASCOGNE comp_alti.cfg \
        --tbound 2025-06-01 2025-08-31

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

    --tbound 2025-01-01 2025-03-31

Scope
-----

Comparison with altimetry products (L4 product : ``fmt=cmems_alti_duacs``) by computing
Eddy Kinetic Energy (EKE) and Mean Kinetic Energy (MKE) respectively from sea level anomaly (sla) 
and sea surface height (ssh or adt).
sla is computed as the anomaly of ssh (for the model) or adt (for the satellite) over the period defined by ``tbound``


Geostrophic current from sla or ssh are computed using ``get_geos`` from the library ``shoot`` 

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

    - ``cmems_alti_duacs``

metazone parameters
-------------------

    - ``tbound``
    - ``trange_seq``
    - ``tfreq``
    - ``polygon``
    - ``href``
    - ``cloud``
    - ``vars``

    .. note::
       Other given parameters are ignored.

outputs
-------

    - ``diagdisp_glob``
    - ``diagdisp_sel``
    - ``timeseries``
    - ``maps``


.. argparse::
    :module: armoor.cli.main
    :func: get_parser_comp_alti
    :prog: armoor-comp-alti
    :nosubcommands:
