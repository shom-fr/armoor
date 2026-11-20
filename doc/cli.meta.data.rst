.. _clidata:

Command-line interfaces for data
################################

Configuration file
------------------

    Armoor executables dedicated to plot data have to be associated with a configuration file based on `data.ini`:
        .. literalinclude:: ../armoor/cli/data.ini
               :language: ini
               
See details for outputs parameters below in :ref:`plot-rendering-parameters`.
               
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
                
*Eddy-detection plots*
^^^^^^^^^^^^^^^^^^^^^^

``armoor-data`` allows specific plots for eddy-detection sources only (``fmt`` in
``eddy_pet``, ``eddy_sacso``, ``eddy_shoot``).

Note that histograms and time series allow counting of eddies, which 
could lead to multiple counting of a single eddy due to missing eddy-tracking 
variables in the current version. Such plots are therefore only allowed for 
single-timestep datasets for now, so that timeseries are not functional
in this version.

    Eddy-typical variables can be automatically used for plotting, depending on their
    availability in the decoded dataset or computability :
        - ``vmax_area`` : area enclosed in the maximum velocity contour, 
        - ``vmax_radius`` : equivalent radius of a circle of ``vmax_area`` size.
    Tracking variables will be included in Armoor next versions.
                
    .. grid:: 3

            .. grid-item-card:: Map of eddy contours (``map_eddies``)

                Plot a map of eddy contours for each timestep of a dataset
                (instantaneous), with distincts cyclones and anticyclones.
                
                .. image:: images/map_sacso_2016-07-13T00:00:00.png

                :download:`Download <images/map_sacso_2016-07-13T00:00:00.png>`
                
            .. grid-item-card:: Map of eddy contours occurence on a custom 
                                grid (``map_occurence_eddies``)

                Plot a map of eddy contour occurence  in a time range 
                (``trange_seq``, ``tbound`` or all available timesteps) 
                for a defined box size (``map_boxsize`` config option). 
                Occurence is given as the percentage of times a given cell 
                allows an eddy contour. Three maps are plotted :
                all eddies, cyclones and anticyclones.

                .. image:: images/map_occurence_sacso_20160701_20160715_all_eddies.png

                :download:`Download <images/map_occurence_sacso_20160701_20160715_all_eddies.png>`
                
            .. grid-item-card:: Histograms for eddy variables (``histogram_eddies``)

                Plot a histogram of number of eddies for every eddy variables available, 
                with distincts cyclones and anticyclones.

                .. image:: images/hist_vmax_area_sacso_20160701_20160715.png

                :download:`Download <images/hist_vmax_area_sacso_20160701_20160715.png>`
                
            .. grid-item-card:: Timeseries (``timeseries_eddies``)

                Plot a timeserie of the number of eddies throughout a period of time.
                Not functional for now due to missing eddy tracking variables.
                
            .. grid-item-card:: PDF for eddy variables (``pdf_eddies``)

                Plot a Probability Density Function for every eddy variables available, 
                with distincts cyclones and anticyclones.

                .. image:: images/pdf_vmax_radius_sacso_20160701_20160715.png

                :download:`Download <images/pdf_vmax_radius_sacso_20160701_20160715.png>`
                

.. _plot-rendering-parameters:                        

*Plot-rendering parameters*
^^^^^^^^^^^^^^^^^^^^^^^^^^^

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
          
        Other ``otype``-specific parameters :
        
        - ``map_boxsize`` : cell size in degrees to compute occurence in ``map_occurence_eddies`` (defaults 0.2°)

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
