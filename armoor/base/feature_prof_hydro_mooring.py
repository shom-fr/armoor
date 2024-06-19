"""Create figures for feature 3:prof_hydro_mooring"""
import os
import copy
import logging
import numpy as np
from armoor.base.tools_features import remove_missing_values_ds, sel_one_var, sel_default_vars
from armoor.base import plot_features
from armoor.hmi.script_tools import create_folder

logger = logging.getLogger(__name__)


def plot(config_obj):
    """
    Plot figures required in functionality 3 : prof_hydro_mooring.

    Parameters
    ----------
    config_obj : dict
        Dictionary with observations and models names and DataSets.

    Returns
    -------
    str
        Path to the generated figures.

    """

    outputs = config_obj["outputs"]
    output_path = config_obj.get("output_path")

    list_config_job = []

    # set flag_interval
    flag_interval = 'interval' in config_obj["meta_zones"].keys()
    flag_slice = 'slice' in config_obj["meta_zones"].keys()

    for output in outputs:
        list_config_job.append(copy.copy(config_obj))
        if output_path:
            sub_func_output_folder = os.path.join(output_path, output["folder_name"])
            create_folder(sub_func_output_folder)
        else:
            sub_func_output_folder = output_path

        # Select the variables
        config_obj = sel_default_vars(config_obj)
        observation = copy.copy(config_obj["observation"])
        models = copy.copy(config_obj["models"])

        # Depth selection
        if "depth" in config_obj["meta_zones"] and "depth" in observation["xarray_meta"].dims:
            depth = config_obj["meta_zones"]["depth"]
            depth_diff = np.abs(observation["xarray_meta"]["depth"] - float(depth[0]))
            nearest_depth_index = np.nanargmin(depth_diff.data)
            observation["xarray_meta"] = observation["xarray_meta"].isel(depth=nearest_depth_index)
            for i_mod, mod in enumerate(models):
                depth_diff = np.abs(observation["xarray_meta_coloc"][i_mod]["depth"] - float(depth[0]))
                nearest_depth_index = np.nanargmin(depth_diff.data)
                observation["xarray_meta_coloc"][i_mod] = observation["xarray_meta_coloc"][i_mod].sel(
                    depth=nearest_depth_index)

        # Removing of the lon-lat dimensions in the model data
        if "lat" not in observation["xarray_meta"].dims and "lat" in models[0]["xarray_meta_coloc"].dims:
            for i_mod, mod in enumerate(models):
                models[i_mod]["xarray_meta_coloc"] = models[i_mod]["xarray_meta_coloc"].isel(lon=0, lat=0)

        vars = [var for var in list(observation["xarray_meta_coloc"][0].keys()) if var in models[0]["xarray_meta_coloc"]]

        # PLOTS
        for var in vars:
            observation_var, models_var = sel_one_var(observation, models, var)
            ########################################################################################
            # TIME SERIES STATS
            plot_ts_metr_stats = {"plot_ts_metr_ecart_stats": 'difference_stats',
                                  "plot_ts_metr_bias_stats": 'bias_stats',
                                  "plot_ts_metr_RMSE_stats": 'RMSEc_stats',
                                  "plot_ts_metr_stats": 'all_metrics'
                                  }
            if output["plot"] in plot_ts_metr_stats:
                plg = config_obj["meta_zones"].get("polygon")
                if 'depth' not in models[0]["xarray_meta_coloc"].dims or len(
                        models[0]["xarray_meta_coloc"].depth) == 1:
                    models_depth, observation_depth = models_var, observation_var
                    plot_features.plot_ts_metr_stats(models_depth, observation_depth, flag_interval,
                                                     flag_slice, output_path=sub_func_output_folder,
                                                     plg=plg)
                else:
                    if config_obj['colocate'] == observation:
                        for i_depth, depth in enumerate(observation["xarray_meta_coloc"][0].depth.values):
                            if depth > 0:
                                models_depth, observation_depth = select_depth(models_var, observation_var,
                                                                               depth)
                                plot_features.plot_ts_metr_stats(models_depth, observation_depth,
                                                                 flag_interval, flag_slice,
                                                                 output_path=sub_func_output_folder,
                                                                 plg=plg)
                        else:
                            for i_depth, depth in enumerate(models[0]["xarray_meta_coloc"].depth.values):
                                if depth > 0:
                                    models_depth, observation_depth = select_depth(models_var, observation_var,
                                                                                   depth)
                                    plot_features.plot_ts_metr_stats(models_depth, observation_depth,
                                                                     flag_interval, flag_slice,
                                                                     output_path=sub_func_output_folder,
                                                                     plg=plg)
############################################################################################
            # PONCTUAL TIMES SERIES
            plot_ts_metr_f3 = {"plot_ts_metr_f3": 'all_metrics'}
            if output["plot"] in plot_ts_metr_f3:
                plg = config_obj["meta_zones"].get("polygon")
                if 'depth' not in models[0]["xarray_meta_coloc"].dims or len(
                        models[0]["xarray_meta_coloc"].depth) == 1:
                    models_depth, observation_depth = models_var, observation_var
                    plot_features.plot_ts_metr_f3(models_depth, observation_depth, flag_interval, flag_slice,
                                                     output_path=sub_func_output_folder,
                                                         plg=plg)
                else:
                    if config_obj['colocate'] == 'observation':
                        for i_depth, depth in enumerate(observation["xarray_meta_coloc"][0].depth.values):
                            if depth > 0:
                                models_depth, observation_depth = select_depth(models_var, observation_var,
                                                                               depth)
                                plot_features.plot_ts_metr_f3(models_depth, observation_depth, flag_interval, flag_slice,
                                                             output_path=sub_func_output_folder,
                                                                 plg=plg)
                    else:
                        for i_depth, depth in enumerate(models[0]["xarray_meta_coloc"].depth.values):
                            if depth > 0:
                                models_depth, observation_depth = select_depth(models_var, observation_var,
                                                                               depth)
                                plot_features.plot_ts_metr_f3(models_depth, observation_depth, flag_interval, flag_slice,
                                                              output_path=sub_func_output_folder,
                                                              plg=plg)

def select_depth(models, observation, depth):
    """
    Select the required depth in model and observation
    Parameters
    ----------
    models : list of xarray.Dataset
    observation : dict of xarray.Dataset
    depth : float

    Returns
    -------
    models_depth : list of xarray.Dataset
    observation_depth : dict of xarray.Dataset
    """
    observation_depth = {}
    observation_depth["xarray_meta"] = observation["xarray_meta"].sel(depth=depth, method='nearest')
    observation_depth['name'] = observation['name']
    models_depth = []
    for i_mod, mod in enumerate(models):
        models_depth.append({})
        observation_depth["xarray_meta_coloc"] = []
        models_depth[i_mod]["xarray_meta"] = mod["xarray_meta"].sel(depth=depth, method='nearest')
        models_depth[i_mod]['name'] = mod['name']
        models_depth[i_mod]["xarray_meta_coloc"] = mod["xarray_meta_coloc"].sel(depth=depth, method='nearest')
        observation_depth["xarray_meta_coloc"].append(
            observation["xarray_meta_coloc"][i_mod].sel(depth=depth, method='nearest'))

    return models_depth, observation_depth
