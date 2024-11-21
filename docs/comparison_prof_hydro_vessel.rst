Hydrological profiles
---------------------

To compare some models outputs with argo-like profiles, use the ``armoor-prof_hydro_vessel`` executable.

Inputs
......

Hydrological profiles data from 
`CMEMS <https://data.marine.copernicus.eu/product/INSITU_GLO_PHYBGCWAV_DISCRETE_MYNRT_013_030/description>`_
or `CORA <https://www.seanoe.org/data/00351/46219/>`_ base can be used (`PR_PF`).


Outputs
.......

- ``plot_profile_u``
     
    Courbes "profil unique" de profils verticaux (un graphe par variable et par profil observé)  
    
- ``plot_profile_multi`` 

    Courbes « multi-profils » de profils verticaux (un graphe par variable et par modèle sur toute la période et par intervalle temporel)
    
- ``plot_ts_metr_stats``
    
    Courbes temporelles de statistiques. Si un découpage vertical par immersion, les statistiques spatiales seront uniquement horizontales et tracées pour chaque immersion. Si un découpage vertical par tranche est spécifié, les statistiques spatiales seront horizontales et verticales et tracées pour chaque tranche
    
- ``diag_ts_unique``

    Diagramme θ-S « profil unique » (un graphe par profil observé avec le profil observé et pour chaque modèle le profil modèle le plus proche spatialement et temporellement de l’observation associée).
    
- ``diag_ts_multi``
    
    Diagramme θ-S « multi-profils » (un graphe par modèle sur toute la période et par intervalle temporel)
    
- ``plot_map_metr_ecart``

    Cartes par variable : cartes des écarts. Si un découpage vertical par immersion est spécifié, seuls les écarts seront tracés à chaque immersion. Si un découpage temporel par intervalle est spécifié, les cartes seront à réaliser pour chaque intervalle.
    
- ``plot_map_metr_biais``

    Cartes par variable : cartes des biais. Si un découpage vertical par tranche est spécifié, les statistiques verticales seront tracées. Si un découpage temporel par intervalle est spécifié, les cartes seront à réaliser pour chaque intervalle.
    
- ``plot_map_metr_RMSE``
    
    Cartes par variable : cartes des rmse. Si un découpage vertical par tranche est spécifié, les statistiques verticales seront tracées. Si un découpage temporel par intervalle est spécifié, les cartes seront à réaliser pour chaque intervalle.
    
- ``plot_map_metr_RMSEc``

    Cartes par variable : cartes des rmse centrées. Si un découpage vertical par tranche est spécifié, les statistiques verticales seront tracées. Si un découpage temporel par intervalle est spécifié, les cartes seront à réaliser pour chaque intervalle.
    
- ``diag_disp_g``

    Diagrammes de dispersion globaux (un diagramme par modèle de toutes les données sélectionnées)
    
- ``diag_disp``

    Diagrammes de dispersion sélectifs : un diagramme par modèle et intervalle temporel si un tel découpage est spécifié et par tranche d’eau ou immersion (selon le découpage vertical spécifié).


Physical parameters
...................

By default, potential temperature, practical salinity and potential density will be plotted. 
Optional parameters are available : in-situ temperature (``temp``) and sound speed (``sound_speed``).
To be plotted, they have to be defined in the configuration file as :

    .. code-block::
    
        [metazone]
        vars = temp, sound_speed
        
Geospatial and temporal parameters
..................................

Some geospatial and temporal parameters are mandatory :
    - ``tbound`` : (list: `[2000-01-01, 2002-05-04]`) start and end dates.
    - ``radius`` : (float) radius in km used to select model grid points around an observation.
    
Other parameters have to be configured depending on the output:
    - `trange_seq` : (string: ``1D``]) time interval.
    - `vlevel` : (dict: ``{"depth": [100, 200, 500]}``) dictionnary specifying the vertical type and levels.
    - `vrange` : (dict: ``{"depth": [100, 200] [400, 500]}``) dictionnary specifying the vertical type and ranges .
    - `vref` : (string: ``obs`` or ``model``) vertical reference.
Some parameters cannot be defined simultaneously.


Templates
.........

Hereafter, we propose a list of configuration files that can be used as templates:

    .. literalinclude:: ../armoor/tests/uni/test_prof_hydro_vessel/cmems_vs_HyCOM.cfg
    
    .. literalinclude:: ../armoor/tests/uni/test_prof_hydro_vessel/cmems_vs_HyCOM_immersions.cfg
    
    .. literalinclude:: ../armoor/tests/uni/test_prof_hydro_vessel/cmems_vs_HyCOM_layers.cfg
    
    .. literalinclude:: ../armoor/tests/uni/test_prof_hydro_vessel/cmems_vs_HyCOM_intervals.cfg
    
    .. literalinclude:: ../armoor/tests/uni/test_prof_hydro_vessel/cmems_vs_HyCOM_immersions_intervals.cfg
    
    .. literalinclude:: ../armoor/tests/uni/test_prof_hydro_vessel/cmems_vs_HyCOM_layers_intervals.cfg
    
Examples
........

    .. image::  images/prof_hydro_vessel/Theta-S_diagram_sloop_oper_cmems_argo_2023-04-13_to_2023-04-14__interval_1D_4.98_42.12_radius_2.0km_0.4m_to_569.0m.png
        :width: 600
        :alt: example of theta-s diagram
        
    .. image::  images/prof_hydro_vessel/Multi_profiles_sound_speed_sloop_oper_cmems_argo_2023-04-14_to_2023-04-15__interval_1D_4.90_42.04_radius_2.0km_0.4m_to_614.3m.png
        :width: 600
        :alt: example of multi-profiles
        
    .. image::  images/prof_hydro_vessel/Statistics_Pot._temperature_sloop_oper_cmems_argo_interval_1D_radius_2.0km_50.0m.png
        :width: 600
        :alt: example of statistics time series
        
    .. image::  images/prof_hydro_vessel/Dispersion_diagram_sound_speed_sloop_oper_cmems_argo_2023-04-12T00-00-00_to_2023-04-19T00-00-00__radius_2.0km_50.0m_to_1500.0m.png
        :width: 600
        :alt: example of dispersion diagram
    
    .. image::  images/prof_hydro_vessel/bias_Salinity_sloop_oper_cmems_argo_2023-04-18_to_2023-04-19__interval_1D_7.02_39.58_radius_2.0km_200_to_500_m.png
        :width: 600
        :alt: example of map profil