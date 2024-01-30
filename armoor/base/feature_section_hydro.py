"""Create figures for feature 4:section_hydro"""
import os
import copy
import xarray as xr
from armoor.base.tools_features import remove_missing_values_ds, sel_one_var, sel_default_vars
from armoor.base import plot_features
from armoor.hmi.script_tools import create_folder
import logging

logger = logging.getLogger(__name__)

def plot(config_obj):
    """
    Plot figures required in functionality 4 : section_hydro.

    Parameters
    ----------
    config_obj : dict
        Dictionary with observations and models names and DataSets.

    Returns
    -------
    str
        Path to the generated figures.

    """

    # Select the variables
    outputs = config_obj["outputs"]
    output_path = config_obj.get("output_path")
    config_obj = sel_default_vars(config_obj)
    observation = copy.copy(config_obj["observation"])
    models = copy.copy(config_obj["models"])

    # Select geostrophic current if required
    vars_to_plot = [output['attribute'][0] for output in outputs if 'attribute' in output]
    if 'current_geo' in vars_to_plot:
        for i_mod, mod in enumerate(models):
            logger.info(f'Selecting geostrophic current for colocated observation {i_mod}')
            observation["xarray_meta_coloc"][i_mod] = xr.merge(
                [observation["xarray_meta_coloc"][i_mod],
                 observation["xarray_meta_coloc"][i_mod].sel_var.sel_current_geo()])

            logger.info(f'Selecting geostrophic current for colocated model {i_mod}')
            mod["xarray_meta_coloc"] = xr.merge(
                [mod["xarray_meta_coloc"],
                 mod["xarray_meta_coloc"].sel_var.sel_current_geo()])


    # Remove missing values
    vars = [var for var in list(observation["xarray_meta_coloc"][0].keys()) if
            var in models[0]["xarray_meta_coloc"]]

    for i_mod, mod in enumerate(models):
        models, observation = remove_missing_values_ds(models, observation, i_mod, vars)

    # PLOTS
    for output in outputs:

        # Get the figure parameters from config obj
        vmin = output.get('vmin')
        vmax = output.get('vmax')
        dvmin = output.get('dvmin')
        dvmax = output.get('dvmax')
        cmap = output.get("colormap")

        if output_path:
            sub_func_output_folder = os.path.join(output_path, output["folder_name"])
            create_folder(sub_func_output_folder)
        else:
            sub_func_output_folder = output_path

        for var in vars:
            observation_var, models_var = sel_one_var(observation, models, var)
            ########################################################################################
            # VARIABLE 3D SECTION
            plot_variable_3d = {"plot_variable_3d": 'variable_3d'}
            if output["plot"] in plot_variable_3d:
                plot_features.plot_variable_3d(models_var, observation_var, cmap, vmin, vmax, dvmin,
                                               dvmax, output_path=sub_func_output_folder)
            ########################################################################################
            # TIMESERIES
            plot_variable_2d = {"plot_variable_2d": 'variable_2d'}
            if output["plot"] in plot_variable_2d:
                plot_features.plot_variable_2d(models_var, observation_var,
                                               output_path=sub_func_output_folder)
