import logging
from typing import List, Optional, Tuple, Union

import numpy as np
import pandas as pd
import xarray as xr
from xoa.geo import m2deg

from armoor.dispatch import SubclassingMethodRegistry
from armoor.interp import grid2loc, interp_time, vinterp, regrid, grid2section, coarsen as _coarsen

logger = logging.getLogger(__name__)


class AbstractInterpolation(SubclassingMethodRegistry):
    """Abstract base for interpolation strategies (time/horizontal/vertical).

    Subclasses register their own methods for dispatch via `call`; see
    `armoor.dispatch.SubclassingMethodRegistry`.
    """

    _dispatch_label = "Interpolation"


class TimeInterpolation(AbstractInterpolation):
    """Interpolate in time a dataset.

    Parameters
    ----------
    xarray_obj : xarray.Dataset
        Product dataset to subset.
    """

    def __init__(self, ds: xr.Dataset, tbound: tuple) -> None:
        self.ds = ds
        self.methods = {}
        self.start = tbound[0]
        self.end = tbound[1]

    def tfreq(self, tfreq: str) -> xr.Dataset:
        """Subset dataset selecting elements at specific terms.

        Parameters
        ----------
        freq : str
            See :ref:`here <pandas:timeseries.offset_aliases>` for a list of
            frequency aliases.

        Returns
        -------
        xarray.Dataset, xarray.Dataset
        """
        time = pd.date_range(start=self.start, end=self.end, freq=tfreq)
        self.ds = interp_time(self.ds, time)
        return self.ds


class HorizontalInterpolation(AbstractInterpolation):
    """Horizontal resampling of a gridded dataset.

    Available strategies (passed as the first element of *param* in
    :func:`process_horizontal_interpolation`):

    * ``"cloud"`` — bilinear interpolation at scattered (lat, lon) points.
    * ``"section"`` — interpolation along a geodesic, broken-line section.
    * ``"regrid_from_latlon"`` — bilinear regrid onto a regular lon/lat grid.
    * ``"regrid_from_nc"`` — bilinear regrid onto a grid defined in a NetCDF
      file.
    * ``"coarsen"`` — block aggregation onto a coarser structured grid
      (no xesmf required).

    Parameters
    ----------
    ds : xarray.Dataset
        Dataset to resample.
    """

    def __init__(self, ds: xr.Dataset) -> None:
        self.ds = ds
        self.methods = {}

    def cloud(self, coords: List[Tuple[float, float]]) -> xr.Dataset:
        """Interpolate datasets at specific coordinates.

        Parameters
        ----------
        coordinates : list of tuples
            Set of points coordinates (lon, lat) defining the coordinates to select.

        Returns
        -------
        xarray.Dataset, xarray.Dataset
            Dataset with elements located at specific coordinates.
        """
        return grid2loc(self.ds, coords)

    def section(self, args: dict) -> Union[xr.Dataset, dict]:
        """Interpolate datasets over one or more named broken-line sections.

        Parameters
        ----------
        args: dict
            Either a single unnamed section -- a ``coords`` key (list of
            (lat, lon) tuples defining the section's waypoints, at least
            two -- more than two makes a broken line/polyline) and a
            ``dx`` key (the along-section step in km) -- or several named
            sections sharing one ``dx``: a ``dx`` key plus one nested dict
            per named section, each with its own ``coords`` key.

        Returns
        -------
        xarray.Dataset or dict
            A single unnamed section's ``xarray.Dataset``, or a mapping of
            section name to its ``xarray.Dataset``, each with a
            ``distance`` coordinate (metres from the first waypoint).
        """
        named_sections = {
            name: subargs for name, subargs in args.items() if isinstance(subargs, dict)
        }
        if not named_sections:
            return grid2section(self.ds, args["coords"], args["dx"])
        dx = args["dx"]
        return {
            name: grid2section(self.ds, subargs["coords"], dx)
            for name, subargs in named_sections.items()
        }

    def regrid_from_latlon(
        self, lon_grid: Tuple[float, float, float], lat_grid: Tuple[float, float, float]
    ) -> xr.Dataset:
        """Regrid dataset on extra grid specified via lat/lon coordinates.

        Parameters
        ----------
        lon_grid : tuple
            lon_min, lon_max, lon_step
        lat_grid : tuple
            lat_min, lat_max, lat_step

        Returns
        -------
        xarray.DataArray
            New grid
        """
        lat_mean = 0.5 * (lat_grid[0] + lat_grid[1])
        lat_grid[2] = m2deg(lat_grid[-1] * 1e3, lat=lat_mean)
        lon_grid[2] = m2deg(lon_grid[-1] * 1e3, lat=lat_mean)
        lat = np.arange(*lat_grid)
        lon = np.arange(*lon_grid)
        lon, lat = np.meshgrid(lon, lat)
        new_grid = xr.DataArray(
            data=np.full((np.shape(lon)), np.nan),
            dims=["y", "x"],
            name="grid",
            coords=dict(
                lon=(["y", "x"], lon),
                lat=(["y", "x"], lat),
            ),
        )
        return self.regrid(new_grid)

    def regrid_from_nc(self, ncin: str) -> xr.Dataset:
        """Regrid dataset on extra grid defined in a netcdf file.

        Parameters
        ----------
        ncin: str
            Path of netcdf file containing the new grid.

        Returns
        -------
        xarray.DataArray
            New grid
        """
        new_grid = xr.open_dataset(ncin)[["lon", "lat"]]
        return self.regrid(new_grid)

    def regrid(self, new_grid: xr.DataArray) -> xr.Dataset:
        """Regrid a dataset on extra grid.

        Parameters
        ----------
        new_grid: xr.DataArray
            New grid defined by new lat/lon coordinates.

        Returns
        -------
        xarray.Dataset
        """
        if "depth" in self.ds.coords:
            self.ds = self.ds.reset_coords("depth")
        self.ds = regrid(self.ds, new_grid)
        if "mask" in self.ds:
            self.ds = self.ds.drop_vars("mask")
        return self.ds

    def coarsen(self, factor: int, boundary: str = "trim", method: str = "mean") -> xr.Dataset:
        """Coarsen the dataset by aggregating over spatial blocks.

        Parameters
        ----------
        factor : int
            Coarsening factor applied to both ``x`` and ``y`` dimensions.
        boundary : str
            How to handle non-divisible sizes: ``"trim"`` (default) or ``"pad"``.
        method : str
            Aggregation method: ``"mean"`` (default), ``"median"``, ``"min"``, ``"max"``.

        Returns
        -------
        xr.Dataset
        """
        self.ds = _coarsen(self.ds, factor=factor, boundary=boundary, method=method)
        return self.ds

    def _clean_coordinates(self, dataset: xr.Dataset) -> xr.Dataset:
        """Remove temporary coordinates and rename primary ones."""
        coords_to_drop = ["lon", "lat", "lon_1", "lat_1"]
        existing_coords = [coord for coord in coords_to_drop if coord in dataset.coords]

        cleaned_ds = dataset.drop_vars(existing_coords)
        return cleaned_ds.rename({"lon_0": "lon", "lat_0": "lat"})


class VerticalInterpolation(AbstractInterpolation):
    """Interpolate verticaly a dataset.

    Parameters
    ----------
    xarray_obj : xarray.Dataset
        Product dataset to interpolate.
    """

    def __init__(self, ds: xr.Dataset) -> None:
        self.ds = ds
        self.methods = {}
        self.logger = logging.getLogger(__name__)

    def vlevel(self, args: dict) -> Optional[xr.Dataset]:
        """Interpolate datasets to specified vertical levels.

        Parameters
        ----------
        args: dict
            Dict with a ``vname`` key (the vertical coordinate name) and a
            ``levels`` key (the list of vertical levels to interpolate to).

        Returns
        -------
        xarray.Dataset, xarray.Dataset
            A tuple containing the verticaly interpolated reference dataset and product dataset.
        """
        vname = args["vname"]
        vlevels = args["levels"]
        return self._vinterp_(vname, vlevels)

    def vfreq(self, args: dict) -> Optional[xr.Dataset]:
        """Interpolate datasets to specified a vertical step.

        Parameters
        ----------
        args: dict
            Dict with a ``vname`` key (the vertical coordinate name) and a
            ``step`` key (the vertical step to interpolate on).

        Returns
        -------
        xarray.Dataset, xarray.Dataset
            A tuple containing the verticaly interpolated reference dataset and product dataset.
        """
        vname = args["vname"]
        vfreq = float(args["step"])
        vlevels = np.arange(self.ds[vname].min(), self.ds[vname].max(), vfreq)
        return self._vinterp_(vname, vlevels)

    def _vinterp_(self, vname, vlevels):
        """Interpolate datasets by specifying vertical levels and vertical coordinate name.

        Parameters
        ----------
        vname: str
            Name of the vertical coordinate.
        vlevels: list
            Vertical levels.

        Returns
        -------
        xarray.Dataset, xarray.Dataset
            A tuple containing the verticaly interpolated reference dataset and product dataset.
        """
        # xoa's regrid1d requires monotonically sorted target levels --
        # passed out of order (e.g. metazones.cfg's `levels=10,1000,500`),
        # it silently interpolates most cells to NaN instead of raising.
        vlevels = xr.DataArray(sorted(vlevels), dims="z", name=vname)
        attrs = self.ds.attrs
        if "z" in self.ds.dims:
            self.ds = vinterp(self.ds, vname, vlevels)
            self.ds.attrs.update(attrs)
            return self.ds
        else:
            logger.warning("No 'z' dim in product")
            return None


def process_time_interpolation(ds: xr.Dataset, param: list, tbound: tuple) -> xr.Dataset:
    """Process interpolation for time dimension.

    Parameters
    ----------
    ds: xr.Dataset
        Product dataset.
    param: list
        Parameters for time interpolation.
    tbound: list
        Time bounds for interpolation.

    Returns
    -------
    tuple
        Interpolated product dataset.
    """
    logger.info("---- Time interpolation")
    interp = TimeInterpolation(ds, tbound)
    interp.__post_init__()
    ds = interp.call(*param)
    return ds


def process_horizontal_interpolation(ds: xr.Dataset, param: list) -> xr.Dataset:
    """Process interpolation for horizontal dimensions.

    Parameters
    ----------
    ds: xr.Dataset
        Product dataset.
    param: list
        Parameters for horizontal interpolation.

    Returns
    -------
    tuple
        Interpolated product dataset.
    """
    logger.info("---- Horizontal interpolation")
    interp = HorizontalInterpolation(ds)
    interp.__post_init__()
    ds = interp.call(*param)
    return ds


def process_vertical_interpolation(ds: xr.Dataset, param: list) -> Optional[xr.Dataset]:
    """Process interpolation for vertical dimensions.

    Parameters
    ----------
    ds: xr.Dataset
        Product dataset.
    param: list
        Parameters for vertical interpolation.

    Returns
    -------
    tuple
        Interpolated product datasets.
    """
    logger.info("---- Vertical interpolation")
    interp = VerticalInterpolation(ds)
    interp.__post_init__()
    ds = interp.call(*param)
    return ds
