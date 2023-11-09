"""Create figures for feature 7:currents_ADCP"""
import os
import copy
import logging
import numpy as np
from armoor.base.tools_features import remove_missing_values_ds
from armoor.base import plot_features, ttide_tide_feature
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

        # PLOTS
        ############################################################################################
        # HOVMOLLER CURRENTS
        plot_hovmoller = {"plot_hovmoller": 'plot_hovmoller'}
        if output["plot"] in plot_hovmoller:
            if 'attribute' in output:
                attribute = output["attribute"][0].replace('current_', '')
            else:
                attribute = "norm"

            # Select attribute in good format
            def to_ds_with_coords(dataset, attribute):
                dataset_coords = dataset[attribute].to_dataset().assign_coords(dataset.coords)
                dataset_coords = dataset_coords.assign_attrs(dataset.attrs)
                dataset_coords = dataset_coords.assign_attrs(dataset[attribute].attrs)
                return dataset_coords

            observation['xarray_meta'] = to_ds_with_coords(observation['xarray_meta'], attribute)
            for i_mod, mod in enumerate(models):
                mod['xarray_meta'] = to_ds_with_coords(mod['xarray_meta'], attribute)
                mod['xarray_meta_coloc'] = to_ds_with_coords(mod['xarray_meta_coloc'], attribute)
                observation['xarray_meta_coloc'][i_mod] = to_ds_with_coords(
                    observation['xarray_meta_coloc'][i_mod], attribute)

                models[i_mod] = mod

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
            # Process harmonic analysis on observation
            logger.info(f'Computing harmonic analysis for the obesrvation...')
            ds_obs = ttide_tide_feature.run_harmonic_analysis(observation["xarray_meta"], output)

            # Process harmonic analysis on models
            for i_mod, mod in enumerate(models):
                logger.info(f'Computing harmonic analysis for model {i_mod}...')
                ds_mod = ttide_tide_feature.run_harmonic_analysis(mod["xarray_meta_coloc"], output)

                # Create the table
                logger.info("Creation of tables in the directory : %s", sub_func_output_folder)
                plot_features.create_harmonic_table(ds_mod, ds_obs,
                                                    output_path=sub_func_output_folder)

        ############################################################################################
        # ELLIPSES TIDAL CURRENTS
        plot_tide_current_ellipses = {"plot_tide_current_ellipses": 'plot_tide_current_ellipses'}

        if output["plot"] in plot_tide_current_ellipses:
            # Calculate harmonic analysis
            logger.info(f'Computing harmonic analysis for the observation...')
            ds_obs = ttide_tide_feature.run_harmonic_analysis(observation["xarray_meta"], output)

            # Process harmonic analysis on models
            ds_models = []
            for i_mod, mod in enumerate(models):
                # Calculate harmonic analysis
                logger.info(f'Computing harmonic analysis for model {i_mod}...')
                ds_mod = ttide_tide_feature.run_harmonic_analysis(mod['xarray_meta_coloc'], output)

                ds_models.append(ds_mod)

            # Plot the ellipses
            plot_features.plot_ellipses_tide_current(ds_models, ds_obs, scale,
                                                     output_path=sub_func_output_folder)
