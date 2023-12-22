"""
Function to create images for forecaster wed interface
"""
import os
import shutil
import sys
import tarfile

from xoa import cfgm

import gc
from multiprocessing import Pool
import multiprocessing
import json
from datetime import datetime, timezone
import time

import numpy as np
import xarray as xr
import dask.array as da

from xoa.thermdyn import mixed_layer_depth

from armoor.hmi.configuration import get_forcing_model, get_model, get_obs
from armoor.hmi.configuration import get_time_spacial_extent, apply_custom_metazone
from armoor.hmi.script_tools import format_times, create_folder, convert_k_c
from armoor.hmi.script_tools import decumulate_data, from_nh_to_1h, get_cumul_info
from armoor.hmi.script_plot import hmi_image
from armoor.base.colocation import colocate_all

import logging

logger = logging.getLogger(__name__)


def create_images(config_obj: dict,
                  input_folder_path: str,
                  output_folder_path: str,
                  legend_configuration: str):
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

    model_name = config_obj['config_reg']['model']
    config_name = config_obj['config_reg']['config']

    config_reg = f"{model_name}_{config_name}"

    parameters = config_obj["parameters"]

    production_day = datetime.now(timezone.utc).strftime("%Y%m%d")
    logger.info(f'Production day : {production_day}')

    config_reg_t0, config_reg_times, config_reg_extent = get_time_spacial_extent(input_folder_path,
                                                                                 config_reg,
                                                                                 production_day)

    model_json = {'parameters': [],
                  'times': format_times(config_reg_times),
                  't0': config_reg_t0.replace(':', 'h'),
                  'production_day': production_day,
                  'config_reg': config_reg,
                  'model': model_name,
                  'config': config_name,
                  'approval': {
                      'status': "not_processed",
                      'last_update': "",
                      'reporter': ""}
                  }
    # CREATING ALL PARAMETERS OF THE REGIONAL CONFIGURATION
    gc.collect()
    for parameter in parameters:
        model_json['parameters'].append(parameter)
        logger.info(f'{config_obj["parameters"][parameter]}')

        for sub_param in ['param_1', 'param_2', 'param_3', 'param_4']:
            start_time = time.time()
            logger.info(f'{config_reg} - {parameter} - {sub_param}')
            try:
                create_param_images(config_reg,
                                    production_day,
                                    config_reg_times,
                                    config_reg_extent,
                                    config_obj,
                                    parameter,
                                    sub_param,
                                    input_folder_path,
                                    os.path.join(output_folder_path, f'{config_reg}_{production_day}'),
                                    legend_configuration)
            except FileNotFoundError:
                # Handle the error when files are not found
                logger.error("Error: Files not found.")
            except Exception as e:
                # Handle other possible exceptions
                logger.error("Error: An exception occurred :")
                logger.error(f"{str(e)}")
                sys.exit()

            logger.info(f'{config_reg} - {parameter} - {sub_param}  '
                        f'in {time.time() - start_time} seconds')

    # WRITING PRODUCTION INFO INTO JSON FILE
    create_data_json_file(model_json,
                          output_folder_path,
                          config_reg,
                          production_day)

    # COMPRESSING to TGZ and delete source directory
    make_tarfile(output_folder_path,
                 config_reg,
                 production_day)

    logger.info(f'PRODUCTION DAY {production_day} : OK')


def create_data_json_file(model_json: dict,
                          output_folder_path: str,
                          config_reg: str,
                          production_day: str):
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
    json_data_path = os.path.join(output_folder_path, f'{config_reg}_{production_day}', 'data.json')
    logger.info(f'Writing production information into :')
    logger.info(f'{json_data_path}')
    with open(json_data_path, 'w', encoding='utf-8') as json_file:
        json.dump(model_json, json_file, indent=4, ensure_ascii=False)
    os.chmod(json_data_path, 0o666)


def make_tarfile(output_folder_path: str,
                 config_reg: str,
                 production_day: str):
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

    source_dir = os.path.join(output_folder_path, f'{config_reg}_{production_day}')
    output_filename = os.path.join(output_folder_path, f'{config_reg}_{production_day}.tgz')

    # COMPRESSING to TGZ
    logger.info(f'COMPRESSING {source_dir} INTO {output_filename}')
    with tarfile.open(output_filename, "w:gz") as tar:
        tar.add(source_dir, arcname=os.path.basename(source_dir))

    # DELETING TEMPORARY FOLDER
    logger.info('Deleting temporary folder')
    logger.info(f'{source_dir}')
    shutil.rmtree(source_dir)


def create_param_images(config_reg: str,
                        production_day: str,
                        config_reg_times: str,
                        config_reg_extent: list,
                        config_obj: dict,
                        parameter_mane: str,
                        sub_param: str,
                        input_folder_path: str,
                        output_folder_path: str,
                        legend_configuration: str):
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

    param = config_obj["parameters"][parameter_mane][sub_param]
    extent = config_obj["parameters"][parameter_mane].get("extent")

    # Model or forcing model used to generate the images for a given parameter
    model2plot_xr, paths = get_model_xr(param,
                                        extent,
                                        input_folder_path,
                                        config_reg,
                                        config_reg_extent,
                                        production_day)
    # Observation used to generate the images for a given parameter
    obs2plot_xr = get_obs_xr(param,
                             extent,
                             input_folder_path,
                             config_reg,
                             config_reg_extent,
                             production_day)
    func = param["func"]
    cbar_range, data2plot_all_times = get_data2plot(func,
                                                    param["var"],
                                                    model2plot_xr,
                                                    obs2plot_xr,
                                                    paths,
                                                    param.get("obs"))
    logger.info(f'Creating images for all steps : {len(config_reg_times)}')
    # Loop on times to create all images
    param_title = param["name"]
    data = []
    multiprocess = param.get("multiprocess")
    stream_legend = (param.get("rarification"),
                     param.get("barbs_length"),
                     param.get("barbs_linewidth"),
                     param.get("quiver_scale"),
                     param.get("quiver_width"),
                     param.get("quiver_headwidth"),
                     param.get("quiver_headlength"))

    for reg_time in config_reg_times:
        path2save = get_path2save(reg_time, parameter_mane, output_folder_path, sub_param)

        if func in ["visu_temp",
                    "visu_sal",
                    "visu_mixedlayer",
                    "visu_solarflux",
                    'visu_precip',
                    "visu_current",
                    "visu_windforcing",
                    "visu_diff_sss",
                    "visu_diff_sst"]:
            data2plot = data2plot_all_times.sel(time=reg_time, method="nearest")
            data2plot = data2plot

        elif func in ['visu_mixedlayer_clim']:
            data2plot = data2plot_all_times

        elif func in ['visu_runoff']:
            data2plot = data2plot_all_times
            cbar_range = reg_time
        else:
            logger.error(f'{func} is not yet implemented for {param_title}')
            break

        if multiprocess:
            data.append([data2plot,
                         func,
                         param_title,
                         path2save,
                         cbar_range,
                         legend_configuration,
                         stream_legend])

        else:
            hmi_image(data2plot,
                      func,
                      param_title,
                      path2save,
                      cbar_range,
                      legend_configuration,
                      stream_legend=stream_legend)

    if multiprocess:
        logger.info(f'Multiprocess')
        nb_cpu = multiprocessing.cpu_count()
        nb_taks = len(data)
        logger.info(f'Tasks {nb_taks} for {nb_cpu} CPUs')
        pool = Pool(nb_cpu)
        pool.map(work_process, data)
        pool.close()
        pool.join()
    del data
    gc.collect()


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
    hmi_image(data2plot,
              func,
              param_title,
              path2save,
              cbar_range,
              legend_configuration,
              stream_legend=stream_legend)


def get_obs_xr(param: dict,
               extent: list,
               input_folder_path: str,
               config_reg: str,
               config_reg_extent: list,
               production_day: str) -> xr.Dataset:
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
        logger.info(f'Reading : {obs_name}')
        obs2plot_xr = get_obs(input_folder_path,
                              config_reg,
                              production_day,
                              obs_name,
                              var_m)
        if obs_name == 'woa18':
            depth = 0
        obs2plot_xr = apply_custom_metazone(obs2plot_xr,
                                            depth,
                                            extent,
                                            var_m,
                                            config_reg_extent)
        return obs2plot_xr
    return None


def get_model_xr(param: dict,
                 extent: list,
                 input_folder_path: str,
                 config_reg: str,
                 config_reg_extent: list,
                 production_day: str) -> xr.Dataset:
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

    depth = param.get("depth")
    var_m = param["var"]
    forcing_model_name = param.get("forcing_model")
    paths = None
    if forcing_model_name:
        logger.info(f'Reading : {forcing_model_name}')
        model2plot_xr, paths = get_forcing_model(input_folder_path,
                                                 config_reg,
                                                 production_day,
                                                 forcing_model_name,
                                                 var_m)
        if forcing_model_name not in ['rivers']:
            model2plot_xr = apply_custom_metazone(model2plot_xr,
                                                  depth,
                                                  extent,
                                                  var_m,
                                                  config_reg_extent)
    else:
        logger.info('Reading model (regional configuration)')
        model_xr = get_model(input_folder_path,
                             config_reg,
                             production_day,
                             var_m)
        model2plot_xr = apply_custom_metazone(model_xr,
                                              depth,
                                              extent,
                                              var_m)
    return model2plot_xr, paths


def get_path2save(reg_time: str,
                  parameter_mane: str,
                  output_folder_path: str,
                  sub_param: str):
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
    reg_time = reg_time.replace(':', 'h')
    path = os.path.join(output_folder_path, reg_time, parameter_mane)
    create_folder(path)
    path2save = os.path.join(path, sub_param)
    return path2save


def get_data2plot(func, var_m, model2plot_xr, obs2plot_xr, file_names, obs_name):
    """
    Retrieve data to plot and colorbar min and max
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
    if func in ["visu_temp", "visu_sal"]:
        data2plot_all_times = model2plot_xr.xoa[var_m]
        cbar_range = np.nanmin(data2plot_all_times), np.nanmax(data2plot_all_times)

    elif func in ["visu_precip", 'visu_solarflux']:
        logger.info('Decumulate data')
        data2plot_all_times = model2plot_xr.xoa[var_m]
        list_cut, cumul_time_in_h = get_cumul_info(file_names)

        result = decumulate_data(data2plot_all_times, list_cut)
        result = from_nh_to_1h(result, cumul_time_in_h)

        data2plot_all_times[:, :, :] = result[:, :, :]
        cbar_range = np.nanmin(data2plot_all_times), np.nanmax(data2plot_all_times)

    elif func in ["visu_current", "visu_windforcing"]:
        model_da_u = model2plot_xr['u']
        model_da_v = model2plot_xr['v']
        model_norm = np.sqrt(model_da_u ** 2 + model_da_v ** 2)
        cbar_range = np.nanmin(model_norm), np.nanmax(model_norm)
        data2plot_all_times = model2plot_xr

    elif func in ["visu_mixedlayer", 'visu_mixedlayer_clim']:
        logger.info('Computing mixed layer.')
        data2plot_all_times = mixed_layer_depth(model2plot_xr.xoa[var_m].squeeze())
        cbar_range = np.nanmin(data2plot_all_times), np.nanmax(data2plot_all_times)

    elif func in ["visu_runoff"]:
        data2plot_all_times = model2plot_xr
        cbar_range = None

    elif func in ["visu_diff_sss", "visu_diff_sst"]:
        logger.info('Collocating and computing difference.')
        model_da = model2plot_xr.xoa[var_m]

        obs_da = obs2plot_xr[var_m]
        obs_da = convert_k_c(obs_da)

        if 'woa' in obs_name:
            logger.info('woa')
            flags = False, True, False
        else:
            logger.info('sst')
            flags = True, True, False

        da_obs_coloc, da_model_coloc = colocate_all(obs_da, model_da, flags, "model")
        difference = da_model_coloc - da_obs_coloc.squeeze()

        cbar_range = np.nanmin(difference), np.nanmax(difference)
        data2plot_all_times = difference

    logger.info('Retrieving colorbar for all times...')
    if not isinstance(data2plot_all_times, list) and isinstance(data2plot_all_times, xr.DataArray) and isinstance(data2plot_all_times.data, da.core.Array):
        logger.info('data2plot_all_times.compute()')
        data2plot_all_times = data2plot_all_times.compute()

    return cbar_range, data2plot_all_times
