.. _cli:

Command-line interfaces
#######################

.. _opendecode:

Open-decode
===========

Every data processed by armoor executables are first opened and decoded in a pivot format.

Open files
----------

The open functions of armoor are based wether on xarray or pandas libraries depending on the original format (netcdf, .txt, .csv...).

Decode data
-----------

To decode data, armoor uses `xoa.cf <https://xoa.readthedocs.io/v0.8.0/uses.cf.html>`_.

Armoor can decode data from model outputs or observations, either in situ or satellite.
               
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
    
.. _varconventions:
    
Decoding data consists in following armoor conventions :

    - time dimension --> ``time``
    - vertical dimension --> ``z``
    - along latitude dimension --> ``y``
    - along longitude dimension --> ``x``
    - depth coordinate --> ``depth``
    - pressure coordinate --> ``pres``
    - density --> ``dens``
    - potential density --> ``pdens``
    - temperature --> ``temp``
    - potential temperature --> ``ptemp``
    - sea surface temperature --> ``sst``
    - salinity --> ``sal``
    - sea surface salinity --> ``sss``
    - sea surface height --> ``ssh``
    - sea water velocity along X - Eastward velocity --> ``u``
    - sea water velocity along Y - Northward velocity --> ``v``
    
See armoor conventions for more variables in the :download:`cf.cfg <../armoor/data/cf.cfg>` file.

Armoor can also decode outputs from the following eddy detection tools :

    - `SHOOT <http://apps.shom.fr/shoot/index.html>`_,
    - `py-eddy-tracker <https://py-eddy-tracker.readthedocs.io/en/stable/>`_
    - SACSO-T (SOAP3.5).

.. toctree::
   :maxdepth: 1
   
   cli.unit
   cli.meta
   
