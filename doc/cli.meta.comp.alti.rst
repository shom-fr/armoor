:command:`armoor-comp-alti`
===========================

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

Comparison with altimetry products (L4 product: ``fmt=cmems_alti_duacs``) on the
following variables:

- ``ssh``: sea surface height (ssh for the model, adt for the satellite).
- ``sla``: sea level anomaly, computed as the anomaly of ssh (for the model) or
  adt (for the satellite) over the colocated time steps within ``tbound``. This
  window is shorter than ``tbound`` if the data do not cover all of it.
- ``eke``: Eddy Kinetic Energy, from the geostrophic current anomalies derived
  from ``sla``.
- ``ke``: Kinetic Energy, from the total u and v.
- ``ke_geos``: Kinetic Energy, from the geostrophic u and v derived from ssh or
  adt.
- ``mke`` and ``mke_geos``: Mean Kinetic Energy, from the time-averaged total and
  geostrophic currents respectively.

``mke`` and ``mke_geos`` are computed from the current averaged over the same
window as ``sla`` (never split by ``trange_seq``/``tfreq``). They
carry a size-1 ``period`` dimension instead of ``time``, are saved in their own
``*_period_<start>_<end>.zarr`` colocation files, and are only produced by the
``maps`` and ``diagdisp_glob`` outputs.

Geostrophic energies are compared geostrophic against geostrophic, computed the
same way on both sides: geostrophic currents are derived with ``get_geos`` from
the library ``shoot``, from the model ssh and from the DUACS adt (and from
``sla`` for ``eke``). The geostrophic currents provided by DUACS
(``ugos``/``vgos``/``ugosa``/``vgosa``) are ignored. ``ke`` and ``mke`` (total current)
are only compared when the reference provides a total current, which altimetry
does not: against DUACS they are dropped and only ``ssh``, ``sla``, ``eke``,
``ke_geos`` and ``mke_geos`` are compared.

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
    - ``thours``
    - ``trange_seq``
    - ``tfreq``
    - ``polygon``
    - ``href``
    - ``oceanvars``
    - ``bathy``

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
