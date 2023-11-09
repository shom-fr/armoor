"""Create figures for feature 6:currents_hfr"""
import logging
import os
import copy
import numpy as np
from armoor.base.tools_features import remove_missing_values_ds
from armoor.base import plot_features, ttide_tide_feature
from armoor.base.colocation import colocate_all
import armoor.hmi.script_tools as st

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

    observation["xarray_meta"] = observation["xarray_meta"].sel_var.selection(
        ['current']).assign_attrs({'name': observation['name']})
    for i_mod, mod in enumerate(models):
        mod["xarray_meta"] = mod["xarray_meta"].sel_var.selection(['current']).assign_attrs(
            {'name': mod['name']})
        mod["xarray_meta_coloc"] = mod["xarray_meta_coloc"].sel_var.selection(
            ['current']).assign_attrs({'name': mod['name']})
        observation["xarray_meta_coloc"][i_mod] = observation["xarray_meta_coloc"][
            i_mod].sel_var.selection(['current']).assign_attrs({'name': observation['name']})

    for output in outputs:
        if output_path:
            sub_func_output_folder = os.path.join(output_path, output["folder_name"])
            st.create_folder(sub_func_output_folder)
        else:
            sub_func_output_folder = output_path

        # Get the figure parameters from config obj
        if 'scale' in output:
            scale = output["scale"]
        else:
            scale = 0.1

        # PLOTS
        ############################################################################################
        # MAP TIDAL CURRENTS
        plot_map_amplitude = {"plot_map_current_harmonic": 'plot_map_current_harmonic'}
        if output["plot"] in plot_map_amplitude:

            for i_mod, mod in enumerate(models):
                # Proceed harmonic analysis on obs
                logger.info(f'Computing harmonic analysis for the observation...')
                ds_obs = ttide_tide_feature.run_harmonic_analysis_map(
                    observation["xarray_meta_coloc"][i_mod], output)
                # Proceed harmonic analysis on mod
                logger.info(f'Computing harmonic analysis for model {i_mod}...')
                ds_mod = ttide_tide_feature.run_harmonic_analysis_map(mod['xarray_meta_coloc'],
                                                                      output)

                # Plot the maps
                plot_features.plot_map_harm(ds_mod, ds_obs, output_path=sub_func_output_folder)

        ############################################################################################
        # ELLIPSES TIDAL CURRENTS
        plot_tide_current_ellipses = {"plot_tide_current_ellipses": 'plot_tide_current_ellipses'}
        if output["plot"] in plot_tide_current_ellipses:
            # Proceed harmonic analysis on obs
            logger.info(f'Computing harmonic analysis for the observation...')
            ds_obs = ttide_tide_feature.run_harmonic_analysis(observation["xarray_meta"], output)

            ds_models = []
            for i_mod, mod in enumerate(models):
                logger.info(f'Computing harmonic analysis for model {i_mod}...')
                ds_mod = ttide_tide_feature.run_harmonic_analysis(mod['xarray_meta_coloc'], output)
                ds_models.append(ds_mod)
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
            if 'attribute' in output:
                attribute = output["attribute"][0].replace('current_', '')
            else:
                attribute = "norm"

            # Remove missing values
            observation['xarray_meta'] = observation['xarray_meta'][attribute].to_dataset()
            for i_mod, mod in enumerate(models):
                mod['xarray_meta'] = mod['xarray_meta'][attribute].to_dataset()
                mod['xarray_meta_coloc'] = mod['xarray_meta_coloc'][attribute].to_dataset()
                observation['xarray_meta_coloc'][i_mod] = observation['xarray_meta_coloc'][i_mod][
                    attribute].to_dataset()
                models[i_mod] = mod
                # Remove missing values
                models, observation = remove_missing_values_ds(models, observation, i_mod,
                                                               [attribute], [attribute])

            # Select variables to plot
            observation['xarray_meta'] = observation['xarray_meta'].to_array()
            for i_mod, mod in enumerate(models):
                mod['xarray_meta'] = mod['xarray_meta'].to_array()
                mod['xarray_meta_coloc'] = mod['xarray_meta_coloc'].to_array()
                observation['xarray_meta_coloc'][i_mod] = observation['xarray_meta_coloc'][
                    i_mod].to_array()

            plot_features.plot_ts_metr_point(models, observation, flag_interval, flag_slice,
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
            if 'attribute' in output:
                attribute = output["attribute"][0].replace('current_', '')
            else:
                attribute = "norm"

            plg = config_obj["meta_zones"].get("polygon")

            # Remove missing values
            observation['xarray_meta'] = observation['xarray_meta'][
                attribute].to_dataset().assign_attrs({'name': observation['name']})
            for i_mod, mod in enumerate(models):
                mod['xarray_meta'] = mod['xarray_meta'][attribute].to_dataset().assign_attrs(
                    {'name': mod['name']})
                mod['xarray_meta_coloc'] = mod['xarray_meta_coloc'][
                    attribute].to_dataset().assign_attrs({'name': mod['name']})
                observation['xarray_meta_coloc'][i_mod] = observation['xarray_meta_coloc'][i_mod][
                    attribute].to_dataset().assign_attrs({'name': observation['name']})
                models[i_mod] = mod
                # Remove missing values
                models, observation = remove_missing_values_ds(models, observation, i_mod,
                                                               [attribute], [attribute])

            # Select variables to plot
            observation['xarray_meta'] = observation['xarray_meta'].to_array()
            for i_mod, mod in enumerate(models):
                mod['xarray_meta'] = mod['xarray_meta'].to_array()
                mod['xarray_meta_coloc'] = mod['xarray_meta_coloc'].to_array()
                observation['xarray_meta_coloc'][i_mod] = observation['xarray_meta_coloc'][
                    i_mod].to_array()

            plot_features.plot_ts_metr_stats(models, observation, flag_interval, flag_slice,
                                             output_path=sub_func_output_folder, plg=plg)

        ############################################################################################
        # CURRENT MAP
        plot_map_metr = {"plot_map_metr_ecart_interval": 'difference',
                         "plot_map_metr_ecart": 'difference', "plot_map_metr_biais": 'bias',
                         "plot_map_metr_RMSEc": 'RMSEc', "plot_map_metr_RMSEcentree": 'RMSEcentree'
                         }
        if output["plot"] in plot_map_metr:
            vmin = output.get('vmin')
            vmax = output.get('vmax')
            dvmin = output.get('dvmin')
            dvmax = output.get('dvmax')
            cmap = output.get("colormap")
            cmap = cmap if cmap is None else f'cmo.{cmap}'

            for i_mod, mod in enumerate(models):
                # Remove missing values
                models, observation = remove_missing_values_ds(models, observation, i_mod,
                                                               ['u', 'v', 'norm'],
                                                               ['u', 'v', 'norm'])

                plot_features.plot_map_metr_current(flag_interval, flag_slice, mod["xarray_meta"],
                                                    mod["xarray_meta_coloc"],
                                                    observation["xarray_meta"],
                                                    observation["xarray_meta_coloc"][i_mod],
                                                    plot_map_metr[output["plot"]], cmap, vmin, vmax,
                                                    dvmin=dvmin, dvmax=dvmax,
                                                    output_path=sub_func_output_folder, )
