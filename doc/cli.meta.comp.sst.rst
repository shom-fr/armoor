:command:`armoor-comp-sst`
==========================

data formats
------------

    - ``cmems_sst_l3``
    - ``cmems_sst_l4``
    - ``cersat_sst_l3``

metazone parameters
-------------------

    - ``tbound``
    - ``trange_seq``
    - ``tfreq``
    - ``tide``
    - ``tresample``
    - ``tsmooth``
    - ``polygon``
    - ``href``
    - ``cloud``
    - ``vars``

    .. note::
       Other given parameters are ignored.

outputs
-------

    - ``diagdisp_glob``
    - ``diagdisp_sel``
    - ``timeseries``
    - ``maps``


.. argparse::
    :module: armoor.cli.main
    :func: get_parser_comp_sst
    :prog: armoor-comp-sst
    :nosubcommands:
