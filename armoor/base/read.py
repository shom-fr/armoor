"""XrReaderAccessor
"""
import xarray as xr
import xoa.grid
import xoa.cf as xcf
import numpy as np
import os
import xoa

import logging
logger = logging.getLogger(__name__)

xoa.register_accessors(decode_sigma=True)


@xr.register_dataarray_accessor("read")
@xr.register_dataset_accessor("read")
class ReadAccessor:
    """
    Read and format a dataset.

    Attributes
    ----------
    xarray_obj : xarray.Dataset
        Dataset to format.
    """

    def __init__(self, xarray_obj):
        self._obj = xarray_obj
        xoa.register_accessors()
        xoa.register_accessors(decode_sigma=True)

        path_cfg = 'cf.cfg'

        try:
            rootdir = os.path.abspath(os.path.dirname(__file__))
            path = os.path.join(rootdir, path_cfg)
        except:
            logger.warning('cf.cfg file not found')
            directory = os.getcwd()
            logger.warning(f'using path : {directory}')

        xcf.register_cf_specs(path)

    def decode(self, ds_h=None):
        """
        Decode the model and observation data to retrieve homogeneous variable names.
        Parameters
        ----------
        ds_h : xarray.dataset
            Vertical grid for models in case of separate data.
        Returns
        -------
        xarray.Dataset
            Decoded dataset.
        """
        logger.info(f"Decoding data")
        # If coords can be regridded with no loss of information
        self._obj = xoa.grid.to_rect(self._obj)
        # Remove QC from variables to prevent random behaviours
        vars_to_remove = ['TEMP_QC', 'PSAL_QC', 'TIME_QC', 'POSITION_QC']
        for var in vars_to_remove:
            if var in self._obj.variables:
                self._obj = self._obj.drop(var)
        # Decode CROCO models
        if 'xi_rho' in self._obj.dims:
            return self._obj.read.decode_croco().read.convert_lons().read.convert_depths()
        else:  # si autre modele/obs
            self._obj = self._obj.read.decode_model()
            if 'lon' in self._obj.lon.dims and len(self._obj.lon.values) == len(self._obj.lat.values) and len(
                    self._obj.lon.values) == len(self._obj.time.values):
                self._obj = self._obj.read.convert_trajectory()

            if 'depth' in self._obj.dims and 'DEPH' in self._obj.variables:
                self._obj = self._obj.read.decode_profiler()
            if 'lon' in self._obj.dims and self._obj.lon.dims == ('lon',) and len(self._obj.lon) == len(self._obj.time):
                self._obj = self._obj.read.decode_profiler()
            if 'depth' in self._obj.dims and 'depth' not in self._obj.coords:
                self._obj = self._obj.assign_coords({'depth': self._obj.depth})
            if 'depth' in self._obj.dims and len(self._obj.depth.dims) == 2:  # resoud cas de profils
                depth = 0
            try:
                self._obj = self._obj.read.convert_lons().read.convert_depths()
                return self._obj
            except:
                self._obj = self._obj.read.convert_depths()
                return self._obj

    # TOPAZ, HYCOM2D, NEMO
    def decode_model(self) -> xr.Dataset:
        """
        Format dataset.

        Returns
        -------
        xarray.Dataset
            Formatted dataset.

        """
        list_to_drop = ['depth_bnds', 's_dd', 's_sd', 's_se']
        for var in list_to_drop:
            if var in list(self._obj.keys()):
                self._obj = self._obj.drop([var])

        if 's_mn' in list(self._obj.keys()):
            self._obj = self._obj.rename({'s_mn': 'sal'})

        if 'sst' in list(self._obj.keys()) and 'adjusted_sea_surface_temperature' in list(self._obj.keys()):
            self._obj = self._obj.drop(['adjusted_sea_surface_temperature'])
        return self._obj.xoa.decode()

    # CROCO
    def decode_croco(self):
        """
        Decode CROCO models.
        Returns
        -------
        xarray.dataset
            Decoded dataset.
        """
        self._obj = self._obj.decode_sigma()

        self._obj = self._obj.rename_dims({'eta_rho': 'lat', 'xi_rho': 'lon', 's_rho': 'z'})
        self._obj = self._obj.drop(['xi_rho', 'eta_rho'])

        longitude = np.unique(self._obj.lon_rho.data)[:-1]
        latitude = np.unique(self._obj.lat_rho.data)[:-1]

        self._obj['lon'] = longitude
        self._obj['lat'] = latitude

        if self._obj.depth.min() < 0 and self._obj.depth.max() > 0:
            self._obj['depth'] = -self._obj.depth.where((self._obj.depth < 0) & (self._obj.depth > -1e5))
        self._obj = self._obj.where(~np.isnan(self._obj.depth))

        return self._obj

    def decode_profiler(self):
        """
        Decode profiler datasets
        Returns
        -------
        xarray.dataset
            Decoded dataset
        """
        colonnes = self._obj.DEPH.values
        depth_values = np.empty(np.size(colonnes, 1))
        for i in range(np.size(colonnes, 1)):
            colonne_test = colonnes[:, i]
            colonne_test = colonne_test[~np.isnan(colonne_test)]
            depth_column = set(colonne_test)
            if len(depth_column) == 1:  # Tests if the depth values are all the same throughout time
                depth_values[i] = list(depth_column)[0]
        self._obj = self._obj.assign_coords({'depth': depth_values})
        self._obj = self._obj.read.convert_trajectory()
        return self._obj

    def convert_trajectory(self):
        """
        Convert trajectories (lon/lat depend on time).
        Returns
        -------
        xarray.dataset
            Decoded dataset.
        """
        da_lon = xr.DataArray(self._obj.lon.values, coords=[self._obj.time.values], dims="time")
        da_lat = xr.DataArray(self._obj.lat.values, coords=[self._obj.time.values], dims="time")
        self._obj = self._obj.drop(['lon', 'lat'])
        self._obj = self._obj.assign_coords({'lon': da_lon})
        self._obj = self._obj.assign_coords({'lat': da_lat})
        return self._obj

    def rename_dims(self):
        """
        Rename dimensions to have homogeneous variable names
        Returns
        -------
        xarray.dataset
            Dataset with homogeneous dimension names.
        """
        if self._obj.xoa.lon.name != 'lon':
            old_lon = self._obj.xoa.lon.name
            self._obj.rename({old_lon: "lon"})
        if self._obj.xoa.lat.name != 'lat':
            old_lat = self._obj.xoa.lat.name
            self._obj.rename({old_lat: "lat"})

        if "depth" in self._obj.dims:
            if self._obj.xoa.depth.name != 'depth':
                self._obj.rename({self._obj.xoa.depth.name: 'depth'})

        if "time" in self._obj.dims:
            if self._obj.xoa.time.name != 'time':
                self._obj.rename({self._obj.xoa.time.name: 'time'})

        return self._obj

    def convert_lons(self):
        """
        Convert latitudes in case they go 0 -> 360°
        Returns
        -------
        xarray.dataset
            Dataset with homogeneous longitudes
        """
        if np.nanmax(self._obj.lon.where(self._obj.lon < 1e+30).data) > 180:
            self._obj.assign_coords({"lon": (((self._obj.lon + 180) % 360) - 180)})
        return self._obj

    def convert_depths(self):
        """
        Convert depths to have positive values only.
        Returns
        -------
        xarray.dataset
            Dataset with positive depths.
        """
        if 'depth' in self._obj.variables:
            if np.nanmin(self._obj.depth.data) < 0:
                self._obj.coords["depth"] = -self._obj.depth
        elif 'depth' in self._obj.dims:
            if np.nanmin(self._obj.depth.data) < 0:
                self._obj.coords["depth"] = -self._obj.depth
        return self._obj
