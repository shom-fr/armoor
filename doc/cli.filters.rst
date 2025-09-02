.. _clifilters:

Command-line interfaces for applying metazone filters
#####################################################

Configuration file
------------------

    Armoor executables dedicated to apply metazone filters have to be associated with a configuration file based on `data.ini`:
        .. literalinclude:: ../armoor/cli/data.ini
               :language: ini
    
data
====
    
        The data section is dedicated to the configuration of input data.
        
        - ``name``: name of the dataset.
        - ``path``: path of the input data files. Use of wild card is possible in order to process multiple files.
        - ``fmt``: user has to configure an armoor format-like.
        - ``platform``: type of platform can be needed for some observations.
    
ouputs
======
    
        A list of NetCDF files is generated.

Workflow
--------

    1. Open, decode input files and apply filters --> NetCDF files stored at ``./{comp_name}/metazones/{metazone.name}/{data.name}``.
    
.. argparse::
    :module: armoor.cli.main
    :func: get_parser_filters
    :prog: armoor-filters
    :nosubcommands:
