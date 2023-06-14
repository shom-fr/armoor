"""Create figures for feature 2:prof_hydro_vessel"""
import os
import copy
from armoor import base
import armoor.base.feature_tools as ft
import armoor.hmi.script_tools as st

import logging

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

    # SET THE FLAGS
    flag_interval = 'interval' in config_obj["meta_zones"]
    flag_slice = 'slice' in config_obj["meta_zones"]

    # SELECT THE VARIABLES
    observation = copy.copy(config_obj["observation"])
    models = copy.copy(config_obj["models"])
    if 'attribute' in outputs[0]:
        var0 = outputs[0]['attribute']
    else:
        raise Exception("Oops, pour utiliser cette fonctionnalité, vous devriez spécifier un attribut...")
    if "list" not in str(type(var0)):
        vars = [var0]
    else:
        vars = var0

    observation["xarray_meta"] = observation["xarray_meta"].read_sst.sel(vars)

    # For the models, we select the potential values
    var_mod = []
    for i_var, var in enumerate(vars):
        if var == 'temp':
            var_mod.append('ptemp')
            logger.info("For this feature, the potential temperature is used in the model")
        elif var == 'dens':
            var_mod.append('pdens')
            logger.info("For this feature, the potential density is used in the model")
        else:
            var_mod.append(var)
    for i_mod, mod in enumerate(models):
        mod["xarray_meta"] = mod["xarray_meta"].read_sst.sel(var_mod)
        mod["xarray_meta_coloc"] = mod["xarray_meta_coloc"].read_sst.sel(var_mod)
        observation["xarray_meta_coloc"][i_mod] = observation["xarray_meta_coloc"][i_mod].read_sst.sel(vars)


        # Remove missing values
        models, observation = base.remove_missing_values_ds(models, observation, i_mod, var_mod, vars)

    # Get names
    models_name = [m['name'] for m in models]
    obs_name = observation['name']

    # PLOT THE OUTPUTS
    for index_output, output in enumerate(outputs):
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

        ################################################################################################################
        # TIME SERIES POINT
        plot_ts_metr_point = {"plot_ts_metr_ecart_point": 'difference_point', "plot_ts_metr_bias_point": 'bias_point',
                              "plot_ts_metr_RMSE_point": 'RMSEc_point', "plot_ts_metr_point": 'all_metrics'
                              }
        if output["plot"] in plot_ts_metr_point:
            base.plot_features.plot_ts_metr_point(models, observation, plot_ts_metr_point[output["plot"]],
                                                  flag_interval, flag_slice, output_path=sub_func_output_folder)

        ################################################################################################################
        # TIME SERIES STATS
        plot_ts_metr_stats = {"plot_ts_metr_stats": 'all_metrics'
                              }
        if output["plot"] in plot_ts_metr_stats:
            base.plot_features.plot_ts_metr_stats(models, observation, flag_interval, flag_slice,
                                                  output_path=sub_func_output_folder)

        ################################################################################################################
        # MAP METRIC
        plot_map_metr = {"plot_map_metr_ecart": 'difference', "plot_map_metr_biais": 'bias',
                         "plot_map_metr_RMSEc": 'RMSEc', "plot_map_metr_RMSEcentree": 'RMSEcentree'
                         }

        if output["plot"] in plot_map_metr:
            for i, mod in enumerate(models):
                base.plot_features.plot_map_metr_profiles(flag_interval, flag_slice, mod["xarray_meta_coloc"],
                                                          observation["xarray_meta_coloc"][i],
                                                          plot_map_metr[output["plot"]], cmap, vmin, vmax,
                                                          mod_name=models_name[i], obs_name=obs_name,
                                                          output_path=sub_func_output_folder, dvmin=dvmin, dvmax=dvmax)

        ################################################################################################################
        # DISP DIAG
        diag_disp = {"diag_disp": 'diag_disp', "diag_disp_g": 'diag_disp_g'}
        if output["plot"] in diag_disp:
            for i, mod in enumerate(models):

                base.plot_features.diag_disp(flag_interval, flag_slice, obs_name, models_name[i], output["plot"],
                                             mod["xarray_meta_coloc"], observation["xarray_meta_coloc"][i],
                                             output_path=sub_func_output_folder)

        ################################################################################################################
        # COURBE PROFIL UNIQUE
        plot_profile_u = {"plot_profile_u": 'profile_u'}
        if output["plot"] in plot_profile_u:
            base.plot_features.plot_profile_unique(models, observation["xarray_meta"],
                                                   config_obj["meta_zones"]["radius"],
                                                   output_path=sub_func_output_folder)

        ################################################################################################################
        # COURBE MULTI PROFILS
        plot_profile_multi = {"plot_profile_multi": 'profile_multi'}
        if output["plot"] in plot_profile_multi:
            base.plot_features.plot_profile_multi(models, observation["xarray_meta"],
                                                  config_obj["meta_zones"]["radius"],
                                                  output_path=sub_func_output_folder)

        ################################################################################################################
        # DIAG TS PROFIL UNIQUE
        plot_profile_u = {"diag_ts_unique": 'diag_ts_unique'}
        if output["plot"] in plot_profile_u:
            base.plot_features.plot_diag_ts_unique(models, observation["xarray_meta"],
                                                   output_path=sub_func_output_folder)

        ################################################################################################################
        # DIAG_TS_MULTI
        diag_ts_multi = {"diag_ts_multi": 'diag_ts_multi'}

        if output["plot"] in diag_ts_multi:
            if "radius" not in config_obj["meta_zones"]:
                logger.warning("Caution ! To plot Theta-S diagrams you need to specify a radius in the meta-zone")
            else:
                base.plot_features.plot_diag_ts_multi(models, observation["xarray_meta"],
                                                      config_obj["meta_zones"]["radius"],
                                                      output_path=sub_func_output_folder)
