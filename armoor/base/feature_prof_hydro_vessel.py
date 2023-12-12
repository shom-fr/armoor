"""Create figures for feature 2:prof_hydro_vessel"""
import os
import copy
import logging
from armoor.base.tools_features import remove_missing_values_ds, sel_one_var, sel_default_vars
from armoor.base import plot_features
import armoor.hmi.script_tools as st

logger = logging.getLogger(__name__)


def plot(config_obj):
    """
    Plot figures required in functionality 2 : prof_hydro_vessel.

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

    # Set the flags
    flag_interval = 'interval' in config_obj["meta_zones"]
    flag_slice = 'slice' in config_obj["meta_zones"]

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

    # PLOT THE OUTPUTS
    for output in outputs:
        if output_path:
            sub_func_output_folder = os.path.join(output_path, output["folder_name"])
            st.create_folder(sub_func_output_folder)
        else:
            sub_func_output_folder = output_path
        # get parameters from config obj
        vmin = output.get('vmin')
        vmax = output.get('vmax')
        dvmin = output.get('dvmin')
        dvmax = output.get('dvmax')
        cmap = output.get("colormap")
        cmap = cmap if cmap is None else f'cmo.{cmap}'

        # PLOTS

        if 'diag_ts' in output["plot"]:  # Plots with several variables (temp sal here)
            ########################################################################################
            # DIAG TS PROFIL UNIQUE
            plot_profile_u = {"diag_ts_unique": 'diag_ts_unique'}
            if output["plot"] in plot_profile_u:
                plot_features.plot_diag_ts_unique(models, observation["xarray_meta"],
                                                  output_path=sub_func_output_folder)

            ########################################################################################
            # DIAG_TS_MULTI
            diag_ts_multi = {"diag_ts_multi": 'diag_ts_multi'}

            if output["plot"] in diag_ts_multi:
                if "radius" not in config_obj["meta_zones"]:
                    logger.warning("Caution ! To plot Theta-S diagrams you need to specify "
                                   "a radius in the meta-zone")
                else:
                    plot_features.plot_diag_ts_multi(models, observation["xarray_meta"],
                                                     config_obj["meta_zones"]["radius"],
                                                     output_path=sub_func_output_folder)

        else:
            for var in vars_obs:
                observation_var, models_var = sel_one_var(observation, models, var)
                ####################################################################################
                # TIME SERIES STATS
                plot_ts_metr_stats = {"plot_ts_metr_stats": 'all_metrics'
                                      }
                if output["plot"] in plot_ts_metr_stats:
                    plg = config_obj["meta_zones"].get("polygon")
                    plot_features.plot_ts_metr_stats(models_var, observation_var, flag_interval,
                                                     flag_slice, output_path=sub_func_output_folder,
                                                     plg=plg)

                ####################################################################################
                # MAP METRIC
                plot_map_metr = {"plot_map_metr_ecart": 'difference', "plot_map_metr_biais": 'bias',
                                 "plot_map_metr_RMSE": 'RMSE', "plot_map_metr_RMSEc": 'RMSEc'
                                 }

                if output["plot"] in plot_map_metr:
                    for i, mod in enumerate(models_var):
                        plot_features.plot_map_metr_profiles(flag_interval, flag_slice,
                                                             mod["xarray_meta_coloc"],
                                                             observation_var["xarray_meta_coloc"][
                                                                 i], plot_map_metr[output["plot"]],
                                                             cmap, vmin, vmax,
                                                             output_path=sub_func_output_folder,
                                                             dvmin=dvmin, dvmax=dvmax)

                ####################################################################################
                # DISP DIAG
                diag_disp = {"diag_disp": 'diag_disp', "diag_disp_g": 'diag_disp_g'}
                if output["plot"] in diag_disp:
                    for i, mod in enumerate(models_var):
                        plot_features.diag_disp(flag_interval, flag_slice, output["plot"],
                                                mod["xarray_meta_coloc"],
                                                observation_var["xarray_meta_coloc"][i],
                                                output_path=sub_func_output_folder)

                ####################################################################################
                # COURBE PROFIL UNIQUE
                plot_profile_u = {"plot_profile_u": 'profile_u'}
                if output["plot"] in plot_profile_u:
                    if 'instr' in observation_var["xarray_meta"].dims:
                        for i_instr, _ in enumerate(observation_var["xarray_meta"].instr):
                            obs_instr = observation_var["xarray_meta"].isel(instr=i_instr)
                            plot_features.plot_profile_unique(models_var, obs_instr,
                                                              config_obj["meta_zones"]["radius"],
                                                              output_path=sub_func_output_folder)
                    else:
                        plot_features.plot_profile_unique(models_var,
                                                          observation_var["xarray_meta"],
                                                          config_obj["meta_zones"]["radius"],
                                                          output_path=sub_func_output_folder)

                ####################################################################################
                # COURBE MULTI PROFILS
                plot_profile_multi = {"plot_profile_multi": 'profile_multi'}
                if output["plot"] in plot_profile_multi:
                    plot_features.plot_profile_multi(models_var, observation_var["xarray_meta"],
                                                     config_obj["meta_zones"]["radius"],
                                                     output_path=sub_func_output_folder)
