Armoor functionalities
======================

.. meta::
    :description: Armoor functionalities | comparison tools.

In this chapter you will find more details and specifics on the 9 armoor's functionalities.

1. SST
------

Comparison to satellite SST:

Available outputs :

* Global scatter plots : ``diag_disp_g``
* Selective scatter plots : ``diag_disp``
* Punctual time series : ``plot_ts_metr_ecart_point``
* Statistical time series : ``plot_ts_metr_stats``
* SST map : ``plot_map_metr_ecart``, ``plot_map_metr_biais``, ``plot_map_metr_RMSEc`` and ``plot_map_metr_RMSEcentree``.

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

This
2. PROF_HYDRO_VESSEL
--------------------

3. PROF_HYDRO_MOORING
---------------------

4. SECTION_HYDRO
----------------

5. CLIM_HYDRO
-------------

6. CURRENTS_HFR
---------------

7. CURRENTS_ADCP
----------------

8. CURRENTS_VMADCP
------------------

9. DRIFTERS
-----------

