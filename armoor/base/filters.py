"""FiltersAccessor
"""

import copy
import logging
import math
import re
import sys

from scipy.signal.windows import gaussian
import dask.array as da
import dask
import numpy as np
import pandas as pd
import xarray as xr
import xoa.filter as xfilter
import xoa.geo as xgeo
from matplotlib import path
from scipy.ndimage import binary_dilation

from armoor.base.interp import grid2loc, regrid
from armoor.data.open_decode import open_decode

R_terre = 6371
logger = logging.getLogger(__name__)
xr.set_options(keep_attrs=True)


@xr.register_dataarray_accessor("armoorfilters")
@xr.register_dataset_accessor("armoorfilters")
class ArmoorFilters:
    """
    Select a subset of the original object filtering elements with conditions across certain dimensions.

    Attributes
    ----------
    xarray_obj : xarray.Dataset
        Observation dataset to subset.
    """

    def __init__(self, ds):
        self.ds = ds
        
    def get_mask(self, coords: [(float, float)]) -> xr.Dataset:
        """Subset dataset selecting elements located within the polygon geometry.

        Parameters
        ----------
        coords : list of tuples
           Set of points coordinates defining the geometry of the polygon.

        Returns
        -------
        xarray.Dataset
           Dataset with elements included inside the polygon.

        See Also
        --------
        https://matplotlib.org/stable/api/path_api.html
        """
        logger.info("getting mask for horizontal_selection_polygon")
        # Create the polygon where to subset
        polygon = path.Path(coords)
        
        # Use .values to avoid creating intermediate arrays
        lons, lats = self.ds.lon.values.flatten(), self.ds.lat.values.flatten()
        
        dims_name = ()
        dims_nb = ()
        for dim in self.ds.dims:
            if (dim in self.ds.lon.dims) or (dim in self.ds.lat.dims):
                dims_name += (dim,)
                dims_nb += (self.ds.sizes[dim],)
        
        # Stack coordinates more efficiently
        coords = np.column_stack((lats, lons))
        del lats, lons
        
        flags = polygon.contains_points(coords)
        if not np.any(flags):  # More efficient than np.all(flags == False)
            return None
            
        mask_poly = xr.DataArray(
            data=np.reshape(flags, dims_nb),
            dims=dims_name,
        )
        return mask_poly

    # Helper methods to extract masks from existing filter methods
    def _get_quality_mask(self, qname: str, qmin: int, qmax: int) -> xr.DataArray:
        """Extract quality mask without applying it."""
        qname += "_qc"
        if qname not in self.ds:
            logger.warning(f"No {qname} in dataset")
            return None
            
        if qmin and qmax:
            return (self.ds[qname] >= int(qmin)) & (self.ds[qname] <= int(qmax))
        elif qmin:
            return self.ds[qname] >= int(qmin)
        elif qmax:
            return self.ds[qname] <= int(qmax)
        return None

    def _get_polygon_mask(self, coords: [(float, float)], dilate: bool = False) -> xr.DataArray:
        """Extract polygon mask without applying it."""
        mask_result = self.get_mask(coords)
        if mask_result is None:
            return None, None
        mask_poly = mask_result.copy()

        if (("x" in self.ds.lon.dims) and ("y" in self.ds.lon.dims)) and dilate:
            structure = np.ones((3, 3), dtype=bool)
            dilated_values = binary_dilation(
                mask_poly.values,
                structure=structure,
                iterations=10
            )
            return mask_result, xr.DataArray(data=dilated_values, dims=mask_poly.dims)
        
        return None, mask_result

    def _get_data_selection_mask(self, dim: str, minimum: float = None, 
                                maximum: float = None, value: float = None) -> xr.DataArray:
        """Extract data selection mask without applying it."""
        if value is not None:
            return self.ds[dim] == value
        elif minimum is not None and maximum is not None:
            return (self.ds[dim] >= minimum) & (self.ds[dim] <= maximum)
        elif minimum is not None:
            return self.ds[dim] >= minimum
        elif maximum is not None:
            return self.ds[dim] <= maximum
        return None

    def bathy_filter(self, path: str, fmt: str, minimum: float, maximum: float) -> xr.DataArray:
        """Filter dataset based on bathymetry depth range.
   
        Parameters:
            path: Path to bathymetry data file
            fmt: File format for reading bathymetry data
            minimum: Minimum depth threshold
            maximum: Maximum depth threshold
            
        Returns:
            Filtered dataset where bathymetry is within specified range
        """
        logger.info("bathy filter")
        ds_bathy = open_decode(path, fmt=fmt)
        if "time" in self.ds.lon.dims:
            if "time" in self.ds.lon.dims:
                dss = []
                for itime, time in enumerate(self.ds.time):
                    coord = self.ds.isel(time=[itime])
                    ds = grid2loc(ds_bathy, [(coord.lat.data[0], coord.lon.data[0])])
                    ds = ds.swap_dims({"npts": "time"})
                    dss.append(ds)
                ds_bathy = xr.combine_nested(dss, "time")
            else:
                ds_bathy = grid2loc(ds_bathy, [(self.ds.lat.data[0], self.ds.lon.data[0])])
        else:
            ds_bathy = regrid(ds_bathy, self.ds[["lon", "lat"]])
        bathy = ds_bathy["bathy"]
        mask = (bathy >= minimum) & (bathy <= maximum)
        mask = mask.compute()
        self.ds = self.ds.where(mask, drop=False)
        return self.ds
    
    @dask.delayed
    def tidal_filter(self, filter_name="demerliac"):
        """
        Apply a tidal filter to time-dependent variables in the dataset.
        
        This method processes all data variables in the dataset that have a time dimension,
        applying the specified tidal filter to remove tidal signals from the data. The 
        filtering is performed using the xoa.filter.tidal_filter function.
        
        Parameters
        ----------
        filter_name : str, default "demerliac"
            Name of the tidal filter to apply. The default "demerliac" filter is commonly
            used for removing tidal variations from oceanographic time series data.
            
        Notes
        -----
        - Only variables with a 'time' dimension are processed
        - If filtering fails for any variable, a warning is logged and the original
          data is preserved for that variable
        - The filtered data replaces the original data in the dataset
        - Uses the xoa (xarray-based ocean analysis) library for tidal filtering
        
        Examples
        --------
        >>> # Apply default Demerliac tidal filter
        >>> obj.tidal_filter()
        >>> 
        >>> # Apply a different tidal filter
        >>> obj.tidal_filter(filter_name="godin")
        
        Raises
        ------
        The method handles exceptions internally and logs warnings rather than raising
        errors, ensuring robustness when processing multiple variables.
        """
        logger.info(f"Apply tidal filter: {filter_name}")
        for vname in self.ds.data_vars:
            dai = self.ds[vname]
            if "time" in dai.dims:
                try:
                    self.ds[vname] = xfilter.tidal_filter(dai, filter_name)
                except Exception as e:
                    logger.warning(f"xoa: {e}")
                    logger.info("Tide filter ignored")
    
    @dask.delayed
    def tresample(self, freq):
        """
        """
        logger.info(f"Apply a time resampling at frequency: {freq}")
        if "time" in self.ds.lon.dims:
            self.ds = self.ds.reset_coords(["lon", "lat"])
        self.ds = self.ds.resample(time=freq).mean()
        if "time" in self.ds.lon.dims:
            self.ds = self.ds.set_coords(["lon", "lat"])
            
    def generate_kernel_from_freq(self, freq: str, time_index: pd.DatetimeIndex, 
                              kernel_type: str = "gaussian"):
        """
        Generate a 1D smoothing kernel based on user frequency and sampling rate.
    
        Parameters
        ----------
        freq : str
            User-specified frequency (e.g., '7D', '12H').
        time_index : pd.DatetimeIndex
            Time index of the data (must be regular).
        kernel_type : str, optional
            'boxcar' (moving average) or 'gaussian'. Default is 'gaussian'.
    
        Returns
        -------
        kernel : np.ndarray
            Normalized smoothing kernel.
        kernel_size : int
            Size of the kernel in number of samples.
        """
    
        # Infer sampling interval of the data
        inferred = pd.infer_freq(time_index)
        if inferred is None:
            raise ValueError("Time index must have a regular frequency. Consider resampling first.")
    
        offset_user = pd.tseries.frequencies.to_offset(freq)
        offset_sample = pd.tseries.frequencies.to_offset(inferred)
    
        # Number of samples per user frequency
        kernel_size = int(round(pd.to_timedelta(offset_user) / pd.to_timedelta(offset_sample)))
        if kernel_size < 1:
            kernel_size = 1
        if kernel_size % 2 == 0:
            kernel_size += 1  # make odd to center
    
        # Build kernel
        if kernel_type == "boxcar":
            kernel = np.ones(kernel_size) / kernel_size
        elif kernel_type == "gaussian":
            std = kernel_size / 6
            kernel = gaussian(kernel_size, std)
            kernel /= kernel.sum()
        else:
            raise ValueError(f"Unknown kernel_type: {kernel_type}")

        return kernel, kernel_size

    @dask.delayed
    def tsmooth(self, freq: str) -> xr.Dataset:
        """
        Apply 1D convolution along 'time' dimension using a custom kernel.
    
        Parameters
        ----------
        freq : str
            User-specified frequency (e.g., '7D', '12H').
    
        Returns
        -------
        xr.DataArray
            Smoothed data.
        """
        logger.info(f"Apply a time smoothing at frequency: {freq}")
        varscoord = []
        for var in ["lon", "lat", "depth"]:
            if "time" in self.ds[var].dims:
                varscoord.append(var)
        self.ds = self.ds.reset_coords(varscoord)
        
        if "drifter" in self.ds.attrs["data_name"]:
            logger.info("Resample drifter")
            logger.info("long?")
            self.ds = self.ds.resample(time="1h").mean()
        kernel, size = self.generate_kernel_from_freq(
            freq,
            self.ds.time,
            kernel_type="gaussian"
            )

        kernel = xr.DataArray(
            data=kernel,
            dims="time"
            )
        dss = []
        for var in self.ds.data_vars:
            if (var != "time") and ("time" in self.ds[var].dims):
                # da = xfilter.smooth(self.ds[var], kernel)
                da = xr.map_blocks(
                    xfilter.smooth, 
                    self.ds[var], 
                    kwargs={'kernel': kernel, "na_thres": 1}
                )
                da.attrs.update({**self.ds[var].attrs})
                ds = da.to_dataset(name=var)
                if var in varscoord:
                    ds = ds.set_coords(var)
            else:
                ds = self.ds[[var]]
            dss.append(ds)
        self.ds = xr.merge(dss)

    def _get_time_bounds_mask(self, start=None, end=None):
        if not start:
            logger.error("Giving a begindate is mandatory.")
            sys.exit(1)
        start = pd.to_datetime(start)
        if isinstance(end, int):
            end = pd.to_datetime(start) + pd.to_timedelta(end, "D")
        end = pd.to_datetime(end)
        if self.ds.time.max().values <= pd.to_datetime(start):
            logger.warning("max(time) <= start")
            return None
        elif self.ds.time.min().values >= pd.to_datetime(end):
            logger.warning("min(time) >= end")
            return None
        else:
            return (self.ds.time >= start) & (self.ds.time <= end)
                    
    def apply_combined_filters(self, filters_config: dict) -> xr.Dataset:
        """
        Apply multiple filters in a single operation to reduce memory usage.
        
        Parameters
        ----------
        filters_config : dict
            Dictionary containing filter configurations:
            - 'quality': {'qname': str, 'qmin': int, 'qmax': int}
            - 'polygon': {'coords': [(float, float)], 'dilate': bool}
            - 'data_selection': {'dim': str, 'minimum': float, 'maximum': float, 'value': float}
            
        Returns
        -------
        xarray.Dataset
            Dataset with all filters applied
        """
        logger.info("Applying combined filters")
        
        combined_mask = None
        mask2keep = None
        # Build combined boolean mask using existing methods
        for filter_type, config in filters_config.items():
            mask = None
            
            if filter_type == 'quality':
                mask = self._get_quality_mask(
                    config['qname'], 
                    config.get('qmin'), 
                    config.get('qmax')
                )
                        
            elif filter_type == 'polygon':
                mask2keep, mask  = self._get_polygon_mask(
                    config['coords'], 
                    config.get('dilate', False)
                )
                if mask is None:
                    return None
                
            elif filter_type == 'data_selection':
                mask = self._get_data_selection_mask(
                    config['dim'],
                    config.get('minimum'),
                    config.get('maximum'),
                    config.get('value')
                )
                
            elif filter_type == 'time_selection':
                mask = self._get_time_bounds_mask(
                    start=config.get('minimum'),
                    end=config.get('maximum'),
                )
            
            # Combine masks
            if mask is not None:
                combined_mask = mask if combined_mask is None else combined_mask & mask
        
        # Apply combined mask once
        depth_was_coord = False
        if combined_mask is not None:
            depth_was_coord = "depth" in self.ds.coords
            if depth_was_coord and ("time" in self.ds.depth.sizes):
                result = self.ds.reset_coords("depth")
            else:
                result = self.ds
            if mask2keep is not None:
                result["mask"] = mask2keep
            # combined_mask = combined_mask.compute()
            result = result.where(combined_mask, drop=True)
            if "mask" in result:
                if "time" in result["mask"].dims:
                    result["mask"] = result.mask.isel(time=0)
            
            self.ds = result.copy()
            result.close()
        
        if "bathy" in filters_config:
            self.bathy_filter(
                filters_config["bathy"].get("path"),
                filters_config["bathy"].get("fmt"),
                filters_config["bathy"].get('min'),
                filters_config["bathy"].get('max'),
            )
            
        if "tide" in filters_config:
            filter_name = filters_config.get("tide")
            self.tidal_filter(filter_name=filter_name)

        if "tresample" in filters_config:
            self.tresample(filters_config.get("tresample"))
            
        if "tsmooth" in filters_config:
            self.tsmooth(filters_config.get("tsmooth"))

        if depth_was_coord and "depth" in result:
            result = result.set_coords("depth")

        if "bathy" in self.ds:
            bathy = self.ds.bathy
            if "time" in bathy.dims:
                self.ds["bathy"] = bathy.isel(time=0)
        return self.ds
    
    def sel_closest(self, ds_obs):
        """
        Select the nearest point around obs.
        Parameters
        ----------
        lon : float
        lat : float

        Returns
        -------
        xarray.Dataset
            Dataset with elements around (lat, lon).
        """
        logger.info("Applying filter - sel_closest")
        if "time" in self.ds.lon.dims:
            dss = []
            for itime, time in enumerate(self.ds.time):
                ds_model = self.ds.isel(time=[itime])
                dist_model2obs = (
                    xgeo.get_distances(ds_model, ds_obs.isel(time=[itime]))
                    .squeeze()
                    .rename({"npts0": "member"})
                )
                ds = ds_model.where(
                    dist_model2obs == dist_model2obs.min(), drop=True
                ).squeeze()
                dss.append(ds)
            return xr.combine_nested(dss, "time")
        else:
            ds_model = self.ds
            dist_model2obs = (
                xgeo.get_distances(ds_model, ds_obs)
                .squeeze()
                .rename({"npts0": "member"})
            )
            return ds_model.where(
                dist_model2obs == dist_model2obs.min(), drop=True
            ).squeeze()


def create_optimized_mask(ds, var_name, bins):
        var = ds[var_name]
        mask = xr.zeros_like(var, dtype=bool)
        for low, high in bins:
            mask = mask | ((var >= low) & (var <= high))
        
        return mask
