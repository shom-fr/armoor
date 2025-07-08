Command-line interfaces
#######################

Armoor provides several executable scripts which have to be associated with a configuration file based on `metazones.ini` defining the metazone and parameters associated with:
    .. literalinclude:: ../armoor/cli/metazones.ini
           :language: ini
    
Multiple metazones can be defined. A metazone is a combination of filters applied over time and spatial coordinates as well as values.
Hereafter we give some details about the available parameters:

- ``name``: name of the metazone.
- ``tbound``: [date_min, date_max] used to filter out not needed time.
- ``tfreq``: frequency (1D, 1Y... )to define a series of terms equaly spaced (see pandas offset alias).
- ``trange_seq``: [1D,reference] list of two strings. The first one define the period of time intervals, the second one, the time axis over which data will be interpolated in time for comparison computing.
- ``polygon``: list of coordinate (lat/lon) defining a polygon to filter out not needed data.
- ``cloud``: list of coordinate (lat/lon) defining a cloud of point over which data will be interpolated.
- ``href``: string defining the grid over which data will be interpolated for comparison computing.
- ``vlevel``: list of type `"depth",[50,100,400,500]`. The first element defines the type of vertical reference, the second one the list of vertical levels.
- ``vrange``: list of type `"reference","depth",[(50, 100), (400, 500), (800, 1000)]`. The first element defines the vertical coordinates over which data will be interpolated in z for comparison computing, the second element defines the type of vertical levels, the third one defines the list of vertical intevals (list of tuple).

Some parameters are not compatible : 

- ``trange_seq`` and ``tfreq``
- ``href`` and ``cloud``
    
.. toctree::
   :maxdepth: 1
   
   cli.comp
   cli.data
   cli.diag



