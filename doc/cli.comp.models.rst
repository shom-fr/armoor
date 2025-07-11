:command:`armoor-comp-models`
=============================

data formats
------------

    - ``cmems_model``
    - ``hycom``

metazone parameters
-------------------

    - ``tbound``
    - ``trange_seq``
    - ``tfreq``
    - ``polygon``
    - ``href``
    - ``cloud``
    - ``vrange``
    - ``vlevel``
    - ``vars``

    .. note::
       Other given parameters are ignored.

outputs
-------

    - ``diagdisp_glob``
    - ``diagdisp_sel``
    - ``timeseries``
    - ``maps``
    - ``mvprofiles``
    - ``mdiagts``
    - ``uvprofiles``
    - ``udiagts``


.. argparse::
    :module: armoor.cli.main
    :func: get_parser_comp_models
    :prog: armoor-comp-models
    :nosubcommands:
