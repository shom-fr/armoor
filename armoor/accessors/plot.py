"""ds.plot accessor — extends xarray's built-in plot accessor.

We subclass xarray's ``DatasetPlotAccessor`` to add armoor-specific
methods while preserving all built-in xarray plotting (scatter, etc.).
The override warning is suppressed because this is an intentional extension.

    ds.plot.maps(var)                  # 2-D map of one variable
    ds.plot.profiles(var, dim)         # vertical profile
    ds.plot.timeseries(var)            # time-series line
    ds.plot.diagdisp(x_var, y_var)     # → base.plot.diagdisp
    ds.plot.shadow_line(x_var, y_var)  # → base.plot.shadow_line

All computation/layout logic for diagdisp and shadow_line lives in
:mod:`armoor.plot`; this accessor only wires them onto xr.Dataset.

The batch DataTree-based plots (maps with cartopy+minimap, T-S diagrams,
multi vertical profiles, …) are handled by :class:`armoor.data.plot.PlotData`
and are not part of this accessor because they operate on a DataTree
produced by the full pipeline, not on a single Dataset.
"""

import warnings

import xarray as xr
from xarray.plot.accessor import DatasetPlotAccessor

# matplotlib and armoor.plot are imported lazily inside each method that
# needs them — both trigger heavy NFS stat chains on HPC cluster filesystems.


class ArmoorPlot(DatasetPlotAccessor):
    """Extended dataset plot accessor.

    All built-in xarray plot methods are inherited.  Armoor adds:

    - :meth:`maps`        — 2-D map of one or all variables
    - :meth:`profiles`    — vertical profiles
    - :meth:`timeseries`  — time-series lines
    - :meth:`diagdisp`    — scatter + linear regression (ref vs prod)
    - :meth:`shadow_line` — line plot with a shadow offset
    """

    def __init__(self, obj):
        super().__init__(obj)
        self._obj = obj

    # ------------------------------------------------------------------
    # Simple plot methods
    # ------------------------------------------------------------------

    def maps(self, var=None, ax=None, **kwargs):
        """Plot a 2-D horizontal map of *var* (or the first variable).

        Parameters
        ----------
        var : str, optional
            Variable name.  If *None* the first data variable is used.
        ax : matplotlib.axes.Axes, optional
            Existing axes to draw on.
        **kwargs
            Forwarded to :func:`xarray.DataArray.plot`.

        Returns
        -------
        matplotlib.collections.QuadMesh or list thereof
        """
        import matplotlib.pyplot as plt
        ds = self._obj
        if var is None:
            var = next(iter(ds.data_vars))
        da = ds[var]
        if ax is None:
            _, ax = plt.subplots()
        return da.plot(ax=ax, **kwargs)

    def profiles(self, var=None, dim="depth", ax=None, **kwargs):
        """Plot vertical profile(s).

        Parameters
        ----------
        var : str, optional
            Variable name.  Defaults to first data variable.
        dim : str
            Vertical dimension name (default ``"depth"``).
        ax : matplotlib.axes.Axes, optional
        **kwargs
            Forwarded to :func:`xarray.DataArray.plot.line`.

        Returns
        -------
        list of Line2D
        """
        import matplotlib.pyplot as plt
        ds = self._obj
        if var is None:
            var = next(iter(ds.data_vars))
        da = ds[var]
        if ax is None:
            _, ax = plt.subplots()
        return da.plot.line(x=dim, ax=ax, **kwargs)

    def timeseries(self, var=None, ax=None, **kwargs):
        """Plot a time-series.

        Parameters
        ----------
        var : str, optional
            Variable name.  Defaults to first data variable.
        ax : matplotlib.axes.Axes, optional
        **kwargs
            Forwarded to :func:`xarray.DataArray.plot.line`.

        Returns
        -------
        list of Line2D
        """
        import matplotlib.pyplot as plt
        ds = self._obj
        if var is None:
            var = next(iter(ds.data_vars))
        da = ds[var]
        if ax is None:
            _, ax = plt.subplots()
        return da.plot.line(x="time", ax=ax, **kwargs)

    # ------------------------------------------------------------------
    # Delegating to armoor.plot
    # ------------------------------------------------------------------

    def diagdisp(self, x_var, y_var, ax=None, x_label=None, y_label=None):
        """Scatter plot with diagonal, linear regression and R² annotation.

        Delegates to :func:`armoor.plot.diagdisp`.

        Parameters
        ----------
        x_var : str
            Dataset variable to plot on the x-axis (e.g. reference values).
        y_var : str
            Dataset variable to plot on the y-axis (e.g. product values).
        ax : matplotlib.axes.Axes, optional
            Existing axes.  A new figure is created when *None*.
        x_label : str, optional
            X-axis label.  Defaults to *x_var*.
        y_label : str, optional
            Y-axis label.  Defaults to *y_var*.

        Returns
        -------
        matplotlib.axes.Axes or None
            *None* if both arrays are fully NaN.

        Examples
        --------
        >>> ds.plot.diagdisp("ref_temp", "prod_temp")
        """
        import matplotlib.pyplot as plt
        from armoor.plot import diagdisp as _diagdisp
        ds = self._obj
        if ax is None:
            _, ax = plt.subplots()
        return _diagdisp(
            ds[x_var],
            ds[y_var],
            ax,
            x_label if x_label is not None else x_var,
            y_label if y_label is not None else y_var,
        )

    def shadow_line(self, x_var, y_var, ax=None, label=None, color="k"):
        """Line plot with a grey shadow offset for visual depth.

        Delegates to :func:`armoor.plot.shadow_line`.

        Parameters
        ----------
        x_var : str
            Dataset variable to use as x values (e.g. ``"time"``), or a
            coordinate name.
        y_var : str
            Dataset variable to use as y values.
        ax : matplotlib.axes.Axes, optional
            Existing axes.  A new figure is created when *None*.
        label : str, optional
            Legend label for the line.
        color : str, optional
            Line colour (default ``"k"``).

        Returns
        -------
        None

        Examples
        --------
        >>> ds.plot.shadow_line("time", "temp", label="temperature")
        """
        import matplotlib.pyplot as plt
        from armoor.plot import shadow_line as _shadow_line
        ds = self._obj
        if ax is None:
            _, ax = plt.subplots()
        x = ds[x_var] if x_var in ds else ds.coords[x_var]
        _shadow_line(x, ds[y_var], ax, label=label, color=color)


# Override xarray's "plot" accessor — suppress the re-registration warning.
with warnings.catch_warnings():
    warnings.simplefilter("ignore")
    xr.register_dataset_accessor("plot")(ArmoorPlot)
