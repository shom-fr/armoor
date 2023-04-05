"""Create figures for feature 7:currents_ADCP"""
import copy
from armoor import base
import numpy as np
import armoor.hmi.script_tools as st

import logging
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
    flag_slice = True if 'slice' in config_obj["meta_zones"].keys() else False

    # SELECT THE VARIABLES
    observation = copy.copy(config_obj["observation"])
    models = copy.copy(config_obj["models"])

    observation["xarray_meta"] = observation["xarray_meta"].read_sst.sel(['current'])
    for i_mod, mod in enumerate(models):
        mod["xarray_meta"] = mod["xarray_meta"].read_sst.sel(['current'])
        mod["xarray_meta_coloc"] = mod["xarray_meta_coloc"].read_sst.sel(['current'])
        observation["xarray_meta_coloc"][i_mod] = observation["xarray_meta_coloc"][i_mod].read_sst.sel(['current'])

    # SELECT THE USED MODEL POINT
    # For feature 7, we do not make horizontal colocation, the point is defined from radius and bathymetry threshold
    models = select_point_bathy_radius(config_obj, observation, models)

    # PLOT
    for index_output, output in enumerate(outputs):
        if output_path:
            sub_func_output_folder = f'{output_path}{output["folder_name"]}/'
            st.create_folder(sub_func_output_folder)
        else:
            sub_func_output_folder = output_path

        # Get the figure parameters from config obj
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

        if 'scale' in output:
            scale = output["scale"]
        else:
            scale = 0.1

        # PLOTS
        ################################################################################################################
        # HOVMOLLER CURRENTS
        plot_hovmoller = {"plot_hovmoller": 'plot_hovmoller'}
        if output["plot"] in plot_hovmoller:
            if 'attribute' in output:
                attribute = output["attribute"][0].replace('current_', '')
            else:
                attribute = "norm"

            observation['xarray_meta'] = observation['xarray_meta'][attribute]
            for i_mod, mod in enumerate(models):
                mod['xarray_meta'] = mod['xarray_meta'][attribute]
                mod['xarray_meta_coloc'] = mod['xarray_meta_coloc'][attribute]
                observation['xarray_meta_coloc'][i_mod] = observation['xarray_meta_coloc'][i_mod][attribute]
                # Remove missing values
                models, observation = base.remove_missing_values_ds(models, observation, i_mod,
                                                                    [attribute], [attribute])

            base.plot_features.plot_variable_3d(models,
                                                observation,
                                                cmap,
                                                vmin,
                                                vmax,
                                                output_path=sub_func_output_folder)

        ################################################################################################################
        # HARMONIC TABLES
        harmonic_table = {"harmonic_table": 'harmonic_table'}

        if output["plot"] in harmonic_table:
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

            # Process harmonic analysis on observation
            logger.info("Beginning of the harmonic analysis on the observation.")
            # If metazone per slice, calculate average per slice
            if flag_slice:
                if len(observation["xarray_meta"]['idx_depth'].values) > 1:
                    observation["xarray_meta"] = observation["xarray_meta"].mean('idx_depth')

            # Calculate harmonic analysis
            ds_obs = base.comodo_tide_feature.harmonic_analysis(observation["xarray_meta"], 'u v', path_nc,
                                                                path_results,
                                                                path_tools, list_waves, 'obs')
            ds_obs = ds_obs.assign_attrs({'name': observation['name']})

            # Re-add the depth / slice values
            if "depth" in observation['xarray_meta'].dims:
                ds_obs['depth'] = observation['xarray_meta']['depth']
            elif "slice" in observation['xarray_meta'].dims:
                ds_obs['slice'] = observation['xarray_meta']['slice']

            # Process harmonic analysis on models
            logger.info("Beginning of the harmonic analysis on the models.")
            for i_mod, mod in enumerate(models):
                path_nc = f"{path_results}mod_tide_uv.nc"
                # If metazone per slice, calculate average per slice
                if flag_slice:
                    if len(mod["xarray_meta_coloc"]['idx_depth'].values) > 1:
                        mod["xarray_meta_coloc"] = mod["xarray_meta_coloc"].mean('idx_depth')

                # Calculate harmonic analysis
                ds_mod = base.comodo_tide_feature.harmonic_analysis(mod['xarray_meta_coloc'], 'u v', path_nc,
                                                                    path_results,
                                                                    path_tools, list_waves, 'mod')
                ds_mod = ds_mod.assign_attrs({'name': mod['name']})

                # Re-add the depth / slice values + colocate
                if "depth" in mod['xarray_meta_coloc'].dims:
                    ds_mod['depth'] = mod['xarray_meta_coloc']['depth']
                    ds_obs, ds_mod = base.colocate_all(ds_obs, ds_mod, False, True, False, coloc_method='nearest',
                                                       opt_grid='observation')
                elif "slice" in mod['xarray_meta_coloc'].dims:
                    ds_mod['slice'] = mod['xarray_meta_coloc']['slice']

                # Create the table
                logger.info(f"Creation of tables in the directory : {sub_func_output_folder}")
                base.plot_features.create_harmonic_table(ds_mod,
                                                         ds_obs,
                                                         output_path=sub_func_output_folder)

        ################################################################################################################
        # ELLIPSES TIDAL CURRENTS
        plot_tide_current_ellipses = {"plot_tide_current_ellipses": 'plot_tide_current_ellipses'}

        if output["plot"] in plot_tide_current_ellipses:
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
                            f"sera ici fait sur toute la période des fichiers d'entrée.")

            # Process harmonic analysis on observation
            # If metazone per slice, calculate average per slice
            if flag_slice:
                if len(observation["xarray_meta"]['idx_depth'].values) > 1:
                    observation["xarray_meta"] = observation["xarray_meta"].mean('idx_depth')

            # Calculate harmonic analysis
            ds_obs = base.comodo_tide_feature.harmonic_analysis(observation["xarray_meta"],
                                                                'u v',
                                                                path_nc,
                                                                path_results,
                                                                path_tools,
                                                                list_waves,
                                                                'obs')

            ds_obs = ds_obs.assign_attrs({'name': observation['name']})

            # Re-add the depth / slice values
            if "depth" in observation['xarray_meta'].dims:
                ds_obs['depth'] = observation['xarray_meta']['depth']
            elif "slice" in observation['xarray_meta'].dims:
                ds_obs['slice'] = observation['xarray_meta']['slice']

            # Process harmonic analysis on models
            ds_models = []
            for i_mod, mod in enumerate(models):
                path_nc = f"{path_results}mod_tide_uv.nc"
                # If metazone per slice, calculate average per slice
                if flag_slice:
                    if len(mod["xarray_meta_coloc"]['idx_depth'].values) > 1:
                        mod["xarray_meta_coloc"] = mod["xarray_meta_coloc"].mean('idx_depth')

                # Calculate harmonic analysis
                ds_mod = base.comodo_tide_feature.harmonic_analysis(mod['xarray_meta_coloc'],
                                                                    'u v',
                                                                    path_nc,
                                                                    path_results,
                                                                    path_tools,
                                                                    list_waves,
                                                                    'mod')
                ds_mod = ds_mod.assign_attrs({'name': mod['name']})

                # Re-add the depth / slice values + colocate
                if "depth" in mod['xarray_meta_coloc'].dims:
                    ds_mod['depth'] = mod['xarray_meta_coloc']['depth']
                    ds_obs, ds_mod = base.colocate_all(ds_obs,
                                                       ds_mod,
                                                       False,
                                                       True,
                                                       False,
                                                       coloc_method='nearest',
                                                       opt_grid='observation')
                elif "slice" in mod['xarray_meta_coloc'].dims:
                    ds_mod['slice'] = mod['xarray_meta_coloc']['slice']
                ds_models.append(ds_mod)

            # Plot the ellipses
            base.plot_features.plot_ellipses_tide_current(ds_models, ds_obs, scale, output_path=sub_func_output_folder)


def select_point_bathy_radius(config_obj, observation, models):
    """
    Select the closest point respecting the thershold and radius criteria.
    Parameters
    ----------
    config_obj : dict
        Dictionary with observations and models names and DataSets.
    observation : dict
        Dictionary with observations.
    models: dict
        Dictionary with models.

    Returns
    -------
    models : dict
        Dictionnary with models with the updated xarray_meta_coloc with the selected point.
    """

    obs_lon, obs_lat = observation["xarray_meta"].lon.values, observation["xarray_meta"].lat.values
    if obs_lon.size > 1:
        obs_lon, obs_lat = obs_lon[0], obs_lat[0]

    # Get the criteria values
    if "bathy_min" in config_obj["meta_zones"] and "radius" in config_obj["meta_zones"]:
        min_bathy = config_obj["meta_zones"]["bathy_min"]
        radius = config_obj["meta_zones"]["radius"]
    else:
        min_bathy = None
        radius = None
        logger.info(f"Oops, pour utiliser cette fonctionnalité, vous devriez spécifier le rayon "
                    f"autour de l'observation et le seuil batyhmétrique.... Le point du modèle "
                    f"le plus proche de l'observation va ici être utilisé....")

    # Select the point which satisfies the criteria, when possible
    for i_mod, mod in enumerate(models):
        if min_bathy and radius:
            if 'bathy' in mod["xarray_meta_coloc"].variables:
                mod["xarray_meta_coloc"] = mod["xarray_meta_coloc"].meta.horizontal_selection_bathy(minimum=min_bathy)
            else:
                logger.info("Oops, le modèle ne contient pas d'information de bathymétrie, "
                            "le critère ne peut donc pas être appliqué...")

            mod["xarray_meta_coloc"] = mod["xarray_meta_coloc"].sel(lon=obs_lon, lat=obs_lat, method='nearest')
            distance = np.sqrt((mod["xarray_meta_coloc"].lon.values - obs_lon) ** 2
                               + (mod["xarray_meta_coloc"].lat.values - obs_lat) ** 2)
            radius_km = observation["xarray_meta"].meta.km_to_deg(radius)
            if distance > radius_km:
                logger.info(f'Oops, le modèle ne contient pas de point qui respecte le critère '
                            f'de bathymétrie et de rayon. Le point le plus proche respectant le '
                            f'seuil bathymétrique bathymétrique est utilisé.')
        else:
            mod["xarray_meta_coloc"] = mod["xarray_meta_coloc"].sel(lon=obs_lon, lat=obs_lat, method='nearest')

    return models
