Forecaster script
=================

.. meta::
    :description: Forecaster script | You can create images for forecaster wed interface.

You will learn here how to create and customize images for the forecaster web interface.


How to use
----------

The command to use this script is ``armoor-script``, which comes with three mandatory options : *output-folder*, *input-folder* and *input-configuration*.

* *output-folder* : Folder path to store outputs created by the script for the web interface.
* *input-folder* : Root folder path from which the data is collected to create images for the forecaster web interface.
* *input-configuration* : Configuration file for image generation

This command generates a **.tgz** file containing all the created images and files with the right tree structure for the forecaster web interface.

Details on input folder
~~~~~~~~~~~~~~~~~~~~~~~

The input folder should contain and be structured as follows ::

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

Where ``config_reg`` is the composition of the **model** and the **config** given in the configuration file (see below), and **YYYYMMDD** the date of production of the data.

Details on configuration file
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

There are two main sections ``[config_reg]`` and ``[parameters]``.

*config_reg* section
____________________

The name of the regional configuration must be identical to the folder name inside the **input-folder**.
For example if the production day is **20230307**, the model **hycom3d** and the configuration **med**, the regional configuration will be **hycom3d_med**,
the folder name **hycom3d_med_20230307** and the content of this section in the configuration file as follows::

    [config_reg]
        model = "hycom3d"
        config = "med"

In this example the **.tgz** output file will be *hycom3d_med_20230307.tgz*.

Section *parameters*
____________________

There can be as many parameters as needed, each parameter being composed of a header and of 4 sub-parameters.

Header
######

The header can be composed of three parts:
    1. ``[[parameter_name]]`` : must be unique, with only *letters*, *numbers* and *_*.
    2. ``name`` is only here to make the configuration file more readable.
    3. ``[[[extent]]]`` is an optional parameter, which must include the minimum and maximum longitudes and latitudes, with the following attributes : *lon_min*, *lon_max*, *lat_min* and *lat_max*.

Sub-parameters
##############

After the header there are 4 sub-parameters which must be named as triple square brackets param_* ( 1 to 4).
Each sub-parameter can have a combination of attributes depending on what we want to display in the forecaster web interface.
Here are the different possible attributes and their purpose:

* ``name`` : Name displayed in the final image, plot or chart.

* ``func`` : Visualization functions among the following :

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

* ``var`` : Variables of interest among the following:

    #. ``temp`` : temperature
    #. ``sst`` : sea surface temperature
    #. ``salt`` : salinity
    #. ``sss`` : sea surface salinity
    #. ``uv`` : current
    #. ``suv`` : surface current
    #. ``hfsen`` : solar flux
    #. ``RVFL`` : runoff
    #. ``tp`` : total precipitation

* ``depth`` : Depth of interest in meters.

* ``obs`` : Relative path to observation for comparison with the model functions *visu_diff_sst* and *visu_diff_sss*.

* ``forcing_model`` : Relative path to forcing model observation for the following functions : *visu_mixedlayer_clim*, *visu_windforcing*, *visu_solarflux*, *visu_runoff* and *visu_precip*.

* ``rarification`` : rarification factor to reduce quivers density. It is used in the functions *visu_current* and *visu_windforcing*.

* ``multiprocess`` : used for acceleration purposes by parallelization on all model's time steps. Its default value is *True* and it is only set to *False* with the function *visu_mixedlayer_clim*.


Example
_______

Example of configuration file::

    [config_reg]
        model = hycom3d
        config = med

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

Run tests
---------

To run Forecaster unit tests, use the following commands::

    pytest your_path_to/tests/uni/hmi/test_path_tools.py
    pytest your_path_to/tests/uni/hmi/test_script_tools.py
    pytest your_path_to/tests/uni/test_approval.py


In the folder where you will run ``pytest`` please create a file named **tests.cfg**
and add the following lines by replacing ``/path/to/output/tests/P2/`` and ``/path/to/output/tests/P3/`` with your information::

    path_p2 = '/path/to/output/tests/P2/'
    path_p3 = '/path/to/output/tests/P3/'

The ``path_p2`` folder is for ``test_approval.py``, and the ``path_p3`` folder is for ``test_path_tools.py``.

To run tests for all the different parameters, use the following command::

    pytest /mnt/c/Users/Pastor/Downloads/WSL_WORKSPACE/Gitlab_SHOM/tests/int/hmi/test_forecaster_script.py

In the ``path_p3`` folder, you must have the ``data`` folder containing ``hycom3d_med_20220310``, ``hycom3d_indien_20220310`` and
``hycom3d_manga_20220310`` from ``/home/shom_simurep/public_no_ftp/Noveltis_19AC22/Developpement/InterfacePrevisionnistes``.

In the ``data`` folder from ``path_p3``, please rename the folders ``*_20220310`` with the current day following this naming convention: ``*_YYYYMMDD``.