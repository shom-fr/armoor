.. _clidata:

Commandeline interfaces for data
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
        
ouputs
======
    
        Multiple outputs can be configured. The available outputs depend on the metazone parameters.
        For instance, a vertical profile of salinity is not possible with ``vlevel``.

        - ``maps``: maps of mean and standard deviation (``tfreq`` is not permitted).
        
        .. image:: images/data_maps.png
            
        - ``timeseries``: time series of mean and standard deviation.
        
        .. image:: images/data_timeseries.png
        
        - ``mvprofiles``: plot of multiple vertical profiles (``vlevel`` is not permitted).
        
        .. image:: images/data_mvprofiles.png
        
        - ``uvprofiles``: plot of a vertical profile over time (``vlevel`` is not permitted).
        
        .. image:: images/data_uvprofiles.png
        
        - ``udiagts``: theta-s diagram of an vertical over time (``vlevel`` is not permitted).
        
        .. image:: images/data_udiagts.png
        
        - ``mdiagts``: theta-s diagram of multiple vertical profiles.
        
        .. image:: images/data_mdiagts.png