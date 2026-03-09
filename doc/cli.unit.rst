.. _cliunit:

Command-line interfaces of elementary armoor executables
########################################################

Elementary executables allow the user to run single elementary tasks such as comparison, colocation, interpolation, filtering, decoding and applying ranges.

Several elementary tasks can be further chained in a terminal script or run independantly.

Elementary executables can typically be run such as follow : ::

   $ armoor-[elementary function] infile outfile --ifmt [infile format] --ofmt [netcdf/zarr]

Other positional arguments or options can be found. See usage in each dedicated subsection :

.. toctree::
   :maxdepth: 1
   
   cli.unit.coloc.horizontal
   cli.unit.coloc.time
   cli.unit.coloc.vertical
   cli.unit.comp
   cli.unit.decode
   cli.unit.filters.horizontal
   cli.unit.filters.oceanvars
   cli.unit.filters.quality
   cli.unit.filters.time   
   cli.unit.interp.horizontal
   cli.unit.interp.time   
   cli.unit.interp.vertical
   cli.unit.range.time
   cli.unit.range.vertical
 
