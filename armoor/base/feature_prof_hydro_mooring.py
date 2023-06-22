"""Create figures for feature 3:prof_hydro_mooring"""
import os
import copy
from armoor import base
import armoor.hmi.script_tools as st

import logging

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

    for output in outputs:
        if output_path:
            sub_func_output_folder = os.path.join(output_path, output["folder_name"])
            st.create_folder(sub_func_output_folder)
        else:
            sub_func_output_folder = output_path

        # get parameters from config obj
        observation = copy.copy(config_obj["observation"])
        models = copy.copy(config_obj["models"])

        # Select the variables
        config_obj = base.sel_default_vars(config_obj)
        observation = copy.copy(config_obj["observation"])
        models = copy.copy(config_obj["models"])

        # Remove missing values
        var = list(observation['xarray_meta'].keys())
        var_mod = copy.copy(var)
        if 'temp' in var_mod:
            var_mod[var_mod.index('temp')] = 'ptemp'
        for i_mod, mod in enumerate(models):
            models, observation = base.remove_missing_values_ds(models, observation, i_mod, var_mod, var)

        # PLOTS
        list_vars = [var for var in list(observation["xarray_meta"].keys()) if var in models[0]["xarray_meta"]]
        for var in list_vars:
            observation_var, models_var = base.sel_one_var(observation, models, var)
            ############################################################################################################
            # TIME SERIES STATS
            plot_ts_metr_stats = {"plot_ts_metr_ecart_stats": 'difference_stats',
                                  "plot_ts_metr_bias_stats": 'bias_stats', "plot_ts_metr_RMSE_stats": 'RMSEc_stats',
                                  "plot_ts_metr_stats": 'all_metrics'
                                  }
            if output["plot"] in plot_ts_metr_stats:
                plg = config_obj["meta_zones"].get("polygon")
                if 'depth' not in models[0]["xarray_meta_coloc"].dims:
                    models_depth, observation_depth = models_var, observation_var
                    base.plot_features.plot_ts_metr_stats(models_depth, observation_depth, flag_interval, flag_slice,
                                                          output_path=sub_func_output_folder, plg=plg)
                else:
                    for i_depth, depth in enumerate(models[0]["xarray_meta_coloc"].depth.values):
                        figname = f"_depth{i_depth}"
                        models_depth, observation_depth = select_depth(models_var, observation_var, depth)
                        base.plot_features.plot_ts_metr_stats(models_depth, observation_depth, flag_interval,
                                                              flag_slice, output_path=sub_func_output_folder,
                                                              figname=figname, plg=plg)


def select_depth(models, observation, depth):
    observation_depth = dict()
    observation_depth["xarray_meta"] = observation["xarray_meta"].sel(depth=depth, method='nearest')
    observation_depth['name'] = observation['name']
    models_depth = []
    for i_mod, mod in enumerate(models):
        models_depth.append(dict())
        observation_depth["xarray_meta_coloc"] = []
        models_depth[i_mod]["xarray_meta"] = mod["xarray_meta"].sel(depth=depth, method='nearest')
        models_depth[i_mod]['name'] = mod['name']
        models_depth[i_mod]["xarray_meta_coloc"] = mod["xarray_meta_coloc"].sel(depth=depth)
        observation_depth["xarray_meta_coloc"].append(
            observation["xarray_meta_coloc"][i_mod].sel(depth=depth, method='nearest'))

    return models_depth, observation_depth
