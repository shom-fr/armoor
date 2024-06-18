"""Create figures for feature 7:currents_ADCP"""
import os
import copy
import logging
import numpy as np
from armoor.base.tools_features import sel_one_var
from armoor.base import plot_features, utide_ttide_tide_feature
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
        # Otherwise select total current
        else:
            observation["xarray_meta"] = observation["xarray_meta"].sel_var.selection(['current'])
            for i_mod, mod in enumerate(models):
                mod["xarray_meta"] = mod["xarray_meta"].sel_var.selection(['current'])
                mod["xarray_meta_coloc"] = mod["xarray_meta_coloc"].sel_var.selection(['current'])
                observation["xarray_meta_coloc"][i_mod] = observation["xarray_meta_coloc"][
                    i_mod].sel_var.selection(['current'])
        # Calculate baroclinic current
        if 'attribute' in output and 'bc' in output['attribute'][0]:
            observation["xarray_meta"] = observation["xarray_meta"].sel_var.selection(
                ['current_bc'])
            for i_mod, mod in enumerate(models):
                mod["xarray_meta"] = mod["xarray_meta"].sel_var.selection(['current_bc'])
                mod["xarray_meta_coloc"] = mod["xarray_meta_coloc"].sel_var.selection(
                    ['current_bc'])
                observation["xarray_meta_coloc"][i_mod] = observation["xarray_meta_coloc"][
                    i_mod].sel_var.selection(['current_bc'])

        # PLOTS
        ############################################################################################
        # HOVMOLLER CURRENTS
        plot_hovmoller = {"plot_hovmoller": 'plot_hovmoller'}
        if output["plot"] in plot_hovmoller:
            # Select the attributes to plot
            if 'attribute' in output:
                if output["attribute"] == ['current_res']:
                    attributes = ['u_res', 'v_res', 'norm_res', 'dir_res']
                elif output["attribute"] == ['current_bc']:
                    attributes = ['u_bc', 'v_bc', 'norm_bc', 'dir_bc']
                else:
                    attributes = ['u', 'v', 'norm', 'dir']
            else:
                attributes = ['u', 'v', 'norm', 'dir']

            for attribute in attributes:
                obs_var, mods_var = sel_one_var(observation, models, attribute)

                plot_features.plot_variable_3d(mods_var, obs_var, cmap, vmin, vmax, dvmin, dvmax,
                                               output_path=sub_func_output_folder)

        ############################################################################################
        # HARMONIC TABLES
        harmonic_table = {"harmonic_table": 'harmonic_table'}
        if output["plot"] in harmonic_table:
            # Process harmonic analysis on observation
            logger.info(f'Computing harmonic analysis for the obesrvation...')
            ds_obs = utide_ttide_tide_feature.run_harmonic_analysis(observation["xarray_meta"], output)

            # Process harmonic analysis on models
            for i_mod, mod in enumerate(models):
                logger.info(f'Computing harmonic analysis for model {i_mod}...')
                ds_mod = utide_ttide_tide_feature.run_harmonic_analysis(mod["xarray_meta_coloc"], output)

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
            ds_obs = utide_ttide_tide_feature.run_harmonic_analysis(observation["xarray_meta"], output)

            # Process harmonic analysis on models
            ds_models = []
            for i_mod, mod in enumerate(models):
                # Calculate harmonic analysis
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

            # Plot the ellipses
            plot_features.plot_ellipses_tide_current(ds_models, ds_obs, scale,
                                                     output_path=sub_func_output_folder)
