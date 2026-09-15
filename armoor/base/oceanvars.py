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
    # Note that not all functions defined hereafter are stored in _VARNAME_METHODS (ex: cgeo)
    _VARNAME_METHODS = {
        "ssh": "sel_ssh",
        "bathy": "sel_bathy",
        "cdir": "sel_current_direction",
        "cspeed": "sel_current_speed",
        "u": "sel_current_zonal",
        "v": "sel_current_meridional",
        "ptemp": "sel_ptemp",
        "temp": "sel_temp",
        "sal": "sel_sal",
        "pres": "sel_pres",
        "pdens": "sel_pdens",
        "sndspeed": "sel_sndspeed",
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

    def sel_ssh(self):
        if "ssh" in self.ds:
            return self.ds["ssh"]
        else:
            logger.warning("ssh not in dataset")


    def sel_bathy(self):
        if "bathy" in self.ds:
            return self.ds["bathy"]
        else:
            logger.warning("bathy not in dataset")

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
            sal = self.sel_sal()
            if isinstance(sal, xr.DataArray):
                pres = self.sel_pres()
                ptemp = _gsw_ufunc(
                    gsw.conversions.pt0_from_t,
                    sal, self.ds.temp, pres,
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
        Select or compute salinity from the dataset.

        Falls back to computing practical salinity from raw conductivity
        (``conduct``, in mS/cm -- the unit `gsw.SP_from_C` expects
        directly, no conversion needed) when ``sal`` isn't already
        present, e.g. for ODAR-decoded towed-CTD sections (seasoar,
        scanfish, ...), which only carry the raw sensor conductivity.

        Returns
        -------
        xarray.DataArray or None
            Data array containing salinity, or None if neither salinity
            nor conductivity (plus temperature and pressure) is available.
        """
        if "sal" in self.ds:
            return self.ds["sal"]
        if "conduct" in self.ds and "temp" in self.ds:
            pres = self.sel_pres()
            if not isinstance(pres, xr.DataArray):
                logger.warning("No pressure found, salinity cannot be computed from conductivity.")
                return None
            sal = _gsw_ufunc(gsw.SP_from_C, self.ds.conduct, self.ds.temp, pres)
            sal.attrs["standard_name"] = "sea_water_salinity"
            sal.attrs["long_name"] = "Practical salinity"
            sal.attrs["units"] = "1e-3"
            return sal
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

    def sel_cgeo(self, p_ref=0.0):
        """
        Compute the geostrophic current normal to a hydrological section,
        via dynamic height (`gsw.geo_strf_dyn_height` +
        `gsw.geostrophic_velocity`).

        Not dispatched through `sel`/`_VARNAME_METHODS` like every other
        variable here: it collapses the along-track dimension from N
        stations to N-1 station *pairs* (one velocity between each pair of
        consecutive profiles, by construction oriented perpendicular to the
        line joining them), so it can't be assigned back onto `self.ds`'s
        own "time" dim the way `compute_oceanvars`'s generic loop assumes.
        Called directly by `armoor.comp.comparison.CompHydrosection`, which
        merges the result (dims ``("pair", "z")``) into the dataset as a
        new variable on a new dim instead.

        Parameters
        ----------
        p_ref : float, optional
            Reference sea pressure (dbar) for the dynamic height
            calculation -- the depth at which the geostrophic velocity is
            assumed to be zero. Defaults to 0 dbar (referenced to the sea
            surface).

        Returns
        -------
        xarray.DataArray or None
            Geostrophic velocity (m/s), dims ``("pair", "z")``, with
            ``lon``/``lat`` coordinates on ``"pair"`` at the midpoint of
            each consecutive station pair. None if there are fewer than 2
            stations or salinity/temperature/pressure/position aren't all
            available.
        """
        if "time" not in self.ds.dims or self.ds.sizes["time"] < 2:
            logger.warning("Fewer than 2 stations, geostrophic velocity cannot be computed.")
            return None
        sal = self.sel_sal()
        ptemp = self.sel_ptemp()
        pres = self.sel_pres()
        if not all(isinstance(x, xr.DataArray) for x in (sal, ptemp, pres)):
            logger.warning(
                "Missing salinity, potential temperature or pressure, "
                "geostrophic velocity cannot be computed."
            )
            return None
        if "lon" not in self.ds.coords or "lat" not in self.ds.coords:
            logger.warning("No lon/lat found, geostrophic velocity cannot be computed.")
            return None

        # pres/depth (unlike sal/ptemp) can be "z"-only -- e.g. a gridded
        # model product's own depth grid doesn't vary per time step, so
        # sel_pres()'s p_from_z fallback never gains a "time" dim. Broadcast
        # everything (including depth, if present, for the mid-pair depth
        # coordinate below) onto a shared (time, z) shape before handing
        # plain numpy arrays to gsw, which does no dim-aware broadcasting.
        has_depth = "depth" in self.ds.coords
        depth = self.ds["depth"] if has_depth else xr.zeros_like(pres)
        sal, ptemp, pres, depth = xr.broadcast(sal, ptemp, pres, depth)

        # Station pairs must follow the track in chronological order --
        # not guaranteed by storage order.
        order = np.argsort(self.ds["time"].values)
        lon = np.atleast_1d(self.ds.lon.values)[order]
        lat = np.atleast_1d(self.ds.lat.values)[order]
        sal_vals = sal.transpose("z", "time").values[:, order]
        ptemp_vals = ptemp.transpose("z", "time").values[:, order]
        pres_vals = pres.transpose("z", "time").values[:, order]
        depth_vals = depth.transpose("z", "time").values[:, order]

        sa = gsw.SA_from_SP(sal_vals, pres_vals, lon[np.newaxis, :], lat[np.newaxis, :])
        ct = gsw.CT_from_pt(sa, ptemp_vals)
        geo_strf = gsw.geo_strf_dyn_height(sa, ct, pres_vals, p_ref=p_ref, axis=0)
        vel, mid_lon, mid_lat = gsw.geostrophic_velocity(geo_strf, lon, lat, p=pres_vals)
        depth_pair = 0.5 * (depth_vals[:, :-1] + depth_vals[:, 1:])

        coords = {"lon": ("pair", mid_lon), "lat": ("pair", mid_lat)}
        if has_depth:
            coords["depth"] = (("z", "pair"), depth_pair)
        cgeo = xr.DataArray(
            vel.astype(np.float32),
            dims=("z", "pair"),
            coords=coords,
        ).transpose("pair", "z")
        cgeo.attrs["standard_name"] = "normal_geostrophic_current"
        cgeo.attrs["long_name"] = "Geostrophic current normal to the section"
        cgeo.attrs["units"] = "m s-1"
        return cgeo

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
