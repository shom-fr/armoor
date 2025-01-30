Production of images
====================

.. meta::
    :description: Forecaster script | You can create images for forecaster wed interface.

You will learn here how to create and customize images for the forecaster web interface.


How to use
----------

The command to use this script is ``armoor-script``, which comes with three mandatory options : *output-folder*, *input-folder* and *input-configuration*.

* *output-folder* : Folder path to store outputs created by the script for the web interface.
* *input-folder* : Root folder path from which the data is collected to create images for the forecaster web interface.
* *input-configuration* : Configuration file for image generation
* (optional) *legend-configuration* : Modify settings by using a configuration file to override internal defaults.

This command generates a **.tgz** file containing all the created images and files with the right tree structure for the forecaster web interface.

Details on input folder
~~~~~~~~~~~~~~~~~~~~~~~

The input folder should contain and be structured as follows
for a sloop-hycom3d production ::

    ├── config_reg_YYYYMMDD
    │   ├── arpege_insta
    │   │   └── arpege_*_insta.grib
    │   ├── hycom3d
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
    │   ├── cmems_sst_l4
    │   │   └── *.nc
    │   └── woa18
    │       ├── woa18_decav_s[imonth]_04.nc
    │       └── woa18_decav_t[imonth]_04.nc

Where ``config_reg`` is the composition of the ``model`` and the ``config`` given in the configuration file (see below), ``YYYYMMDD`` the date of production of the data and ``imonth`` is the number of the month of the current production.

Details on configuration file
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

There are two main sections ``[config_reg]`` and ``[parameters]``.

*config_reg* section
____________________

The name of the regional configuration must be identical to the folder name inside the **input-folder**.
For example if the production day is **20230307**, the model **hycom3d** and the configuration **manga**, the regional configuration will be **hycom3d_manga**,
the folder name **hycom3d_manga_20230307** and the content of this section in the configuration file as follows::

    [config_reg]
        model = hycom3d
        config = manga
        n_workers = 16
        memory_limit = 2Gb

``n_workers`` and ``memory_limit`` are dask parameters defined in order to produce images in parallel.


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
    #. ``visu_windforcing`` : 2D map with quivers for wind.
    #. ``visu_current`` : 2D map with quivers for current.

* ``var`` : Variables of interest among the following:

    #. ``temp`` : temperature
    #. ``sst`` : sea surface temperature
    #. ``salt`` : salinity
    #. ``sss`` : sea surface salinity
    #. ``uv`` : current

* ``vlevel`` : Depths of interest in meters.

* ``fmt`` : Data format.

* ``rarification`` : Rarification factor used to decrease quiver and barb density. Utilized in the functions *visu_current* and *visu_windforcing*.

* ``barbs_length`` : Length of barbs (default set to 4.0). Applied in the function *visu_windforcing*.

* ``barbs_linewidth`` : Width of barbs' lines (default set to 0.3). Applied in the function *visu_windforcing*.

* ``quiver_scale`` : Scales the length of the arrow inversely (c.f. `quiver <https://matplotlib.org/stable/api/\_as_gen/matplotlib.quiver.Quiver.html>`_ ). Applied in the function *visu_current*.

* ``quiver_width`` : Shaft width in arrow units (c.f. `quiver <https://matplotlib.org/stable/api/\_as_gen/matplotlib.quiver.Quiver.html>`_ ). Applied in the function *visu_current*.

* ``quiver_headwidth`` : Head width as multiple of shaft width (c.f. `quiver <https://matplotlib.org/stable/api/\_as_gen/matplotlib.quiver.Quiver.html>`_ ). Applied in the function *visu_current*.

* ``quiver_headlength`` : Head length as multiple of shaft width (c.f. `quiver <https://matplotlib.org/stable/api/\_as_gen/matplotlib.quiver.Quiver.html>`_ ). Applied in the function *visu_current*.

* ``multiprocess`` : Used for acceleration purposes by parallelization on all model's time steps. Its default value is *True*.

For each parameter, a sub-section ``cbar`` can be defined to configure the colorbar with:

* ``minmax``: Boolean to use real min and max values (default: False).

* ``nstd``: Float used for computed min (max) as *mean(values) -(+) nstd * std(values)*.

* ``difference``: Boolean to center the colorbar around 0.

* ``norm``: Boolean to fix min value to 0.

* ``var_name``: String, name of variable.

* ``var_unit``: String, unit of variable.

* ``cmap``: String, colormap to use.

Example
_______

Example of configuration file::
    
    [config_reg]
        model = 'hycom3d'
        config = 'manga'
        n_workers = 16
        memory_limit = 2Gb
    [parameters]
        [[SURFACE]]
        name = "Surface"
            [[[param_1]]]
                name = SST (hycom)
                func = visu_temp
                var = sst
                fmt = hycom3d
                [[[[legend]]]]
                    var_name = 'Temperature, '
                    var_unit = '°C'
                    cmap = 'cmo.thermal'
            [[[param_2]]]
                name  = SST (L4)
                func = visu_temp
                var = sst
                fmt = cmems_sst_l4
                [[[[legend]]]]
                    var_name = 'Temperature, '
                    var_unit = '°C'
                    cmap = 'cmo.thermal'
            [[[param_3]]]
                name = SSS
                func = visu_sal
                var = sss
                fmt = hycom3d
                [[[[legend]]]]
                    var_name = 'Salinity, '
                    var_unit = 'psu'
                    cmap = 'cmo.haline'
            [[[param_4]]]
                name = Wind speed (arpege)
                func = visu_windforcing
                var = suv
                fmt = arpege_insta
                rarification = 5
                [[[[cbar]]]]
                    norm = True
                [[[[legend]]]]
                    var_name = 'Wind speed @10m, '
                    var_unit = 'kt'
                    cmap = 'cmo.speed'
        [[TEMPERATURE]]
        name = "Temperature"
            [[[common]]]
                var = ptemp
                vlevel = {'depth': [0, 50, 100, 200]}
                fmt = hycom3d
            [[[param_1]]]
                name = Temperature @0m (hycom)
                func = visu_temp
                var = ptemp
                vlevel = {'depth': [0]}
                fmt = hycom3d
                [[[[legend]]]]
                    var_name = 'Temperature, '
                    var_unit = '°C'
                    cmap = 'cmo.thermal'
            [[[param_2]]]
                name = Temperature @50m (hycom)
                func = visu_temp
                var = ptemp
                vlevel = {'depth': [50]}
                fmt = hycom3d
                [[[[legend]]]]
                    var_name = 'Temperature, '
                    var_unit = '°C'
                    cmap = 'cmo.thermal'
            [[[param_3]]]
                name = Temperature @100m (hycom)
                func = visu_temp
                var = ptemp
                vlevel = {'depth': [100]}
                fmt = hycom3d
                [[[[legend]]]]
                    var_name = 'Temperature, '
                    var_unit = '°C'
                    cmap = 'cmo.thermal'
            [[[param_4]]]
                name = Temperature @200m (hycom)
                func = visu_temp
                var = ptemp
                vlevel = {'depth': [200]}
                fmt = hycom3d
                [[[[legend]]]]
                    var_name = 'Temperature, '
                    var_unit = '°C'
                    cmap = 'cmo.thermal'
