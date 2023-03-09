Armoor
======

.. meta::
    :description: Armoor | comparison tool for models and observations.

How to use armoor
-----------------

You will learn here how to use armoor comparison tool.
The command to use this script is ``armoor``.
To access directly to a specific functionality there are 9 more main scripts : ``armoor-sst``, ``armoor-prof_hydro_vessel``, ``armoor-prof_hydro_mooring``, ``armoor-section_hydro``, ``armoor-clim_hydro``, ``armoor-currents_hfr``, ``armoor-currents_ADCP``, ``armoor-currents_VMADCP`` and ``armoor-drifters``.

In this chapter we will focus on how to call ``armoor`` with a configuration file with the option ``--cfgfile``,
to add parameters or use only parameters in command line use the help option ``-h`` for more information.

There are 5 sections we can distinguish in the configuration file :

    #. Header : common part on the execution
    #. Observation : part relative to the observation
    #. Models : part relative to the models
    #. Meta-zones : filters applied to the datasets
    #. Outputs : in this section we specify what we want to plot with the remaining datasets.

1. Header
---------

In the header there are 5 attributes :

    * ``functionality`` : there are 9 functionalities : *sst*, *prof_hydro_vessel*, *prof_hydro_mooring*, *section_hydro*, *clim_hydro*, *currents_hfr*, *currents_ADCP*, *currents_VMADCP* and *drifters*. For more information refer to the :doc:`functionalities` chapter.
    * ``colocate`` : Put the model and observation dataset on the same grid defined according to the selected target: model's, observation's or auto (less dense grid, default).
    * ``output-path`` : directory path to store the outputs, if there is no path provided the plots will popup.
    * ``horizontal_step`` : @TODO
    * ``vertical_step`` : @TODO


2. Observation
--------------

To specify the observation there are 5 attributes that can be provided after model name:

    * ``name`` : observation name appearing in the plots.
    * ``path`` : path to the observation file(s).
    * ``type`` : observation type use if there is a specific method to open the dataset : *mouillage*, *LADCP* and *VMADCP*.
    * ``method`` : horizontal colocation method.
    * ``method-z`` : vertical colocation method if different from ``method``.

3. Models
---------

The model's section is very similar to the observation, the main difference is that we can provide as many models as we need to compare to the observation after ``[models]`` :

.. IMPORTANT::
    For each model, you must provide a unique model name between double brackets ``[[model_name]]`` then provide the same 5 attributes as the observation.

The only other difference is the values for ``type`` that are specific for the models : *HYCOM_currents*, *HYCOM_3D* and *CROCO_currents*.

4. Meta-zones
-------------

The *meta-zone* allow you to select a subset of the original dataset, here is the list of possible options with the associated description that can be provided after ``[[meta-zones]]``:

    * ``name`` : *meta-zone* name appearing in the title plots.

Relative to time restriction:

    * ``start`` : to only consider dates from a given date, the date can be relative (ex: -2, for two days ago) or absolute in the following format *YYYY-MM-DDTHH:mm:ss*.
    * ``end`` : to consider only dates up to a given date.
    * ``times`` : only the dates from this list will be kept.
    * ``time-highlight`` : the dates of this list will be highlighted on the time series.
    * ``interval`` : to group into intervals: hour(s), day(s), month, season(s) or year(s).
    * ``cyclic`` : this keyword makes it possible to consider only a period of the year expressed in months (january, february, march, april, may, june, july, august, september, october, november, december) or a series of several months ( between 2 and 11 consecutive letters from this list: *JFMAMJJASOND*)
    * ``time-restriction`` : two values for the start and end time, to only consider times in between (may straddle two days).

Relative to horizontal restriction :

    * ``cloud`` : to indicate the list of points of interest
    * ``radius`` : to expand the area of interest to a radius (in km), used in combination with 'cloud'
    * ``polygon`` : to consider only the region inside the polygon defined by a list of points.
    * ``bathy_min`` : minimum authorized bathymetry value. @TODO
    * ``bathy_max`` : maximum authorized bathymetry value. @TODO

Relative to vertical restriction :

    * ``depth`` : selection by z level, passing 1, 2 or 3 arguments as follows:

        #. an immersion (z=x0 meters);
        #. a list of immersions (z=x0, x1, x2 meters)
        #. a slice of water (z ∈ [x0 meters, x1 meters])

    * ``density`` : the selection of immersions and slices of water is done in the same way as with *depth*, except that instead of indicating depths in meters, we indicate potential densities.

Other restrictions :

    * ``quality`` : to set minimum and maximum quality thresholds.
    * ``vars`` : to select the variables of interest.

5. Outputs
----------

It's possible to ask for as many outputs as needed after ``[outputs]``.

.. IMPORTANT::

    For each output, you must provide a unique output name between double brackets ``[[output_name]]``.

.. NOTE::

    if an *output-path* is provided in the **header** a sub-folder will be created inside with **output_name** folder name.


For each output here is the list of possible options with the associated description that can be provided after an ``[[output_name]]``:

    * ``plot`` : plot options :

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
        #. ``diag_ts_unique``: single theta s diagram
        #. ``diag_ts_multi``: multi theta s diagram
        #. ``plot_ts_metr_stats``: @TODO
        #. ``plot_ts_metr_ecart_point``: @TODO
        #. ``diag_disp``: scatter plot
        #. ``diag_disp_g``: global scatter plot
        #. ``plot_map_metr_ecart``: 2D map with deviation metric
        #. ``plot_map_metr_biais``: 2D map with bias metric
        #. ``plot_map_metr_RMSEc``: @TODO
        #. ``plot_map_metr_RMSEcentree``: @TODO
        #. ``plot_profile_u``: @TODO
        #. ``plot_profile_multi``: @TODO

    * ``attribute`` : list of attributes to process
    * ``colormap`` : name of the colormap, ex: *solar*, *thermal*.
    * ``vmin`` : to fixe minimum value scale
    * ``vmax`` : to fixe maximum value scale
    * ``path_results_traj`` : path to store temporary dataset files
    * ``traj_duration_plot`` : @TODO
    * ``traj_freq_plot`` : @TODO
    * ``scale`` : @TODO
    * ``analysis_start`` : @TODO
    * ``analysis_end`` : @TODO
    * ``tidal_waves`` : @TODO
    * ``path_results`` : @TODO
    * ``path_comodo`` : @TODO