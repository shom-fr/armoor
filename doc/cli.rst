Command-line interfaces
#######################

Open-decode
===========

Every data processed by armoor executables are first opened and decoded in a pivot format.

Open files
----------

The open functions of armoor are based wether on xarray or pandas libraries depending on the original format (netcdf, .txt, .csv...).

Decode data
-----------

To decode data, armoor uses `xoa.cf <https://xoa.readthedocs.io/develop/uses.cf.html>`_.
               
The list of configuration files used can be found at ``armoor/data/`` :
    
    - cf_cersat_sst_l3.cfg
    - cf_cmems_argo.cfg
    - cf_cmems_drifter.cfg
    - cf_cmems_glider.cfg
    - cf_cmems_mooring.cfg
    - cf_cmems_sst_l3.cfg
    - cf_cmems_sst_l4.cfg
    - cf_cora_argo.cfg
    - cf_hycom.cfg
    
Decoding data consists in following armoor conventions:

    - time dimension --> ``time``
    - vertical dimension --> ``z``
    - along latitude dimension --> ``y``
    - along longitude dimension --> ``x``
    - depth coordinate --> ``depth``
    - pressure coordinate --> ``pres``
    - potential density coordinate --> ``pdens``
    - potential temperature --> ``ptemp``
    - in-situ temperature --> ``temp``
    - practical salinity --> ``sal``
 
Metazones
=========

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
   
   cli.filters
   cli.comp
   cli.data
   cli.diag



