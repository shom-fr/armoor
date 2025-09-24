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


.. toctree::
   :maxdepth: 1
   
   cli.unit
   cli.meta
   