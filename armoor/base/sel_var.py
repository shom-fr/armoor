# -*- coding: utf-8 -*-
"""read variables in models and observation
"""
import os
import logging
import numpy as np
import xarray as xr
import xoa
import xoa.cf as xcf
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
        xr.set_options(keep_attrs=True)
        path_cfg = '../../config/cf.cfg'

        try:
            rootdir = os.path.abspath(os.path.dirname(__file__))
            path = os.path.join(rootdir, path_cfg)
        except:
            logger.warning('cf.cfg file not found')
            directory = os.getcwd()
            logger.warning('using path : %s', directory)

        xcf.register_cf_specs(path)

    def selection(self, vars, depth=0):
        """
        Select the variable.
        Parameters
        ----------
        vars
        depth
        """
        liste_ds = []
        for var in vars:
            if var == 'SST':
                dataset = self._obj.sel_var.sel_sst(depth)
                dataset = dataset.rename('sst') if dataset is not None else dataset
            elif var == 'temp':
                dataset = self._obj.sel_var.sel_temp()
            elif var == 'ptemp':
                dataset = self._obj.sel_var.sel_ptemp()
                dataset = dataset.rename('ptemp') if dataset is not None else dataset
            elif var == 'ssh':
                dataset = self._obj.sel_var.sel_ssh()
            elif var == 'sal':
                dataset = self._obj.sel_var.sel_sal()
            elif var == 'dens':
                dataset = self._obj.sel_var.sel_density()
            elif var == 'pdens':
                dataset = self._obj.sel_var.sel_pdensity()
            elif var == 'current':
                dataset = self._obj.sel_var.sel_current()
            elif var == 'mld':
                dataset = self._obj.sel_var.sel_mixed_layer_depth()
            elif var == 'sound_speed':
                dataset = self._obj.sel_var.sel_sound_speed()
            elif var == 'geostrophic_current':
                dataset = self._obj.sel_var.sel_geo_current()
            liste_ds.append(dataset)

        # Remove None datasets
        liste_ds = [dataset for dataset in liste_ds if dataset is not None]

        # Merge
        if len(liste_ds) == 1:
            ds_all = liste_ds[0]
        elif len(liste_ds) > 1:
            ds_all = xr.merge(liste_ds)

        # Convert to dataset for homogeneous processing
        if not isinstance(ds_all, xr.Dataset):
            ds_all = ds_all.to_dataset()

        # Assign attributes (name especially)
        ds_all = ds_all.assign_attrs(self._obj.attrs)

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
            Data array containing SST. If several depth temperature,
            the temperature of the min depth is taken.
        """
        if 'sst' in self._obj:
            return self._obj.sst.sel_var.convert_K_C()
        if 'temp' in self._obj:
            logger.info('SST retrieved from temperature variable')
            if 'depth' in self._obj.squeeze().dims:
                return self._obj.temp.sel(depth=depth, method='nearest').sel_var.convert_K_C()
            if 'z' in self._obj.squeeze().dims:
                return self._obj.temp.sel(z=depth).sel_var.convert_K_C()
            if 'depth' in self._obj.variables and (
                    'z' in self._obj.dims or 'level' in self._obj.dims):
                return self._obj.meta.vertical_selection_ponct(depth).sel_var.convert_K_C()
            # if no depth (obs sst for example)
            return self._obj.temp.sel_var.convert_K_C()
        if 'ptemp' in self._obj:
            logger.info('SST retrieved from potential temperature variable')
            if 'depth' in self._obj.squeeze().dims:
                return self._obj.ptemp.sel(depth=depth, method='nearest').sel_var.convert_K_C()
            if 'z' in self._obj.squeeze().dims:
                return self._obj.ptemp.sel(z=depth).sel_var.convert_K_C()
            if 'depth' in list(self._obj.keys()) and (
                    'z' in self._obj.dims or 'level' in self._obj.dims):
                depth = xr.DataArray([0], name="depth", dims="depth")
                return self._obj.meta.vertical_selection_ponct(depth).sel_var.convert_K_C()
            # if no depth (obs sst for example)
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
        if 'temp' in self._obj:
            # verify salinity and pressure are also included
            if 'sal' in self._obj and 'pres' in self._obj:
                ptemp = gsw.conversions.pt0_from_t(self._obj.sal, self._obj.temp, self._obj.pres)
                ptemp.attrs['standard_name'] = "sea_water_potential_temperature"
                ptemp.attrs['units'] = "degrees_celsius"
                ptemp.attrs['long_name'] = "Potential temperature"
                self._obj['ptemp'] = ptemp
                return self._obj

            logging.warning(
                'The potential temperature could not be calculated, sea temperature will be used')
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

        logger.warning("To compute sound speed you need to have salinity, "
                       "potential temperature and depth in your dataset.")
        return self._obj

    def sel_mixed_layer_depth(self):
        """
        Compute the mixed layer depth

        Returns
        -------
        xarray.DataArray
            Data array containing the mixed layer depth.
        """
        if "temp" in self._obj:
            self._obj = compute_mixed_layer(self._obj['temp'])
        elif "ptemp" in self._obj:
            self._obj = compute_mixed_layer(self._obj['ptemp'])
        return self._obj

    def sel_density(self):
        """
        Select density from the dataset.

        Returns
        -------
        xarray.DataArray
            Data array containing density.
        """
        if "dens" in self._obj:
            return self._obj.xoa.dens
        else:
            temp = self._obj.sel_var.sel_temp()
            sal = self._obj.sel_var.sel_sal()
            if "pres" in self._obj:
                pres = self._obj['pres']
            else:
                pres = gsw.p_from_z(self._obj.depth, self._obj.lat, geo_strf_dyn_height=0,
                                    sea_surface_geopotential=0)
            dens = gsw.density.rho(sal, temp, pres)
            dens.name = 'dens'
            return dens

    def sel_pdensity(self):
        """
        Select density from the dataset.

        Returns
        -------
        xarray.DataArray
            Data array containing density.
        """
        ds_dens = self._obj.xoa.pdens
        if ds_dens is None:
            sal = self._obj.sel_var.sel_sal()
            temp = self._obj.sel_var.sel_temp()
            if not sal is None and not temp is None:
                pdens = gsw.sigma0(sal, temp)
                self._obj['pdens'] = pdens
                return self._obj['pdens']
        else:
            return ds_dens

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

        if 'units' in self._obj.attrs and self._obj.attrs[
            'units'] == 'kelvin' or self._obj.max() > 200:
            self._obj = self._obj - 273.15
            self._obj.attrs['units'] = 'degC'
            return self._obj
        self._obj.attrs['units'] = 'degC'
        return self._obj
