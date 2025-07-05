#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Tue Jun 10 19:47:07 2025

@author: lmmorvan
"""
import logging
import gsw
import xarray as xr

logger = logging.getLogger(__name__)

@xr.register_dataarray_accessor("oceanvars")
@xr.register_dataset_accessor("oceanvars")
class OceanVars:
    """
    Sel or compute ocean variable from a dataset in a user-friendly format.

    Parameters
    ----------
    xarray_obj : xarray.Dataset
    """

    def __init__(self, ds):
        self.ds = ds
        
    def sel(self, varname: str):
        if varname == "ptemp":
            return self.ds.oceanvars.sel_ptemp()
        elif varname == "temp":
            return self.ds.oceanvars.sel_temp()
        elif varname == "sal":
            return self.ds.oceanvars.sel_sal()
        elif varname == "sndspeed":
            return self.ds.oceanvars.sel_sndspeed()
        elif varname == "pdens":
            return self.ds.oceanvars.sel_pdens()
        
    def sel_ptemp(self):
        if "ptemp" in self.ds:
            return self.ds["ptemp"]
        elif "temp" in self.ds:
            if "sal" in self.ds:
                if "pres" not in self.ds:
                    pres = self.ds.oceanvars.sel_pres()
                else:
                    pres = self.ds["pres"]
                ptemp = gsw.conversions.pt0_from_t(
                    self.ds.sal.data, self.ds.temp.data, pres.data
                    )
                ptemp = xr.DataArray(data=ptemp, coords=self.ds.temp.coords)
                ptemp.attrs["standard_name"] = (
                    "sea_water_potential_temperature"
                )
                ptemp.attrs["units"] = "degrees_celsius"
                ptemp.attrs["long_name"] = "Potential temperature"
                return ptemp
            else:
                logger.warning(
                    "No salinity found, potential temperature cannot be computed."
                )
                return None
    
    def sel_temp(self):
        """
        Select temperature from the dataset.

        Returns
        -------
        xarray.DataArray
            Data array containing temperature.
        """
        if "temp" in self.ds:
            return self.ds["temp"]
        if "ptemp" in self.ds:
            sal = self.sel_sal()
            ptemp = self.sel_ptemp()
            pres = self.sel_pres()
            cons_temp = gsw.CT_from_pt(sal, ptemp)
            temp = gsw.t_from_CT(sal, cons_temp, pres)
            temp.attrs["units"] = "degC"
            return temp
    
    def sel_sal(self):
        """
        Select salinity from the dataset.

        Returns
        -------
        xarray.DataArray
            Data array containing salinity.
        """
        if "sal" in self.ds:
            return self.ds["sal"]
        else:
            return None
    
    def sel_pres(self):
        if "pres" in self.ds:
            return self.ds["pres"]
        elif "depth" in self.ds:
            return gsw.conversions.p_from_z(-self.ds.depth, self.ds.lat)
        
    def sel_pdens(self, ref_dens=None):
        """
        Select density from the dataset.

        Returns
        -------
        xarray.DataArray
            Data array containing density.
        """
        if "pdens" not in self.ds:
            sal = self.sel_sal()
            pres = self.sel_pres()
            if not isinstance(pres, xr.DataArray):
                logger.warning("Potential density cannot be computed")
                return None
            if not isinstance(sal, xr.DataArray):
                logger.warning("Potential density cannot be computed")
                return None
            asal = gsw.conversions.SA_from_SP(
                self.sel_sal(), self.sel_pres(), self.ds.lon, self.ds.lat
                )
            ctemp = gsw.CT_from_pt(
                asal, self.sel_ptemp()
                )
            if not asal is None and not ctemp is None:
                if ref_dens is None or ref_dens not in [
                    0,
                    1000,
                    2000,
                    3000,
                    4000,
                ]:
                    logger.warning(
                        "You did not specify the vertical reference to compute the potential density. "
                        "Please define reference_density in the configuration file, with values among 0, 1000, 2000, 3000 and 4000 dbar."
                        "The reference will be 0 dbar here."
                    )
                    func = gsw.sigma0
                elif ref_dens == 0:
                    func = gsw.sigma0
                elif ref_dens == 1000:
                    func = gsw.sigma1
                elif ref_dens == 2000:
                    func = gsw.sigma2
                elif ref_dens == 3000:
                    func = gsw.sigma3
                elif ref_dens == 4000:
                    func = gsw.sigma4
                pdens = func(asal, ctemp)
                self.ds["pdens"] = pdens
                self.ds["pdens"] = self.ds["pdens"].assign_attrs(
                    {"units": "kg/m3"}
                )
            else:
                logger.warning(
                    "Caution, potential density could not be computed, ptemp or sal are missing."
                )
                return None
        return self.ds["pdens"]
    
    def sel_sndspeed(self):
        """
        Compute the sound speed.

        Returns
        -------
        xarray.DataArray
            Data array containing the sound speed.
        """
        # Verify all the required variables are included in the dataset
        ptemp = self.sel_ptemp()
        sal = self.sel_sal()
        if not isinstance(ptemp, xr.DataArray):
            logger.warning("Potential density cannot be computed")
            return None
        if not isinstance(sal, xr.DataArray):
            logger.warning("Potential density cannot be computed")
            return None
        cons_temp = gsw.CT_from_pt(sal, ptemp)
            
        pres = self.sel_pres()
        sal = gsw.conversions.SA_from_SP(
            self.sel_sal(), pres, self.ds.lon, self.ds.lat
        )
        snd_speed = gsw.sound_speed(sal, cons_temp, pres)
        snd_speed.attrs["units"] = "m/s"
        self.ds["sndspeed"] = snd_speed
        return self.ds["sndspeed"]

        