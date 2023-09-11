"""Create figures for feature 7:currents_ADCP"""
import os
import copy
import logging
import numpy as np
from armoor.base.tools_features import remove_missing_values_ds
from armoor.base import plot_features, comodo_tide_feature
from armoor.base.colocation import colocate_all
import armoor.hmi.script_tools as st

logger = logging.getLogger(__name__)


def plot(config_obj):
    """
    Plot figures required in functionality 7 : currents_ADCP.

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
    flag_slice = 'slice' in config_obj["meta_zones"].keys()

    # SELECT THE VARIABLES
    observation = copy.copy(config_obj["observation"])
    models = copy.copy(config_obj["models"])
    observation["xarray_meta"] = observation["xarray_meta"].sel_var.selection(['current'])

    for i_mod, mod in enumerate(models):
        mod["xarray_meta"] = mod["xarray_meta"].sel_var.selection(['current'])
        mod["xarray_meta_coloc"] = mod["xarray_meta_coloc"].sel_var.selection(['current'])
        observation["xarray_meta_coloc"][i_mod] = observation["xarray_meta_coloc"][
            i_mod].sel_var.selection(['current'])

    # PLOT
    for output in outputs:
        if output_path:
            sub_func_output_folder = os.path.join(output_path, output["folder_name"])
            st.create_folder(sub_func_output_folder)
        else:
            sub_func_output_folder = os.getcwd()

        # Get the figure parameters from config obj
        vmin = output.get('vmin')
        vmax = output.get('vmax')
        dvmin = output.get('dvmin')
        dvmax = output.get('dvmax')
        cmap = output.get("colormap")

        if 'scale' in output:
            scale = output["scale"]
        else:
            scale = 0.1

        if "env_comodo" in output:
            env_comodo = output["env_comodo"]
        else:
            env_comodo = ''

        # PLOTS
        ############################################################################################
        # HOVMOLLER CURRENTS
        plot_hovmoller = {"plot_hovmoller": 'plot_hovmoller'}
        if output["plot"] in plot_hovmoller:
            if 'attribute' in output:
                attribute = output["attribute"][0].replace('current_', '')
            else:
                attribute = "norm"

            # Remove missing values
            def to_ds_with_coords(dataset, attribute):
                return dataset[attribute].to_dataset().assign_coords(dataset.coords)

            observation['xarray_meta'] = to_ds_with_coords(observation['xarray_meta'], attribute)
            for i_mod, mod in enumerate(models):
                mod['xarray_meta'] = to_ds_with_coords(mod['xarray_meta'], attribute)
                mod['xarray_meta_coloc'] = to_ds_with_coords(mod['xarray_meta_coloc'], attribute)
                observation['xarray_meta_coloc'][i_mod] = to_ds_with_coords(
                    observation['xarray_meta_coloc'][i_mod], attribute)

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

            plot_features.plot_variable_3d(models, observation, cmap, vmin, vmax, dvmin, dvmax,
                                           output_path=sub_func_output_folder)

        ############################################################################################
        # HARMONIC TABLES
        harmonic_table = {"harmonic_table": 'harmonic_table'}

        if output["plot"] in harmonic_table:
            # Check if all the required data are in the configObj
            # List of tidal waves to calculate
            if "tidal_waves" in output:
                list_waves = output["tidal_waves"]
            else:
                raise ValueError("Oops, pour réaliser l'analyse harmonique vous devriez spécifier"
                                 " les ondes à calculer...")

            # Path where to get the comodo tool
            if 'path_comodo' in output:
                path_tools = output["path_comodo"]
            else:
                raise ValueError("Oops, pour réaliser l'analyse harmonique vous devriez spécifier"
                                 " le chemin vers les Comodo tools à utiliser...")

            # Path where to save the results
            if 'path_results' in output:
                path_results = output["path_results"]
                path_nc = os.path.join(path_results, 'obs_tide_uv.nc')
            else:
                raise ValueError("Oops, pour réaliser l'analyse harmonique vous devriez spécifier"
                                 " le chemin où sauvegarder les fichiers résultats...")

            # Definition of the period for the harmonic analysis
            if 'analysis_start' in output and 'analysis_end' in output:
                analysis_start = np.datetime64(output["analysis_start"])
                analysis_end = np.datetime64(output["analysis_end"])
                observation["xarray_meta"] = observation["xarray_meta"].sel(
                    time=slice(analysis_start, analysis_end))
                for i_mod, mod in enumerate(models):
                    mod['xarray_meta'] = mod['xarray_meta'].sel(
                        time=slice(analysis_start, analysis_end))
            else:
                logger.info("Oops, pour réaliser l'analyse harmonique vous devriez spécifier "
                            "la période sur laquelle calculer l'analyse harmonique. Le calcul "
                            "sera ici fait sur toute la période des fichiers d'entrée...")

            # Process harmonic analysis on observation
            logger.info("Beginning of the harmonic analysis on the observation.")
            # If metazone per slice, calculate average per slice
            if flag_slice:
                if len(observation["xarray_meta"]['idx_depth'].values) > 1:
                    observation["xarray_meta"] = observation["xarray_meta"].mean('idx_depth')

            # Calculate harmonic analysis
            ds_obs = comodo_tide_feature.harmonic_analysis(observation["xarray_meta"], 'u v',
                                                           path_nc, path_results, path_tools,
                                                           list_waves, 'obs', env_comodo=env_comodo)
            ds_obs = ds_obs.assign_attrs({'name': observation['name']})

            # Re-add the depth / slice values
            if "depth" in observation['xarray_meta'].dims:
                ds_obs['depth'] = observation['xarray_meta']['depth']
            elif "slice" in observation['xarray_meta'].dims:
                ds_obs['slice'] = observation['xarray_meta']['slice']

            # Process harmonic analysis on models
            logger.info("Beginning of the harmonic analysis on the models.")
            for i_mod, mod in enumerate(models):
                path_nc = os.path.join(path_results, 'mod_tide_uv.nc')
                # If metazone per slice, calculate average per slice
                if flag_slice:
                    if len(mod["xarray_meta_coloc"]['idx_depth'].values) > 1:
                        mod["xarray_meta_coloc"] = mod["xarray_meta_coloc"].mean('idx_depth')

                # Calculate harmonic analysis
                ds_mod = comodo_tide_feature.harmonic_analysis(mod['xarray_meta_coloc'], 'u v',
                                                               path_nc, path_results, path_tools,
                                                               list_waves, 'mod',
                                                               env_comodo=env_comodo)
                ds_mod = ds_mod.assign_attrs({'name': mod['name']})

                # Re-add the depth / slice values + colocate
                if "depth" in mod['xarray_meta_coloc'].dims:
                    ds_mod['depth'] = mod['xarray_meta_coloc']['depth']
                    flags = False, True, False
                    tgt_grid = 'observation'
                    ds_obs, ds_mod = colocate_all(ds_obs, ds_mod, flags, tgt_grid,
                                                  coloc_method='nearest')
                elif "slice" in mod['xarray_meta_coloc'].dims:
                    ds_mod['slice'] = mod['xarray_meta_coloc']['slice']

                # Create the table
                logger.info("Creation of tables in the directory : %s", sub_func_output_folder)
                plot_features.create_harmonic_table(ds_mod, ds_obs,
                                                    output_path=sub_func_output_folder)

        ############################################################################################
        # ELLIPSES TIDAL CURRENTS
        plot_tide_current_ellipses = {"plot_tide_current_ellipses": 'plot_tide_current_ellipses'}

        if output["plot"] in plot_tide_current_ellipses:

            # Check if all the required data are in the configObj
            # List of tidal waves to calculate
            if "tidal_waves" in output:
                list_waves = output["tidal_waves"]
            else:
                raise ValueError("Oops, pour réaliser l'analyse harmonique vous devriez spécifier"
                                 " les ondes à calculer...")

            # Path where to get the comodo tool
            if 'path_comodo' in output:
                path_tools = output["path_comodo"]
            else:
                raise ValueError("Oops, pour réaliser l'analyse harmonique vous devriez spécifier"
                                 " le chemin vers les Comodo tools à utiliser...")

            # Path where to save the results
            if 'path_results' in output:
                path_results = output["path_results"]
                path_nc = os.path.join(path_results, 'obs_tide_uv.nc')
            else:
                raise ValueError("Oops, pour réaliser l'analyse harmonique vous devriez spécifier"
                                 " le chemin où sauvegarder les fichiers résultats...")

            # Definition of the period for the harmonic analysis
            if 'analysis_start' in output and 'analysis_end' in output:
                analysis_start = np.datetime64(output["analysis_start"])
                analysis_end = np.datetime64(output["analysis_end"])
                observation["xarray_meta"] = observation["xarray_meta"].sel(
                    time=slice(analysis_start, analysis_end))
                for i_mod, mod in enumerate(models):
                    mod['xarray_meta'] = mod['xarray_meta'].sel(
                        time=slice(analysis_start, analysis_end))

            else:
                logger.info("Oops, pour réaliser l'analyse harmonique vous devriez spécifier "
                            "la période sur laquelle calculer l'analyse harmonique. Le calcul "
                            "sera ici fait sur toute la période des fichiers d'entrée.")

            # Process harmonic analysis on observation
            # If metazone per slice, calculate average per slice
            if flag_slice:
                if len(observation["xarray_meta"]['idx_depth'].values) > 1:
                    observation["xarray_meta"] = observation["xarray_meta"].mean('idx_depth')

            # Calculate harmonic analysis
            ds_obs = comodo_tide_feature.harmonic_analysis(observation["xarray_meta"], 'u v',
                                                           path_nc, path_results, path_tools,
                                                           list_waves, 'obs', env_comodo=env_comodo)

            ds_obs = ds_obs.assign_attrs({'name': observation['name']})

            # Re-add the depth / slice values
            if "depth" in observation['xarray_meta'].dims:
                ds_obs['depth'] = observation['xarray_meta']['depth']
            elif "slice" in observation['xarray_meta'].dims:
                ds_obs['slice'] = observation['xarray_meta']['slice']

            # Process harmonic analysis on models
            ds_models = []
            for i_mod, mod in enumerate(models):
                path_nc = os.path.join(path_results, 'mod_tide_uv.nc')
                # If metazone per slice, calculate average per slice
                if flag_slice:
                    if len(mod["xarray_meta_coloc"]['idx_depth'].values) > 1:
                        mod["xarray_meta_coloc"] = mod["xarray_meta_coloc"].mean('idx_depth')

                # Calculate harmonic analysis
                ds_mod = comodo_tide_feature.harmonic_analysis(mod['xarray_meta_coloc'], 'u v',
                                                               path_nc, path_results, path_tools,
                                                               list_waves, 'mod',
                                                               env_comodo=env_comodo)
                ds_mod = ds_mod.assign_attrs({'name': mod['name']})

                # Re-add the depth / slice values + colocate
                if "depth" in mod['xarray_meta_coloc'].dims:
                    ds_mod['depth'] = mod['xarray_meta_coloc']['depth']
                    flags = False, True, False
                    tgt_grid = 'observation'
                    ds_obs, ds_mod = colocate_all(ds_obs, ds_mod, flags, tgt_grid,
                                                  coloc_method='nearest')
                elif "slice" in mod['xarray_meta_coloc'].dims:
                    ds_mod['slice'] = mod['xarray_meta_coloc']['slice']
                ds_models.append(ds_mod)

            # Plot the ellipses
            plot_features.plot_ellipses_tide_current(ds_models, ds_obs, scale,
                                                     output_path=sub_func_output_folder)
