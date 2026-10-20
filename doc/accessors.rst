.. _accessors:

Dataset Accessors
=================

Importing ``armoor`` registers seven xarray *accessor* plugins on every
:class:`xarray.Dataset`.  Each accessor groups a family of operations under a
short namespace, so you can chain them directly on any dataset without
importing helper modules manually.

.. code-block:: python

    import armoor          # one import registers all accessors
    import xarray as xr

    ds = xr.open_dataset("mydata.nc")

    ds.filters             # → FiltersAccessor
    ds.oceanvars           # → OceanVars
    ds.coloc               # → ColocAccessor
    ds.stats               # → StatsAccessor
    ds.interp              # → InterpAccessor
    ds.range               # → RangeAccessor
    ds.plot                # → ArmoorPlot (extends xarray's built-in)

.. contents:: Accessors
   :local:
   :depth: 1


.. _accessor-filters:

ds.filters
----------

**Module:** :mod:`armoor.accessors.filters`

Filter a dataset along time, space, quality or bathymetry dimensions.
All filter types are combined in a single mask operation to minimise
memory allocations.

.. code-block:: python

    # Apply multiple filters at once
    ds2 = ds.filters.combined({
        "time_selection": {"minimum": "2020-01-01", "maximum": "2020-03-31"},
        "polygon":        {"coords": [(lat0, lon0), (lat1, lon1), ...]},
        "quality":        {"qname": "temp", "qmin": 1, "qmax": 3},
        "tresample":      "1D",
    })

    # Nearest-neighbour selection around observation locations
    ds2 = ds.filters.sel_closest(ds_obs)

Supported filter keys for :meth:`~armoor.accessors.filters.FiltersAccessor.combined`:

.. list-table::
   :header-rows: 1
   :widths: 20 80

   * - Key
     - Effect
   * - ``time_selection``
     - Keep data between ``minimum`` and ``maximum`` dates
   * - ``hours_selection``
     - Keep data within a daily hour range (handles midnight wrap-around)
   * - ``polygon``
     - Keep points inside a polygon defined by ``coords`` (lat, lon) tuples; ``dilate: true`` expands the mask on gridded data
   * - ``quality``
     - Keep points where ``<qname>_qc`` is between ``qmin`` and ``qmax``
   * - ``data_selection``
     - Keep points where ``dim`` is between ``minimum`` and ``maximum`` (or equal to ``value``)
   * - ``bathy``
     - Keep points where bathymetry depth is between ``min`` and ``max``
   * - ``tide``
     - Apply a tidal filter (``"demerliac"``, ``"godin"``, …)
   * - ``tresample``
     - Resample in time to the given frequency string (e.g. ``"1D"``)
   * - ``tsmooth``
     - Gaussian temporal smoothing over the given frequency window
   * - ``oceanvars``
     - Select / compute ocean variables by name (see :ref:`accessor-oceanvars`)


.. _accessor-oceanvars:

ds.oceanvars
------------

**Module:** :mod:`armoor.accessors.oceanvars`

Select or derive standard ocean variables.  Computed quantities (potential
temperature, pressure, potential density, sound speed) are derived from
whatever variables are present in the dataset using the
`GSW <https://teos-10.github.io/GSW-Python/>`_ Thermodynamic Equation of
Seawater library.

.. code-block:: python

    temp   = ds.oceanvars.sel("temp")       # in-situ temperature
    ptemp  = ds.oceanvars.sel("ptemp")      # potential temperature (computed if absent)
    sal    = ds.oceanvars.sel("sal")        # salinity
    pres   = ds.oceanvars.sel("pres")       # pressure (computed from depth if absent)
    pdens  = ds.oceanvars.sel("pdens")      # potential density
    speed  = ds.oceanvars.sel("cspeed")     # current speed  (u²+v²)^½
    cdir   = ds.oceanvars.sel("cdir")       # current direction arctan(v, u)

    # Individual methods are also available
    ptemp = ds.oceanvars.sel_ptemp()
    pdens = ds.oceanvars.sel_pdens(ref_dens=0)   # σ₀, σ₁, …, σ₄

Variable derivation cascade:

.. list-table::
   :header-rows: 1
   :widths: 15 85

   * - Variable
     - Derivation
   * - ``ptemp``
     - From ``temp`` + ``sal`` + ``pres`` via :func:`gsw.pt0_from_t`
   * - ``temp``
     - From ``ptemp`` + ``sal`` + ``pres`` via :func:`gsw.t_from_CT`
   * - ``pres``
     - From ``depth`` via :func:`gsw.p_from_z` (mean latitude approximation)
   * - ``pdens``
     - From ``sal`` + ``ptemp`` + ``pres`` via GSW sigma functions (σ₀ … σ₄)
   * - ``sndspeed``
     - From ``sal`` + ``ptemp`` + ``pres`` via :func:`gsw.sound_speed`
   * - ``cspeed``
     - :math:`\sqrt{u^2 + v^2}`
   * - ``cdir``
     - :math:`\arctan(v, u)`


.. _accessor-coloc:

ds.coloc
--------

**Module:** :mod:`armoor.accessors.coloc`

Colocate a product dataset against a reference dataset in time, space and/or
depth.  The entry point is :meth:`~armoor.accessors.coloc.ColocAccessor.with_ref`,
which returns a :class:`~armoor.accessors.coloc.ColocSession` that supports
method chaining.

.. code-block:: python

    # Basic usage — unpack directly
    ds_prod2, ds_ref2 = ds_prod.coloc.with_ref(ds_ref).time(param, tbound=tbound)

    # Chaining multiple colocation steps
    session = (
        ds_prod.coloc.with_ref(ds_ref)
               .time(("trange_seq", ["3D", "reference"]), tbound=tbound)
               .horizontal(("grid2loc", [...]))
               .vertical(("vrange", [0, 10, 50, 100, 200]))
    )
    ds_prod3, ds_ref3 = session

A :class:`~armoor.accessors.coloc.ColocSession` always holds the current
``(prod, ref)`` pair.  Each step returns a **new** session so the original
datasets are never modified.

.. list-table::
   :header-rows: 1
   :widths: 25 75

   * - Method
     - Description
   * - ``.with_ref(ds_ref)``
     - Start a session — ``ds_prod.coloc.with_ref(ds_ref)``
   * - ``.time(param, tbound)``
     - Temporal colocation; ``param`` selects the strategy (``trange_seq``, ``tfreq``, …)
   * - ``.horizontal(param)``
     - Horizontal colocation (grid-to-location or nearest-neighbour)
   * - ``.vertical(param)``
     - Vertical colocation (depth levels or density levels)

.. seealso:: :ref:`guide-colocation` for how these strategies map to
   metazone parameters in the ``armoor-comp-*`` pipeline.


.. _accessor-stats:

ds.stats
--------

**Module:** :mod:`armoor.accessors.stats`

Statistical reduction and model-vs-reference comparison.  Simple reductions
return an :class:`xarray.Dataset` and can be chained with ``.plot``.

.. code-block:: python

    # Reductions
    ds.stats.mean(dim="time")
    ds.stats.std(dim="time")

    # Point-wise metrics (return a Dataset of the same shape)
    ds.stats.bias(ds_ref)
    ds.stats.rmse(ds_ref)
    ds.stats.rmsec(ds_ref)

    # Reduced metrics
    ds.stats.bias(ds_ref, dim="time")
    ds.stats.rmse(ds_ref, dim="time")

    # Full bias/RMSE/RMSEc DataTree workflow
    dtprod, dtref, dtcomps = ds_prod.stats.compare(
        ds_ref,
        dims=["time"],
        mparams={"trange_seq": True},
    )

    # Chaining example
    ds.stats.mean(dim="time").plot.maps()

:meth:`~armoor.accessors.stats.StatsAccessor.compare` delegates to
:class:`armoor.comp.stats.StatsComp` and returns three
:class:`xarray.DataTree` objects (product, reference, comparisons) exactly
as used by the plotting pipeline.


.. _accessor-interp:

ds.interp
---------

**Module:** :mod:`armoor.accessors.interp`

Temporal, horizontal and vertical interpolation.  xarray's native
``ds.interp(coords, …)`` is **preserved** via ``__call__``, so existing code
requires no changes.

.. code-block:: python

    # xarray native interp — unchanged
    ds2 = ds.interp(time=target_times)

    # Armoor temporal interpolation
    # (handles out-of-range dates, persistency, diurnal correction)
    ds2 = ds.interp.time(
        dates=["2020-06-15 00:00", "2020-06-15 12:00"],
        persistency="mean_3D",       # optional
        diurnal_vars=["sst"],        # optional
    )

    # Grid → scattered locations
    ds2 = ds.interp.grid2loc([(lat0, lon0), (lat1, lon1)])

    # Grid → section  (waypoints + step in km)
    ds2 = ds.interp.grid2section([(lat0, lon0), (lat1, lon1)], dx=5.0)

    # Vertical interpolation (list is auto-wrapped in a DataArray)
    ds2 = ds.interp.vertical("depth", [0, 10, 50, 100, 200, 500])

    # Horizontal regridding (bilinear, bicubic or conservative)
    ds2 = ds.interp.regrid(ds_target_grid)

.. list-table::
   :header-rows: 1
   :widths: 30 70

   * - Method
     - Description
   * - ``__call__(coords, …)``
     - xarray's native ``Dataset.interp`` (no change)
   * - ``.time(dates, …)``
     - Vectorised temporal interp with persistency and diurnal options
   * - ``.grid2loc(coords)``
     - Bilinear interpolation from a 2-D grid to scattered (lat, lon) points
   * - ``.grid2section(coords, dx)``
     - Interpolation along a geodesic section; output has a ``distance`` coordinate
   * - ``.vertical(vname, vlevels)``
     - 1-D vertical interpolation via ``xoa.regrid.regrid1d``
   * - ``.regrid(ds_target)``
     - Horizontal regridding between two grids via ``xoa.regrid.Regridder``


.. _accessor-range:

ds.range
--------

**Module:** :mod:`armoor.accessors.range`

Temporal and vertical range operations.  High-level methods (``tfreq``,
``vertical``) return a single :class:`xarray.Dataset`; low-level split
methods (``trange_seq``, ``vrange``, ``vlevels``, ``by_time``) return a
**list** of datasets (one per bin/level).

.. code-block:: python

    # Split into daily bins → Dataset with a 'trange' dimension
    ds2 = ds.range.tfreq("1D")

    # Mask values outside a depth range
    ds2 = ds.range.vertical("depth", [0, 200])

    # Split into sequential time bins → list of datasets
    subsets = ds.range.trange_seq("2020-01-01", "2020-12-31", "1MS")

    # Vertical range mask per bin → list of datasets
    subsets = ds.range.vrange("depth", [(0, 100), (100, 500)])

    # One dataset per vertical level → list of datasets
    subsets = ds.range.vlevels("depth")

    # One dataset per unique time step → list of datasets
    subsets = ds.range.by_time()

.. list-table::
   :header-rows: 1
   :widths: 30 70

   * - Method
     - Description
   * - ``.tfreq(freq)``
     - Split into time bins; concatenate along a new ``trange`` dimension. Returns :class:`xr.Dataset`.
   * - ``.vertical(vname, vrange)``
     - Mask 3-D variables outside ``(vmin, vmax)`` along *vname*. Returns :class:`xr.Dataset`.
   * - ``.trange_seq(tstart, tend, tbin)``
     - Sequential time-bin split. Returns ``list[xr.Dataset]``.
   * - ``.vrange(vname, vbins)``
     - Vertical range mask per bin. Returns ``list[xr.Dataset]``.
   * - ``.vlevels(vname)``
     - One subset per ``z`` index. Returns ``list[xr.Dataset]``.
   * - ``.by_time()``
     - One subset per unique time step. Returns ``list[xr.Dataset]``.


.. _accessor-plot:

ds.plot
-------

**Module:** :mod:`armoor.accessors.plot`

Extends xarray's built-in ``DatasetPlotAccessor`` with armoor-specific
convenience methods.  All built-in xarray plot methods (``scatter``, etc.)
are inherited unchanged.

.. code-block:: python

    # Simple plots
    ds.plot.maps()                              # 2-D map (first variable)
    ds.plot.maps(var="temp")                    # specify variable
    ds.plot.profiles(var="temp", dim="depth")   # vertical profile
    ds.plot.timeseries(var="temp")              # time-series line

    # From armoor.plot
    ds.plot.diagdisp("ref_temp", "prod_temp")   # scatter + regression (R²)
    ds.plot.shadow_line("time", "temp",
                        label="temperature")    # line with grey shadow offset

    # xarray built-ins still work
    ds.plot.scatter(x="lon", y="lat", hue="temp")

    # Chain from stats
    ds.stats.mean(dim="time").plot.maps()

.. note::

   The batch, DataTree-based plots (cartopy maps with minimap, T-S diagrams,
   multi vertical profiles, …) are produced by
   :class:`armoor.data.plot.PlotOceanModel`, which operates on the full pipeline
   DataTree, and are **not** exposed through this accessor.

.. list-table::
   :header-rows: 1
   :widths: 30 70

   * - Method
     - Description
   * - ``.maps(var, ax, **kw)``
     - 2-D map of a variable via :func:`xarray.DataArray.plot`
   * - ``.profiles(var, dim, ax, **kw)``
     - Vertical profile line via :func:`xarray.DataArray.plot.line`
   * - ``.timeseries(var, ax, **kw)``
     - Time-series line via :func:`xarray.DataArray.plot.line`
   * - ``.diagdisp(x_var, y_var, ax, …)``
     - Scatter + diagonal + regression + R² — delegates to :func:`armoor.plot.diagdisp`
   * - ``.shadow_line(x_var, y_var, ax, …)``
     - Line with a grey shadow offset — delegates to :func:`armoor.plot.shadow_line`


API Reference
-------------

.. autosummary::
   :toctree: _api
   :nosignatures:

   armoor.accessors.filters
   armoor.accessors.oceanvars
   armoor.accessors.coloc
   armoor.accessors.stats
   armoor.accessors.interp
   armoor.accessors.range
   armoor.accessors.plot
