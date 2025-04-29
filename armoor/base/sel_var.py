"""read variables in models and observation."""

import logging

import gsw
import numpy as np
import pandas as pd
import xarray as xr
import xoa.filter as xfilter
from xoa.thermdyn import mixed_layer_depth

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
        # xoa.register_accessors()
        # xoa.register_accessors(decode_sigma=True)
        # xr.set_options(keep_attrs=True)
        # path_cfg = '../../config/cf.cfg'

        # try:
        #     rootdir = os.path.abspath(os.path.dirname(__file__))
        #     path = os.path.join(rootdir, path_cfg)
        # except:
        #     logger.warning('cf.cfg file not found')
        #     directory = os.getcwd()
        #     logger.warning('using path : %s', directory)

        # xcf.register_cf_specs(path)

    def selection(self, vars, depth=0, filter=None):
        """
        Select the variable.

        Parameters
        ----------
        vars
        depth
        """
        # Remove duplicates
        # vars = list(set(vars))
        # liste_ds = []
        logger.info(f"Will sel {vars}")
        for var in vars:
            logger.info(f"{var}")
            if var == "SST":
                dataset = self._obj.sel_var.sel_sst(depth)
                dataset = (
                    dataset.rename("sst") if dataset is not None else dataset
                )
            elif var == "temp":
                dataset = self._obj.sel_var.sel_temp()
                # dataset = dataset.rename('temp') if dataset is not None else dataset
            elif var == "ptemp":
                dataset = self._obj.sel_var.sel_ptemp()
                # dataset = dataset.rename('ptemp') if dataset is not None else dataset
            elif var == "ssh":
                dataset = self._obj.sel_var.sel_ssh()
            elif var == "sal":
                dataset = self._obj.sel_var.sel_sal()
                # dataset = dataset.rename('sal') if dataset is not None else dataset
            elif var == "dens":
                dataset = self._obj.sel_var.sel_density()
            elif var == "pdens":
                dataset = self._obj.sel_var.sel_pdensity()
            elif var == "current":
                dataset = self._obj.sel_var.sel_current()
            elif var == "current_geos":
                dataset = self._obj.sel_var.sel_current_geos()
            elif var == "current_res":
                dataset = self._obj.sel_var.sel_current_res(filter)
            elif var == "current_bc":
                dataset = self._obj.sel_var.sel_current_barocline()
            elif var == "mld_pdens":
                dataset = self._obj.sel_var.sel_mixed_layer_depth("pdens")
            elif var == "mld_ptemp":
                dataset = self._obj.sel_var.sel_mixed_layer_depth("ptemp")
            elif var == "pres":
                dataset = self._obj.sel_var.sel_pres()
            elif var == "sound_speed":
                dataset = self._obj.sel_var.sel_sound_speed()
                # dataset = dataset.rename('sound_speed') if dataset is not None else dataset
            else:
                if var in self._obj:
                    dataset = self._obj[var]
                else:
                    dataset = None

        return self._obj

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
        self._obj["u"] = u
        self._obj["v"] = v
        return self._obj

    def sel_current(self):
        """
        Select the u/v current from dataset
        Returns
        -------
        xarray.DataArray
            Data array containing current.

        """
        # Retrieve u & v
        if "u" in self._obj.variables:
            current = self._obj[["u", "v"]]
            current = current.assign_coords(self._obj.coords)
        else:
            current = self._obj.sel_var.convert_current()

        # Retrieve norm
        if "HCSP" in self._obj.variables:
            current["norm"] = self._obj["HCSP"]
        else:
            current["norm"] = (current.u**2 + current.v**2) ** 0.5

        # Retrieve direction
        current["dir"] = np.arctan2(current["u"], current["v"]) * 180 / np.pi
        current["dir"] = current["dir"].assign_attrs({"units": "°"})
        return current

    def sel_current_geos(self):
        """
        Select the u/v current from dataset
        Returns
        -------
        xarray.DataArray
            Data array containing geostrophic current.

        """
        if "current_geos" in self._obj:
            return self._obj

        # Get variables

        SA = self._obj.sel_var.sel_sal()["sal"]
        temp = self._obj.sel_var.sel_temp()["temp"]
        pres = self._obj.sel_var.sel_pres()["pres"]
        depth = self._obj.depth.values
        CT = gsw.conversions.CT_from_t(SA, temp, pres)
        lon = self._obj.lon.values
        lat = self._obj.lat.values
        # # Incrinsing along depth
        if "z" in pres.dims:
            pres = pres.transpose("z", ...).isel(z=slice(None, None, -1))
            SA = SA.transpose("z", ...).isel(z=slice(None, None, -1))
            CT = CT.transpose("z", ...).isel(z=slice(None, None, -1))
        # Stream function
        geo_strf = gsw.geostrophy.geo_strf_dyn_height(
            SA,
            CT,
            pres,
        )
        # Calculate geostrophic current
        [geo_vel, lon, lat] = gsw.geostrophy.geostrophic_velocity(
            geo_strf, lon, lat, p=0, axis=0
        )
        # Create dataset
        times = [
            time.astype("datetime64[s]") for time in self._obj.time.values
        ]
        times = [
            (times[i].astype(float) + times[i + 1].astype(float)) / 2
            for i in range(len(times) - 1)
        ]
        times = [np.datetime64(int(time), "s") for time in times]
        # if 'z' not in pres.dims:
        #     geo_vel = [geo_vel]

        geo_vel = xr.DataArray(
            data=geo_vel, dims=["z", "time"], coords=dict(time=times)
        )
        # Put  back on the times
        geo_vel = geo_vel.interp(time=self._obj.time.data)
        geo_vel = geo_vel.assign_coords(
            dict(lon=self._obj.lon, lat=self._obj.lat, depth=self._obj.depth)
        ).assign_attrs({"units": "m s-1"})

        # Convert to dataset
        self._obj["current_geos"] = geo_vel
        return self._obj

    def get_norm_dir(self, type):
        u = self._obj[f"u{type}"]
        v = self._obj[f"v{type}"]
        norm = (u**2 + v**2) ** 0.5
        dir = np.arctan2(u, v) * 180 / np.pi
        self._obj[f"norm{type}"] = norm
        self._obj[f"norm{type}"] = self._obj[f"norm{type}"].assign_attrs(
            {"units": "m/s"}
        )
        self._obj[f"dir{type}"] = dir
        self._obj[f"dir{type}"] = self._obj[f"dir{type}"].assign_attrs(
            {"units": "°"}
        )
        return self._obj

    def sel_current_res(self, filter):
        """
        Select residual current from the dataset with demerliac, godin or mean filter.

        Returns
        -------
        xarray.DataArray
            Data array containing residual current.
        """
        if "u_res" in self._obj:
            current_res = self._obj[["u_res", "v_res", "norm_res", "dir_res"]]
            return current_res

        if "u" in self._obj.variables:
            try:
                # Filter
                da_u = self._obj["u"]
                da_v = self._obj["v"]
                da_u_res = xfilter.tidal_filter(da_u, filter)
                da_v_res = xfilter.tidal_filter(da_v, filter)
            except:
                logger.info(
                    f"The time step of the data is not constant, it will be resampled on hourly dates."
                )
                # Resample the data on hourly dates
                ini_time = self._obj["time"].data
                min_date = self._obj["time"].min().data.astype("datetime64[h]")
                max_date = self._obj["time"].max().data.astype("datetime64[h]")
                time_hor = pd.date_range(
                    min_date.item(), max_date.item(), freq="1H"
                )

                self._obj = self._obj.interp(
                    time=time_hor,
                    method="linear",
                    kwargs={"fill_value": "extrapolate"},
                )

                # Filter
                da_u = self._obj["u"]
                da_v = self._obj["v"]
                da_u_res = xfilter.tidal_filter(da_u, filter, na_thres=1)
                da_v_res = xfilter.tidal_filter(da_v, filter, na_thres=1)

                # Put back on original dates
                da_u_res = da_u_res.interp(time=ini_time)
                da_v_res = da_v_res.interp(time=ini_time)

            current_res = xr.Dataset()
            current_res["u_res"] = da_u_res
            current_res["v_res"] = da_v_res
            current_res = current_res.sel_var.get_norm_dir(type="_res")
            return current_res

    def sel_current_barocline(self):
        """
        Select barocllinic current from the dataset.

        Returns
        -------
        xarray.DataArray
            Data array containing baroclinic current.
        """

        if "u_bc" in self._obj:
            current_bc = self._obj[["u_bc", "v_bc", "norm_bc", "dir_bc"]]
            return current_bc

        # Calculate the total current
        current = self._obj.sel_var.sel_current()

        # Calculate the mean current
        if "depth" in self._obj.squeeze().dims:
            current_mean_depth = current.mean("depth")
        elif "z" in self._obj.squeeze().dims:
            current_mean_depth = current.mean("z")

        # Calculate the baroclinic current
        current_bc = current["norm"] - current_mean_depth["norm"]

        # Calculate the azimuth (in radians)
        azimut = np.arctan2(current["u"], current["v"])

        # Calculate the zonal and meridional components of the baroclinic current
        ubc = current_bc * np.cos(azimut)
        vbc = current_bc * np.sin(azimut)

        current_bc = xr.Dataset()
        current_bc["u_bc"] = ubc
        current_bc["v_bc"] = vbc
        current_bc = current_bc.sel_var.get_norm_dir(type="_bc")
        current_bc = current_bc.assign_attrs({"name": self._obj.attrs["name"]})
        return current_bc

    def sel_sst(self, depth=0):
        """
        Select SST from the dataset.

        Returns
        -------
        xarray.DataArray
            Data array containing SST. If several depth temperature,
            the temperature of the min depth is taken.
        """
        if "sst" in self._obj:
            return self._obj.sst.sel_var.convert_K_C()
        if "temp" in self._obj:
            logger.info("SST retrieved from temperature variable")
            if "depth" in self._obj.squeeze().dims:
                return self._obj.temp.sel(
                    depth=depth, method="nearest"
                ).sel_var.convert_K_C()
            if "z" in self._obj.squeeze().dims:
                return self._obj.temp.sel(z=depth).sel_var.convert_K_C()
            if "depth" in self._obj.variables and (
                "z" in self._obj.dims or "level" in self._obj.dims
            ):
                return self._obj.meta.vertical_selection_ponct(
                    depth
                ).sel_var.convert_K_C()
            # if no depth (obs sst for example)
            return self._obj.temp.sel_var.convert_K_C()
        if "ptemp" in self._obj:
            logger.info("SST retrieved from potential temperature variable")
            if "depth" in self._obj.squeeze().dims:
                return self._obj.ptemp.sel(
                    depth=depth, method="nearest"
                ).sel_var.convert_K_C()
            if "z" in self._obj.squeeze().dims:
                return self._obj.ptemp.sel(z=depth).sel_var.convert_K_C()
            if "depth" in list(self._obj.keys()) and (
                "z" in self._obj.dims or "level" in self._obj.dims
            ):
                depth = xr.DataArray([0], name="depth", dims="depth")
                return self._obj.meta.vertical_selection_ponct(
                    depth
                ).sel_var.convert_K_C()
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
        if "sal" not in self._obj:
            logger.warning("No salinity found.")
        return self._obj

    def sel_temp(self):
        """
        Select temperature from the dataset.

        Returns
        -------
        xarray.DataArray
            Data array containing temperature.
        """
        if "temp" in self._obj:
            self._obj = convert_K_C(self._obj, "temp")
            return self._obj
        if "ptemp" in self._obj:
            sal = self._obj.sel_var.sel_sal()["sal"]
            ptemp = self._obj["ptemp"]
            pres = self._obj.sel_var.sel_pres()["pres"]
            cons_temp = gsw.CT_from_pt(sal, ptemp)
            temp = gsw.t_from_CT(sal, cons_temp, pres)
            temp.attrs["units"] = "degC"
            # if np.isnan(ds_temp.min(skipna=True).data):  # If all nans, try the ptemp
            #     logger.warning(
            #         'Temperature computation returned all nans : pot. temp. will be used.')
            #     ds_temp = self._obj.sel_var.sel_ptemp()
            #     ds_temp = ds_temp.rename('temp')
            self._obj["temp"] = temp
            return self._obj

    def sel_ptemp(self):
        """
        Select temperature from the dataset.

        Returns
        -------
        xarray.DataArray
            Data array containing temperature.
        """
        if "ptemp" in self._obj:
            self._obj = convert_K_C(self._obj, "ptemp")
            return self._obj
        if "temp" in self._obj:
            # verify salinity and pressure are also included
            if "sal" in self._obj:
                if "pres" not in self._obj:
                    pres = self._obj.sel_var.sel_pres()["pres"]
                    #pres = pres.transpose()
                else:
                    pres = self._obj["pres"]
                ptemp = gsw.conversions.pt0_from_t(
                    self._obj.sal.data, self._obj.temp.data, pres.data
                )
                ptemp = xr.DataArray(data=ptemp, coords=self._obj.temp.coords)
                ptemp.attrs["standard_name"] = (
                    "sea_water_potential_temperature"
                )
                ptemp.attrs["units"] = "degrees_celsius"
                ptemp.attrs["long_name"] = "Potential temperature"
                self._obj["ptemp"] = ptemp
                return self._obj
            else:
                logger.warning(
                    "No salinity found, potential temperature cannot be computed."
                )
                return self._obj

    def sel_sound_speed(self):
        """
        Compute the sound speed.

        Returns
        -------
        xarray.DataArray
            Data array containing the sound speed.
        """
        # Verify all the required variables are included in the dataset
        if "sal" in self._obj:
            ptemp = self._obj.sel_var.sel_ptemp()["ptemp"]
            cons_temp = gsw.CT_from_pt(self._obj.sal, ptemp)
            pres = self._obj.sel_var.sel_pres()["pres"]
            sal = gsw.conversions.SA_from_SP(
                self._obj.sal, pres, self._obj.lon, self._obj.lat
            )
            snd_speed = gsw.sound_speed(sal, cons_temp, pres)
            snd_speed.attrs["units"] = "m/s"
            self._obj["sound_speed"] = snd_speed
        else:
            logger.warning("The sound speed cannot be calculated.")
        return self._obj

    def sel_mixed_layer_depth(self, var: str):
        """
        Compute the mixed layer depth

        Returns
        -------
        xarray.DataArray
            Data array containing the mixed layer depth.
        """
        logger.info("Compute mixed layer depth")
        # Compute mld from ptemp
        if var == "ptemp":
            dain = self._obj.sel_var.sel_ptemp()["ptemp"].isel(
                z=slice(None, None, -1)
            )
            method = "deltatemp"
            varout = "mld_ptemp"
        # Compute mld from pdens
        elif var == "pdens":
            dain = self._obj.sel_var.sel_pdensity()["pdens"].isel(
                z=slice(None, None, -1)
            )
            method = "deltadens"
            varout = "mld_pdens"
        mld = mixed_layer_depth(dain, method=method, zref=10)
        mld.attrs["varname"] = "mld"

        # else:
        #     msg = f"Currently, we do not compute the mixed layer depth using {var}."
        #     logger.error(msg)
        #     raise ValueError(msg)
        # # mld empty
        # if np.isnan(mld.max().data):
        #     msg = f"The mixed layer depth is full of NaNs, which likely indicates that " \
        #           f"your dataset does not have {var} values at a reference depth of 10 meters."
        #     logger.error(msg)
        #     raise ValueError(msg)
        # return mld
        self._obj[varout] = mld
        return self._obj

    def sel_pres(self):
        if "pres" in self._obj:
            return self._obj
        elif "depth" in self._obj:
            pres = gsw.conversions.p_from_z(-self._obj.depth, self._obj.lat)
            self._obj["pres"] = pres
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
            pres = self._obj.sel_var.sel_pres()
            dens = gsw.density.rho(sal, temp, pres)
            dens.name = "dens"
            return dens

    def sel_pdensity(self, ref_dens=None):
        """
        Select density from the dataset.

        Returns
        -------
        xarray.DataArray
            Data array containing density.
        """
        ds_dens = self._obj.xoa.pdens
        if ds_dens is None:
            if "sal" not in self._obj:
                logger.warning(
                    "No salinity found, potential density cannot be computed"
                )
                return self._obj
            logger.info("convert pressure from depth")
            pres = gsw.conversions.p_from_z(-self._obj.depth, self._obj.lat)
            logger.info("convert absolute salinity from practical salinity")
            asal = gsw.conversions.SA_from_SP(
                self._obj.sal, pres, self._obj.lon, self._obj.lat
            )
            # sal = self._obj.sel_var.sel_sal().sal #should be absolute sal
            # temp = self._obj.sel_var.sel_temp().temp #should be conservative temp
            logger.info(
                "convert conservative temperature from potential temperature"
            )
            ctemp = gsw.CT_from_pt(
                asal, self._obj.sel_var.sel_ptemp()["ptemp"]
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
                logger.info("compute density")
                pdens = func(asal, ctemp)
                self._obj["pdens"] = pdens
                self._obj["pdens"] = self._obj["pdens"].assign_attrs(
                    {"units": "kg/m3"}
                )
                return self._obj
            else:
                logger.warning(
                    "Caution, potential density could not be computed, ptemp or sal are missing."
                )
        self._obj["pdens"] = ds_dens
        return self._obj

    def sel_ssh(self):
        """
        Select density from the dataset.

        Returns
        -------
        xarray.DataArray
            Data array containing density.
        """
        return self._obj.ssh


def convert_K_C(ds, varname):
    """
    Convert temperature units into Celcius degrees.

    Returns
    -------
    xarray.DataArray
        Data array containing SST in Celcius degrees.
    """
    if "units" in ds[varname].attrs and "kelvin" in ds[varname].attrs["units"]:
        da = ds[varname]
        da = da - 273.15
        da.attrs["units"] = "degC"
        ds[varname] = da
    return ds
