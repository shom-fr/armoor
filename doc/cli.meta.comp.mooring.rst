:command:`armoor-comp-mooring`
==============================

data formats
------------

    - ``cmems_mooring``

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

.. argparse::
    :module: armoor.cli.main
    :func: get_parser_comp_mooring
    :prog: armoor-comp-mooring
    :nosubcommands:
