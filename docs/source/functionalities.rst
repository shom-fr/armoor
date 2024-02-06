Armoor functionalities
======================

.. meta::
    :description: Armoor functionalities | comparison tools.

In this chapter you will find more details and specifics on the 9 armoor's functionalities.

1. SST
------

Comparison to satellite SST.

Variables to plot
~~~~~~~~~~~~~~~~~

* Sea surface temperature : ``attribute = SST``

Available outputs
~~~~~~~~~~~~~~~~~

* Global dispersion diagram  : ``diag_disp_g``
    One plot per meta-zone, per model, for all selected data.
* Selective  dispersion diagram  : ``diag_disp``
    One plot per meta-zone, per model, and per date or interval (depending on the specified temporal segmentation).
* Punctual time series : ``plot_ts_metr_ecart_point``
    Time series of the statistics for specific points in the meta-zone parameters (e.g. ``cloud = [ [-8.8, 47.2], [-8.7, 47.3] ]``).
    If time intervals are defined  in the meta-zone parameters (e.g. ``interval = 2H``), the temporal statistics will be plotted : *difference, bias, centered RMSE, RMSE*.
    Otherwise, only the *difference* metric will be plotted.
* Statistical time series : ``plot_ts_metr_stats``
    Time series of statistical spatial metrics : *difference, bias, centered RMSE, RMSE*.
    If time intervals are defined in the meta-zone parameters (e.g. ``interval = 2H`` ), the statistics will be spatiotemporal.
    Otherwise the statistics will only be spatial.
* SST map : ``plot_map_metr_ecart``, ``plot_map_metr_biais``, ``plot_map_metr_RMSE`` and ``plot_map_metr_RMSEc``
    Maps for each meta-zone based of the statistical metrics : *difference, bias, centered RMSE, RMSE*.
    If time intervals are defined in the meta-zone parameters (e.g. ``interval = 2H``), the temporal statistics will be plotted.
    Otherwise, only the *difference* metric will be plotted.

2. PROF_HYDRO_VESSEL
--------------------

Comparison to hydrological profiles.

.. NOTE::

    Some outputs of this functionality require to specify the radius of the disk around an observation within which model data are considered must be defined in the meta-zone parameters (e.g. ``radius = 15``, in kilometers).

Variables to plot
~~~~~~~~~~~~~~~~~

* Potential temperature : ``attribute = ptemp``
* Salinity : ``attribute = sal``
* Potential density : ``attribute = pdens``
* In-situ temperature : ``attribute = temp``
* Sound speed : ``attribute = sound_speed``

Available outputs
~~~~~~~~~~~~~~~~~

* Variable map : ``plot_map_metr_ecart``, ``plot_map_metr_biais``, ``plot_map_metr_RMSE`` and ``plot_map_metr_RMSEc``
    Maps for each meta-zone based of the statistical metrics : *difference, bias, centered RMSE, RMSE*.
    If time intervals are defined in the meta-zone parameters (e.g. ``interval = 2H``), the temporal statistics will be plotted, one plot per interval.
    If vertical slices are defined in the meta-zone parameters (e.g. ``slice = [[0,5],[5,10],[20,30]]``), the vertical statistics will be plotted, one plot per vertical slice.
    If vertical immersion are defined in the meta-zone parameters (e.g. ``depth = 0,5,20``), only the *difference* metric will be plotted, one plot per immersion.
* Global dispersion diagram  : ``diag_disp_g``
    One plot per meta-zone, per model, for all selected data.
* Selective  dispersion diagram  : ``diag_disp``
    One plot per meta-zone, per model, and per date or interval (depending on the specified temporal segmentation).
* Statistical time series : ``plot_ts_metr_stats``
    Time series of statistical spatial metrics : *difference, bias, centered RMSE, RMSE*.

    **Time intervals must be defined in the meta-zone parameters (e.g. ``interval = 2H``).**

    If vertical immersion are defined in the meta-zone parameters (e.g. ``depth = 0,5,20``), the horizontal statistics will be plotted, one plot per immersion.
    If vertical slices are defined in the meta-zone parameters (e.g. ``slice = [[0,5],[5,10],[20,30]]``), the horizontal and vertical statistics will be plotted, one plot per vertical slice.
* « Multi-profile » vertical plot : ``plot_profile_multi``
    Vertical profile plot for each variable, meta-zone, and model over the entire period and time interval, one plot for all profiles.

    **The radius of the disk around an observation within which model data are considered must be defined in the meta-zone parameters (e.g. ``radius = 15``, in kilometers).**

    **Time intervals must be defined in the meta-zone parameters (e.g. ``interval = 2H``).**

    The plot will display observed profiles, nearest model profiles, mean profile of observations and model profiles and standard deviation of observations and model.
* « One-profile » vertical plot : ``plot_profile_u``
    Vertical profile plot for each variable, meta-zone, and model over the entire period and time interval, one plot per profile.

    **The radius of the disk around an observation within which model data are considered must be defined in the meta-zone parameters (e.g. ``radius = 15``, in kilometers).**


    The plot will display observed profile, nearest model profile and standard deviation of model profiles within the disk.
* « Multi-profile »  θ-S diagram : ``diag_ts_multi``
    Plot of potential temperature versus salinity for each defined meta-zone and model over the entire period and time interval, one plot for all profiles.

    **The radius of the disk around an observation within which model data are considered must be defined in the meta-zone parameters (e.g. ``radius = 15``, in kilometers).**

    **Time intervals must be defined in the meta-zone parameters (e.g. ``interval = 2H``).**

    The plot will display observed profiles, nearest model profiles and mean profile of observations and model profile.
* « One-profile »  θ-S diagram : ``diag_ts_unique``
    Plot of potential temperature versus salinity for each defined meta-zone and model over the entire period and time interval, one plot per profile.

    The plot will display observed profiles and nearest model profiles.

3. PROF_HYDRO_MOORING
---------------------

Comparison to hydrological moorings.

Variables to plot
~~~~~~~~~~~~~~~~~

* Potential temperature : ``attribute = ptemp``
* Salinity : ``attribute = sal``
* Potential density : ``attribute = pdens``
* In-situ temperature : ``attribute = temp``
* Sound speed : ``attribute = sound_speed``

Available outputs
~~~~~~~~~~~~~~~~~

* Statistical time series : ``plot_ts_metr_stats``
    Time series of statistical spatial metrics : *difference, bias, centered RMSE, RMSE*. One plot per mooring depth.

    If time intervals are defined in the meta-zone parameters (e.g. ``interval = 2H``), the temporal statistics will be plotted, one plot per interval.

    Otherwise, only the *difference* metric will be plotted.


4. SECTION_HYDRO
----------------

Comparison to hydrological sections.

.. NOTE::

    This functionality requires to specify the 2D projection grid with the ``horizontal_step`` (kilometers) and ``vertical_step`` (meters) in the configuration file.


Variables to plot
~~~~~~~~~~~~~~~~~

* Potential temperature : ``attribute = ptemp``
* Salinity : ``attribute = sal``
* Potential density : ``attribute = pdens``
* In-situ temperature : ``attribute = temp``
* Geostrophic current : ``attribute = current_geo``
* Mixed layer depth : ``attribute = mld``

Available outputs
~~~~~~~~~~~~~~~~~

* 3D variables : ``plot_variable_3d``
    2D graphs (variable along time and depth) per variable and per section of the statistical metrics : *difference, bias, centered RMSE, RMSE*.
* 2D variables : ``plot_variable_2d``
    Time series of the variable statistical metrics : *difference, bias, centered RMSE, RMSE*.


5. CLIM_HYDRO
-------------

Comparison to hydrological climatologies.

Variables to plot
~~~~~~~~~~~~~~~~~

* Potential temperature : ``attribute = ptemp``
* Salinity : ``attribute = sal``

Available outputs
~~~~~~~~~~~~~~~~~

* Maps : ``plot_map_metr_ecart``
    Maps for each variable, month and immersion of the meta-zone, of the *difference* statistic metric.
* Statistical time series : ``plot_ts_metr_stats``
    Time series of statistical spatial metrics : *difference, bias, centered RMSE, RMSE*. One plot per variable and vertical immersion.
* Punctual time series : ``plot_ts_metr_ecart_point``
    Time series of the difference statistic metric for specific points in the meta-zone parameters (e.g. ``cloud = [ [-8.8, 47.2], [-8.7, 47.3] ]``).  One plot per variable and vertical immersion.

6. CURRENTS_HFR
---------------

Comparison to HF radar surface currents.

.. NOTE::

    Some outputs of this functionality require to specify additional parameters to plot tidal constituent: ``analysis_start``, ``analysis_end``, ``tidal_waves`` and ``tide_tool``.

Variables to plot
~~~~~~~~~~~~~~~~~

* Total current : ``attribute = current``
* Residual current : ``attribute = current_res``
* Tidal current harmonic consituents : ``plot = plot_map_current_harmonic`` or ``plot = plot_tide_current_ellipses``


Available outputs
~~~~~~~~~~~~~~~~~

* Current maps : ``plot_map_metr_ecart``, ``plot_map_metr_biais``, ``plot_map_metr_RMSE`` and ``plot_map_metr_RMSEc``
    Maps for each variable and meta-zone, of the statistical metrics : *difference, bias, centered RMSE, RMSE*.
* Tidal current harmonic consituents maps : ``plot_map_harm``
    Maps of the *difference* statistic metric for each specified tidal wave, of the tidal current amplitude and phase.

    **These maps require to specify the additional parameters : ``analysis_start``, ``analysis_end`` and ``tidal_waves``**.
* Tidal current ellipsis : ``plot_tide_current_ellipses``
    Maps of tidal current ellipses from model and observation at points in the meta-zone. One map per tidal wave.

    **These ellipses require to specify the additional parameters : ``analysis_start``, ``analysis_end`` and ``tidal_waves``**.
* Punctual time series : ``plot_ts_metr_ecart_point``
    Time series of the statistics for specific points in the meta-zone parameters (e.g. ``cloud = [ [-8.8, 47.2], [-8.7, 47.3] ]``).
    If time intervals are defined  in the meta-zone parameters (e.g. ``interval = 2H``), the temporal statistics will be plotted : *difference, bias, centered RMSE, RMSE*.
    Otherwise, only the *difference* metric will be plotted.
* Statistical time series : ``plot_ts_metr_stats``
    Time series of statistical spatial metrics : *difference, bias, centered RMSE, RMSE*.
    If time intervals are defined in the meta-zone parameters (e.g. ``interval = 2H`` ), the statistics will be spatiotemporal.
    Otherwise the statistics will only be spatial.

7. CURRENTS_ADCP
----------------

Comparison to ADCP measurements.

.. NOTE::

    Some outputs of this functionality require to specify additional parameters to plot tidal constituent: ``analysis_start``, ``analysis_end``, ``tidal_waves`` and ``tide_tool``.


Variables to plot
~~~~~~~~~~~~~~~~~

* Total current : ``attribute = current``
* Residual current : ``attribute = current_res``
* Baroclinic current : ``attribute = current_bc``
* Tidal current harmonic consituents : ``plot = plot_map_current_harmonic`` or ``plot = plot_tide_current_ellipses``


Available outputs
~~~~~~~~~~~~~~~~~

* Hovmöller diagrams : ``plot_hovmoller``
    Hovmöller 2D graphs (variable along time and depth) per variable and per section of the *difference* statistical metrics.
* Tidal harmonic tables : ``harmonic_table``
    Tables per harmonic component and per current component.
    Diplays values for observed and modelled current amplitudes and phase and their difference.
* Tidal current ellipsis : ``plot_tide_current_ellipses``
   Maps of tidal current ellipses from model and observation at points in the meta-zone. One map per tidal wave and per vertical immersion or slice.

   **These ellipses require to specify the additional parameters : ``analysis_start``, ``analysis_end``, ``tidal_waves`` and ``tide_tool``**.

8. CURRENTS_VMADCP
------------------

Comparison to VM-ADCP measurements.

.. NOTE::

    This functionality requires to specify the 2D projection grid with the ``horizontal_step`` (kilometers) and ``vertical_step`` (meters) in the configuration file.

Variables to plot
~~~~~~~~~~~~~~~~~

* Total current : ``attribute = current``
* Baroclinic current : ``attribute = current_bc``


Available outputs
~~~~~~~~~~~~~~~~~

* 2D graphs  : ``plot_variable_3d``
    2D graphs (variable along time and depth) per variable and per section of the *difference* statistical metrics.
* Stick plots : ``plot_stick_plot``
    Stick plot diagrams per radial and per specified vertical immersion or slice.

9. DRIFTERS
-----------

Comparison to drifter measurements.

.. NOTE::

    Some outputs of this functionality require to specify additional parameters to compute trajectories : ``traj_freq_plot`` and ``traj_duration_plot``.


Variables to plot
~~~~~~~~~~~~~~~~~

* Total current : ``attribute = current``

Available outputs
~~~~~~~~~~~~~~~~~

* Current maps along trajectory : ``map_current_trajectroy``
    Map of current along the drifter trajectory from the model and the observation.
* Trajectory maps : ``map_trajectroy``
    Map of the observed and simulated trajectory of the drifter.

    ** The model trajectories are re-initialized at the specified frequency (e.g. ``traj_freq_plot = 5``) and calculated over the specified integration period (e.g. ``traj_duration_plot = 10``)
* Direction / distance difference plot : ``plot_diff_traj_dist``
    Evolution over the trajectory duration of the average distance and direction deviation between modeled and observed trajectory.
