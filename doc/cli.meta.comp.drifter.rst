:command:`armoor-comp-drifter`
==============================

data formats
------------

    - ``cmems_drifter``
    
metazone parameters
-------------------

    - ``tbound``
    - ``trange_seq``
    - ``tfreq``
    - ``tide``
    - ``tresample``
    - ``tsmooth``
    - ``polygon``
    - ``vars``
    
    .. note::
       Other given parameters are ignored.

outputs
-------

    - ``timeseries``
    - ``maps_trajectory``
    - ``maps_current``

.. argparse::
    :module: armoor.cli.main
    :func: get_parser_comp_drifter
    :prog: armoor-comp-drifter
    :nosubcommands:
