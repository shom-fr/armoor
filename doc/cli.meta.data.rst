.. _clidata:

Command-line interfaces for data
################################

Configuration file
------------------

    Armoor executables dedicated to plot data have to be associated with a configuration file based on `data.ini`:
        .. literalinclude:: ../armoor/cli/data.ini
               :language: ini
               
data
====
    
        The data section is dedicated to the configuration of input data.
        
        - ``name``: name of the dataset.
        - ``path``: path of the input data files. Use of wild card is possible in order to process multiple files.
        - ``fmt``: user has to configure an armoor format-like.   
        - ``vminmax``: (optional) set colorbar/axis limits for each variable and plot type. 
          Format is a dictionnary such as `vminmax = {'ptemp': (15,25), 'sal': (33,36)}`
          Variables names are those of the Armoor pivot format (see :ref:`Armoor conventions <varconventions>`).
        
outputs
======
    
        Multiple outputs can be configured. The available outputs depend on the metazone parameters.
        For instance, a vertical profile of salinity is not possible with ``vlevel``.

	.. grid:: 3

            .. grid-item-card:: Maps of statistics (``maps``)

                Maps of statistical metrics (mean and standard deviation). ``tfreq`` is not permitted.

                .. image:: images/data_map.png
                
                :download:`Download <images/data_map.png>`
		
            .. grid-item-card:: Time series (``timeseries``)

                Time series of statistical metrics (mean and standard deviation).
                
                .. image:: images/data_timeseries.png
                
                :download:`Download <images/data_timeseries.png>`

            .. grid-item-card:: Multiple vertical profiles (``mvprofiles``)

                Plot of multiple vertical profiles. ``vlevel`` is not permitted.
                
                .. image:: images/data_mvprofiles.png
                
                :download:`Download <images/data_mvprofiles.png>`

            .. grid-item-card:: Theta-S diagrams for multiple vertical profiles (``mdiagts``)

                Plot of a theta-s diagram of every vertical profiles.
                
                .. image:: images/data_mdiagts.png
                
                :download:`Download <images/data_mdiagts.png>`

            .. grid-item-card:: Unique vertical profiles (``uvprofiles``)

                Plot of unique vertical profiles. ``vlevel`` is not permitted.
                
            .. grid-item-card:: Theta-S diagram for a unique vertical profiles (``udiagts``)

                Plot of a theta-s diagram by profile. ``vlevel`` is not permitted.

Execution
---------

.. program-output:: armoor-data -h
   :shell:
   :returncode: 0
        
Workflow
--------

    1. Open, decode input files and apply filters --> Zarr files stored at ``./data/metazones/{metazone.name}/{data.name}/``.
    2. Interpolate/organize data in time and space if necessary, cleanup unecessary variables --> Zarr files stored at ``./data/interp/{metazone.name}/{data.name}/``.
    3. Compute outputs --> Zarr files stored at ``./data/output/{metazone.name}/{data.name}/{otype}/``.
    4. (if png format is given) Plots --> png files stored at ``./data/plot/{metazone.name}/``.


.. argparse::
    :module: armoor.cli.main
    :prog: armoor-data
    :nosubcommands:
