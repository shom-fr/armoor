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
    * ``output_path`` : Directory path to store the outputs. If no path is provided the plots will pop up.
    * ``horizontal_step`` : The products can be projected on a grid with the horizontal resolution, in meters, you set.
    * ``vertical_step`` : The products can be projected on a grid with the vertical resolution, in meters, you set. If you intend to colocate the products on an HYCOM product grid, this option is required.


2. Observation
--------------

To specify the observation, 5 attributes can be provided after ``[observation]``:

    * ``name`` : Observation name appearing in the plots.
    * ``path`` : Path to the observation file(s).
    * ``type`` : Observation type, to be used if there is a specific method to open the dataset : *WOA18*, *CMEMS*, *scanfish*, *seasoar*, *mouillage*, *LADCP* and *VMADCP*. Any other type of observation will be automatically decoded.
    * ``method`` : Horizontal colocation method.
    * ``method_z`` : Vertical colocation method if different from ``method``.

If several paths are given, the files will be merged along the time dimension.

3. Models
---------

The model's section is very similar to the observation's one, the main difference is that we can provide as many models as we need to compare to the observation after ``[models]`` :

.. IMPORTANT::
    For each model, you must provide a unique model name in double brackets ``[[model_name]]`` then provide the same 5 attributes as the observation.

The only other difference concerns the ``type`` values, that are specific regarding the models : *CROCO*, *CROCO_currents*, *HYCOM_currents*, *HYCOM_3D* and *CORA*. Any other type of model will be automatically decoded.

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
    * ``radius`` : To expand the area of interest to a radius (in km). This option is in combination with ``[[cloud]]``.
    * ``polygon`` : To consider only the region inside the polygon defined by a list of points.
    * ``bathy_min`` : Minimum authorized bathymetry value.
    * ``bathy_max`` : Maximum authorized bathymetry value.

Relative to vertical restriction:

    * ``depth`` : Selection by z level, passing 1, 2 or 3 arguments as follows:

        #. an immersion (z=x0 meters);
        #. a list of immersions (z=x0, x1, x2 meters)
        #. a slice of water (z ∈ [x0 meters, x1 meters])

    * ``density`` : The selection of immersions and slices of water is done in the same way as with *depth*, except that we indicate potential densities (instead of depths in meters).
    * ``slice`` : To group into vertical slices, in meters.

Other restrictions :

    * ``quality`` : To set minimum and maximum quality thresholds on a variable.
    * ``vars`` : To select the variables of interest.

5. Outputs
----------

It is possible to ask for as many outputs as needed after ``[outputs]``.

.. IMPORTANT::

    For each output, you must provide a unique output name in double brackets ``[[output_name]]``.

.. NOTE::

    If an *output_path* is provided in the **header** a sub-folder will be created inside with **output_name** folder name.


For each output here is the list of possible options (with their associated description) that can be provided after an ``[[output_name]]``:

    * ``plot`` : Plot options :

        #. ``map_current_trajectroy`` : Plot the current vectors along the trajectories.
        #. ``plot_stick_plot``: Plot stick plots for current data
        #. ``plot_diff_traj_dist``: Plot the difference in terms of distance and direction between the model and observation trajectories.
        #. ``map_trajectroy``: Plot the modelled and observed trajectories
        #. ``plot_map_current_harmonic``: Plot the map of amplitude, phase and norm of each tidal harmonic.
        #. ``plot_tide_current_ellipses``: Plot the map with the tidal current ellipses
        #. ``harmonic_table``: Create a table per tidal wave and per current constituent(u & v) with, for each depth, the amplitude and phase of the observation and the model and their differences
        #. ``plot_hovmoller``: Plot 2d figure, Hovmoller diagram
        #. ``plot_variable_3d``: Plot 3D variable section difference between observation and model
        #. ``plot_variable_2d``: Plot 2d figure, Hovmoller diagram
        #. ``plot_ts_metr_point``: Plot punctual time series of model and observation and the associated metric.
        #. ``diag_ts_unique``: Single theta s diagram
        #. ``diag_ts_multi``: Multi theta s diagram
        #. ``plot_ts_metr_stats``: Plot statistical time series of model and observation.
        #. ``diag_disp``: Scatter plot dispersion diagram
        #. ``diag_disp_g``: Global scatter plot dispersion diagram
        #. ``plot_map_metr_ecart``: 2D map with deviation metric
        #. ``plot_map_metr_biais``: 2D map with bias metric
        #. ``plot_map_metr_RMSEc``: Plot RMSE map
        #. ``plot_map_metr_RMSEcentree``: Plot centered RMSE map
        #. ``plot_profile_u``: Create unique vertical profiles figures of a variable
        #. ``plot_profile_multi``: Create multi vertical profiles figures of a variable

    * ``attribute`` : List of attributes to process
    * ``colormap`` : Name of the colormap, ex: *solar*, *thermal*
    * ``vmin`` : To fix minimum value scale
    * ``vmax`` : To fix maximum value scale
    * ``dvmin`` : To fix minimum comparison figure value scale
    * ``dvmax`` : To fix maximum comparison figure value scale
    * ``path_results_traj`` : Path to store temporary dataset files
    * ``traj_duration_plot`` : Duration of the simulated trajectory to plot
    * ``traj_freq_plot`` : Frequency at which the trajectories are plotted (ex : one ine 3)
    * ``scale`` : Scale to adapt the size of the ellipses/vectors
    * ``analysis_start`` : Date to start the harmonic analysis
    * ``analysis_end`` : Date to end the harmonic analysis
    * ``tidal_waves`` : List of the tidal waves to compute. At least 1 tidal wave must be given, a good start is M2 S2 K1 O1 P1 Q1.
    * ``path_results`` : Path where to save the detided result files
    * ``path_comodo`` : Path of the comodo-detidor executable
    * ``env_comodo`` : Commandline needed to load the comodo environment : "module load sirocco". For more information, read ~dallain/softs/LISEZMOI.rst



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




Run test
--------

Unit tests verify the correct opening and decoding of observation and model products, as well as the meta zones and some internally calculated variables.
To run the unit tests, use the following command::

    pytest your_path_to/tests/uni/test_open_data.py
    pytest your_path_to/tests/uni/test_meta_zone.py
    pytest your_path_to/tests/uni/test_read_var.py

Integration tests verify the accurate running of the required features. To run the integration tests use the following command::

    pytest your_path_to/tests/int/base/test_f1.py
    pytest your_path_to/tests/int/base/test_f2.py
    pytest your_path_to/tests/int/base/test_f3.py
    pytest your_path_to/tests/int/base/test_f4.py
    pytest your_path_to/tests/int/base/test_f5.py
    pytest your_path_to/tests/int/base/test_f6.py
    pytest your_path_to/tests/int/base/test_f7.py
    pytest your_path_to/tests/int/base/test_f8.py
    pytest your_path_to/tests/int/base/test_f9.py
    pytest your_path_to/tests/int/base/test_VA.py

Note that for ``test_6`` and ``test_7`` you will need to specify the parameters : ``path_comodo`` and
``env_comodo``.


In both cases, you will need to have a ``/path/to/output/tests/P1/`` with the files from the delivered data archive.
In the folder where you will run ``pytest`` please create a file named **tests.cfg**
and add the following lines by replacing ``/path/to/output/tests/P1/``, ``/path/to/comodo/`` and ``your commandline`` with your information::

    path_p1 = '/path/to/output/tests/P1/'
    path_comodo = '/path/to/comodo/'
    env_comodo = 'your commandline'

.. NOTE::

    The ``data`` folder from the archive must be in the ``path_p1`` folder.

    For more information on ``path_comodo`` and ``env_comodo`` refer to section **5. Outputs** above.
