:command:`armoor-comp-mooring`
==============================

Usage
-----

.. code-block:: bash

    armoor-comp-mooring METAZONES CFGFILE RADIUS [OPTIONS]

.. rubric:: Example

.. code-block:: bash

    armoor-comp-mooring GOLFE_DE_GASCOGNE comp_mooring.cfg 20.0 \
        --tbound 2025-01-01 2025-12-31

``METAZONES``
    Comma-separated list of metazone names to process (must exist in
    ``metazones.cfg`` or the file given to ``-m``).

``CFGFILE``
    Path to the comparison configuration file (see :ref:`clicomp`).

``RADIUS``
    Radius in kilometres of the disk used to spatially average model
    grid points around each mooring position.  Typical values: ``5.0``
    to ``50.0``.

Quality control (``--qc``)
--------------------------

Filter mooring observations by quality-control flag before colocating.

Syntax: ``<variable>:<min_flag>,<max_flag>``  *(dict format — colon
separates the variable name from the flag range)*

.. code-block:: bash

    --qc ptemp:1,2   # keep records where ptemp QC flag is 1 or 2

.. note::
   The mooring ``--qc`` uses a colon (``:``) between the variable name
   and the flag range, unlike ``armoor-comp-argo`` and
   ``armoor-comp-sst`` which use a comma throughout.

Time bounds (``--tbound``)
--------------------------

``--tbound`` overrides the ``tbound`` parameter defined in the metazone
configuration for the current run only.

.. code-block:: bash

    --tbound 2025-01-01 2025-03-31

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

    - ``cmems_mooring``

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

.. argparse::
    :module: armoor.cli.main
    :func: get_parser_comp_mooring
    :prog: armoor-comp-mooring
    :nosubcommands:
