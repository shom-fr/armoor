"""
Function to create images for forecaster wed interface
"""

import gc
import json
import logging
import os
import shutil
import sys
import tarfile
import time
from multiprocessing import cpu_count

import dask.array as da
import numpy as np
import pandas as pd
import xarray as xr
from distributed import progress
import dask
from dask import compute, delayed
from dask import config as cfg
from dask.distributed import Client, LocalCluster
from xoa.thermdyn import mixed_layer_depth

import armoor.base.sel_var
from armoor.base.open_decode import open_decode
from armoor.hmi.configuration import (
    apply_custom_metazone,
    get_forcing_model,
    get_model,
    get_obs,
    get_time_spacial_extent,
)
from armoor.hmi.path_tools import get_config_reg_path
from armoor.hmi.script_plot import hmi_image
from armoor.hmi.script_tools import (
    create_folder,
    decumulate_data,
    format_times,
    from_nh_to_1h,
    get_cumul_info,
)

logger = logging.getLogger(__name__)

OCEAN_MODELS = ["hycom", "hycom3d", "croco"]

xr.set_options(keep_attrs=True) 

cfg.set({
    'distributed.scheduler.worker-ttl': None,
    'distributed.worker.memory.target': 0.8,  # Gérer la mémoire avant le swap
    'distributed.worker.memory.spill': 0.9,   # Utiliser le disque au-delà de 90%
    'distributed.worker.memory.pause': 0.95   # Pause au-delà de 95% d'utilisation
})

NC_COMMON = "nc_common.nc"

# import multiprocessing.resource_tracker
# multiprocessing.resource_tracker.DEBUG = True

def create_images(
    config_obj: dict,
    input_folder_path: str,
    output_folder_path: str,
    # legend_configuration: str,
    rundate: str,
):
    """
    Create images and zip them
    Parameters
    ----------
    config_obj : configuration
    input_folder_path : input folder where data comes from
    output_folder_path : folder where the files are saved

    Returns
    -------
    None
    """

    model_name = config_obj["config_reg"]["model"]
    config_name = config_obj["config_reg"]["config"]
    n_workers = config_obj["config_reg"]["n_workers"]
    memory_limit = config_obj["config_reg"]["memory_limit"]

    cluster1 = LocalCluster(
            n_workers=n_workers,
            threads_per_worker=1,
            memory_limit=memory_limit,
            processes=True,
            dashboard_address=None
    )

    config_reg = f"{model_name}_{config_name}"

    parameters = config_obj["parameters"]

    production_day = pd.to_datetime(rundate).strftime("%Y%m%d")

    logger.info(f"Production day : {production_day}")

    config_reg_t0, config_reg_times, config_reg_extent = (
        get_time_spacial_extent(
            input_folder_path,
            model_name,
            config_reg,
            production_day
        )
    )

    input_folder_path = os.path.join(
        input_folder_path,
        f"{config_reg}_{production_day}"
    )

    model_json = {
        "parameters": [],
        "times": format_times(config_reg_times),
        "t0": config_reg_t0.replace(":", "h"),
        "production_day": production_day,
        "config_reg": config_reg,
        "model": model_name,
        "config": config_name,
        "approval": {
            "status": "not_processed",
            "last_update": "",
            "reporter": "",
        },
    }
    # CREATING ALL PARAMETERS OF THE REGIONAL CONFIGURATION
    gc.collect()
    for parameter in parameters:
        model_json["parameters"].append(parameter)
        extent = config_obj["parameters"][parameter].get("extent")
        logger.info(f'{config_obj["parameters"][parameter]}')
        if "common" in config_obj["parameters"][parameter]:
            ds = get_model_xr(
                config_obj["parameters"][parameter]["common"],
                extent,
                input_folder_path,
                config_reg,
                config_reg_extent,
                production_day,
            )
            with Client(cluster1) as client:
                logger.info("to netcdf")
                ds.to_netcdf(NC_COMMON, engine="h5netcdf")
            ds.close() 
        cbar_range = None
        for isub_param, sub_param in enumerate(
                ["param_1", "param_2", "param_3", "param_4"]
            ):
            start_time = time.time()
            logger.info(f"{config_reg} - {parameter} - {sub_param}")
            param = config_obj["parameters"][parameter][sub_param]
            if os.path.exists(NC_COMMON):
                ds = xr.open_dataset(NC_COMMON, chunks="auto").set_xindex("depth")
                var = param["var"][0]
                if var not in ("uv", "suv"):
                    model2plot_xr = ds[[var]]
                else:
                    model2plot_xr = ds
                idx = np.argwhere(
                    model2plot_xr["depth"].values == param["vlevel"]["depth"]
                )[0][0]
                model2plot_xr = model2plot_xr.isel(z=idx)
                if var in ("sal", "ptemp"):
                    if "clim_min" in model2plot_xr[var].attrs:
                        model2plot_xr[var].attrs.update({
                            "clim_min": ds[var].attrs["clim_min"][idx],
                            "clim_max": ds[var].attrs["clim_max"][idx]
                        })
                logger.info(model2plot_xr)
                ds.close()
            else:
                model2plot_xr = get_model_xr(
                    param,
                    extent,
                    input_folder_path,
                    config_reg,
                    config_reg_extent,
                    production_day,
                )
                logger.info("compute dataset")
            nctr = "to_plot.nc"
            if os.path.exists(nctr):
                os.remove(nctr)
            if param["fmt"] != "arpege_insta":
                with Client(cluster1) as client:
                    model2plot_xr.to_netcdf(nctr)
            else:
                model2plot_xr.to_netcdf(nctr)
            model2plot_xr.close()
            logger.info(model2plot_xr)
            cbar_range = create_param_images(
                cluster1,
                config_reg,
                production_day,
                config_reg_times,
                config_reg_extent,
                config_obj,
                parameter,
                sub_param,
                input_folder_path,
                os.path.join(
                    output_folder_path, f"{config_reg}_{production_day}"
                ),
                cbar_range_fix=cbar_range,
                n_workers=n_workers,
                memory_limit=memory_limit
            )
            logger.info(
                f"{config_reg} - {parameter} - {sub_param}  "
                f"in {time.time() - start_time} seconds"
            )
        if os.path.exists(NC_COMMON):
            os.remove(NC_COMMON)
        gc.collect()
    # WRITING PRODUCTION INFO INTO JSON FILE
    create_data_json_file(
        model_json, output_folder_path, config_reg, production_day
    )

    # COMPRESSING to TGZ and delete source directory
    make_tarfile(output_folder_path, config_reg, production_day)

    logger.info(f"PRODUCTION DAY {production_day} : OK")


def create_data_json_file(
    model_json: dict,
    output_folder_path: str,
    config_reg: str,
    production_day: str,
):
    """

    Parameters
    ----------
    model_json: dictionary formatted as json
    output_folder_path : folder where the files are saved
    config_reg : regional configuration name
    production_day : day of the production

    Returns
    -------
    None
    """
    json_data_path = os.path.join(
        output_folder_path, f"{config_reg}_{production_day}", "data.json"
    )
    logger.info(f"Writing production information into :")
    logger.info(f"{json_data_path}")
    with open(json_data_path, "w", encoding="utf-8") as json_file:
        json.dump(model_json, json_file, indent=4, ensure_ascii=False)
    os.chmod(json_data_path, 0o666)


def make_tarfile(
    output_folder_path: str, config_reg: str, production_day: str
):
    """
    Generates compress file and delete source directory
    Parameters
    ----------
    output_folder_path : folder where the files are saved
    config_reg : regional configuration name
    production_day : day of the production

    Returns
    -------
    None
    """

    source_dir = os.path.join(
        output_folder_path, f"{config_reg}_{production_day}"
    )
    output_filename = os.path.join(
        output_folder_path, f"{config_reg}_{production_day}.tgz"
    )

    # COMPRESSING to TGZ
    logger.info(f"COMPRESSING {source_dir} INTO {output_filename}")
    with tarfile.open(output_filename, "w:gz") as tar:
        tar.add(source_dir, arcname=os.path.basename(source_dir))

    # DELETING TEMPORARY FOLDER
    logger.info("Deleting temporary folder")
    logger.info(f"{source_dir}")
    shutil.rmtree(source_dir)


def create_param_images(
    cluster,
    config_reg: str,
    production_day: str,
    config_reg_times: str,
    config_reg_extent: list,
    config_obj: dict,
    parameter_mane: str,
    sub_param: str,
    input_folder_path: str,
    output_folder_path: str,
    cbar_range_fix: tuple=None,
    # legend_configuration: str,
    n_workers: int=20,
    memory_limit: str="20Gb"
):
    """

    Parameters
    ----------
    config_reg : regional configuration name
    production_day: day of the production
    config_reg_times : times of the model to follow
    config_reg_extent : list of 4 elements lon/lat min/max
    config_obj : dictionary with details to generate the images
    parameter_mane : parameter name
    sub_param : param_1, param_2, param_3 or param_4
    input_folder_path : input folder where data comes from
    output_folder_path : folder where the files are saved

    Returns
    -------
    None
    """

    model2plot_xr = xr.open_dataset("to_plot.nc", chunks="auto")

    param = config_obj["parameters"][parameter_mane][sub_param]
    func = param["func"]

    # Model or forcing model used to generate the images for a given parameter
    
    
    cbar_range, data2plot_all_times = get_data2plot(
        func,
        param["var"][0],
        model2plot_xr,
        param.get("cbar"),
    )
    
    logger.info(data2plot_all_times)
    if cbar_range_fix != None:
        cbar_range = cbar_range_fix
    logger.info(f"cbar_range: {cbar_range}")
    logger.info(f"Creating images for all steps : {len(config_reg_times)}")
    # Loop on times to create all images
    param_title = param["name"]
    data = []
    multiprocess = param.get("multiprocess")
    
    stream_legend = (
        param.get("rarification"),
        param.get("barbs_length"),
        param.get("barbs_linewidth"),
        param.get("quiver_scale"),
        param.get("quiver_width"),
        param.get("quiver_headwidth"),
        param.get("quiver_headlength"),
    )
    legend_configuration = param.get("cbar")
    for reg_time in config_reg_times:
        path2save = get_path2save(
            reg_time, parameter_mane, output_folder_path, sub_param
        )

        if func in [
            "visu_temp",
            "visu_sal",
            "visu_mixedlayer",
            "visu_solarflux",
            "visu_precip",
            "visu_current",
            "visu_windforcing",
            "visu_diff_sss",
            "visu_diff_sst",
        ]:
            time_str = [time.dt.strftime("%Y-%m-%dT%H:%M").values for time in data2plot_all_times.time]
            if reg_time in time_str:
                data2plot = data2plot_all_times.sel(time=reg_time)
            else:
                data2plot = data2plot_all_times.sel(time=reg_time, method="nearest")
            

        elif func in ["visu_mixedlayer_clim"]:
            data2plot = data2plot_all_times

        elif func in ["visu_runoff"]:
            data2plot = data2plot_all_times
            cbar_range = reg_time
        else:
            logger.error(f"{func} is not yet implemented for {param_title}")
            break

        if multiprocess:
            clargs = [
                data2plot,
                func,
                param_title,
                path2save,
                cbar_range,
                legend_configuration,
                stream_legend,
            ]
            data.append(delayed(work_process)(clargs))
            del clargs
            data2plot.close()
        else:
            work_process([
                data2plot,
                func,
                param_title,
                path2save,
                cbar_range,
                legend_configuration,
                stream_legend]
            )
            data2plot.close()

    if multiprocess:
        logger.info("Start local cluster")
        '''
        with LocalCluster(
            n_workers=n_workers,
            threads_per_worker=1,
            memory_limit=memory_limit,
            processes=True,
            dashboard_address=None
        ) as cluster:
        '''
        with Client(cluster) as client:
                logger.info(client)
                compute(*data)
    del data
    gc.collect()
    
    if param["var"] == "sst" and param["fmt"] in OCEAN_MODELS:
        return cbar_range
    else:
        return None

def work_process(data: list):
    """
    Sub task to be parallelize
    Parameters
    ----------
    data: list of parameters to generate one image

    Returns
    -------
    None
    """
    data2plot = data[0]
    func = data[1]
    param_title = data[2]
    path2save = data[3]
    cbar_range = data[4]
    legend_configuration = data[5]
    stream_legend = data[6]
    hmi_image(
        data2plot,
        func,
        param_title,
        path2save,
        cbar_range,
        legend_configuration,
        stream_legend=stream_legend,
    )
    data2plot.close()


def get_obs_xr(
    param: dict,
    extent: list,
    input_folder_path: str,
    config_reg: str,
    config_reg_extent: list,
    production_day: str,
) -> xr.Dataset:
    """
    Function to get data to be compered to the model
    Parameters
    ----------
    param : details of the parameter to be plot
    extent : extent to take into account
    input_folder_path : input folder where data comes from
    config_reg: regional configuration name
    config_reg_extent: regional configuration extent
    production_day: day of the production

    Returns
    -------
    observation
    """
    # Observation used to generate the images for a given parameter
    depth = param.get("depth")
    var_m = param["var"]
    obs_name = param.get("obs")
    if obs_name:
        logger.info(f"Reading : {obs_name}")
        obs2plot_xr = get_obs(
            input_folder_path, config_reg, production_day, obs_name, var_m
        )
        if obs_name == "woa18":
            depth = 0
        obs2plot_xr = apply_custom_metazone(
            obs2plot_xr, depth, extent, var_m, config_reg_extent
        )
        return obs2plot_xr
    return None


def get_model_xr(
    param: dict,
    extent: list,
    input_folder_path: str,
    config_reg: str,
    config_reg_extent: list,
    production_day: str,
) -> xr.Dataset:
    """
    Function to get data from the model
    Parameters
    ----------
    param : details of the parameter to be plot
    extent : extent to take into account
    input_folder_path : input folder where data comes from
    config_reg: regional configuration name
    config_reg_extent: regional configuration extent
    production_day: day of the production

    Returns
    -------
    model
    """
    fmt = param.get("fmt")
    depth = param.get("vlevel")
    var_m = param["var"]
    
    logger.info("Get path of input files")
    paths = get_config_reg_path(
        input_folder_path,
        fmt,
        var_m
    ) 
    
    logger.info(f"Open and decode {fmt} files")
    model_xr = open_decode(
        paths,
        fmt=fmt
    )
    if isinstance(model_xr, list):
        model_xr = model_xr[0]

    logger.info("Apply custom metazone")
    logger.info(model_xr)
    model2plot_xr = apply_custom_metazone(
        model_xr,
        depth,
        extent,
        var_m,
        config_reg_extent=config_reg_extent
    )
    for var in var_m:
        if var in ("ptemp", "sal", "sst", "sss"):
            clim_xr = open_decode(
                [os.path.join(input_folder_path, "woa18", "*.nc")],
            fmt="woa18"
        )
            if var in ("sst", "sss"):
                depth = {"depth": [0]}
            if var == "sst":
                var = "ptemp"
            elif var == "sss":
                var = "sal"
            clim_xr = apply_custom_metazone(
                clim_xr,
                depth,
                extent,
                [var],
                config_reg_extent=config_reg_extent
            ).squeeze()
            model2plot_xr[var].attrs.update({
                "clim_min": np.round(clim_xr[var].min(dim=["x", "y"]).values.tolist(), decimals=2),
                "clim_max": np.round(clim_xr[var].max(dim=["x", "y"]).values.tolist(), decimals=2)
            })
            logger.info(model2plot_xr[var].attrs)
    return model2plot_xr


def get_path2save(
    reg_time: str, parameter_mane: str, output_folder_path: str, sub_param: str
):
    """
    Get the path file name to save a sub parameter
    Parameters
    ----------
    reg_time: model time step
    parameter_mane : parameter name
    output_folder_path : folder where the files are saved
    sub_param : param_1, param_2, param_3 or param_4

    Returns
    -------

    """
    reg_time = reg_time.replace(":", "h")
    path = os.path.join(output_folder_path, reg_time, parameter_mane)
    create_folder(path)
    path2save = os.path.join(path, sub_param)
    return path2save


def get_cbar_minmax(ds, minmax=False, nstd=None, difference=False, norm=False):
    """
    Compute min and max values of colorbar
    Parameters
    ----------
    ds : xarray.Dataset
        xarray dataset containing a scalar field.
    minmax : boolean, optional
        If True, keep min and max values of ds as min and max colorbar values
        respectively. If False, min and max are compited as the mean plus or
        minus nstd times the standard deviation. The default is False.
    nstd : float, optional
        The default is 3.0.
    difference : boolean, optional
        If True, min and max values of colorbar are centered around 0.
    norm : boolean, optional
        If True, min value of colorbar is 0.

    Returns
    -------
    float
        Minimum value of the colorbar.
    float
        Maximum value of the colorbar.

    """
    if minmax == True and nstd == True:
        logger.error("minmax and nstd cannot be both equal to True")
        sys.exit(1)
    elif minmax == True:
        if difference == True:
            logger.info("Get cbar minmax: differeance")
            return -np.nanmax(np.abs(ds)), np.nanmax(np.abs(ds))
        elif norm == True:
            logger.info("Get cbar minmax: norm")
            return 0.0, np.nanmax(np.abs(ds))
        else:
            logger.info("Get cbar minmax: the true ones")
            return np.nanmin(ds), np.nanmax(ds)
    else:
        if nstd:
            if difference == True:
                logger.info("Get cbar nstd: difference")
                return -ds.std() * nstd, ds.std() * nstd
            elif norm == True:
                logger.info("Get cbar nstd: norm")
                percentile = ds.chunk(dict(time=-1)).quantile(0.98, dim="time")
                return 0.0, (percentile.mean() + percentile.std()).values
            else:
                logger.info("Get cbar nstd: the true ones")
                logger.info("Compute 0.98 quantile")
                percentile = ds.chunk(
                    dict(time=-1)
                ).quantile(0.98, dim="time", skipna=False)#.compute()
                logger.info("Compute quantile mean")
                mean = percentile.mean().compute()
                logger.info("Compute quantile std")
                std = percentile.std().compute()
                vmin = mean - std * nstd
                vmax = mean + std * nstd
                return vmin.values, vmax.values
        else:
            logger.error(
                "If minmax is False (that is the default value),"
                " nstd has to be a float not None, check your"
                " configuration file"
            )
            sys.exit(1)


def get_data2plot(func, var_m, model2plot_xr, param_cbar):
    """
    Retrieve data to plot and colorbar min and max.
    
    Parameters
    ----------
    obs_name: observation name
    file_names: file names to decumulate data
    func : visualisation function
    var_m : valiable to plot
    model2plot_xr : model data
    obs2plot_xr: observation date

    Returns
    -------
    cbar_range : min, max values for the color bar
    data2plot_all_times: all tata to be plot
    """
    print(param_cbar)
    cb = {}
    for k in ("minmax", "nstd", "difference", "norm"):
        v =  param_cbar.get(k)
        if v:
            cb.update({k: v})
    
    if func in ["visu_temp", "visu_sal"]:
        if var_m == "sst":
            var = "ptemp"
        elif var_m == "sss":
            var = "sal"
        else:
            var = var_m
        data2plot_all_times = model2plot_xr[var]
        cbar_range = get_cbar_minmax(data2plot_all_times, **cb)

    elif func in ["visu_precip", "visu_solarflux"]:
        logger.info("Decumulate data")
        data2plot_all_times = model2plot_xr.xoa[var_m]
        list_cut, cumul_time_in_h = get_cumul_info()

        result = decumulate_data(data2plot_all_times, list_cut)
        result = from_nh_to_1h(result, cumul_time_in_h)

        data2plot_all_times[:, :, :] = result[:, :, :]
        cbar_range = get_cbar_minmax(data2plot_all_times, **cb)

    elif func in ["visu_current", "visu_windforcing"]:
        if func == "visu_windforcing":
            model2plot_xr["u"] = model2plot_xr["u"] * 3600.0 / 1852.0
            model2plot_xr["v"] = model2plot_xr["v"] * 3600.0 / 1852.0
        model_da_u = model2plot_xr["u"]
        model_da_v = model2plot_xr["v"]
        model_norm = np.sqrt(model_da_u**2 + model_da_v**2)
        cbar_range = get_cbar_minmax(model_norm, **cb)
        data2plot_all_times = model2plot_xr

    elif func in ["visu_mixedlayer", "visu_mixedlayer_clim"]:
        logger.info("Computing mixed layer.")
        if "pdens" in var_m:
            var = "pdens"
        elif "ptemp" in var_m:
            var = "ptemp"
        data2plot_all_times = model2plot_xr.chunk(dict(z=-1)).sel_var.sel_mixed_layer_depth(var)[var_m]
        if func == "visu_mixedlayer":
            cbar_range = get_cbar_minmax(data2plot_all_times, **cb)
            global cbar_range_mld
            cbar_range_mld = cbar_range
        else:
            cbar_range = cbar_range_mld

    elif func in ["visu_runoff"]:
        data2plot_all_times = model2plot_xr
        cbar_range = None

    data2plot_all_times = data2plot_all_times.assign_attrs(
        **model2plot_xr.attrs
    )
    return cbar_range, data2plot_all_times
