Forecaster script
=================

.. meta::
    :description: Forecaster script | You can create images for forecaster wed interface.

You will learn here how to create and customise the creation of images for the forecaster web interface.


How to use
----------

The command to use this script is ``armoor-script`` which comes with three mandatory options : *output-folder*, *input-folder* and *input-configuration*.

* *output-folder* : Folder path to store outputs created by the script for the web interface.
* *input-folder* : Root folder path from which the data is collected to created images for the forecaster web interface.
* *input-configuration* : Configuration file for image generation

This command generates a **.tgz** file containing all the created images and files with the right tree structure for the forecaster web interface.

Details on input folder
~~~~~~~~~~~~~~~~~~~~~~~

The entries folder should contain and be structured as follows ::

    ├── config_reg_YYYYMMDD
    │   ├── atmfrc
    │   │   ├── cumul
    │   │   │   └── arpege_*_cumul.grib
    │   │   └── insta
    │   │       └── arpege_*_insta.grib
    │   ├── model
    │   │   ├── h_3D_[reg].nc
    │   │   ├── saln_3D_[reg].nc
    │   │   ├── sigma_3D_[reg].nc
    │   │   ├── ssh_2D_[reg].nc
    │   │   ├── sss_2D_[reg].nc
    │   │   ├── sst_2D_[reg].nc
    │   │   ├── temp_3D_[reg].nc
    │   │   ├── u_2D_[reg].nc
    │   │   ├── u_3D_[reg].nc
    │   │   ├── v_2D_[reg].nc
    │   │   └── v_3D_[reg].nc
    │   ├── rivers
    │   │   └── GL_TS_RF_EXSC*.nc
    │   ├── sstl4
    │   │   └── *.nc
    │   └── woa18
    │       ├── woa18_decav_s03_04.nc
    │       └── woa18_decav_t03_04.nc

With ``config_reg`` the *name* given in the configuration file si bellow and *YYYYMMDD* the production day (day of execution).

Details on configuration file
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

There is two main sections ``[config_reg]`` and ``[parameters]``.

Section *config_reg*
____________________

The name of the regional configuration must be the same as the folder inside the *input-folder* folder.
Example if the production day is *20230307* and the regional configuration is *hycom3d_med* the folder name
is *hycom3d_med_20230307* and the content of this section in the configuration file is as follow ::

    [config_reg]
        name = "hycom3d_med"

In this example the **.tgz** output file will be *hycom3d_med_20230307.tgz*.

Section *parameters*
____________________

There can be as many parameters as need, each parameter is composed with a header and 4 sub-parameters.

Header
######

The header can be composed of three parts :
    1. ``[[parameter_name]]`` : must be unique and with only *letters*, *numbers* and *_*.
    2. ``name`` is here only to make the configuration file more readable.
    3. ``[[[extent]]]`` is an optional parameter, it must include the minimum, maximum longitudes and latitudes with the following attributes : *lon_min*, *lon_max*, *lat_min* and *lat_max*.

Sub-parameters
##############

After the header the are 4 sub-parameters which must be named in triple square brackets param_* ( 1 to 4).
Each sub-parameter can have combination of attributes depending on we want to display in the forecaster web interface.
Here are the different attributes and their purpose :

* ``name`` : Name displayed in the final image, plot or chart.

* ``func`` : Visualisation functions, can either of the following :

    #. ``visu_temp`` : 2D map of temperature or sea surface temperature.
    #. ``visu_sal`` : 2D map of salinity or sea surface salinity.
    #. ``visu_diff_sst`` : 2D difference map of sea surface temperature.
    #. ``visu_diff_sss`` : 2D difference map of sea surface salinity.
    #. ``visu_current`` : 2D map with quivers for current.
    #. ``visu_windforcing`` : 2D map with quivers for wind.
    #. ``visu_solarflux`` : 2D map with quivers for solar flux.
    #. ``visu_runoff`` : River runoff time series chart, one line per buoy.
    #. ``visu_precip`` : 2D map total precipitation.
    #. ``visu_mixedlayer`` : Mixed layer thickness computed from model.
    #. ``visu_mixedlayer_clim`` : Mixed layer thickness computed from climatology.

* ``var`` : Variable of interest :

    #. ``temp`` : temperature
    #. ``sst`` : sea surface temperature
    #. ``salt`` : salinity
    #. ``sss`` : sea surface salinity
    #. ``uv`` : current
    #. ``suv`` : surface current
    #. ``hfsen`` : solar flux
    #. ``RVFL`` : runoff
    #. ``tp`` : total precipitation

* ``depth`` : depth of interest in meters.

* ``obs`` : relative path to observation for comparison with model functions *visu_diff_sst* and *visu_diff_sss*.

* ``forcing_model`` : relative path to forcing model observation for the following functions : *visu_mixedlayer_clim*, *visu_windforcing*, *visu_solarflux*, *visu_runoff* and *visu_precip*.

* ``rarification`` : rarification factor to reduce quivers density, used in functions *visu_current* and *visu_windforcing*.

* ``multiprocess`` : used to speed up by parallelizing on all model's time steps, default value is *True*. Set to *False* only with function *visu_mixedlayer_clim*.


Example
_______

Example of configuration file::

    [config_reg]
        name = "hycom3d_med"

    [parameters]

        [[SEA_SURFACE_TEMPERATURE]]
            name = "1- température de surface"
            [[[param_1]]]
                name = SST modèle
                func = visu_temp
                var = sst
            [[[param_2]]]
                name = "Ecart de la SST modèle avec la SST satellite"
                func = visu_diff_sst
                var = sst
                obs = sstl4
            [[[param_3]]]
                name = Champ de vent ayant forcé le modèle
                func = visu_windforcing
                var = uv
                forcing_model = "atmfrc/insta"
                rarification = 10
            [[[param_4]]]
                name = Champ de flux solaire ayant forcé le modèle
                func = visu_solarflux
                var = hfsen
                forcing_model = "atmfrc/cumul"

        [[SEA_SURFACE_SALINITY]]
            name = "2- salinité de surface"
            [[[param_1]]]
                name = SSS modèle
                func = visu_sal
                var = sss
            [[[param_2]]]
                name = Ecart de la SSS modèle avec une climatologie
                func = visu_diff_sss
                var = sss
                obs = woa18
            [[[param_3]]]
                name = Débits des fleuves
                func = visu_runoff
                var = RVFL
                forcing_model = rivers
            [[[param_4]]]
                name = Précipitations
                func = visu_precip
                var = tp
                forcing_model = "atmfrc/cumul"

        [[MIXED_LAYER]]
            name = "3- couche de mélange"
            [[[param_1]]]
                name = Epaisseur de la couche de mélange modèle
                func = visu_mixedlayer
                var = temp
            [[[param_2]]]
                name = Epaisseur de la couche de mélange climatologie
                func = visu_mixedlayer_clim
                var = temp
                forcing_model = woa18
                multiprocess = False
            [[[param_3]]]
                name = Champ de flux solaire ayant forcé le modèle
                func = visu_solarflux
                var = hfsen
                forcing_model = "atmfrc/cumul"
            [[[param_4]]]
                name = Champ de vent ayant forcé le modèle
                func = visu_windforcing
                var = uv
                forcing_model = "atmfrc/insta"
                rarification = 10

        [[CURRENT]]
            name = "4- courant"
            [[[param_1]]]
                name = Courant modèle de surface
                func = visu_current
                var = suv
                rarification = 20
            [[[param_2]]]
                name = Courant modèle à 50 m
                func = visu_current
                var = uv
                depth = 50
                rarification = 20
            [[[param_3]]]
                name = Courant modèle à 100 m
                func = visu_current
                var = uv
                depth = 100
                rarification = 20
            [[[param_4]]]
                name = Courant modèle à 200 m
                func = visu_current
                var = uv
                depth = 200
                rarification = 20

        [[TEMPERATURE]]
            name = "5- température"
            [[[param_1]]]
                name = SST modèle
                func = visu_temp
                var = sst
            [[[param_2]]]
                name = Température modèle à 50 m
                func = visu_temp
                var = temp
                depth = 50
            [[[param_3]]]
                name = Température modèle à 100 m
                func = visu_temp
                var = temp
                depth = 100
            [[[param_4]]]
                name = Température modèle à 200 m
                func = visu_temp
                var = temp
                depth = 200

        [[GIBRALTAR_TEMP]]
            name = "10- Gibraltar - température"
            [[[extent]]]
                lon_min = -7.0
                lon_max = -4.0
                lat_min = 35.5
                lat_max = 36.5
            [[[param_1]]]
                name = SST modèle
                func = visu_temp
                var = sst
            [[[param_2]]]
                name = Température modèle à 100 m
                func = visu_temp
                var = temp
                depth = 100
            [[[param_3]]]
                name = Température modèle à 200 m
                func = visu_temp
                var = temp
                depth = 200
            [[[param_4]]]
                name = Température modèle à 300 m
                func = visu_temp
                var = temp
                depth = 300

        [[GIBRALTAR_SAL]]
            name = "11- Gibraltar - salinité"
            [[[extent]]]
                lon_min = -7.0
                lon_max = -4.0
                lat_min = 35.5
                lat_max = 36.5
            [[[param_1]]]
                name = SSS modèle
                func = visu_sal
                var = sss
            [[[param_2]]]
                name = Salinité modèle à 100 m
                func = visu_sal
                var = sal
                depth = 100
            [[[param_3]]]
                name = Salinité modèle à 200 m
                func = visu_sal
                var = sal
                depth = 200
            [[[param_4]]]
                name = Salinité modèle à 300 m
                func = visu_sal
                var = sal
                depth = 300

        [[GIBRALTAR_CURRENT]]
            name = "12- Gibraltar - courant"
            [[[extent]]]
                lon_min = -7.0
                lon_max = -4.0
                lat_min = 35.5
                lat_max = 36.5
            [[[param_1]]]
                name = Courant modèle de surface
                func = visu_current
                var = suv
                rarification = 4
            [[[param_2]]]
                name = Courant modèle à 100 m
                func = visu_current
                var = uv
                depth = 100
                rarification = 4
            [[[param_3]]]
                name = Courant modèle à 200 m
                func = visu_current
                var = uv
                depth = 200
                rarification = 4
            [[[param_4]]]
                name = Courant modèle à 300 m
                func = visu_current
                var = uv
                depth = 300
                rarification = 4