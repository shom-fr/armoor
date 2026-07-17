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
- ``trange_seq``: subsection defining the sequential time-ranging used for comparison computing::

    [[trange_seq]]
        tfreq = 1D          # period of the time intervals
        tref = reference    # time axis to interpolate onto: reference or product
        method = linear     # optional, interpolation method (defaults to linear)

- ``tide``: tidal filters (godin, demerliac, 25h mean).
- ``tresample``: time resampling at given frequency.
- ``tsmooth``: time smoothing over a given period.
- ``polygon``: list of coordinate (lat/lon) defining a polygon to filter out not needed data.
- ``cloud``: list of coordinate (lat/lon) defining a cloud of point over which data will be interpolated.
- ``bathy``: subsection defining a bathymetry-based filter::

    [[bathy]]
        path = /local/misc/data/bathy_indien.nc  # path to the bathymetry file
        fmt = hycom                              # format of the bathymetry file
        min = 0.0                                # bathy thresholds to apply
        max = 1000.0

- ``href``: string defining the grid over which data will be interpolated for comparison computing.
- ``vlevel``: subsection defining vertical levels to interpolate onto::

    [[vlevel]]
        vname = depth               # vertical coordinate name
        levels = 50, 100, 400, 500  # vertical levels

- ``vrange``: subsection defining vertical ranges for comparison computing::

    [[vrange]]
        vref = reference                 # vertical reference to interpolate onto: reference or product
        vname = depth                    # vertical coordinate name
        bins_min = 50, 400, 800          # lower bound of each vertical bin
        bins_max = 100, 500, 1000        # upper bound of each vertical bin

- ``vfreq``: subsection defining a regular vertical step to interpolate onto::

    [[vfreq]]
        vname = depth  # vertical coordinate name
        step = 25.0    # vertical step

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



