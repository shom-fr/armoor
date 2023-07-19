"""Create figures for feature 5:clim_hydro"""
import os
import copy
from armoor import base
import calendar
import armoor.hmi.script_tools as st

import logging

logger = logging.getLogger(__name__)


def plot(config_obj):
    """
    Plot figures required in functionality 5 : clim_hydro.

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

    # SET THE FLAGS
    flag_interval = False
    flag_slice = False

    observation = copy.copy(config_obj["observation"])
    models = copy.copy(config_obj["models"])

    # Get names
    models_name = [m['name'] for m in models]
    obs_name = observation['name']

    for index_output, output in enumerate(outputs):
        if output_path:
            sub_func_output_folder = os.path.join(output_path, output["folder_name"])
            st.create_folder(sub_func_output_folder)
        else:
            sub_func_output_folder = output_path

        # Get the figure parameters from config obj
        vmin = output.get('vmin')
        vmax = output.get('vmax')
        dvmin = output.get('dvmin')
        dvmax = output.get('dvmax')
        cmap = output.get("colormap")

        # Select the variables
        config_obj = base.sel_default_vars(config_obj)
        observation = copy.copy(config_obj["observation"])
        models = copy.copy(config_obj["models"])

        # Remove missing values
        vars = [var for var in list(observation["xarray_meta"].keys()) if
                var in models[0]["xarray_meta"] or f"p{var}" in models[0]["xarray_meta"]]
        vars_mod = copy.copy(vars)
        if 'temp' in vars_mod:
            vars_mod[vars_mod.index('temp')] = 'ptemp'
        for i_mod, mod in enumerate(models):
            models, observation = base.remove_missing_values_ds(models, observation, i_mod, vars_mod, vars)

        # PLOTS
        for var in vars:
            observation_var, models_var = base.sel_one_var(observation, models, var)
            ############################################################################################################
            # TIME SERIES POINT
            plot_ts_metr_point = {"plot_ts_metr_ecart_point": 'difference_point'}
            if output["plot"] in plot_ts_metr_point:
                base.plot_features.plot_ts_metr_point(models_var, observation_var, plot_ts_metr_point[output["plot"]],
                                                      flag_interval, flag_slice, output_path=sub_func_output_folder)

            ############################################################################################################
            # TIME SERIES STATS
            plot_ts_metr_stats = {"plot_ts_metr_ecart_stats": 'difference_stats',
                                  "plot_ts_metr_bias_stats": 'bias_stats', "plot_ts_metr_RMSE_stats": 'RMSEc_stats',
                                  "plot_ts_metr_stats": 'all_metrics'
                                  }
            if output["plot"] in plot_ts_metr_stats:
                plg = config_obj["meta_zones"].get("polygon")
                base.plot_features.plot_ts_metr_stats(models_var, observation_var, flag_interval, flag_slice,
                                                      output_path=sub_func_output_folder, plg=plg)

            ############################################################################################################
            # MAP METRIC
            plot_map_metr = {"plot_map_metr_ecart": 'difference'}
            if output["plot"] in plot_map_metr:
                for i, mod in enumerate(models_var):
                    if 'depth' not in mod["xarray_meta_coloc"].dims:
                        base.plot_features.plot_map_metr(flag_interval, flag_slice, mod["xarray_meta"],
                                                         mod["xarray_meta_coloc"], observation_var["xarray_meta"],
                                                         observation_var["xarray_meta_coloc"][i],
                                                         plot_map_metr[output["plot"]], cmap, vmin, vmax,
                                                         output_path=sub_func_output_folder, dvmin=dvmin, dvmax=dvmax,
                                                         obs_name=obs_name, mod_name=models_name[i])
                    else:
                        for i_depth, depth in enumerate(models_var[0]["xarray_meta_coloc"].depth.values):
                            mod["xarray_meta"] = mod["xarray_meta"].meta.vertical_selection_ponct(depth)
                            mod["xarray_meta_coloc"] = mod["xarray_meta_coloc"].meta.vertical_selection_ponct(depth)
                            observation_var["xarray_meta"] = observation_var["xarray_meta"].meta.vertical_selection_ponct(depth)
                            observation_var["xarray_meta_coloc"][i] = observation_var["xarray_meta_coloc"][i].meta.vertical_selection_ponct(depth)

                            figname = f"depth{i_depth}"
                            base.plot_features.plot_map_metr(flag_interval, flag_slice, mod["xarray_meta"],
                                                             mod["xarray_meta_coloc"], observation_var["xarray_meta"],
                                                             observation_var["xarray_meta_coloc"][i],
                                                             plot_map_metr[output["plot"]], cmap, vmin, vmax,
                                                             output_path=sub_func_output_folder, dvmin=dvmin,
                                                             dvmax=dvmax, obs_name=obs_name, mod_name=models_name[i],
                                                             figname=figname)
