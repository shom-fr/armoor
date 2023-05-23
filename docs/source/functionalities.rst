Armoor functionalities
======================

.. meta::
    :description: Armoor functionalities | comparison tools.

In this chapter you will find more details and specifics on the 9 armoor's functionalities.

1. SST
------

Comparison to satellite SST.

Available outputs :

* Global dispersion diagram  : ``diag_disp_g``
* Selective  dispersion diagram  : ``diag_disp``
* Punctual time series : ``plot_ts_metr_ecart_point``
* Statistical time series : ``plot_ts_metr_stats``
* SST map : ``plot_map_metr_ecart``, ``plot_map_metr_biais``, ``plot_map_metr_RMSEc`` and ``plot_map_metr_RMSEcentree``


2. PROF_HYDRO_VESSEL
--------------------

Comparison to hydrological profiles.

Available outputs :

* Variable map : ``plot_map_metr_ecart``, ``plot_map_metr_biais``, ``plot_map_metr_RMSEc`` and ``plot_map_metr_RMSEcentree``
* Global dispersion diagram  : ``diag_disp_g``
* Statistical time series : ``plot_ts_metr_stats``
* « Multi-profile » vertical plot : ``plot_profile_multi``
* « One-profile » vertical plot : ``plot_profile_u``
* « Multi-profile »  θ-S diagram : ``diag_ts_multi``
* « One-profile »  θ-S diagram : ``diag_ts_unique``


3. PROF_HYDRO_MOORING
---------------------

Comparison to hydrological moorings.

Available outputs :

* Statistical time series : ``plot_ts_metr_stats``


4. SECTION_HYDRO
----------------

Comparison to hydrological sections.

Available outputs :

* 3D variables : ``plot_variable_3d``
* 2D variables : ``plot_variable_2d``


5. CLIM_HYDRO
-------------

Comparison to hydrological climatologies.

Available outputs :

* Punctual time series : ``plot_ts_metr_ecart_point``
* Statistical time series : ``plot_ts_metr_stats``
* Maps : ``plot_map_metr_ecart``


6. CURRENTS_HFR
---------------

Comparison to HF radar surface currents.

Available outputs :

* Current maps : * Variable map : ``plot_map_metr_ecart``, ``plot_map_metr_biais``, ``plot_map_metr_RMSEc`` and ``plot_map_metr_RMSEcentree``
* Tidal current ellipsis : ``plot_tide_current_ellipses``
* Punctual time series : ``plot_ts_metr_ecart_point``


7. CURRENTS_ADCP
----------------

Comparison to ADCP measurements.

Available outputs :

* Hovmöller diagrams : ``plot_hovmoller``
* Tidal harmonic tables : ``harmonic_table``
* Tidal current ellipsis : ``plot_tide_current_ellipses``


8. CURRENTS_VMADCP
------------------

Comparison to VM-ADCP measurements.

Available outputs :

* 2D graphs  : ``plot_variable_3d``
* Stick plots : ``plot_stick_plot``


9. DRIFTERS
-----------

Comparison to drifter measurements.

Available outputs :

* Current maps along trajectory : ``map_current_trajectroy``
* Trajectory maps : ``map_trajectroy``
* Direction / distance difference plot : ``plot_diff_traj_dist``
