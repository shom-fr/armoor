"""Create figures for feature 8:currents_VMADCP"""
import os
import copy
from armoor.base.tools_features import remove_missing_values_ds
from armoor.base import plot_features
from armoor.hmi.script_tools import create_folder


def plot(config_obj):
    """
    Plot figures required in functionality 8 : currents_VMADCP.

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

    # SELECT THE VARIABLES
    observation = copy.copy(config_obj["observation"])
    models = copy.copy(config_obj["models"])

    # PLOT
    for output in outputs:
        if output_path:
            sub_func_output_folder = os.path.join(output_path, output["folder_name"])
            create_folder(sub_func_output_folder)
        else:
            sub_func_output_folder = output_path

        # Get the figure parameters from config obj
        vmin = output.get('vmin')
        vmax = output.get('vmax')
        dvmin = output.get('dvmin')
        dvmax = output.get('dvmax')
        cmap = output.get("colormap")

        # Calculate baroclinic current
        if 'attribute' not in output or output['attribute'][0] == 'current':
            var_norm = ['norm']
            observation["xarray_meta"] = observation["xarray_meta"].sel_var.selection(['current'])
            for i_mod, mod in enumerate(models):
                mod["xarray_meta"] = mod["xarray_meta"].sel_var.selection(['current'])
                mod["xarray_meta_coloc"] = mod["xarray_meta_coloc"].sel_var.selection(['current'])
                observation["xarray_meta_coloc"][i_mod] = observation["xarray_meta_coloc"][
                    i_mod].sel_var.selection(['current'])

        elif 'attribute' in output and 'bc' in output['attribute'][0]:
            var_norm = ['norm_bc']
            observation["xarray_meta"] = observation["xarray_meta"].sel_var.selection(
                ['current_bc'])
            for i_mod, mod in enumerate(models):
                mod["xarray_meta"] = mod["xarray_meta"].sel_var.selection(['current_bc'])
                mod["xarray_meta_coloc"] = mod["xarray_meta_coloc"].sel_var.selection(
                    ['current_bc'])
                observation["xarray_meta_coloc"][i_mod] = observation["xarray_meta_coloc"][
                    i_mod].sel_var.selection(['current_bc'])
        ############################################################################################
        # VARIABLE 3D SECTION
        plot_variable_3d = {"plot_variable_3d": 'variable_3d'}
        if output["plot"] in plot_variable_3d:
            # Remove missing values
            for i_mod, mod in enumerate(models):
                models, observation = remove_missing_values_ds(models, observation, i_mod, var_norm,
                                                               var_norm)

            plot_features.plot_variable_3d(models, observation, cmap, vmin, vmax, dvmin, dvmax,
                                           output_path=sub_func_output_folder)

        ############################################################################################
        # STICKS PLOT
        plot_stick_plot = {"plot_stick_plot": 'stick_plot'}
        if output["plot"] in plot_stick_plot:
            plot_features.plot_stick_plots(models, observation, output_path=sub_func_output_folder)
