"""ds.interp accessor — thin facade over armoor's interpolation layer.

xarray already has a ``ds.interp()`` method.  Registering this accessor
shadows that method on ``xr.Dataset``, so we restore it via ``__call__``:

    ds.interp(time=target)                  # → xarray's native interp (unchanged)
    ds.interp.time(dates)                   # → base.interp.interp_time (explicit dates)
    ds.interp.tfreq(freq)                   # → data.interp.process_time_interpolation
    ds.interp.grid2loc(coords)              # → data.interp.process_horizontal_interpolation
    ds.interp.grid2section(coords, dx)      # → data.interp.process_horizontal_interpolation
    ds.interp.regrid_from_latlon(lon, lat)  # → data.interp.process_horizontal_interpolation
    ds.interp.regrid_from_nc(ncin)          # → data.interp.process_horizontal_interpolation
    ds.interp.vertical(vname, vlevels)      # → data.interp.process_vertical_interpolation
    ds.interp.vfreq(vname, step)            # → data.interp.process_vertical_interpolation
    ds.interp.regrid(ds_target)             # → base.interp.regrid (needs xesmf)

All business logic lives in ``data/interp.py`` (TimeInterpolation,
HorizontalInterpolation, VerticalInterpolation) and ``base/interp.py``.
This module adds no new logic — it is only a dataset-accessor facade.
"""

import warnings

import xarray as xr

from armoor.base.interp import interp_time, regrid
from armoor.data.interp import (
    process_horizontal_interpolation,
    process_time_interpolation,
    process_vertical_interpolation,
)

# Store xarray's native interp before the accessor shadows it.
_xr_dataset_interp = xr.Dataset.interp


class InterpAccessor:
    """Interpolation accessor for xr.Dataset.

    Examples
    --------
    >>> ds2 = ds.interp(time=target_times)            # xarray native (unchanged)
    >>> ds2 = ds.interp.time(dates)                   # explicit dates
    >>> ds2 = ds.interp.tfreq("1H")                   # regular frequency
    >>> ds2 = ds.interp.grid2loc([(lat, lon), ...])   # scattered locations
    >>> ds2 = ds.interp.grid2section(coords, dx=5.0)  # geodesic section
    >>> ds2 = ds.interp.regrid_from_latlon(lon_grid, lat_grid)
    >>> ds2 = ds.interp.regrid_from_nc("grid.nc")
    >>> ds2 = ds.interp.vertical("depth", [0, 10, 50, 200])
    >>> ds2 = ds.interp.vfreq("depth", step=25.0)
    >>> ds2 = ds.interp.regrid(ds_target)             # needs xesmf
    """

    def __init__(self, obj):
        self._obj = obj

    # ------------------------------------------------------------------
    # Preserve xarray's native ds.interp(coords, …) behaviour
    # ------------------------------------------------------------------

    def __call__(self, coords=None, method="linear", assume_sorted=False,
                 kwargs=None, **coords_kwargs):
        """Delegate to xarray's native ``Dataset.interp``."""
        return _xr_dataset_interp(
            self._obj,
            coords=coords,
            method=method,
            assume_sorted=assume_sorted,
            kwargs=kwargs,
            **coords_kwargs,
        )

    # ------------------------------------------------------------------
    # Temporal
    # ------------------------------------------------------------------

    def time(self, dates, method="linear", preserve_encoding=False,
             keep_flag=False, diurnal_vars=None, persistency=None):
        """Temporal interpolation at arbitrary dates.

        Delegates to :func:`armoor.base.interp.interp_time` (handles
        out-of-range dates, persistency, diurnal correction).

        Parameters
        ----------
        dates : date-like or list of date-like
            Target interpolation dates.
        method : str
            Scipy interpolation method (default ``"linear"``).
        preserve_encoding : bool
            Copy variable encoding to the output.
        keep_flag : bool
            Keep QC flag variables in the output.
        diurnal_vars : list of str, optional
            Variables for which a diurnal correction is applied at edge dates.
        persistency : str, optional
            E.g. ``"mean_3D"`` — window for edge-value computation.

        Returns
        -------
        xr.Dataset
        """
        return interp_time(
            self._obj, dates,
            method=method,
            preserve_encoding=preserve_encoding,
            keep_flag=keep_flag,
            diurnal_vars=diurnal_vars,
            persistency=persistency,
        )

    def tfreq(self, freq, tbound=None):
        """Temporal interpolation at a regular frequency.

        Delegates to :func:`armoor.data.interp.process_time_interpolation`
        with strategy ``"tfreq"`` (internally uses
        :class:`~armoor.data.interp.TimeInterpolation`).

        Parameters
        ----------
        freq : str
            Pandas frequency string (e.g. ``"1H"``, ``"6H"``, ``"1D"``).
        tbound : tuple of date-like, optional
            ``(start, end)`` override.  Defaults to the dataset's own time bounds.

        Returns
        -------
        xr.Dataset
        """
        if tbound is None:
            start = self._obj.time.min().values
            end = self._obj.time.max().values
        else:
            start, end = tbound
        return process_time_interpolation(self._obj, ("tfreq", freq), [start, end])

    # ------------------------------------------------------------------
    # Horizontal
    # ------------------------------------------------------------------

    def grid2loc(self, coords):
        """Interpolate a gridded dataset at scattered (lat, lon) locations.

        Delegates to :func:`armoor.data.interp.process_horizontal_interpolation`
        with strategy ``"cloud"``.

        Parameters
        ----------
        coords : list of (lat, lon) tuples
            Target locations.

        Returns
        -------
        xr.Dataset
            Dataset indexed by ``npts`` instead of the grid (x, y) dims.
        """
        return process_horizontal_interpolation(self._obj, ("cloud", coords))

    def grid2section(self, coords, dx):
        """Interpolate a gridded dataset along a geodesic section.

        Delegates to :func:`armoor.data.interp.process_horizontal_interpolation`
        with strategy ``"section"``.

        Parameters
        ----------
        coords : list of (lat, lon) tuples
            Section waypoints (at least two).
        dx : float
            Along-section step in km.

        Returns
        -------
        xr.Dataset
            Dataset with a ``distance`` coordinate (metres from start).
        """
        return process_horizontal_interpolation(self._obj, ("section", coords, dx))

    def regrid_from_latlon(self, lon_grid, lat_grid):
        """Horizontal regrid onto a regular lon/lat grid (requires xesmf).

        Delegates to :func:`armoor.data.interp.process_horizontal_interpolation`
        with strategy ``"regrid_from_latlon"``.

        Parameters
        ----------
        lon_grid : list of float
            ``[lon_min, lon_max, step_km]``
        lat_grid : list of float
            ``[lat_min, lat_max, step_km]``

        Returns
        -------
        xr.Dataset
        """
        return process_horizontal_interpolation(
            self._obj, ("regrid_from_latlon", lon_grid, lat_grid)
        )

    def regrid_from_nc(self, ncin):
        """Horizontal regrid onto a grid defined in a NetCDF file (requires xesmf).

        Delegates to :func:`armoor.data.interp.process_horizontal_interpolation`
        with strategy ``"regrid_from_nc"``.

        Parameters
        ----------
        ncin : str
            Path to the NetCDF file containing the target grid.

        Returns
        -------
        xr.Dataset
        """
        return process_horizontal_interpolation(self._obj, ("regrid_from_nc", ncin))

    def regrid(self, ds_target):
        """Horizontal regridding onto an arbitrary target grid (requires xesmf).

        Delegates to :func:`armoor.base.interp.regrid`.

        Parameters
        ----------
        ds_target : xr.Dataset
            Dataset defining the target grid (must have ``lon`` / ``lat`` coords).

        Returns
        -------
        xr.Dataset
        """
        return regrid(self._obj, ds_target)

    # ------------------------------------------------------------------
    # Vertical
    # ------------------------------------------------------------------

    def vertical(self, vname, vlevels):
        """Vertical interpolation to specified levels.

        Delegates to :func:`armoor.data.interp.process_vertical_interpolation`
        with strategy ``"vlevel"``.  A plain list is automatically wrapped in an
        ``xr.DataArray`` by the underlying
        :class:`~armoor.data.interp.VerticalInterpolation` class.

        Parameters
        ----------
        vname : str
            Name of the vertical coordinate (``"depth"`` or ``"dens"``).
        vlevels : list, array-like, or xr.DataArray
            Target vertical levels (same units as *vname*).

        Returns
        -------
        xr.Dataset or None
            ``None`` if the dataset has no ``"z"`` dimension.
        """
        return process_vertical_interpolation(self._obj, ("vlevel", (vname, vlevels)))

    def vfreq(self, vname, step):
        """Vertical interpolation at a regular step.

        Delegates to :func:`armoor.data.interp.process_vertical_interpolation`
        with strategy ``"vfreq"``.

        Parameters
        ----------
        vname : str
            Name of the vertical coordinate (``"depth"`` or ``"dens"``).
        step : float
            Vertical step (same units as *vname*).

        Returns
        -------
        xr.Dataset or None
            ``None`` if the dataset has no ``"z"`` dimension.
        """
        return process_vertical_interpolation(self._obj, ("vfreq", (vname, step)))


# Register after class definition — suppress warning because we intentionally
# shadow xarray's built-in ds.interp() method (restored via __call__).
with warnings.catch_warnings():
    warnings.simplefilter("ignore")
    xr.register_dataset_accessor("interp")(InterpAccessor)
