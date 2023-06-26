"""Create figures for feature 8:currents_VMADCP"""
import os
import copy
from armoor import base
import armoor.hmi.script_tools as st


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

    observation["xarray_meta"] = observation["xarray_meta"].sel_var.selection(['current'])
    for i_mod, mod in enumerate(models):
        mod["xarray_meta"] = mod["xarray_meta"].sel_var.selection(['current'])
        mod["xarray_meta_coloc"] = mod["xarray_meta_coloc"].sel_var.selection(['current'])
        observation["xarray_meta_coloc"][i_mod] = observation["xarray_meta_coloc"][i_mod].sel_var.selection(['current'])

    # PLOT
    for index_output, output in enumerate(outputs):
        if output_path:
            sub_func_output_folder = os.path.join(output_path, output["folder_name"])
            st.create_folder(sub_func_output_folder)
        else:
            sub_func_output_folder = output_path

        # Get the figure parameters from config obj
        vmin = output.get('vmin')
        vmax = output.get('vmax')
        _ = output.get('dvmin')
        _ = output.get('dvmax')
        cmap = output.get("colormap")

        ################################################################################################################
        # VARIABLE 3D SECTION
        plot_variable_3d = {"plot_variable_3d": 'variable_3d'}
        if output["plot"] in plot_variable_3d:
            # Remove missing values
            for i_mod, mod in enumerate(models):
                models, observation = base.remove_missing_values_ds(models, observation, i_mod, ['norm'], ['norm'])

            base.plot_features.plot_variable_3d(models, observation, cmap, vmin, vmax,
                                                output_path=sub_func_output_folder)

        ################################################################################################################
        # STICKS PLOT
        plot_stick_plot = {"plot_stick_plot": 'stick_plot'}
        if output["plot"] in plot_stick_plot:
            base.plot_features.plot_stick_plots(models, observation, output_path=sub_func_output_folder)
