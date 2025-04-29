Climatological hydrology
------------------------

To compare some models outputs with climatological hydrology data, use the ``armoor-clim_hydro`` executable.

Inputs
......

Climatology from `woa18 <https://www.ncei.noaa.gov/access/metadata/landing-page/bin/iso?id=gov.noaa.nodc:NCEI-WOA18>`_ 
can be used.

Outputs
.......
 
- ``plot_ts_metr_stats``

    Séries temporelles: graphes par variable et par immersion des évolutions temporelles des métriques statistiques, spatiales.
    
- ``plot_ts_metr_cloud``
        
    Séries temporelles: graphes par variable et par immersion des évolutions temporelles de la métrique « écart ».
    
- ``plot_map_metr_ecart``

    Cartes par variable : cartes des écarts par mois et par immersion.
        
Geospatial and temporal parameters
..................................

A temporal parameter are mandatory :
    - ``tbound`` : (list: `[2000-01-01, 2002-05-04]`) start and end dates
    
Other parameters have to be configured depending on the output:
    - ``trange_clim`` : (string: ``month``]) monthly time interval.
    - ``href``: (string: ``model``/``obs``) horizontal reference for regridding.
    - ``coord``: (list of `[lat/lon]`: ``[41, 5], [42, 6], [40, 7]``) to select horizontal point.
    
Some parameters have to  be defined simultaneously, some cannot.


Templates
.........

Hereafter, we propose a list of configuration files that can be used as templates:
    
    .. literalinclude:: ../armoor/tests/uni/clim_hydro/woa18_hycom3d_cloud.cfg
    
    .. literalinclude:: ../armoor/tests/uni/clim_hydro/woa18_hycom3d_href.cfg

Examples
........

     .. image::  images/clim_hydro/__Salinity_HyCOM_woa18_climato_month_61.00_23.00_10.0m.png
         :width: 600
         :alt: example of time series
         
    .. image::  images/clim_hydro/Statistics_Salinity_HyCOM_woa18_climato_month_100.0m.png
        :width: 600
        :alt: example of time series
        
    .. image::  images/clim_hydro/Map_difference_Pot._temperature_HyCOM_woa18_2023-03-01_to_2025-06-01__climato_apr_100.0m.png
        :width: 600
        :alt: example of map
        
    .. image::  images/clim_hydro/Map_difference_Pot._temperature_HyCOM_woa18_2023-03-01_to_2025-06-01__climato_aug_10.0m.png
        :width: 600
        :alt: example of map
        
    