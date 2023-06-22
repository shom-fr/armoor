"""Create figures for feature 4:section_hydro"""
import os
import copy
from armoor import base
import armoor.hmi.script_tools as st


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
    outputs = config_obj["outputs"]
    output_path = config_obj.get("output_path")

    # Select the variables
    config_obj = base.sel_default_vars(config_obj)
    observation = copy.copy(config_obj["observation"])
    models = copy.copy(config_obj["models"])

    # Remove missing values
    vars = [var for var in list(observation["xarray_meta"].keys()) if var in models[0]["xarray_meta"]]
    vars_mod = copy.copy(vars)
    if 'temp' in vars_mod:
        vars_mod[vars_mod.index('temp')] = 'ptemp'
    for i_mod, mod in enumerate(models):
        models, observation = base.remove_missing_values_ds(models, observation, i_mod, vars_mod, vars)

    # PLOTS
    for index_output, output in enumerate(outputs):
        if output_path:
            sub_func_output_folder = os.path.join(output_path, output["folder_name"])
            st.create_folder(sub_func_output_folder)
        else:
            sub_func_output_folder = output_path

        for var in vars:
            observation_var, models_var = base.sel_one_var(observation, models, var)
            ############################################################################################################
            # VARIABLE 3D SECTION
            plot_variable_3d = {"plot_variable_3d": 'variable_3d'}
            if output["plot"] in plot_variable_3d:
                base.plot_features.plot_variable_3d(models_var, observation_var, output_path=sub_func_output_folder)

            ############################################################################################################
            # TIMESERIES
            plot_variable_2d = {"plot_variable_2d": 'variable_2d'}
            if output["plot"] in plot_variable_2d:
                base.plot_features.plot_variable_2d(models_var, observation_var, output_path=sub_func_output_folder)
