Sea surface temperature
-----------------------

To compare some models outputs with sst satellite data, use the ``armoor-sst`` executable.

Inputs
......

Sea surface temperature  from 
`CMEMS <https://data.marine.copernicus.eu/products?facets=sources%7ESatellite+observations--mainVariables%7ETemperature>`_
or `CERSAT <https://cersat.ifremer.fr/Data/Catalogue#/search?from=1&to=30>`_ base can be used (L3 or L4).


Outputs
.......
 
- ``plot_ts_metr_stats``

    Séries temporelles: graphes par méta-zone des métriques statistiques spatiales. Si un découpage temporel par échéance est spécifié, ces échéances seront indiquées sur les courbes. Si un découpage temporel par intervalle est spécifié, les statistiques seront spatio-temporelles.

- ``plot_ts_metr_cloud``
        
    Séries temporelles: graphes par point spécifique de la méta-zone. Si un découpage temporel par intervalle est spécifié, les statistiques seront temporelles sinon seule la métrique écart sera traitée.
    
- ``plot_map_metr_ecart``

    Cartes par variable : cartes des écarts dans le cas d'un découpage temporel par échéance (``tfreq``).
    
- ``plot_map_metr_biais``

    Cartes par variable : cartes des biais dans le cas d'un découpage temporel par intervalle (``trange_seq``).
    
- ``plot_map_metr_RMSE``
    
    Cartes par variable : cartes des rmse dans le cas d'un découpage temporel par intervalle (``trange_seq``).
    
- ``plot_map_metr_RMSEc``

    Cartes par variable : cartes des rmse centrées dans le cas d'un découpage temporel par intervalle (``trange_seq``).
    
- ``diag_disp_g``

    Diagrammes de dispersion globaux (un diagramme par modèle de toutes les données sélectionnées)
    
- ``diag_disp``

    Diagrammes de dispersion sélectifs : un diagramme par modèle et par échéance ou intervalle (selon le découpage temporel spécifié).

        
Geospatial and temporal parameters
..................................

A temporal parameter are mandatory :
    - ``tbound`` : (list: `[2000-01-01, 2002-05-04]`) start and end dates
    
Other parameters have to be configured depending on the output:
    - ``trange_seq`` : (string: ``1D``]) time interval.
    - ``tref`` : (string: ``model``/``obs``) time reference to perform time intervals.
    - ``tfreq``: (string:  ``1D``) time frequency to define terms.
    - ``href``: (string: ``model``/``obs``) horizontal reference for regridding.
    - ``coord``: (list of `[lat/lon]`: ``[41, 5], [42, 6], [40, 7]``) to select horizontal point.
    
Some parameters have to  be defined simultaneously, some cannot


Templates
.........

Hereafter, we propose a list of configuration files that can be used as templates:
    
    .. literalinclude:: ../armoor/tests/uni/sst/L4_vs_HyCOM_cloud_intervals.cfg
    
    .. literalinclude:: ../armoor/tests/uni/sst/L4_vs_HyCOM_cloud_terms.cfg
    
    .. literalinclude:: ../armoor/tests/uni/sst/L4_vs_HyCOM_href_intervals.cfg
    
    .. literalinclude:: ../armoor/tests/uni/sst/L4_vs_HyCOM_href_terms.cfg
    
Examples
........

    .. image::  images/sst/Map_difference_Pot._temperature_sloop_oper_cmems_l4_2023-04-19T00-00.png
        :width: 600
        :alt: example of sst maps

    .. image::  images/sst/Dispersion_diagram_Pot._temperature_sloop_oper_cmems_l4_2023-04-16T00-00.png
        :width: 600
        :alt: example of dispersion diagram
        
    .. image::  images/sst/Statistics_Pot._temperature_sloop_oper_cmems_l4_interval_1D.png
        :width: 600
        :alt: example of statistics time series