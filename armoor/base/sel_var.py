# -*- coding: utf-8 -*-
"""read variables in models and observation
"""
import os
import numpy as np
import xarray as xr
from xoa.regrid import grid2loc, regrid1d
import xoa
import xoa.cf as xcf
import logging
import gsw
from armoor.hmi.script_tools import compute_mixed_layer

logger = logging.getLogger(__name__)


@xr.register_dataarray_accessor("sel_var")
@xr.register_dataset_accessor("sel_var")
class SSTAccessor:
    """
    Read SST out of a dataset in a user-friendly format.

    Attributes
    ----------
    xarray_obj : xarray.Dataset
        Dataset to extract SST from.
    """

    def __init__(self, xarray_obj):
        self._obj = xarray_obj
        xoa.register_accessors()
        xoa.register_accessors(decode_sigma=True)

        path_cfg = '../../config/cf.cfg'

        try:
            rootdir = os.path.abspath(os.path.dirname(__file__))
            path = os.path.join(rootdir, path_cfg)
        except:
            logger.warning('cf.cfg file not found')
            directory = os.getcwd()
            logger.warning(f'using path : {directory}')

        xcf.register_cf_specs(path)

    def selection(self, vars, depth=0):
        liste_ds = []
        for var in vars:
            if var == 'SST':
                ds = self._obj.sel_var.sel_sst(depth)
                ds = ds.rename('sst') if ds is not None else ds
            elif var == 'temp':
                ds = self._obj.sel_var.sel_temp()
            elif var == 'ptemp':
                ds = self._obj.sel_var.sel_ptemp()
                ds = ds.rename('ptemp') if ds is not None else ds
            elif var == 'ssh':
                ds = self._obj.sel_var.sel_ssh()
            elif var == 'sal':
                ds = self._obj.sel_var.sel_sal()
            elif var == 'dens':
                ds = self._obj.sel_var.sel_density()
            elif var == 'pdens':
                ds = self._obj.sel_var.sel_pdensity()
            elif var == 'current':
                ds = self._obj.sel_var.sel_current()
            elif var == 'mld':
                ds = self._obj.sel_var.sel_mixed_layer_depth()
            elif var == 'sound_speed':
                ds = self._obj.sel_var.sel_sound_speed()
            elif var == 'geostrophic_current':
                ds = self._obj.sel_var.sel_geo_current()

            liste_ds.append(ds)

        # Remove None datasets
        liste_ds = [ds for ds in liste_ds if ds is not None]

        # Merge
        if len(liste_ds) == 1:
            ds_all = liste_ds[0]
        elif len(liste_ds) > 1:
            ds_all = xr.merge(liste_ds)

        # Convert to dataset for homogeneous processing
        if not isinstance(ds_all, xr.Dataset):
            ds_all = ds_all.to_dataset()

        return ds_all

    def convert_current(self):
        """
        convert current speed / direction into u /v
        Returns
        -------

        """
        speed = self._obj.HCSP
        direction = self._obj.HCDT
        u = speed / np.sin(direction)
        v = speed / np.cos(direction)
        self._obj['u'] = u
        self._obj['v'] = v
        return self._obj

    def sel_current(self):
        """
        Select the u/v current from dataset
        Returns
        -------
        xarray.DataArray
            Data array containing current.

        """
        if 'u' in self._obj.variables:
            current = self._obj[['u', 'v']]
            current = current.assign_coords(self._obj.coords)
        else:
            current = self._obj.sel_var.convert_current()
        if 'HCSP' in self._obj.variables:
            current['norm'] = self._obj['HCSP']
        else:
            current['norm'] = (current.u ** 2 + current.v ** 2) ** 0.5
        return current

    def sel_geo_current(self):
        """
        Select the u/v current from dataset
        Returns
        -------
        xarray.DataArray
            Data array containing geostrophic current.

        """
        current = self._obj[["ugbt", "vgbt"]]

        return current

    def sel_sst(self, depth=0):
        """
        Select SST from the dataset.

        Returns
        -------
        xarray.DataArray
            Data array containing SST. If several depth temperature, the temperature of the min depth is taken.
        """
        if 'sst' in self._obj:
            return self._obj.sst.sel_var.convert_K_C()
        elif 'temp' in self._obj:
            logger.info('SST retrieved from temperature variable')
            if 'depth' in self._obj.dims:
                return self._obj.temp.sel(depth=depth, method='nearest').sel_var.convert_K_C()
            elif 'z' in self._obj.dims:
                return self._obj.temp.sel(z=depth).sel_var.convert_K_C()
            elif 'depth' in self._obj.variables:
                depth = xr.DataArray([0], name="depth", dims="depth")
                return regrid1d(self._obj.temp, depth).sel_var.convert_K_C()
            else:  # if no depth (obs sst for example)
                return self._obj.temp.sel_var.convert_K_C()
        elif 'ptemp' in self._obj:
            logger.info('SST retrieved from potential temperature variable')
            if 'depth' in self._obj.dims:
                return self._obj.ptemp.sel(depth=depth, method='nearest').sel_var.convert_K_C()
            elif 'z' in self._obj.dims:
                return self._obj.ptemp.sel(z=depth).sel_var.convert_K_C()
            elif 'depth' in self._obj.variables:
                depth = xr.DataArray([0], name="depth", dims="depth")
                return regrid1d(self._obj.ptemp, depth).sel_var.convert_K_C()
            else:  # if no depth (obs sst for example)
                return self._obj.ptemp.sel_var.convert_K_C()

    def sel_sal(self):
        """
        Select salinity from the dataset.

        Returns
        -------
        xarray.DataArray
            Data array containing salinity.
        """

        try:  # dataset
            if "sal" in self._obj.variables:
                return self._obj.sal
        except:
            return self._obj.xoa.sal

    def sel_temp(self):
        """
        Select temperature from the dataset.

        Returns
        -------
        xarray.DataArray
            Data array containing temperature.
        """
        if self._obj.xoa.temp is not None:
            ds_temp = self._obj.xoa.temp.sel_var.convert_K_C()
            ds_temp = ds_temp.rename('temp')
            return ds_temp

    def sel_ptemp(self):
        """
        Select temperature from the dataset.

        Returns
        -------
        xarray.DataArray
            Data array containing temperature.
        """
        if 'ptemp' in self._obj:
            return self._obj['ptemp'].sel_var.convert_K_C()
        elif 'temp' in self._obj:
            # verify salinity and pressure are also included
            if 'sal' in self._obj and 'pres' in self._obj:
                ptemp = gsw.conversions.pt0_from_t(self._obj.sal, self._obj.temp, self._obj.pres)
                ptemp.attrs['standard_name'] = "sea_water_potential_temperature"
                ptemp.attrs['units'] = "degrees_celsius"
                ptemp.attrs['long_name'] = "Potential temperature"
                self._obj['ptemp'] = ptemp
                return self._obj
            else:
                logging.warning('The potential temperature could not be calculated, sea temperature will be used')
                return self._obj.temp

    def sel_sound_speed(self):
        """
        Compute the sound speed.

        Returns
        -------
        xarray.DataArray
            Data array containing the sound speed.
        """
        # Verify all the required variables are included in the dataset
        sal = self._obj.sel_var.sel_sal()

        ptemp = self._obj.sel_var.sel_ptemp()
        cons_temp = gsw.CT_from_pt(sal, ptemp)

        depth = self._obj.depth
        lat = self._obj.lat
        pres = gsw.p_from_z(depth, lat, geo_strf_dyn_height=0, sea_surface_geopotential=0)

        if sal is not None and cons_temp is not None and pres is not None:
            return gsw.sound_speed(sal, cons_temp, pres)
        else:
            logger.warning("To compute sound speed you need to have salinity, potential temperature and depth in your"
                           "dataset.")
            return self._obj

    def sel_mixed_layer_depth(self):
        """
        Compute the mixed layer depth

        Returns
        -------
        xarray.DataArray
            Data array containing the mixed layer depth.
        """
        return compute_mixed_layer(self._obj['temp'])

    def sel_density(self):
        """
        Select density from the dataset.

        Returns
        -------
        xarray.DataArray
            Data array containing density.
        """
        return self._obj.xoa.dens

    def sel_pdensity(self):
        """
        Select density from the dataset.

        Returns
        -------
        xarray.DataArray
            Data array containing density.
        """
        return self._obj.xoa.pden

    def sel_ssh(self):
        """
        Select density from the dataset.

        Returns
        -------
        xarray.DataArray
            Data array containing density.
        """
        return self._obj.ssh

    def convert_K_C(self):
        """
        Convert temperature units into Celcius degrees.

        Returns
        -------
        xarray.DataArray
            Data array containing SST in Celcius degrees.
        """

        if 'units' in self._obj.attrs and self._obj.attrs['units'] == 'kelvin':
            return self._obj - 273.15
        elif self._obj.max() > 200:
            return self._obj - 273.15
        else:
            return self._obj
