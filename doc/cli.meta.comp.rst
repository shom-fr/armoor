.. _clicomp:

Command-line interfaces for comparison
######################################

Configuration file
------------------

    Armoor executables dedicated to comparison have to be associated with a configuration file based on `comp.ini`:
        .. literalinclude:: ../armoor/cli/comp.ini
               :language: ini
    
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
        
        .. grid:: 3

            .. grid-item-card:: Maps of statistics (``maps``)

                Maps of statistical metrics (bias, rmse, rmsec) or deviation (difference).

                .. image:: images/comp_maps.png
                
                :download:`Download <images/comp_maps.png>`

            .. grid-item-card:: Dispersion diagrams (``diagdisp_glob``)

                Dispersion diagrams of data.
                
                .. image:: images/comp_diagdisp_glob.png
                
                :download:`Download <images/comp_diagdisp_glob.png>`
                
            .. grid-item-card:: Dispersion diagrams by intervals (``diagdisp_sel``)

                Dispersion diagrams of selected data by intervals.
                
                .. image:: images/comp_diagdisp_sel.png
                
                :download:`Download <images/comp_diagdisp_sel.png>`
                
            .. grid-item-card:: Time series (``timeseries``)

                Time series of statistical metrics or deviation.
                
                .. image:: images/comp_timeseries.png
                
                :download:`Download <images/comp_timeseries.png>`
                
            .. grid-item-card:: Multiple vertical profiles (``mvprofiles``)

                Plot of multiple vertical profiles.
                
                .. image:: images/comp_mvprofiles.png
                
                :download:`Download <images/comp_mvprofiles.png>`
                
            .. grid-item-card:: Unique vertical profiles (``uvprofiles``)

                Plot of unique vertical profiles.
                
                .. image:: images/comp_uvprofiles.png
                
                :download:`Download <images/comp_uvprofiles.png>`
                
            .. grid-item-card:: theta-s diagram of an unique vertical profiles (``udiagts``)

                Plot of a theta-s diagram by observed profile.
                
                .. image:: images/comp_udiagts.png
                
                :download:`Download <images/comp_udiagts.png>`
                
            .. grid-item-card:: theta-s diagram of multiple vertical profiles (``mdiagts``)

                Plot of a theta-s diagram of every observed profiles.
                
                .. image:: images/comp_mdiagts.png
                
                :download:`Download <images/comp_mdiagts.png>`

            .. grid-item-card:: time series for drifters (``timeseries``)

                Time series distance and direction between drifter and virtual trajectories computed by parcels with the model currents.
                
                .. image:: images/comp_timeseries_drifter.png
                
                :download:`Download <images/comp_timeseries_drifter.png>`
                
            .. grid-item-card:: trajectories maps for drifters (``maps_trajectory``)

                Maps of a drifter trajectory and virtual ones computed by parcels with the model currents.
                
                .. image:: images/comp_map_trajectories.png
                
                :download:`Download <images/comp_map_trajectories.png>`
                
            .. grid-item-card:: current maps for drifters (``maps_current``)

                Maps of currents of a drifter and the model ones interpolated along the drifter trajectory.
                
                .. image:: images/comp_map_current.png
                
                :download:`Download <images/comp_map_current.png>`
   

Workflow
--------

    1. Open, decode input files and apply filters --> Zarr files stored at ``./{comp_name}/metazones/{metazone.name}/{data.name}``.
    2. Colocate products and reference --> Zarr files stored at ``./{comp_name}/coloc/{metazone.name}/{ref.name}/{data.name}``.
    3. Compute outputs --> Zarr files stored at ``./{comp_name}/output/{metazone.name}/{ref.name}/{data.name}/{otype}/``.
    4. Plots --> png files stored at ``./{comp_name}/plot/{metazone.name}/{ref.name}/{otype}/``.


.. toctree::
   :maxdepth: 1
   
   cli.meta.comp.argo
   cli.meta.comp.drifter
   cli.meta.comp.models
   cli.meta.comp.mooring
   cli.meta.comp.sst
   




