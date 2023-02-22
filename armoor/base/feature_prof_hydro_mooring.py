"""Create figures for feature 3:prof_hydro_mooring"""
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
            sub_func_output_folder = f'{output_path}{output["folder_name"]}/'
            st.create_folder(sub_func_output_folder)
        else:
            sub_func_output_folder = output_path

        # get parameters from config obj
        if 'vmin' in output:
            vmin = output["vmin"]
        else:
            vmin = None

        if 'vmax' in output:
            vmax = output["vmax"]
        else:
            vmax = None

        if 'colormap' in output:
            cmap = 'cmo.' + output["colormap"]
        else:
            cmap = None
        observation = copy.copy(config_obj["observation"])
        models = copy.copy(config_obj["models"])

        # SELECT VAR
        if 'attribute' in output:
            var = output['attribute']
        else:
            logger.info("You should indicate which variable you want to plot with keyword : attribute = ")
            var = None
        observation["xarray_meta"] = observation["xarray_meta"].read_sst.sel(var)
        for i_mod, mod in enumerate(models):
            mod["xarray_meta"] = mod["xarray_meta"].read_sst.sel(var)
            mod["xarray_meta_coloc"] = mod["xarray_meta_coloc"].read.decode().read_sst.sel(var)
            observation["xarray_meta_coloc"][i_mod] = observation["xarray_meta_coloc"][i_mod].read_sst.sel(var)

            # Remove missing values
            models, observation = base.remove_missing_values_ds(models, observation, i_mod, var, var)

        # PLOTS

        ################################################################################################################
        # TIME SERIES STATS
        plot_ts_metr_stats = {"plot_ts_metr_ecart_stats": 'difference_stats',
                              "plot_ts_metr_bias_stats": 'bias_stats',
                              "plot_ts_metr_RMSE_stats": 'RMSEc_stats',
                              "plot_ts_metr_stats": 'all_metrics'}
        if output["plot"] in plot_ts_metr_stats:
            if 'depth' not in models[0]["xarray_meta_coloc"].dims:
                models_depth, observation_depth = models, observation
                base.plot_features.plot_ts_metr_stats(models_depth,
                                                      observation_depth,
                                                      flag_interval,
                                                      flag_slice,
                                                      output_path=sub_func_output_folder)
            else:
                for i_depth, depth in enumerate(models[0]["xarray_meta_coloc"].depth.values):
                    models_depth, observation_depth = select_depth(models, observation, depth)
                    base.plot_features.plot_ts_metr_stats(models_depth,
                                                          observation_depth,
                                                          flag_interval,
                                                          flag_slice,
                                                          output_path=sub_func_output_folder)


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
        observation_depth["xarray_meta_coloc"].append(observation["xarray_meta_coloc"][i_mod].sel(depth=depth,
                                                                                                  method='nearest'))

    return models_depth, observation_depth
