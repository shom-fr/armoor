import logging

import gsw
import xarray as xr
import numpy as np

from armoor import ArmoorError
from armoor.base.dispatch import MethodRegistry

logger = logging.getLogger(__name__)


def _gsw_ufunc(func, *args):
    """Wrap a gsw function so it works with both numpy and dask arrays."""
    return xr.apply_ufunc(
        func, *args,
        dask="parallelized",
        output_dtypes=[np.float32],
    )

class OceanVars(MethodRegistry):
    """
    Sel or compute ocean variable from a dataset in a user-friendly format.

    Variables are dispatched by name via `call` (see
    `armoor.base.dispatch.MethodRegistry`).

    Parameters
    ----------
    xarray_obj : xarray.Dataset
    """

    _dispatch_label = "Ocean variable"

    #: varname (as used in comp_vars/oceanvars filters) -> sel_* method name.
    _VARNAME_METHODS = {
        "ptemp": "sel_ptemp",
        "temp": "sel_temp",
        "sal": "sel_sal",
        "sndspeed": "sel_sndspeed",
        "pdens": "sel_pdens",
        "u": "sel_current_zonal",
        "v": "sel_current_meridional",
        "cdir": "sel_current_direction",
        "cspeed": "sel_current_speed",
        "mld": "sel_mld",
        "div": "sel_divergence",
        "okuboweiss": "sel_okuboweiss",
        "relvort": "sel_relvort",
    }

    def __init__(self, ds):
        self.ds = ds
        self.methods = {}
        self.__post_init__()

    def sel(self, varname: str):
        method_name = self._VARNAME_METHODS.get(varname)
        if method_name is None:
            raise ArmoorError(f"Unknown ocean variable '{varname}'")
        return self.call(method_name)

    def sel_current_direction(self):
        if "cdir" in self.ds:
            return self.ds["cdir"]
        elif set(("u", "v")).issubset(self.ds.data_vars):
            return np.arctan2(self.ds.v, self.ds.u)
        else:
            logger.warning("cdir cannot be infered or computed")
            
    def sel_current_speed(self):
        if "cspeed" in self.ds:
            return self.ds["cspeed"]
        elif set(("u", "v")).issubset(self.ds.data_vars):
            return (self.ds.u ** 2 + self.ds.v ** 2) ** 0.5
        else:
            logger.warning("cspeed cannot be infered or computed")        
            
    def sel_current_zonal(self):
        if "u" in self.ds:
            return self.ds["u"]
        elif set(("cdir", "cspeed")).issubset(self.ds.data_vars):
            return self.ds.cspeed * np.cos(self.ds.cdir * np.pi / 180.0)
        else:
            logger.warning("u cannot be infered or computed")
    
    def sel_current_meridional(self):
        if "v" in self.ds:
            return self.ds["v"]
        elif set(("cdir", "cspeed")).issubset(self.ds.data_vars):
            return self.ds.cspeed * np.sin(self.ds.cdir * np.pi / 180.0)
        else:
            logger.warning("v cannot be infered or computed")
    
    def sel_ptemp(self):
        if "ptemp" in self.ds:
            return self.ds["ptemp"]
        elif "temp" in self.ds:
            if "sal" in self.ds:
                if "pres" not in self.ds:
                    pres = self.ds.oceanvars.sel_pres()
                else:
                    pres = self.ds["pres"]
                ptemp = _gsw_ufunc(
                    gsw.conversions.pt0_from_t,
                    self.ds.sal, self.ds.temp, pres,
                )
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
            pres = self.sel_pres()
            if not isinstance(sal, xr.DataArray) or not isinstance(pres, xr.DataArray):
                logger.warning(
                    "No salinity or pressure found, in situ temperature cannot be computed."
                )
                return None
            ptemp = self.sel_ptemp()
            cons_temp = _gsw_ufunc(gsw.CT_from_pt, sal, ptemp)
            temp = _gsw_ufunc(gsw.t_from_CT, sal, cons_temp, pres)
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
            # Use mean latitude to avoid broadcasting depth against lat's
            # spatial dimensions, which can create huge intermediate arrays
            # on gridded products. The lat dependence in p_from_z is only
            # a minor gravity correction (~0.5%).
            if "lat" not in self.ds:
                logger.warning("pressure cannot be computed")
                return None
            lat = float(self.ds.lat.mean())
            pres = gsw.conversions.p_from_z(-self.ds.depth, lat)
            # Cache to avoid recomputing (sel_pdens calls sel_pres
            # multiple times via sel_ptemp / SA_from_SP).
            self.ds["pres"] = pres
            return self.ds["pres"]
        
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
            ptemp = self.sel_ptemp()
            asal = _gsw_ufunc(
                gsw.conversions.SA_from_SP,
                sal, pres, self.ds.lon, self.ds.lat,
            )
            ctemp = _gsw_ufunc(gsw.CT_from_pt, asal, ptemp)
            del ptemp
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
                pdens = _gsw_ufunc(func, asal, ctemp)
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
        cons_temp = _gsw_ufunc(gsw.CT_from_pt, sal, ptemp)

        pres = self.sel_pres()
        sal = _gsw_ufunc(
            gsw.conversions.SA_from_SP,
            self.sel_sal(), pres, self.ds.lon, self.ds.lat,
        )
        snd_speed = _gsw_ufunc(gsw.sound_speed, sal, cons_temp, pres)
        snd_speed.attrs["units"] = "m/s"
        self.ds["sndspeed"] = snd_speed
        return self.ds["sndspeed"]

    def sel_mld(self):
        """
        Compute the mixed layer depth.

        Returns
        -------
        xarray.DataArray
            Data array containing the mixed layer depth.
        """
        from xoa.thermdyn import mixed_layer_depth

        logger.info(
                "COMPUTE MLD"
        ) 
        if "mld" not in self.ds:
            ptemp = self.sel_ptemp()
            if not isinstance(ptemp, xr.DataArray):
                logger.warning("Potential temperature cannot be computed")
                return None
            if "depth" not in self.ds:
                logger.warning(
                    "No depth coordinate found, mixed layer depth cannot be computed"
                )
                return None
            # armoor.data.open_decode.register_cf() registers per-format CF
            # specs (cmems_argo, cmems_model, ...) into xoa's global meta
            # specs registry. Without this, xoa.meta.get_meta_specs infers
            # the "best matching" spec for ptemp from its coordinate names,
            # which can select a per-format spec that doesn't declare
            # "depth" as a coordinate (e.g. cmems_model only knows lon/lat),
            # making xoa.thermdyn.mixed_layer_depth fail with
            # "No depth coordinate found" even though ptemp does carry a
            # valid CF depth coordinate. Force xoa's generic default specs
            # so the depth coordinate is always recognized.
            ptemp = ptemp.copy()
            ptemp.encoding["meta_specs"] = "default"
            mld = mixed_layer_depth(ptemp, method='deltatemp')
            mld.attrs["units"] = "m"
            self.ds["mld"] = mld

        return self.ds["mld"]

    def sel_divergence(self):
        """
        Compute the divergence of the flow.

        Returns
        -------
        xarray.DataArray
            Data array containing the divergence.
        """
        if "div" in self.ds:
            return self.ds["div"]
        elif set(("u", "v")).issubset(self.ds.data_vars):
            from shoot.dyn import get_div
            return get_div(self.ds.u, self.ds.v)
        else:
            logger.warning("Divergence cannot be infered or computed")

    def sel_okuboweiss(self):
        """
        Compute the Okubo-Weiss parameter.

        Returns
        -------
        xarray.DataArray
            Data array containing the Okubo-Weiss.
        """
        if "okuboweiss" in self.ds:
            return self.ds["okuboweiss"]
        elif set(("u", "v")).issubset(self.ds.data_vars):
            from shoot.dyn import get_okuboweiss
            return get_okuboweiss(self.ds.u, self.ds.v)
        else:
            logger.warning("Okubo-Weiss cannot be infered or computed")

    def sel_relvort(self):
        """
        Compute the relative vorticity.

        Returns
        -------
        xarray.DataArray
            Data array containing the relative vorticity.
        """
        if "relvort" in self.ds:
            return self.ds["relvort"]
        elif set(("u", "v")).issubset(self.ds.data_vars):
            from shoot.dyn import get_relvort
            return get_relvort(self.ds.u, self.ds.v)
        else:
            logger.warning("Relative vorticity cannot be infered or computed")
