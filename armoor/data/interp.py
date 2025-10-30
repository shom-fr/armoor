import logging

import numpy as np
import pandas as pd
import xarray as xr
from xoa.geo import m2deg

from armoor.__init__ import ArmoorError
from armoor.base.interp import grid2loc, interp_time, vinterp, regrid, grid2section

logger = logging.getLogger(__name__)

    
class AbstractInterpolation:
    """Abstract class for interpolation."""
    
    def __init__(self):
        """Initialize the AbstractInterpolation instance with an empty dictionary to store methods."""
        self.methods = {}

    def register_method(self, func):
        """Register a method in the methods dictionary.

        Parameters
        ----------
        func
            The method to be registered.

        Returns
        -------
            The registered method.
        """
        self.methods[func.__name__] = func
        return func

    def __post_init__(self):
        """Register all callable methods of the class after initialization.
        
        This method is called after the instance is initialized.
        """
        for name, method in vars(self.__class__).items():
            if callable(method) and not name.startswith("__"):
                self.register_method(method)

    def call(self, method_name, *args, **kwargs):
        """Call a method by its name.

        Parameters
        ----------
        method_name: str
            The name of the method to call.

        Returns
        -------
            The result of the called method.

        Raises
        ------
            AttributeError: If the method is not found.
        """
        method = self.methods.get(method_name)
        if method:
            return method(self, *args, **kwargs)
        raise ArmoorError(f"Interpolation '{method_name}' not found")

    def __init_subclass__(cls):
        """Initialize the subclass by adding the __post_init__ method to the class.
        
        This method is called after the class is defined.
        """
        def __post_init__(self):
            for name, method in vars(cls).items():
                if callable(method) and not name.startswith("__"):
                    self.register_method(method)
        cls.__post_init__ = __post_init__


class TimeInterpolation(AbstractInterpolation):
    """Interpolate in time a dataset.

    Parameters
    ----------
    xarray_obj : xarray.Dataset
        Product dataset to subset.
    """
    
    def __init__(self, ds, tbound):
        self.ds = ds
        self.methods = {}
        self.start = tbound[0]
        self.end = tbound[1]

    def tfreq(self, tfreq: str) -> xr.Dataset:
        """Subset dataset selecting elements at specific terms.
    
        Parameters
        ----------
        freq : str
            See :ref:`here <timeseries.offset_aliases>` for a list of
            frequency aliases.
            
        Returns
        -------
        xarray.Dataset, xarray.Dataset
        """
        time = pd.date_range(start=self.start, end=self.end, freq=tfreq)
        self.ds = interp_time(self.ds, time)
        return self.ds


class HorizontalInterpolation(AbstractInterpolation):
    """Interpolate horizontaly a dataset.

    Parameters
    ----------
    xarray_obj : xarray.Dataset
        Product dataset to subset.
    """
    
    def __init__(self, ds):
        self.ds = ds
        self.methods = {}

    def cloud(self, coords: [(float, float)]):
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
    
    def section(self, coords: [(float, float)], dx: float):
        """Interpolate datasets over section.

        Parameters
        ----------
        coordinates : list of 2 tuples
            Two points coordinates (lon, lat) defining the bounds of the section.

        Returns
        -------
        xarray.Dataset, xarray.Dataset
            Dataset interpolated over the section.
        """
        return grid2section(self.ds, coords, dx)
    
    def regrid_from_latlon(self, lon_grid: (float, float, float), lat_grid: (float, float, float)):
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
        lat_grid[2] = m2deg(
            lat_grid[-1] * 1e3,
            lat=lat_mean
            )
        lon_grid[2] = m2deg(
            lon_grid[-1] * 1e3,
            lat=lat_mean
            )
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
    
    def regrid_from_nc(self, ncin: str):
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
    
    def regrid(self, new_grid: xr.DataArray):
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
    
    def __init__(self, ds):
        self.ds = ds
        self.methods = {}
        self.logger = logging.getLogger(__name__)
        
    def vlevel(self, args: (str, list)):
        """Interpolate datasets to specified vertical levels.
        
        Parameters
        ----------
        args: dict
            A dictionary with a single key-value pair where the key is the vertical coordinate name
            and the value is a list of vertical levels to interpolate to.
        
        Returns
        -------
        xarray.Dataset, xarray.Dataset
            A tuple containing the verticaly interpolated reference dataset and product dataset.
        """
        vname = args[0]
        vlevels = args[1]
        return self._vinterp_(vname, vlevels)
        
    def vfreq(self, args: (str, list)):
        """Interpolate datasets to specified a vertical step.
        
        Parameters
        ----------
        args: dict
            A dictionary with a single key-value pair where the key is the vertical coordinate name
            and the value is a list of vertical levels to interpolate to.
        
        Returns
        -------
        xarray.Dataset, xarray.Dataset
            A tuple containing the verticaly interpolated reference dataset and product dataset.
        """
        vname = args[0]
        vfreq = args[1]
        vlevels = np.arange(
            self.ds[vname].min(),
            self.ds[vname].max(),
            vfreq
            )
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
        vlevels = xr.DataArray(vlevels, dims="z", name=vname)
        attrs = self.ds.attrs
        if "z" in self.ds.dims:
            self.ds = vinterp(self.ds, vname, vlevels)
            self.ds.attrs.update(attrs)
            return self.ds
        else:
            logger.warning("No 'z' dim in product")
            return None


def process_time_interpolation(ds, param, tbound):
    """Process interpolation for time dimension.
    
    Parameters
    ----------
    ds: xr.Dataset
        Product dataset.
    param: list
        Parameters for time colocation.
    tbound: list
        Time bounds for colocation.
    
    Returns
    -------
    tuple
        Interpolated product dataset.
    """
    logger.info("---- Time interpolation")
    coloc = TimeInterpolation(ds, tbound)
    coloc.__post_init__()
    ds = coloc.call(*param)
    return ds
    
def process_horizontal_interpolation(ds, param):
    """Process interpolation for horizontal dimensions.
    
    Parameters
    ----------
    ds: xr.Dataset
        Product dataset.
    param: list
        Parameters for horizontal colocation.
    
    Returns
    -------
    tuple
        Interpolated product dataset.
    """
    logger.info("---- Horizontal interpolation")
    coloc = HorizontalInterpolation(ds)
    coloc.__post_init__()
    ds = coloc.call(*param)
    return ds

def process_vertical_interpolation(ds, param):
    """Process interpolation for vertical dimensions.
    
    Parameters
    ----------
    ds: xr.Dataset
        Product dataset.
    param: list
        Parameters for vertical colocation.
    
    Returns
    -------
    tuple
        Interpolated product datasets.
    """
    logger.info("---- Vertical colocation")    
    coloc = VerticalInterpolation(ds)
    coloc.__post_init__()
    ds = coloc.call(*param)
    return ds
