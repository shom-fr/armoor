.. _climeta:

Command-line interfaces of metazone-based armoor executables
############################################################

Metazone-based executables allow the user to automatically chain multiple tasks.

Five metazone-based executables can be used in Armoor : 

- armoor-filters
- armoor-comp-[function*]
- armoor-data
- armoor-diag
- armoor-bull
  
Note that armoor-diag is still under development and will be available soon.

\* *comparison functions can be found under the dedicated section*

Each executable starts with an open-decode task (see section :ref:`opendecode`). It can further be followed by colocation/interpolation and comparison/computation, as well as plotting.

Such executables rely on two distinct **configuration files** : the metazones file and the data (and output) file.

Metazones configuration file
----------------------------

Armoor provides several executable scripts which have to be associated with a configuration file based on `metazones.ini` defining the metazone and parameters associated with:
    
    .. literalinclude:: ../armoor/cli/metazones.ini
           :language: ini
    
Multiple metazones can be defined. A metazone is a combination of filters applied over time and spatial coordinates as well as values.
Hereafter we give some details about the available parameters:

- ``name``: name of the metazone.
- ``tbound``: [date_min, date_max] used to filter out not needed dates.
- ``thours``: [hour_min, hour_max] used to filter out not needed times.
- ``tide``: string (demerliac, godin, mean) to apply a tidal filter.
- ``tfreq``: frequency (1D, 1Y... ) to define a series of terms equaly spaced (see pandas offset alias).
- ``trange_seq``: [1D,reference] list of two strings. The first one define the period of time intervals, the second one, the time axis over which data will be interpolated in time for comparison computing.
- ``tide``: tidal filters (godin, demerliac, 25h mean).
- ``tresample``: time resampling at given frequency.
- ``tsmooth``: time smoothing over a given period.
- ``polygon``: list of coordinate (lat/lon) defining a polygon to filter out not needed data.
- ``cloud``: list of coordinate (lat/lon) defining a cloud of point over which data will be interpolated.
- ``bathy``: list of type `path, fmt, min, max`. The first element is the directory of the bathymetry file, the second one is the format of the bathymetry file, min/max are bathy tresholds to apply.
- ``href``: string defining the grid over which data will be interpolated for comparison computing.
- ``vlevel``: string list of type `' "depth",[50,100,400,500] '`. The first element defines the type of vertical reference, the second one the list of vertical levels.
- ``vrange``: string list of type `' "reference","depth",[(50, 100), (400, 500), (800, 1000)] '`. The first element defines the vertical coordinates over which data will be interpolated in z for comparison computing, the second element defines the type of vertical levels, the third one defines the list of vertical intevals (list of tuple).
- ``oceanvars``: list of ocean variables to be processed.

Some parameters are not compatible : 

- ``tfreq`` and ``thours``
- ``trange_seq`` and ``tfreq``
- ``href`` and ``cloud``

You can find an example of a metazones configuration file in the :ref:`examples` section :

.. literalinclude:: examples/configs/metazones.cfg
         :language: ini
         :caption: metazones.cfg
         :linenos:

Data and output configuration file
----------------------------------

Each metazone-based executable allows a certain variety of parameters. See details in the dedicated sections :

.. toctree::
   :maxdepth: 1
   
   cli.meta.filters
   cli.meta.comp
   cli.meta.data
   cli.meta.diag
   cli.meta.bull



