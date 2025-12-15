Hydrological sections
---------------------

To compare some models outputs with glider-like data, use the ``armoor-section_hydro`` executable.

Inputs
......

Hydrological sections data from 
`CMEMS <https://data.marine.copernicus.eu/product/INSITU_GLO_PHYBGCWAV_DISCRETE_MYNRT_013_030/description>`_ base can be used (`PR_GL`).


Outputs
.......

- ``plot_variable_3d``
    
    Vertical section.
    
- ``plot_variable_2d``
    
    Time series of mixed layer depth.



Physical parameters
...................

By default, potential temperature and practical salinity will be plotted. 
Optional parameters are available : in-situ temperature (``temp``), potential density (``pdens``), 
mixed layer depth from potential temperature (``mld_ptemp``) or potential density (``mld_pdens``), and
geostrophic current (``current_geos``).
To be plotted, they have to be defined in the configuration file as :

    .. code-block::
    
        [metazone]
        vars = temp, pdens,  mld_ptemp, current_geos

Geospatial and temporal parameters
..................................

Some geospatial and temporal parameters are mandatory :
    - ``tbound`` : (list: `[2000-01-01, 2002-05-04]`) start and end dates.
    
Other parameters have to be configured depending on the output:
    - ``vfreq`` : (dict: ``{"depth": 10.0}``]) vertical step.


Templates
.........

Hereafter, we propose a list of configuration files that can be used as templates:
    
    .. literalinclude:: ../armoor/tests/uni/section_hydro/cmems_vs_HyCOM.cfg

Example
.......

    .. image::  images/section_hydro/3D_variable_Pot._temperature_sloop_oper_8901012_2023-04-12T00-00-00_to_2023-04-19T00-00-00__3.0m_to_1008.0m.png
        :width: 600
        :alt: example of vertical section