##########################################################
Armoor - Analysis of Regional MOdelised and ObseRved ocean
##########################################################

Armoor is a python library for helping analysis of regional modelised and observed ocean.

- Pipeline

        Every analysis follows the same stages:

        * Open and decode a dataset (CMEMS model outputs, HYCOM/CROCO,
          Argo/mooring/drifter in-situ observations, satellite SST,
          WOA18/BOBYCLIM climatologies, hydrological sections...)
        * Filter and range it (time, horizontal, vertical, quality)
        * Colocate it against a reference (disk radius, grid regridding,
          a cloud of fixed points, or a moving track)
        * Compute comparison statistics (bias, RMSE, centered RMSE)
        * Render the result (maps, timeseries, dispersion diagrams,
          vertical profiles, T-S diagrams, hydrological sections...)

- Interfaces

        * Python/xarray accessors (``ds.filters``, ``ds.oceanvars``,
          ``ds.interp``, ``ds.range``, ``ds.coloc``, ``ds.stats``,
          ``ds.plot``) for interactive or scripted use
        * Command-line executables (``armoor-comp-argo``/``-sst``/``-drifter``/
          ``-mooring``/``-models``/``-clim``/``-hydrosection``, ``armoor-data``,
          ``armoor-filters-*``, ``armoor-interp-*``, ``armoor-coloc-*``, ...)
          driven by a pair of configuration files (metazones + data/outputs)
        * A web viewer (``armoor-viewer``) for interactive exploration of
          produced datasets
        * GitLab issue tracking integration (``armoor-tick``)

- Documentation

        The documentation is generated and hosted by GitHub Pages:
        https://shom-fr.github.io/armoor/

- Sources and help

        Sources are available on GitHub:
        https://github.com/shom-fr/armoor.
        Here you can also post issues for requests and bug reports.


- License

        Armoor is licensed under the Apache License, Version 2.0. Copyright 2026
        Shom. See ``LICENSE.rst`` for the full text.


- Contacts

        * Mathieu Morvan <mathieu.morvan[at]shom.fr>

