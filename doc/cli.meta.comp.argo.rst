:command:`armoor-comp-argo`
===========================

data formats
------------

    - ``cmems_argo``
    - ``cora_argo``

metazone parameters
-------------------

    - ``tbound``
    - ``trange_seq``
    - ``tide``
    - ``tresample``
    - ``tsmooth``
    - ``polygon``
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
    :func: get_parser_comp_argo
    :prog: armoor-comp-argo
    :nosubcommands:
