Armoor
======

.. meta::
    :description: Armoor | comparison tool for models and observations.

How to use armoor
-----------------

You will learn here how to use armoor comparison tool.
The command to use this script is ``armoor``.
To access directly to a specific functionality there are 9 additional main scripts : ``armoor-sst``, ``armoor-prof_hydro_vessel``, ``armoor-prof_hydro_mooring``, ``armoor-section_hydro``, ``armoor-clim_hydro``, ``armoor-currents_hfr``, ``armoor-currents_ADCP``, ``armoor-currents_VMADCP`` and ``armoor-drifters``.

In this chapter we will focus on how to call ``armoor`` with a configuration file using the option ``--cfgfile``.
To add parameters or use only parameters in command line, please refer to the help using the ``-h`` option for more information.

We can distinguish 5 sections in the configuration file:

    #. Header : common part of the execution
    #. Observation : part relative to the observation
    #. Models : part relative to the models
    #. Meta-zones : filters applied to the datasets
    #. Outputs : in this section we specify what we want to plot with the remaining datasets.

1. Header
---------

In the header there are 5 attributes:

    * ``functionality`` : There are 9 functionalities : *sst*, *prof_hydro_vessel*, *prof_hydro_mooring*, *section_hydro*, *clim_hydro*, *currents_hfr*, *currents_ADCP*, *currents_VMADCP* and *drifters*. For more information refer to the :doc:`functionalities` chapter.
    * ``colocate`` : Put the model and observation dataset on the same grid defined according to the selected target: model's, observation's or auto (less dense grid, default).
    * ``output-path`` : Directory path to store the outputs. If no path is provided the plots will pop up.
    * ``horizontal_step`` : @TODO
    * ``vertical_step`` : @TODO


2. Observation
--------------

To specify the observation, 5 attributes can be provided after ``[observation]``:

    * ``name`` : Observation name appearing in the plots.
    * ``path`` : Path to the observation file(s).
    * ``type`` : Observation type, to be used if there is a specific method to open the dataset : *mouillage*, *LADCP* and *VMADCP*.
    * ``method`` : Horizontal colocation method.
    * ``method-z`` : Vertical colocation method if different from ``method``.

3. Models
---------

The model's section is very similar to the observation's one, the main difference is that we can provide as many models as we need to compare to the observation after ``[models]`` :

.. IMPORTANT::
    For each model, you must provide a unique model name in double brackets ``[[model_name]]`` then provide the same 5 attributes as the observation.

The only other difference concerns the ``type`` values, that are specific regarding the models : *HYCOM_currents*, *HYCOM_3D* and *CROCO_currents*.

4. Meta-zones
-------------

The *meta-zone* allows you to select a subset of the original dataset. Here is the list of possible options (with their associated description) that can be provided after ``[[meta-zones]]``:

    * ``name`` : *meta-zone* name appearing in the title plots.

Relative to time restriction:

    * ``start`` : To consider only the dates from a given date. The dates can be relative (ex: -2, for two days ago) or absolute in the following format *YYYY-MM-DDTHH:mm:ss*.
    * ``end`` : To consider only the dates up to a given date.
    * ``times`` : Only the dates from this list will be kept.
    * ``time-highlight`` : The dates of this list will be highlighted in the time series.
    * ``interval`` : To group into intervals: hour(s), day(s), month, season(s) or year(s).
    * ``cyclic`` : This keyword makes it possible to consider only a period of the year expressed in months (january, february, march, april, may, june, july, august, september, october, november, december) or a series of several months ( between 2 and 11 consecutive letters from this list: *JFMAMJJASOND*)
    * ``time-restriction`` : Two values for the start and end times. To consider only the times in between (may straddle two days).

Relative to horizontal restriction:

    * ``cloud`` : To indicate the list of points of interest
    * ``radius`` : To expand the area of interest to a radius (in km). This option is in combination with 'cloud'.
    * ``polygon`` : To consider only the region inside the polygon defined by a list of points.
    * ``bathy_min`` : Minimum authorized bathymetry value.
    * ``bathy_max`` : Maximum authorized bathymetry value.

Relative to vertical restriction:

    * ``depth`` : Selection by z level, passing 1, 2 or 3 arguments as follows:

        #. an immersion (z=x0 meters);
        #. a list of immersions (z=x0, x1, x2 meters)
        #. a slice of water (z ∈ [x0 meters, x1 meters])

    * ``density`` : The selection of immersions and slices of water is done in the same way as with *depth*, except that we indicate potential densities (instead of depths in meters).

Other restrictions :

    * ``quality`` : To set minimum and maximum quality thresholds.
    * ``vars`` : To select the variables of interest.

5. Outputs
----------

It is possible to ask for as many outputs as needed after ``[outputs]``.

.. IMPORTANT::

    For each output, you must provide a unique output name in double brackets ``[[output_name]]``.

.. NOTE::

    If an *output-path* is provided in the **header** a sub-folder will be created inside with **output_name** folder name.


For each output here is the list of possible options (with their associated description) that can be provided after an ``[[output_name]]``:

    * ``plot`` : Plot options :

        #. ``map_current_trajectroy`` : @TODO
        #. ``plot_stick_plot``: @TODO
        #. ``plot_diff_traj_dist``: @TODO
        #. ``map_trajectroy``: @TODO
        #. ``plot_map_current_harmonic``: @TODO
        #. ``plot_tide_current_ellipses``: @TODO
        #. ``harmonic_table``: @TODO
        #. ``plot_hovmoller``: @TODO
        #. ``plot_variable_3d``: @TODO
        #. ``plot_variable_2d``: @TODO
        #. ``plot_ts_metr_point``: @TODO
        #. ``diag_ts_unique``: Single theta s diagram
        #. ``diag_ts_multi``: Multi theta s diagram
        #. ``plot_ts_metr_stats``: @TODO
        #. ``plot_ts_metr_ecart_point``: @TODO
        #. ``diag_disp``: Scatter plot
        #. ``diag_disp_g``: Global scatter plot
        #. ``plot_map_metr_ecart``: 2D map with deviation metric
        #. ``plot_map_metr_biais``: 2D map with bias metric
        #. ``plot_map_metr_RMSEc``: @TODO
        #. ``plot_map_metr_RMSEcentree``: @TODO
        #. ``plot_profile_u``: @TODO
        #. ``plot_profile_multi``: @TODO

    * ``attribute`` : List of attributes to process
    * ``colormap`` : Name of the colormap, ex: *solar*, *thermal*.
    * ``vmin`` : To fix minimum value scale
    * ``vmax`` : To fix maximum value scale
    * ``path_results_traj`` : Path to store temporary dataset files
    * ``traj_duration_plot`` : @TODO
    * ``traj_freq_plot`` : @TODO
    * ``scale`` : @TODO
    * ``analysis_start`` : @TODO
    * ``analysis_end`` : @TODO
    * ``tidal_waves`` : @TODO
    * ``path_results`` : @TODO
    * ``path_comodo`` : @TODO



Example
-------

Example of configuration file for a *global scatter plots* and a *statistical time series*::

    functionality = sst
    colocate = auto

    [observation]
        name = "L3 METEOFRANCE"
        path = data/test_f1/OBS/nov_METEOFRANCE-EUR-SST_L3MONOSENSOR_NRT-OBS_V2-AVHRR_METOP_B_FULL_TIME_SERIE_1621503492101.nc
        method = nearest

    [models]
        [[HYCOM]]
            name = HYCOM
            path = data/test_f1/MODEL/HYCOMsst_2D.nc
            method = nearest

    [outputs]
        [[plot_diag_disp]]
            plot = diag_disp_g
            colormap = thermal
        [[ts_stats]]
            plot = plot_ts_metr_stats



