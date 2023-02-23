"""Create figures for feature 6:currents_hfr"""
import copy
from armoor import base
import numpy as np
import armoor.base.feature_tools as ft
import armoor.hmi.script_tools as st

import logging
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
    coloc_product = config_obj["colocate"]
    outputs = config_obj["outputs"]
    output_path = config_obj.get("output_path")

    # SET THE FLAGS
    flag_interval = 'interval' in config_obj["meta_zones"].keys()
    flag_slice = 'slice' in config_obj["meta_zones"].keys()

    # SELECT THE CURRENT VARIABLES
    observation = copy.copy(config_obj["observation"])
    models = copy.copy(config_obj["models"])

    observation["xarray_meta"] = observation["xarray_meta"].read_sst.sel(['current'])
    for i_mod, mod in enumerate(models):
        mod["xarray_meta"] = mod["xarray_meta"].read_sst.sel(['current'])
        mod["xarray_meta_coloc"] = mod["xarray_meta_coloc"].read_sst.sel(['current'])
        observation["xarray_meta_coloc"][i_mod] = observation["xarray_meta_coloc"][i_mod].read_sst.sel(['current'])

    # Surface current only in this feature
    observation["xarray_meta"] = observation["xarray_meta"].meta.vertical_selection_ponct(0)
    for i_mod, mod in enumerate(models):
        mod["xarray_meta"] = mod["xarray_meta"].meta.vertical_selection_ponct(0)
        mod["xarray_meta_coloc"] = mod["xarray_meta_coloc"].meta.vertical_selection_ponct(0)
        observation["xarray_meta_coloc"][i_mod] = observation["xarray_meta_coloc"][i_mod]. \
            meta.vertical_selection_ponct(0)

    for index_output, output in enumerate(outputs):
        if output_path:
            sub_func_output_folder = f'{output_path}{output["folder_name"]}/'
            st.create_folder(sub_func_output_folder)
        else:
            sub_func_output_folder = output_path
        # Get the figure parameters from config obj
        if 'scale' in output:
            scale = output["scale"]
        else:
            scale = 0.1

        # PLOTS
        ################################################################################################################
        # MAP TIDAL CURRENTS
        plot_map_amplitude = {"plot_map_current_harmonic": 'plot_map_current_harmonic'}
        if output["plot"] in plot_map_amplitude:
            # Check if all the required data are in the configObj
            # List of tidal waves to calculate
            if "tidal_waves" in output:
                list_waves = output["tidal_waves"]
            else:
                raise Exception("Oops, pour réaliser l'analyse harmonique vous devriez spécifier"
                                " les ondes à calculer...")

            # Path where to get the comodo tool
            if 'path_comodo' in output:
                path_tools = output["path_comodo"]
            else:
                raise Exception("Oops, pour réaliser l'analyse harmonique vous devriez spécifier"
                                " le chemin vers les Comodo tools à utiliser...")

            # Path where to save the results
            if 'path_results' in output:
                path_results = output["path_results"]
                path_nc = f"{path_results}obs_tide_uv.nc"
            else:
                raise Exception("Oops, pour réaliser l'analyse harmonique vous devriez spécifier"
                                " le chemin où sauvegarder les fichiers résultats...")

            # Definition of the period for the harmonic analysis
            if 'analysis_start' in output and 'analysis_end' in output:
                analysis_start = np.datetime64(output["analysis_start"])
                analysis_end = np.datetime64(output["analysis_end"])
                observation["xarray_meta"] = observation["xarray_meta"].sel(time=slice(analysis_start, analysis_end))
                for i_mod, mod in enumerate(models):
                    mod['xarray_meta'] = mod['xarray_meta'].sel(time=slice(analysis_start, analysis_end))
            else:
                logger.info(f"Oops, pour réaliser l'analyse harmonique vous devriez spécifier "
                            f"la période sur laquelle calculer l'analyse harmonique. Le calcul "
                            f"sera ici fait sur toute la période des fichiers d'entrée...")

            # Proceed harmonic analysis on obs
            ds_obs = base.comodo_tide_feature.harmonic_analysis(observation["xarray_meta"], 'u v', path_nc,
                                                                path_results, path_tools, list_waves, 'obs')
            for i_mod, mod in enumerate(models):
                # Proceed harmonic analysis on mod
                path_nc = f"{path_results}mod_tide_uv.nc"
                ds_mod = base.comodo_tide_feature.harmonic_analysis(mod['xarray_meta'], 'u v', path_nc, path_results,
                                                                    path_tools, list_waves, 'mod')
                obs_coloc, mod_coloc = base.colocate_all(ds_obs, ds_mod, True, False, False, coloc_method='nearest',
                                                         opt_grid=coloc_product)
                # Plot the maps
                base.plot_features.plot_map_harm(mod_coloc,
                                                 obs_coloc,
                                                 output_path=sub_func_output_folder)

        ################################################################################################################
        # ELLIPSES TIDAL CURRENTS
        plot_tide_current_ellipses = {"plot_tide_current_ellipses": 'plot_tide_current_ellipses'}
        if output["plot"] in plot_tide_current_ellipses:
            # Process observation
            # List of tidal waves to calculate
            if "tidal_waves" in output:
                list_waves = output["tidal_waves"]
            else:
                raise Exception("Oops, pour réaliser l'analyse harmonique vous devriez spécifier"
                                " les ondes à calculer...")

            # Path where to get the comodo tool
            if 'path_comodo' in output:
                path_tools = output["path_comodo"]
            else:
                raise Exception("Oops, pour réaliser l'analyse harmonique vous devriez spécifier"
                                " le chemin vers les Comodo tools à utiliser...")

            # Path where to save the results
            if 'path_results' in output:
                path_results = output["path_results"]
                path_nc = f"{path_results}obs_tide_uv.nc"
            else:
                raise Exception("Oops, pour réaliser l'analyse harmonique vous devriez spécifier"
                                " le chemin où sauvegarder les fichiers résultats...")

            # Definition of the period for the harmonic analysis
            if 'analysis_start' in output and 'analysis_end' in output:
                analysis_start = np.datetime64(output["analysis_start"])
                analysis_end = np.datetime64(output["analysis_end"])
                observation["xarray_meta"] = observation["xarray_meta"].sel(time=slice(analysis_start, analysis_end))
                for i_mod, mod in enumerate(models):
                    mod['xarray_meta'] = mod['xarray_meta'].sel(time=slice(analysis_start, analysis_end))
            else:
                logger.info(f"Oops, pour réaliser l'analyse harmonique vous devriez spécifier "
                            f"la période sur laquelle calculer l'analyse harmonique. Le calcul "
                            f"sera ici fait sur toute la période des fichiers d'entrée...")

            # Proceed harmonic analysis on obs
            ds_obs = base.comodo_tide_feature.harmonic_analysis(observation["xarray_meta"], 'u v', path_nc,
                                                                path_results, path_tools, list_waves, 'obs')
            ds_obs = ds_obs.assign_attrs({'name': observation['name']})

            ds_models = []
            for i_mod, mod in enumerate(models):
                # Proceed harmonic analysis on mod
                path_nc = f"{path_results}mod_tide_uv.nc"
                ds_mod = base.comodo_tide_feature.harmonic_analysis(mod['xarray_meta'], 'u v', path_nc,
                                                                    path_results, path_tools, list_waves, 'mod')
                ds_mod = ds_mod.assign_attrs({'name': mod['name']})
                ds_models.append(ds_mod)
            # Plot the maps
            base.plot_features.plot_ellipses_tide_current(ds_models,
                                                          ds_obs,
                                                          scale,
                                                          output_path=sub_func_output_folder)

        ################################################################################################################
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

            observation['xarray_meta'] = observation['xarray_meta'][attribute]
            for i_mod, mod in enumerate(models):
                mod['xarray_meta'] = mod['xarray_meta'][attribute]
                mod['xarray_meta_coloc'] = mod['xarray_meta_coloc'][attribute]
                observation['xarray_meta_coloc'][i_mod] = observation['xarray_meta_coloc'][i_mod][attribute]
                models[i_mod] = mod
                # Remove missing values
                models, observation = base.remove_missing_values_ds(models,
                                                                    observation,
                                                                    i_mod,
                                                                    [attribute],
                                                                    [attribute])

            base.plot_features.plot_ts_metr_point(models,
                                                  observation,
                                                  plot_ts_metr_point[output["plot"]],
                                                  flag_interval,
                                                  flag_slice,
                                                  output_path=sub_func_output_folder)
        ################################################################################################################
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

            observation['xarray_meta'] = observation['xarray_meta'][attribute]
            for i_mod, mod in enumerate(models):
                mod['xarray_meta'] = mod['xarray_meta'][attribute]
                mod['xarray_meta_coloc'] = mod['xarray_meta_coloc'][attribute]
                observation['xarray_meta_coloc'][i_mod] = observation['xarray_meta_coloc'][i_mod][attribute]
                models[i_mod] = mod
                # Remove missing values
                models, observation = base.remove_missing_values_ds(models,
                                                                    observation,
                                                                    i_mod,
                                                                    [attribute],
                                                                    [attribute])

            base.plot_features.plot_ts_metr_stats(models,
                                                  observation,
                                                  flag_interval,
                                                  flag_slice,
                                                  output_path=sub_func_output_folder)

        ################################################################################################################
        # CURRENT MAP
        plot_map_metr = {"plot_map_metr_ecart_interval": 'difference',
                         "plot_map_metr_ecart": 'difference',
                         "plot_map_metr_biais": 'bias',
                         "plot_map_metr_RMSEc": 'RMSEc',
                         "plot_map_metr_RMSEcentree": 'RMSEcentree'
                         }
        if output["plot"] in plot_map_metr:
            vmin = ft.get_output('vmin', output)
            vmax = ft.get_output('vmax', output)
            cmap = ft.get_output("colormap", output)
            cmap = cmap if cmap is None else f'cmo.{cmap}'

            for i_mod, mod in enumerate(models):
                # Remove missing values
                models, observation = base.remove_missing_values_ds(models, observation, i_mod,
                                                                    ['u', 'v', 'norm'],
                                                                    ['u', 'v', 'norm'])

                base.plot_features.plot_map_metr_current(flag_interval,
                                                         flag_slice,
                                                         mod["xarray_meta"],
                                                         mod["xarray_meta_coloc"],
                                                         observation["xarray_meta"],
                                                         observation["xarray_meta_coloc"][i_mod],
                                                         plot_map_metr[output["plot"]],
                                                         cmap,
                                                         vmin,
                                                         vmax,
                                                         output_path=sub_func_output_folder)
