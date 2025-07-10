"""MetazonAccessor
"""

import copy
import logging
import math
import re
import sys

import numpy as np
import pandas as pd
import xarray as xr
import dask.array as da
import xoa.geo as xgeo
from matplotlib import path
from scipy.ndimage import binary_dilation

R_terre = 6371
logger = logging.getLogger(__name__)
xr.set_options(keep_attrs=True)

@xr.register_dataarray_accessor("armoorfilters")
@xr.register_dataset_accessor("armoorfilters")
class ArmoorSelectionAccessor:
    """
    Select a subset of the original object filtering elements with conditions across certain dimensions.

    Attributes
    ----------
    xarray_obj : xarray.Dataset
        Observation dataset to subset.
    """

    def __init__(self, ds):
        self.ds = ds

    def quality_filter(self, qname: str, qmin: int, qmax: int) -> xr.Dataset:
        """
        Subset dataset filtering quality levels.

        Parameters
        ----------
        qname : str
            Name of the variable quality name.
        qmin : int
            Minimum value of quality.
        qmax : int
            Maximum value of quality.
        Returns
        -------
        xarray.Dataset
            Dataset filtered with quality levels input restrictions.
        """
        logger.info("Applying filter - quality_filter")
        qname += "_qc"

        if qname in self.ds:
            if qmin and qmax:
                selection = (self.ds[qname] >= int(qmin)) & (
                    self.ds[qname] <= int(qmax)
                )
            elif qmin:
                selection = self.ds[qname] >= int(qmin)
            elif qmax:
                selection = self.ds[qname] <= int(qmax)
            else:
                logger.warning(
                    "qmin and/or qmax are missing."
                    "No quality filter applied."
                )
                return self.ds
            return self.ds.where(selection, drop=True)
        else:
            logger.warning(
                "min_q and/or max_q are missing."
                "Quality filter is not applied."
            )
            return self.ds
        
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
        return mask_poly, dims_name

    def horizontal_selection_polygon(
        self,
        coords: [(float, float)],
    ) -> xr.Dataset:
        """
        Subset dataset selecting elements located within the polygon geometry.

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
        logger.info("Applying filter - horizontal_selection_polygon")
        mask = self.get_mask(coords)
        if mask is None:
            return None
            
        mask_poly, dims_name = mask
        
        # Handle depth coordinate more efficiently
        depth_was_coord = "depth" in self.ds.coords
        if depth_was_coord:
            self.ds = self.ds.reset_coords("depth")
            
        # Apply mask without creating intermediate datasets
        result = self.ds.where(mask_poly, drop=True)
        
        if depth_was_coord and "depth" in result:
            result = result.set_coords("depth")
            
        # Check if any dimension is empty
        if any(result.sizes[dim] == 0 for dim in dims_name):
            return None
            
        return result
    
    def horizontal_selection_polygon_dilat(
        self,
        coords: [(float, float)],
    ) -> xr.Dataset:
        """
        Subset dataset selecting elements located within the polygon geometry with dilation.

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
        logger.info("Applying filter - horizontal_selection_polygon_dilat")

        mask_result = self.get_mask(coords)
        if mask_result is None:
            return None
            
        mask_poly2, dims_name = mask_result

        logger.info("storing mask into dataset after binary dilation")

        # Apply binary dilation directly to values (more memory efficient)
        structure = np.ones((3, 3), dtype=bool)
        dilated_mask = binary_dilation(
            mask_poly2.values,
            structure=structure,
            iterations=10
        )
        
        # Create new mask with dilated values
        mask_poly2 = xr.DataArray(
            data=dilated_mask,
            dims=mask_poly2.dims,
        )
        
        # Store original mask for reference
        self.ds["mask"] = mask_result
        
        depth_was_coord = "depth" in self.ds.coords
        if depth_was_coord:
            self.ds = self.ds.reset_coords("depth")
            
        result = self.ds.where(mask_poly2, drop=True)
        
        if depth_was_coord and "depth" in result:
            result = result.set_coords("depth")
            
        if any(result.sizes[dim] == 0 for dim in dims_name):
            return None
            
        return result

    def data_selection(
        self,
        dim: str,
        minimum: float = None,
        maximum: float = None,
        value: float = None,
    ) -> xr.Dataset:
        """
        Subset dataset filtering elements values along the specified dimension.

        Parameters
        ----------
        dim : str
            Dimension whom to apply the filter.
        minimum : float
            Minimum value kept.
        maximum : float
            Maximum value kept.
        value : float
            Only value kept (i.e. maximum = minimum).

        Returns
        -------
        xarray.Dataset
             Dataset with elements values meeting the condition(s).
        """
        logger.info("Applying filter - data_selection")

        if value is not None:
            selection = self.ds[dim] == value
        elif minimum is not None and maximum is not None:
            selection = (self.ds[dim] >= minimum) & (
                self.ds[dim] <= maximum
            )
        elif minimum is not None:
            selection = self.ds[dim] >= minimum
        elif maximum is not None:
            selection = self.ds[dim] <= maximum
        else:
            selection = None
            
        return self.ds.where(selection, drop=True)  # Added drop=True for consistency

    # Helper methods to extract masks from existing filter methods
    def _get_quality_mask(self, qname: str, qmin: int, qmax: int) -> xr.DataArray:
        """Extract quality mask without applying it."""
        qname += "_qc"
        if qname not in self.ds:
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
            return None
            
        mask_poly, dims_name = mask_result
        
        if dilate:
            structure = np.ones((3, 3), dtype=bool)
            dilated_values = binary_dilation(
                mask_poly.values,
                structure=structure,
                iterations=10
            )
            return xr.DataArray(data=dilated_values, dims=mask_poly.dims)
        
        return mask_poly

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

    # NEW: Combined filter method to reduce intermediate operations
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
                mask = self._get_polygon_mask(
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
            
            # Combine masks
            if mask is not None:
                combined_mask = mask if combined_mask is None else combined_mask & mask
        
        # Apply combined mask once
        if combined_mask is not None:
            depth_was_coord = "depth" in self.ds.coords
            if depth_was_coord:
                result = self.ds.reset_coords("depth")
            else:
                result = self.ds
                
            result = result.where(combined_mask, drop=True)
            
            if depth_was_coord and "depth" in result:
                result = result.set_coords("depth")
                
            return result
        
        return self.ds
# @xr.register_dataarray_accessor("armoorfilters")
# @xr.register_dataset_accessor("armoorfilters")
# class ArmoorSelectionAccessor:
#     """
#     Select a subset of the original object filtering elements with conditions across certain dimensions.

#     Attributes
#     ----------
#     xarray_obj : xarray.Dataset
#         Observation dataset to subset.
#     """

#     def __init__(self, ds):
#         self.ds = ds

#     def quality_filter(self, qname: str, qmin: int, qmax: int) -> xr.Dataset:
#         """
#         Subset dataset filtering quality levels.

#         Parameters
#         ----------
#         qname : str
#             Name of the variable quality name.
#         qmin : int
#             Minimum value of quality.
#         qmax : int
#             Maximum value of quality.
#         Returns
#         -------
#         xarray.Dataset
#             Dataset filtered with quality levels input restrictions.
#         """
#         logger.info("Applying filter - quality_filter")
#         qname += "_qc"

#         if qname in self.ds:
#             if qmin and qmax:
#                 selection = (self.ds[qname] >= int(qmin)) & (
#                     self.ds[qname] <= int(qmax)
#                 )
#             elif qmin:
#                 selection = self.ds[qname] >= int(qmin)
#             elif qmax:
#                 selection = self.ds[qname] <= int(qmax)
#             else:
#                 logger.warning(
#                     "qmin and/or qmax are missing."
#                     "No quality filter applied."
#                 )
#                 return self.ds
#             return self.ds.where(selection, drop=True)
#         else:
#             logger.warning(
#                 "min_q and/or max_q are missing."
#                 "Quality filter is not applied."
#             )
#             return self.ds
        
#     def get_mask(self,coords: [(float, float)]) -> xr.Dataset:
#         """Subset dataset selecting elements located within the polygon geometry.

#         Parameters
#         ----------
#         coords : list of tuples
#            Set of points coordinates defining the geometry of the polygon.

#         Returns
#         -------
#         xarray.Dataset
#            Dataset with elements included inside the polygon.

#         See Also
#         --------
#         https://matplotlib.org/stable/api/path_api.html
#         """
#         logger.info("getting mask for horizontal_selection_polygon")
#         # Create the polygon where to subset
#         polygon = path.Path(coords)
#         lons, lats = self.ds.lon.data.flatten(), self.ds.lat.data.flatten()
#         dims_name = ()
#         dims_nb = ()
#         for dim in self.ds.dims:
#             if (dim in self.ds.lon.dims) or (dim in self.ds.lat.dims):
#                 dims_name += (dim,)
#                 dims_nb += (self.ds.sizes[dim],)
#         coords = np.vstack((lats, lons)).T
#         del lats, lons
#         flags = polygon.contains_points(coords)
#         if np.all(flags == False):
#             return None
#         mask_poly = xr.DataArray(
#             data=np.reshape(flags, dims_nb),
#             dims=dims_name,
#         )
#         return mask_poly, dims_name


#     def horizontal_selection_polygon(
#         self,
#         coords: [(float, float)],
#     ) -> xr.Dataset:
#         """
#         Subset dataset selecting elements located within the polygon geometry.

#         Parameters
#         ----------
#         coords : list of tuples
#            Set of points coordinates defining the geometry of the polygon.

#         Returns
#         -------
#         xarray.Dataset
#            Dataset with elements included inside the polygon.

#         See Also
#         --------
#         https://matplotlib.org/stable/api/path_api.html
#         """
#         logger.info("Applying filter - horizontal_selection_polygon")
#         # mask_poly, dims_name = self.get_mask(coords)
#         mask = self.get_mask(coords)
#         if mask:
#             mask_poly, dims_name = mask
#         else:
#             return None
#         if "depth" in self.ds.coords:
#             self.ds = self.ds.reset_coords("depth")
#         self.ds = self.ds.where(mask_poly, drop=True)
#         if "depth" in self.ds:
#             self.ds = self.ds.set_coords("depth")
#         for dim in dims_name:
#             if self.ds.sizes[dim] == 0:
#                 return None
#         return self.ds
    
#     def horizontal_selection_polygon_dilat(
#         self,
#         coords: [(float, float)],
#     ) -> xr.Dataset:
#         """
#         Subset dataset selecting elements located within the polygon geometry.

#         Parameters
#         ----------
#         coords : list of tuples
#            Set of points coordinates defining the geometry of the polygon.

#         Returns
#         -------
#         xarray.Dataset
#            Dataset with elements included inside the polygon.

#         See Also
#         --------
#         https://matplotlib.org/stable/api/path_api.html
#         """
#         logger.info("Applying filter - horizontal_selection_polygon_dilat")

#         mask_poly2, dims_name = self.get_mask(coords)

#         logger.info("storing mask into dataset after binary dilation")

#         self.ds["mask"] = mask_poly2
#         structure = np.ones((3, 3), dtype=bool)
#         mask_poly2.values = binary_dilation(
#             mask_poly2.values,
#             structure=structure,
#             iterations=10
#         )
#         depth_was_coord = "depth" in self.ds.coords
#         if depth_was_coord:
#             self.ds = self.ds.reset_coords("depth")
#         self.ds = self.ds.where(mask_poly2, drop=True)
#         if depth_was_coord and "depth" in self.ds:
#             self.ds = self.ds.set_coords("depth")
#         if any(self.ds.sizes[dim] == 0 for dim in dims_name):
#             return None
#         return self.ds

#     def data_selection(
#         self,
#         dim: str,
#         minimum: float = None,
#         maximum: float = None,
#         value: float = None,
#     ) -> xr.Dataset:
#         """
#         Subset dataset filtering elements values along the specified dimension.

#         Parameters
#         ----------
#         dim : str
#             Dimension whom to apply the filter.
#         minimum : float
#             Minimum value kept.
#         maximum : float
#             Maximum value kept.
#         value : float
#             Only value kept (i.e. maximum = minimum).

#         Returns
#         -------
#         xarray.Dataset
#              Dataset with elements values meeting the condition(s).
#         """
#         logger.info("Applying filter - data_selection")

#         if value is not None:
#             selection = self.ds[dim] == value
#         elif minimum is not None and maximum is not None:
#             selection = (self.ds[dim] >= minimum) & (
#                 self.ds[dim] <= maximum
#             )
#         elif minimum is not None:
#             selection = self.ds[dim] >= minimum
#         elif maximum is not None:
#             selection = self.ds[dim] <= maximum
#         else:
#             selection = None
#         return self.ds.where(selection)

    # def horizontal_selection_coords(
    #     self, coordinates: [(float, float)]
    # ) -> xr.Dataset:
    #     """
    #     Subset dataset selecting elements interpolated at specific coordinates.

    #     Parameters
    #     ----------
    #     coordinates : list of tuples
    #         Set of points coordinates (lon, lat) defining the coordinates to select.

    #     Returns
    #     -------
    #     xarray.Dataset
    #         Dataset with elements located at specific coordinates.
    #     """
    #     logger.info("Applying filter - horizontal_selection_coords")

    #     lat, lon = zip(*coordinates)
    #     loc = xr.Dataset(
    #         coords={
    #             "lon": ("npts", list(lon)),
    #             "lat": ("npts", list(lat)),
    #         }
    #     )
    #     dsi = self.ds.copy()
    #     dso = xr.Dataset(coords=dict(time=dsi.time, **loc.coords))
    #     if "depth" in dsi.coords:
    #         if "time" in dsi.depth.dims:
    #             dsi = dsi.reset_coords("depth")

    #     dss = []
    #     for var in dsi.data_vars:
    #         if ("time" in dsi[var].dims) and ("z" in dsi[var].dims):
    #             arr = np.nan * np.zeros(
    #                 (dsi.sizes["time"], dsi.sizes["z"], len(lon))
    #             )
    #             for itime in range(dsi.sizes["time"]):
    #                 for iz in range(dsi.sizes["z"]):
    #                     arr[itime, iz, :] = grid2loc(
    #                         dsi[var].isel(time=itime, z=iz), loc
    #                     )
    #             dims = ["time", "z", "npts"]
    #             coords = dict(time=dsi.time, **loc.coords)
    #         elif ("time" in dsi[var].dims) and ("z" not in dsi[var].dims):
    #             arr = np.nan * np.zeros((dsi.sizes["time"], len(lon)))
    #             for itime in range(dsi.sizes["time"]):
    #                 arr[itime, :] = grid2loc(dsi[var].isel(time=itime), loc)
    #             dims = ["time", "npts"]
    #             coords = dict(time=dsi.time, **loc.coords)
    #         else:
    #             arr = grid2loc(dsi[var], loc)
    #             dims = ["npts"]
    #             coords = dict(**loc.coords)
    #             if isinstance(arr, xr.DataArray):
    #                 arr = arr.data
    #         dsvar = xr.Dataset(data_vars={var: (dims, arr)}, coords=coords)
    #         dsvar[var] = dsvar[var].assign_attrs(**dsi[var].attrs)
    #         dss.append(dsvar)
    #     dso = xr.merge(dss)
    #     if "depth" in dso:
    #         dso = dso.set_coords("depth")
    #     elif ("depth" in dsi.coords) and ("time" not in dsi["depth"].dims):
    #         dso["depth"] = dsi.depth
    #         dso = dso.set_coords("depth")
    #     self.ds = dso
    #     return self.ds

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

    def horizontal_selection_bathy(
        self,
        minimum: float = None,
        maximum: float = None,
    ) -> xr.Dataset:
        """
        Subset dataset selecting elements whom bathymetry values are included in the specified
        bathymetry range.

        Parameters
        ----------
        minimum : float
            Minimum bathymetry value kept.
        maximum : float
            Maximum bathymetry value kept.

        Returns
        -------
        xarray.Dataset
             Dataset with bathymetry values meeting the condition(s).

        See Also
        --------
        cli.base.meta_zone.MetazoneAccessor.data_selection
        """

        logger.info("Applying filter - horizontal_selection_bathymetry")
        return self.data_selection(
            dim="bathy", minimum=minimum, maximum=maximum
        )

    # def vertical_selection_range(
    #     self, vname: str, vranges: list
    # ) -> xr.Dataset:
    #     """
    #     Subset dataset selecting elements whom depth values are included in the specified
    #     depth ranges.

    #     Parameters
    #     ----------
    #     vname : str
    #         Name of vertical coordinate.
    #     vranges : list
    #         List of vertical range.

    #     Returns
    #     -------
    #     xarray.Dataset
    #          Dataset with vertical ranges.
    #     """
    #     logger.info("Applying filter - vertical_selection_range")
    #     dsi = self.ds
    #     if "dens" in self.ds.coords:
    #         dsi = dsi.reset_coords("dens")
    #     if "depth" in self.ds.coords:
    #         dsi = dsi.reset_coords("depth")
    #     dss = []
    #     for ivrange, vrange in enumerate(vranges):
    #         ds = dsi.where(
    #             (dsi[vname] >= vrange[0]) & (dsi[vname] <= vrange[1])
    #         )
    #         dso = ds.expand_dims(dim="vrange")

    #         dso["vrange"] = xr.DataArray(
    #             data=[vrange],
    #             dims=("vrange", "vbin"),
    #         )
    #         dss.append(dso)
    #     dso = xr.combine_nested(dss, "vrange")
    #     if "dens" in self.ds.coords:
    #         dso = dso.set_coords("dens")
    #     if "depth" in self.ds.coords:
    #         dso = dso.set_coords("depth")
    #     self.ds = dso
    #     return self.ds

    # def vertical_selection_levels(
    #     self, vname: str, vlevels: list, method: str = "linear"
    # ) -> xr.Dataset:
    #     """
    #     Subset dataset selecting elements at specific vertical levels.

    #     Parameters
    #     ----------
    #     vlevels : list
    #         List of vertical levels.
    #     vname : str
    #         Name of vertical coordinate.
    #     method : str
    #         Method of interpolation.

    #     Returns
    #     -------
    #     xarray.Dataset
    #     """
    #     logger.info("Applying filter - vertical_selection_levels")
    #     dsi = self.ds
    #     if (vname == "depth") and ("dens" in self.ds.coords):
    #         dsi = dsi.reset_coords("dens")
    #     elif (vname == "dens") and ("depth" in self.ds.coords):
    #         dsi = dsi.reset_coords("depth")
    #         if "dens" not in self.ds.coords:
    #             dsi = dsi.set_coords("dens")
    #     vlevels = xr.DataArray(vlevels, dims="z", name=vname)
    #     das = []
    #     for var in dsi.data_vars:
    #         if "z" in dsi[var].dims:
    #             da = regrid1d(
    #                 dsi[var].chunk(dict(z=-1)),
    #                 vlevels,
    #                 method=method,
    #                 extrap="bottom"
    #             )
    #         else:
    #             da = dsi[var]
    #         das.append(da)
    #     self.ds = xr.merge(das, combine_attrs='drop_conflicts')
    #     self.ds = self.ds.set_xindex(vname)
    #     return self.ds

    def time_selection_bounds(self, start, end) -> xr.Dataset:
        """
        Subset dataset selecting elements in a bounded temporal interval.

        Parameters
        ----------
        start : str
            Date (YYYY-MM-DD HH:MM:SS)
        end : str
            Date (YYYY-MM-DD HH:MM:SS)

        Returns
        -------
        xarray.Dataset
        """
        logger.info("Applying filter - time_selection_bounds")
        if not start:
            logger.error("Giving a begindate is mandatory.")
            sys.exit(1)

        # start = pd.to_datetime(start)
        if isinstance(end, int):
            end = pd.to_datetime(start) + pd.to_timedelta(end, "D")
            end = end.strftime("%Y-%m-%d")
        # else:
        #     end = pd.to_datetime(end)
        if self.ds.time.max().values <= pd.to_datetime(start):
            logger.warning("max(time) <= start")
            return None
        elif self.ds.time.min().values >= pd.to_datetime(end):
            logger.warning("min(time) >= end")
            return None
        else:
            return self.ds.sel(time=slice(start, end))

    # def time_selection_terms(
    #     self, start=None, end=None, freq=None, dates=None
    # ):
    #     """
    #     Subset dataset selecting elements at specific terms.

    #     Parameters
    #     ----------
    #     start : str
    #         Date (YYYY-MM-DD HH:MM:SS)
    #     end : str
    #         Date (YYYY-MM-DD HH:MM:SS)
    #     freq : str
    #         See :ref:`here <timeseries.offset_aliases>` for a list of
    #         frequency aliases.
    #     Returns
    #     -------
    #     xarray.Dataset
    #     """
    #     logger.info("Applying filter - time_selection_terms")
    #     if dates:
    #         time = [pd.to_datetime(date) for date in dates]
    #     else:
    #         time = pd.date_range(start=start, end=end, freq=freq)
    #     return self.ds.interp(
    #         time=time, method="linear", kwargs={"fill_value": "extrapolate"}
    #     )

#     def time_selection_range_seq(self, start, end, tbin: str) -> xr.Dataset:
#         """
#         Subset dataset selecting elements by temporal bin.

#         Parameters
#         ----------
#         start : str
#             Date (YYYY-MM-DD HH:MM:SS)
#         end : str
#             Date (YYYY-MM-DD HH:MM:SS)
#         tbin: str
#             See :ref:`here <timeseries.offset_aliases>` for a list of
#             bin aliases.
#         Returns
#         -------
#         xarray.core.groupby.DatasetGroupBy
#         """
#         logger.info("Applying filter - time_selection_range_seq")
#         regex = re.compile(r"[0-9][M-Y]")
#         if regex.fullmatch(tbin):
#             logger.error(
#                 "Use trange=1MS, 2MS... to specify a  monthly sequential range."
#             )
#             sys.exit(1)
#         time_bins = get_time_bins(start, end, tbin)
#         labels = [
#             time_bins[it] + 0.5 * (time_bins[it + 1] - time_bins[it])
#             for it in range(len(time_bins) - 1)
#         ]
#         return self.ds.groupby_bins(
#             "time", time_bins, labels=labels, right=False
#         )

#     def time_selection_range_clim(self,  start, end, tbin: str = None) -> xr.Dataset:
#         """
#         Subset dataset selecting elements by climatological bin.

#         Parameters
#         ----------
#         tbin: str
#             See :ref:`here <timeseries.offset_aliases>` for a list of
#             bin aliases.
#         Returns
#         -------
#         xarray.core.groupby.DatasetGroupBy
#         """
#         logger.info("Applying filter - time_selection_range_clim")
#         if isinstance(tbin, dict):
#             months = self.ds.time.dt.month
#             clim = xr.full_like(months, fill_value="none", dtype="U4")
#             clim.name = "season"
#             for k, v in tbin.items():
#                 clim[months.isin(v)] = k
#         else:
#             clim = f"time.{tbin}"
#         return self.ds.groupby(clim)

#     def time_selection_cut(
#         self, freq: str, fmin: float, fmax: float
#     ) -> xr.Dataset:
#         """
#         Subset dataset selecting elements in a temporal bin sequentially.

#         Parameters
#         ----------
#         freq: str
#             See :ref:`here <timeseries.offset_aliases>` for a list of
#             bin aliases.
#         fmin: float
#             Minimum value of freq.
#         fmax : float
#             Maximum value of freq.

#         Returns
#         -------
#         xarray.Dataset
#         """
#         logger.info("Applying filter - time_selection_cut")
#         dt = self.ds.time.dt
#         if freq == "hour":
#             dt = dt.hour
#         elif freq == "month":
#             dt = dt.month
#         elif freq == "year":
#             dt = dt.year
#         else:
#             logger.error(f"Cutting the dataset at {freq} is not implemented.")
#             sys.exit(1)
#         return self.ds.where((dt >= fmin) & (dt <= fmax), drop=True)


# def apply_trange(ds, metazone):

#     # time intervals
#     time_range = ["trange_seq", "trange_clim"]
#     for k in time_range:
#         if k in metazone.keys():
#             ds = FILTERS[k](ds)(
#                 metazone["tbound"][0], metazone["tbound"][1], metazone[k]
#             )
#     return ds


# def apply_vrange(ds, metazone):

#     # vertical intervals
#     if "vrange" in metazone:
#         attrs = ds.attrs
#         ds = FILTERS["vrange"](ds)(*metazone["vrange"].items()[0])
#         ds = ds.assign_attrs({**attrs})
#     return ds


# def get_time_bins(start, end, tbin):
#     return pd.date_range(
#         start=pd.to_datetime(start),
#         end=pd.to_datetime(end),
#         freq=tbin,
#     )


def create_optimized_mask(ds, var_name, bins):
        var = ds[var_name]
        # Initialiser avec False
        mask = xr.zeros_like(var, dtype=bool)
        
        # Ajouter chaque condition
        for low, high in bins:
            mask = mask | ((var >= low) & (var <= high))
        
        return mask