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
logger = logging.getLogger(__name__)


@xr.register_dataarray_accessor("read_sst")
@xr.register_dataset_accessor("read_sst")
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

    def sel(self, vars, depth=0):
        liste_ds = []
        for var in vars:
            if var == 'SST':
                ds = self._obj.read_sst.sel_sst(depth)
            elif var == 'temp':
                ds = self._obj.read_sst.sel_temp()
            elif var == 'ptemp':
                ds = self._obj.read_sst.sel_ptemp()
            elif var == 'ssh':
                ds = self._obj.read_sst.sel_ssh()
            elif var == 'sal':
                ds = self._obj.read_sst.sel_sal()
            elif var == 'dens':
                ds = self._obj.read_sst.sel_dens()
            elif var == 'pdens':
                ds = self._obj.read_sst.sel_pdens()
            elif var == 'current':
                ds = self._obj.read_sst.sel_current()

            liste_ds.append(ds)
        if len(liste_ds) == 1:
            ds_all = xr.concat(liste_ds, 'mean_time', combine_attrs="drop")
        elif len(liste_ds) > 1:
            ds_all = xr.merge(liste_ds)  # xr.concat(liste_ds, 'mean_time', combine_attrs="drop")
        return ds_all.squeeze()

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

        """
        if 'u' in self._obj.variables:
            self._obj = self._obj[['u', 'v']]
        else:
            self._obj = self._obj.read_sst.convert_current()
        if 'HCSP' in self._obj.variables:
            self._obj['norm'] = self._obj['HCSP']
        else:
            self._obj['norm'] = (self._obj.u ** 2 + self._obj.v ** 2) ** 0.5
        return self._obj

    def sel_sst(self, depth=0):
        """
        Select SST from the dataset.

        Returns
        -------
        xarray.DataArray
            Data array containing SST. If several depth temperature, the temperature of the min depth is taken.
        """

        if 'depth' in self._obj.coords:

            try:
                return self._obj.xoa.temp.sel(depth=depth, method='nearest').read_sst.convert_K_C()
            except:  # CROCO
                try:
                    return self._obj.xoa.temp.sel(z=depth).read_sst.convert_K_C()  # method='nearest'
                except:
                    return self._obj.xoa.temp.read_sst.convert_K_C()
        elif 'depth' in self._obj.variables:
            depth = xr.DataArray([0], name="depth", dims="depth")
            return regrid1d(self._obj.xoa.temp, depth).read_sst.convert_K_C()
        else:  # if no depth (obs sst for example)
            try:
                return self._obj.xoa.temp.read_sst.convert_K_C()
            except:
                return self._obj.sst.read_sst.convert_K_C()

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
        ds_temp = self._obj.xoa.temp.read_sst.convert_K_C()
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
        return self._obj['ptemp'].read_sst.convert_K_C()

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
        else:
            return self._obj
