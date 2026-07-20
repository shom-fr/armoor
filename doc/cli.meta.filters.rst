.. _clifilters:

Command-line interfaces for applying metazone filters
#####################################################

Configuration file
------------------

    Armoor executables dedicated to apply metazone filters have to be associated with a configuration file based on `filters.ini`:
        .. literalinclude:: ../armoor/cli/filters.ini
               :language: ini
    
data
====
    
        The data section is dedicated to the configuration of input data.
        
        - ``name``: name of the dataset.
        - ``path``: path of the input data files. Use of wild card is possible in order to process multiple files.
        - ``fmt``: user has to configure an armoor format-like.
    
ouputs
======
    
        A list of NetCDF files is generated.

Execution
---------

.. program-output:: armoor-filters -h
   :shell:
   :returncode: 0

Workflow
--------

    Open, decode input files and apply filters. Files are then stored at ``./metazones/{metazone.name}/{data.name}``.
    
.. argparse::
    :module: armoor.cli.main
    :prog: armoor-filters
    :nosubcommands:
