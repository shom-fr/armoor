Hydrological stations
---------------------

To compare some models outputs with mooring-like data, use the ``armoor-prof_hydro_mooring`` executable.

Inputs
......

Hydrological profiles data from 
`CMEMS <https://data.marine.copernicus.eu/product/INSITU_GLO_PHYBGCWAV_DISCRETE_MYNRT_013_030/description>`_ base can be used (`TS_MO`).


Outputs
.......

- ``plot_ts_metr_stats``
    
    Courbes temporelles de statistiques. graphes par mouillage et par immersion du mouillage. Si un découpage temporel par échéance est spécifié, seuls les écarts seront tracés. Si un découpage temporel par intervalle est spécifié, les statistiques seront temporelles.
    
Physical parameters
...................

By default, potential temperature, practical salinity and potential density will be plotted. 
Optional parameters are available : in-situ temperature (``temp``) and sound speed (``sound_speed``).
To be plotted, they have to be defined in the configuration file as :

    .. code-block::
    
        [metazone]
        vars = temp, sound_speed


.. warning::
    Most of the time, mooring data contain only in-situ temperature.

Geospatial and temporal parameters
..................................

Some geospatial and temporal parameters are mandatory :
    - ``tbound`` : (list: `[2000-01-01, 2002-05-04]`) start and end dates.
    - ``radius`` : (float) radius in km used to select model grid points around an observation.
    
Other parameters have to be configured depending on the output:
    - ``trange_seq`` : (string: ``1D``]) time interval.
    - ``tref``: (string: ``model/obs``]) reference time for colocation.
    - ``tfreq``: (string:  ``1D``) time frequency to define terms.
Some parameters cannot be defined simultaneously.


Templates
.........

Hereafter, we propose a list of configuration files that can be used as templates:
    
    
    .. literalinclude:: ../armoor/tests/uni/test_prof_hydro_mooring/cmems_vs_HyCOM_intervals.cfg
    
    .. literalinclude:: ../armoor/tests/uni/test_prof_hydro_mooring/cmems_vs_HyCOM_terms.cfg
    