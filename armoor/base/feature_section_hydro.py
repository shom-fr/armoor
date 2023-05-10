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

    # SELECT THE VARIABLES
    observation = copy.copy(config_obj["observation"])
    models = copy.copy(config_obj["models"])

    if 'attribute' in outputs[0]:
        var0 = outputs[0]['attribute']
    else:
        raise Exception(
            "Oops, pour utiliser cette fonctionnalité, vous devriez spécifier un attribut...")
    if "list" not in str(type(var0)):
        vars = [var0]
    else:
        vars = var0
    observation["xarray_meta"] = observation["xarray_meta"].read_sst.sel(vars)

    for i_mod, mod in enumerate(models):
        mod["xarray_meta"] = mod["xarray_meta"].read_sst.sel(vars)
        mod["xarray_meta_coloc"] = mod["xarray_meta_coloc"].read_sst.sel(vars)
        observation["xarray_meta_coloc"][i_mod] = observation["xarray_meta_coloc"][i_mod].read_sst.sel(vars)

    # # Set horizontal and vertical steps
    # models, observation = base.set_hor_vert_step(config_obj, models, observation)

    # Remove missing values
    for i_mod, mod in enumerate(models):
        models, observation = base.remove_missing_values_ds(models, observation, i_mod, vars, vars)

    # PLOTS
    for index_output, output in enumerate(outputs):
        if output_path:
            sub_func_output_folder = os.path.join(output_path, output["folder_name"])
            st.create_folder(sub_func_output_folder)
        else:
            sub_func_output_folder = output_path
        ################################################################################################################
        # VARIABLE 3D SECTION
        plot_variable_3d = {"plot_variable_3d": 'variable_3d'}
        if output["plot"] in plot_variable_3d:
            base.plot_features.plot_variable_3d(models,
                                                observation,
                                                output_path=sub_func_output_folder)

        ################################################################################################################
        # TIMESERIES
        plot_variable_2d = {"plot_variable_2d": 'variable_2d'}
        if output["plot"] in plot_variable_2d:
            base.plot_features.plot_variable_2d(models,
                                                observation,
                                                output_path=sub_func_output_folder)
