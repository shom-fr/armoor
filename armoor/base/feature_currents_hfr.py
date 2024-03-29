"""Create figures for feature 6:currents_hfr"""
import logging
import os
import copy
import numpy as np
from armoor.base.tools_features import remove_missing_values_ds
from armoor.base import plot_features, utide_ttide_tide_feature
from armoor.base.colocation import colocate_all
from armoor.hmi.script_tools import create_folder

logger = logging.getLogger(__name__)


def plot(config_obj):
    """
    Plot figures required in functionality 6 : currents_hfr.

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
    flag_interval = 'interval' in config_obj["meta_zones"].keys()
    flag_slice = 'slice' in config_obj["meta_zones"].keys()

    # SELECT THE CURRENT VARIABLES
    observation = copy.copy(config_obj["observation"])
    models = copy.copy(config_obj["models"])

    for output in outputs:
        if output_path:
            sub_func_output_folder = os.path.join(output_path, output["folder_name"])
            create_folder(sub_func_output_folder)
        else:
            sub_func_output_folder = output_path

        # Calculate residual current
        if 'attribute' in output and 'res' in output['attribute'][0]:
            if 'low_pass_filter' in output:
                filter = output['low_pass_filter']
                observation["xarray_meta"] = observation["xarray_meta"].sel_var.selection(
                    ['current_res'], filter=filter)
                for i_mod, mod in enumerate(models):
                    mod["xarray_meta"] = mod["xarray_meta"].sel_var.selection(['current_res'],
                                                                              filter=filter)
                    mod["xarray_meta_coloc"] = mod["xarray_meta_coloc"].sel_var.selection(
                        ['current_res'], filter=filter)
                    observation["xarray_meta_coloc"][i_mod] = observation["xarray_meta_coloc"][
                        i_mod].sel_var.selection(['current_res'], filter=filter)
            else:
                logger.warning(
                    'Caution ! To retrieve residual currents, please specify low_pass_filter with demerliac, godin or mean.')
        else:
            observation["xarray_meta"] = observation["xarray_meta"].sel_var.selection(['current'])
            for i_mod, mod in enumerate(models):
                mod["xarray_meta"] = mod["xarray_meta"].sel_var.selection(['current'])
                mod["xarray_meta_coloc"] = mod["xarray_meta_coloc"].sel_var.selection(['current'])
                observation["xarray_meta_coloc"][i_mod] = observation["xarray_meta_coloc"][
                    i_mod].sel_var.selection(['current'])

        # PLOTS
        ############################################################################################
        # MAP TIDAL CURRENTS
        plot_map_amplitude = {"plot_map_current_harmonic": 'plot_map_current_harmonic'}
        if output["plot"] in plot_map_amplitude:

            for i_mod, mod in enumerate(models):
                # Proceed harmonic analysis on obs
                logger.info(f'Computing harmonic analysis for the observation...')
                ds_obs = utide_ttide_tide_feature.run_harmonic_analysis_map(
                    observation["xarray_meta_coloc"][i_mod], output)
                # Proceed harmonic analysis on mod
                logger.info(f'Computing harmonic analysis for model {i_mod}...')
                ds_mod = utide_ttide_tide_feature.run_harmonic_analysis_map(mod['xarray_meta_coloc'],
                                                                      output)

                # Plot the maps
                plot_features.plot_map_harm(ds_mod, ds_obs, output_path=sub_func_output_folder)

        ############################################################################################
        # ELLIPSES TIDAL CURRENTS
        plot_tide_current_ellipses = {"plot_tide_current_ellipses": 'plot_tide_current_ellipses'}
        if output["plot"] in plot_tide_current_ellipses:

            # Proceed harmonic analysis on obs
            logger.info(f'Computing harmonic analysis for the observation...')
            ds_obs = utide_ttide_tide_feature.run_harmonic_analysis(observation["xarray_meta"], output)

            ds_models = []
            for i_mod, mod in enumerate(models):
                logger.info(f'Computing harmonic analysis for model {i_mod}...')
                ds_mod = utide_ttide_tide_feature.run_harmonic_analysis(mod['xarray_meta_coloc'], output)
                ds_models.append(ds_mod)

            # Get scale
            scale = output.get("scale")
            if scale is not None:
                list_waves = output.get("tidal_waves").split()
                if len(scale) < len(list_waves):
                    logger.warning(
                        f'You should specify one scale value per required tidal wave. By default, the scale will be {scale[0]} for all tidal waves.')
                    scale = [scale[0]] * len(list_waves)

            # Plot the maps
            plot_features.plot_ellipses_tide_current(ds_models, ds_obs, scale,
                                                     output_path=sub_func_output_folder)

        ############################################################################################
        # PONCTUAL TIMES SERIES
        plot_ts_metr_point = {"plot_ts_metr_ecart_point": 'difference_point',
                              "plot_ts_metr_bias_point": 'bias_point',
                              "plot_ts_metr_RMSE_point": 'RMSEc_point',
                              "plot_ts_metr_point": 'all_metrics'
                              }
        if output["plot"] in plot_ts_metr_point:
            # Select the attributes to plot
            if 'attribute' in output and output["attribute"] == ['current_res']:
                attributes = ['u_res', 'v_res', 'norm_res', 'dir_res']
            else:
                attributes = ['u', 'v', 'norm', 'dir']

            for attribute in attributes:
                obs_var, mods_var = copy.deepcopy(observation), copy.deepcopy(models)
                for i_mod, mod_var in enumerate(mods_var):
                    # Remove missing values
                    mods_var, obs_var = remove_missing_values_ds(mods_var, obs_var, i_mod,
                                                                 [attribute])
                    # Select variables to plot
                    mod_var['xarray_meta'] = mod_var['xarray_meta'][attribute]
                    mod_var['xarray_meta_coloc'] = mod_var['xarray_meta_coloc'][attribute]
                    obs_var['xarray_meta_coloc'][i_mod] = obs_var['xarray_meta_coloc'][i_mod][
                        attribute]
                obs_var['xarray_meta'] = obs_var['xarray_meta'][attribute]
                # Plot
                plot_features.plot_ts_metr_point(mods_var, obs_var, flag_interval, flag_slice,
                                                 output_path=sub_func_output_folder)
        ############################################################################################
        # STATS TIMES SERIES
        plot_ts_metr_stats = {"plot_ts_metr_ecart_stats": 'difference_stats',
                              "plot_ts_metr_bias_stats": 'bias_stats',
                              "plot_ts_metr_RMSE_stats": 'RMSEc_stats',
                              "plot_ts_metr_stats": 'all_metrics'
                              }
        if output["plot"] in plot_ts_metr_stats:
            # Select the attributes to plot
            if 'attribute' in output and output["attribute"] == ['current_res']:
                attributes = ['u_res', 'v_res', 'norm_res', 'dir_res']
            else:
                attributes = ['u', 'v', 'norm', 'dir']

            plg = config_obj["meta_zones"].get("polygon")

            for attribute in attributes:
                obs_var, mods_var = copy.deepcopy(observation), copy.deepcopy(models)
                for i_mod, mod_var in enumerate(mods_var):
                    # Remove missing values
                    mods_var, obs_var = remove_missing_values_ds(mods_var, obs_var, i_mod,
                                                                 [attribute])
                    # Select variables to plot
                    mod_var['xarray_meta'] = mod_var['xarray_meta'][attribute]
                    mod_var['xarray_meta_coloc'] = mod_var['xarray_meta_coloc'][attribute]
                    obs_var['xarray_meta_coloc'][i_mod] = obs_var['xarray_meta_coloc'][i_mod][
                        attribute]
                obs_var['xarray_meta'] = obs_var['xarray_meta'][attribute]

                plot_features.plot_ts_metr_stats(mods_var, obs_var, flag_interval, flag_slice,
                                                 output_path=sub_func_output_folder, plg=plg)

        ############################################################################################
        # CURRENT MAP
        plot_map_metr = {"plot_map_metr_ecart_interval": 'difference',
                         "plot_map_metr_ecart": 'difference', "plot_map_metr_biais": 'bias',
                         "plot_map_metr_RMSE": 'RMSE', "plot_map_metr_RMSEc": 'RMSEc'
                         }
        if output["plot"] in plot_map_metr:
            vmin = output.get('vmin')
            vmax = output.get('vmax')
            dvmin = output.get('dvmin')
            dvmax = output.get('dvmax')
            cmap = output.get("colormap")
            cmap = cmap if cmap is None else f'cmo.{cmap}'
            metric = plot_map_metr[output["plot"]]

            # Select the attributes to plot
            if 'attribute' in output and output["attribute"] == ['current_res']:
                attribute = 'current_res'
                attributes = ['u_res', 'v_res', 'norm_res']
            else:
                attribute = 'current'
                attributes = ['u', 'v', 'norm']

            for i_mod, mod in enumerate(models):
                # Remove missing values
                models, observation = remove_missing_values_ds(models, observation, i_mod,
                                                               attributes)

                plot_features.plot_map_metr_current(flag_interval, flag_slice, models, observation,
                                                    i_mod, metric, attribute, cmap, vmin, vmax,
                                                    dvmin=dvmin, dvmax=dvmax,
                                                    output_path=sub_func_output_folder)
