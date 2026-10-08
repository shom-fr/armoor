.. _clidata:

Command-line interfaces for data
################################

Configuration file
------------------

    Armoor executables dedicated to plot data have to be associated with a configuration file based on `data.ini`:
        .. literalinclude:: ../armoor/cli/data.ini
               :language: ini
               
data
====

        The data section is dedicated to the configuration of input data.

        - ``name``: name of the dataset.
        - ``path``: path of the input data files. Use of wild card is possible in order to process multiple files.
        - ``fmt``: user has to configure an armoor format-like.

outputs
=======

        Multiple outputs can be configured. The available outputs depend on the metazone parameters.
        For instance, a vertical profile of salinity is not possible with ``vlevel``.

        - ``fmt``: (top-level, applies to every configured output) which
          artifacts to write -- any combination of ``zarr``/``netcdf`` (the
          colocated/reduced dataset itself) and ``png`` (rendered plots).
        - ``otype``: the kind of output to compute -- see the cards below.

	.. grid:: 3

            .. grid-item-card:: Maps of statistics (``maps``)

                Maps of statistical metrics (mean and standard deviation). ``tfreq`` is not permitted.

                .. image:: images/data_map.png

                :download:`Download <images/data_map.png>`

            .. grid-item-card:: Time series (``timeseries``)

                Time series of statistical metrics (mean and standard deviation).

                .. image:: images/data_timeseries.png

                :download:`Download <images/data_timeseries.png>`

            .. grid-item-card:: Multiple vertical profiles (``mvprofiles``)

                Plot of multiple vertical profiles. ``vlevel`` is not permitted.

                .. image:: images/data_mvprofiles.png

                :download:`Download <images/data_mvprofiles.png>`

            .. grid-item-card:: Theta-S diagrams for multiple vertical profiles (``mdiagts``)

                Plot of a theta-s diagram of every vertical profiles.

                .. image:: images/data_mdiagts.png

                :download:`Download <images/data_mdiagts.png>`

            .. grid-item-card:: Unique vertical profiles (``uvprofiles``)

                Plot of unique vertical profiles. ``vlevel`` is not permitted.

            .. grid-item-card:: Theta-S diagram for a unique vertical profiles (``udiagts``)

                Plot of a theta-s diagram by profile. ``vlevel`` is not permitted.

            .. grid-item-card:: Selected vertical profiles (``vprofiles_sel``)

                One figure per time/depth group (``tfreq``, ``trange_seq``,
                ``vlevel`` or ``vrange`` must be configured to define the
                groups -- use ``mvprofiles`` for a bare metazone).

            .. grid-item-card:: Selected Theta-S diagrams (``diagts_sel``)

                Theta-S diagram, one figure per time/depth group (same
                grouping requirement as ``vprofiles_sel``).

            .. grid-item-card:: Vertical sections (``vsections``)

                Distance-vs-depth plot along a broken-line transect.
                Requires a ``section`` metazone parameter.

            .. grid-item-card:: Map series (``mapseries``)

                One map per native time step (not aggregated), color scale
                fixed once over the whole series. See ``vminmax`` and the
                mapseries-specific parameters below.

            .. grid-item-card:: Eddy detections PDF (``pdf_eddies``)

                Probability-density plot of eddy detections (max
                area/radius). Only for eddy-detection sources (``fmt`` in
                ``eddy_pet``, ``eddy_sacso``, ``eddy_shoot``).

        .. rubric:: ``vminmax`` and plot-rendering parameters

        Each output block also accepts, nested under its own name:

        - ``vminmax``: (optional) set colorbar/axis limits for each
          variable, overriding the automatic mean/std-based scaling.
          Format is a dictionnary such as ``vminmax = {'ptemp': (15,25), 'sal': (33,36)}``.
          Variable names are those of the Armoor pivot format (see :ref:`Armoor conventions <varconventions>`).

        The following parameters only take effect when ``otype=mapseries``,
        and only for vector variables (currents/wind, rendered as quiver
        arrows or wind barbs):

        - ``nstd``: (default ``2.5``) number of standard deviations around
          the series mean used for the automatic color-scale bounds, when
          ``vminmax`` isn't set for that variable.
        - ``vector_style``: ``quiver`` (default) or ``barbs``.
        - ``vector_scale``: (default ``1.0``) multiplier applied to the U/V
          *data values* before rendering, for either ``vector_style``.
        - ``quiver_scale``: (default: matplotlib's own autoscale)
          ``quiver``-only; passed straight through as matplotlib's own
          ``scale=`` (data units per arrow length -- smaller means longer
          arrows). Doesn't affect the data itself, unlike ``vector_scale``.
        - ``rarification``: (default: auto, ~30 arrows along the grid's
          longer axis) subsample every Nth grid point before drawing
          arrows/barbs, to keep the plot readable on high-resolution grids.
        - ``barbs_length`` / ``barbs_linewidth``: (defaults ``4.0``/``0.3``)
          only used when ``vector_style=barbs``.
        - ``clim``: (optional) name of another configured output to use as
          a reference climatology min/max, shown as an extra row in each
          frame's min/max table.
        - ``cbar_group``: (optional) name shared by several ``mapseries``
          outputs to pool their color-scale range, so they use the same
          fixed min/max instead of each being scaled independently.

Execution
---------

.. program-output:: armoor-data -h
   :shell:
   :returncode: 0
        
Workflow
--------

    1. Open, decode input files and apply filters --> Zarr files stored at ``./data/metazones/{metazone.name}/{data.name}/``.
    2. Interpolate/organize data in time and space if necessary, cleanup unecessary variables --> Zarr files stored at ``./data/interp/{metazone.name}/{data.name}/``.
    3. Compute outputs --> Zarr files stored at ``./data/output/{metazone.name}/{data.name}/{otype}/``.
    4. (if png format is given) Plots --> png files stored at ``./data/plot/{metazone.name}/``.

Pipeline control
-----------------

By default all stages run in sequence: *load (+ interpolation) → output →
plot*. ``armoor-data`` has no colocation stage (unlike ``armoor-comp-*``).
Each flag short-circuits the pipeline after the named stage:

.. list-table::
   :header-rows: 1
   :widths: 30 70

   * - Flag
     - Effect
   * - ``--filters-only``
     - Stop after loading (and interpolating).  Zarr files are written to
       ``data/interp/{metazone}/{data.name}/``.
   * - ``--no-plot``
     - Run load + output but skip the plot stage.
   * - ``--plot-only OTYPE``
     - Regenerate plots for a single output type from existing zarr files.
       Requires ``--input-json``.

HPC options
-----------

``--hosts-cfg PATH``
    Path to a *woom* ``hosts.cfg`` file.  When provided, armoor submits
    pipeline stages as Slurm/PBS jobs (Wave 0 → Wave 3) instead of running
    them in the foreground -- same mechanism as ``armoor-comp-*``, minus the
    colocation wave.  Walltimes/queue/cpu counts are configured via the
    ``[hpc]`` section of ``data.ini`` above.

``--load-only DATASET_KEY``
    *Internal — used by HPC Wave 0 jobs.*  Load (and interpolate) a single
    dataset for all metazones and write zarr paths to ``--jsonfile``.

``--input-zarrs JSON,...``
    *Internal — used by HPC Wave 1 jobs.*  Comma-separated list of
    zarr-paths JSON files produced by Wave 0.  When provided, the load
    stage is skipped.


.. argparse::
    :module: armoor.cli.main
    :func: get_parser_data
    :prog: armoor-data
    :nosubcommands:
