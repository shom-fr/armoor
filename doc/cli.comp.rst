.. _clicomp:

Command-line interfaces for comparison
######################################

Configuration file
------------------

    Armoor executables dedicated to comparison have to be associated with a configuration file based on `comp.ini`:
        .. literalinclude:: ../armoor/cli/comp.ini
               :language: ini
    
metazones
=========
   
        Multiple metazones can be defined. A metazone is a combination of filters applied over time and spatial coordinates as well as values.
        Hereafter we give some details about the available parameters:
    
        - ``name``: name of the metazone.
        - ``tbound``: [date_min, date_max] used to filter out not needed time.
        - ``tfreq``: frequency (1D, 1Y... )to define a series of terms equaly spaced (see pandas offset alias).
        - ``trange_seq``: [1D,reference] list of two strings. The first one define the period of time intervals, the second one, the time axis over which data will be interpolated in time for comparison computing.
        - ``polygon``: list of coordinate (lat/lon) defining a polygon to filter out not needed data.
        - ``cloud``: list of coordinate (lat/lon) defining a cloud of point over which data will be interpolated.
        - ``href``: string defining the grid over which data will be interpolated for comparison computing.
        - ``vlevel``: list of type `"depth",[50,100,400,500]`. The first element defines the type of vertical reference, the second one the list of vertical levels.
        - ``vrange``: list of type `"reference","depth",[(50, 100), (400, 500), (800, 1000)]`. The first element defines the vertical coordinates over which data will be interpolated in z for comparison computing, the second element defines the type of vertical levels, the third one defines the list of vertical intevals (list of tuple).
        
        Some parameters are not compatible : 
        
        - ``trange_seq`` and ``tfreq``
        - ``href`` and ``cloud``
    
data
====
    
        The data section is dedicated to the configuration of input data.
        
        - ``name``: name of the dataset.
        - ``path``: path of the input data files. Use of wild card is possible in order to process multiple files.
        - ``fmt``: user has to configure an armoor format-like.
        - ``platform``: type of platform can be needed for some observations.
        - ``ref``: default value is False. Necessary to flag a dataset as the reference.
    
ouputs
======
    
        Multiple outputs can be configured. The available outputs depend on the executed comparison.
        For instance, a vertical profile of salinity is not possible with ``armoor-comp-sst``.
        See the possible outputs in the dedicated section of the documentation.

        - ``maps``: maps of statistical metrics (bias, rmse, rmsec) or deviation (difference).
        
        .. image:: images/maps.png
            
        - ``diagdisp_glob``: dispersion diagram of selected data.
        
        .. image:: images/diagdisp_glob.png
            
        - ``diagdisp_sel``: dispersion diagram by intervals.
        
        .. image:: images/diagdisp_sel.png
            
        - ``timeseries``: time series of statistical metrics or deviation.
        
        .. image:: images/timeseries.png
        
        - ``mvprofiles``: plot of multiple vertical profiles.
        
        .. image:: images/mvprofiles.png
        
        - ``uvprofiles``: plot of an unique vertical observed profile.
        
        .. image:: images/uvprofiles.png
        
        - ``udiagts``: theta-s diagram of an unique vertical observed profile.
        
        .. image:: images/udiagts.png
        
        - ``mdiagts``: theta-s diagram of multiple vertical observed profiles.
        
        .. image:: images/mdiagts.png

Workflow
--------

    1. Open, decode input files and apply filters --> NetCDF files stored at ``./{comp_name}/metazones/{metazone.name}/{data.name}``.
    2. Colocate products and reference --> NetCDF files stored at ``./{comp_name}/coloc/{metazone.name}/{ref.name}/{data.name}``.
    3. Compute outputs --> NetCDF files stored at ``./{comp_name}/output/{metazone.name}/{ref.name}/{data.name}/{otype}/``.
    4. Plots --> png files stored at ``./{comp_name}/plot/{metazone.name}/{ref.name}/{otype}/``.


.. toctree::
   :maxdepth: 1
   
   cli.comp.sst
   cli.comp.argo
   cli.comp.mooring




