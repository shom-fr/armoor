"""Create figures for feature 5:clim_hydro"""
import os
import copy
import logging
from armoor.base.tools_features import remove_missing_values_ds, sel_one_var, sel_default_vars
from armoor.base import plot_features
import armoor.hmi.script_tools as st

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

    for output in outputs:
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
        config_obj = sel_default_vars(config_obj)
        observation = copy.copy(config_obj["observation"])
        models = copy.copy(config_obj["models"])

        # Remove missing values
        vars_obs = [var for var in list(observation["xarray_meta"].keys()) if
                    var in models[0]["xarray_meta"] or f"p{var}" in models[0]["xarray_meta"]]
        vars_mod = copy.copy(vars_obs)
        for i_mod, mod in enumerate(models):
            models, observation = remove_missing_values_ds(models, observation, i_mod, vars_mod,
                                                           vars_obs)

        # PLOTS
        for var in vars_obs:

            ########################################################################################
            # TIME SERIES POINT
            plot_ts_metr_point = {"plot_ts_metr_ecart_point": 'difference_point'}
            if output["plot"] in plot_ts_metr_point:
                if 'depth' in models[0]["xarray_meta_coloc"].squeeze().dims:
                    for _, depth in enumerate(models[0]["xarray_meta_coloc"].depth.values):
                        observation_var, models_var = sel_one_var(observation, models, var,
                                                                  depth=depth)
                        plot_features.plot_ts_metr_point(models_var, observation_var, flag_interval,
                                                         flag_slice,
                                                         output_path=sub_func_output_folder)
                else:
                    observation_var, models_var = sel_one_var(observation, models, var)
                    plot_features.plot_ts_metr_point(models_var, observation_var, flag_interval,
                                                     flag_slice, output_path=sub_func_output_folder)

            ########################################################################################
            # TIME SERIES STATS
            plot_ts_metr_stats = {"plot_ts_metr_ecart_stats": 'difference_stats',
                                  "plot_ts_metr_bias_stats": 'bias_stats',
                                  "plot_ts_metr_RMSE_stats": 'RMSEc_stats',
                                  "plot_ts_metr_stats": 'all_metrics'
                                  }
            if output["plot"] in plot_ts_metr_stats:
                plg = config_obj["meta_zones"].get("polygon")
                if 'depth' in models[0]["xarray_meta_coloc"].squeeze().dims:
                    for _, depth in enumerate(models[0]["xarray_meta_coloc"].depth.values):
                        observation_var, models_var = sel_one_var(observation, models, var,
                                                                  depth=depth)
                        plot_features.plot_ts_metr_stats(models_var, observation_var, flag_interval,
                                                         flag_slice,
                                                         output_path=sub_func_output_folder,
                                                         plg=plg)
                else:
                    observation_var, models_var = sel_one_var(observation, models, var)
                    plot_features.plot_ts_metr_stats(models_var, observation_var, flag_interval,
                                                     flag_slice, output_path=sub_func_output_folder,
                                                     plg=plg)

            ########################################################################################
            # MAP METRIC
            plot_map_metr = {"plot_map_metr_ecart": 'difference'}
            if output["plot"] in plot_map_metr:

                observation_var, models_var = sel_one_var(observation, models, var)

                for i, mod in enumerate(models_var):
                    if 'depth' not in mod["xarray_meta_coloc"].dims and 'pdens' not in mod[
                        "xarray_meta_coloc"].dims:
                        plot_features.plot_map_metr(flag_interval, flag_slice, mod["xarray_meta"],
                                                    mod["xarray_meta_coloc"],
                                                    observation_var["xarray_meta"],
                                                    observation_var["xarray_meta_coloc"][i],
                                                    plot_map_metr[output["plot"]], cmap, vmin, vmax,
                                                    output_path=sub_func_output_folder, dvmin=dvmin,
                                                    dvmax=dvmax)
                    elif 'depth' in mod["xarray_meta_coloc"].dims:
                        for i_depth, depth in enumerate(
                                models_var[0]["xarray_meta_coloc"].depth.values):
                            # Decoupage par immersions obligatoire
                            mod_meta = mod["xarray_meta"].isel(depth=i_depth)
                            mod_coloc = mod["xarray_meta_coloc"].isel(depth=i_depth)
                            obs_meta = observation_var["xarray_meta"].isel(depth=i_depth)
                            obs_coloc = observation_var["xarray_meta_coloc"][i].isel(depth=i_depth)

                            plot_features.plot_map_metr(flag_interval, flag_slice, mod_meta,
                                                        mod_coloc, obs_meta, obs_coloc,
                                                        plot_map_metr[output["plot"]], cmap, vmin,
                                                        vmax, output_path=sub_func_output_folder,
                                                        dvmin=dvmin, dvmax=dvmax)
                    elif 'pdens' in mod["xarray_meta_coloc"].dims:
                        for i_pdens, pdens in enumerate(
                                models_var[0]["xarray_meta_coloc"].pdens.values):
                            # Decoupage par immersions obligatoire
                            mod_meta = mod["xarray_meta"].isel(pdens=i_pdens)
                            mod_coloc = mod["xarray_meta_coloc"].isel(pdens=i_pdens)
                            obs_meta = observation_var["xarray_meta"].isel(pdens=i_pdens)
                            obs_coloc = observation_var["xarray_meta_coloc"][i].isel(pdens=i_pdens)

                            plot_features.plot_map_metr(flag_interval, flag_slice, mod_meta,
                                                        mod_coloc, obs_meta, obs_coloc,
                                                        plot_map_metr[output["plot"]], cmap, vmin,
                                                        vmax, output_path=sub_func_output_folder,
                                                        dvmin=dvmin, dvmax=dvmax)