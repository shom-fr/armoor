"""Common tools for all features"""
import os
import logging
import copy
import numpy as np
import pandas as pd
import logging
import calendar
import matplotlib.pyplot as plt

logger = logging.getLogger(__name__)


def manage_output(plot, figure_name, folder_path):
    """

    Parameters
    ----------
    plot
    figure_name
    folder_path

    Returns
    -------

    """
    if folder_path:
        figure_name = figure_name.replace(' ', '_').replace('[', '').replace(']', '').replace('/',
                                                                                              '')
        date_now = np.datetime_as_string(np.datetime64('now'), unit='s').replace('-', '').replace(
            ':', '')
        # path = os.path.join(folder_path, f'{figure_name}_{date_now}.png')
        path = os.path.join(folder_path, f'{figure_name}.png')
        path = path.replace(':', '-')
        path = path.replace(' ', '')
        logger.info(f'Saving :: {path}')
        plot.savefig(path, bbox_inches='tight', format='png')
        plot.close('all')
    else:
        plot.show()


def remove_missing_values_ds(models, observation, i, var_mod, vars):

    # Remove missing values
    if len(var_mod) == 1:
        obs = observation["xarray_meta_coloc"][i][vars[0]]
        mod = models[i]["xarray_meta_coloc"][var_mod[0]]

        mod, obs = remove_missing_values(mod, obs)
        observation["xarray_meta_coloc"][i][vars[0]] = obs
        models[i]["xarray_meta_coloc"][var_mod[0]] = mod
    else:
        for i_var, var in enumerate(var_mod):
            obs = observation["xarray_meta_coloc"][i][vars[i_var]]
            mod = models[i]["xarray_meta_coloc"][var_mod[i_var]]
            mod, obs = remove_missing_values(mod, obs)
            observation["xarray_meta_coloc"][i][vars[i_var]] = obs
            models[i]["xarray_meta_coloc"][var_mod[i_var]] = mod

    return models, observation


def remove_missing_values(model, obs):
    """
    Remove the missing values in model and observation to retrieve the two datasets on the exact same extents.
    Parameters
    ----------
    model : xr.DataArray
        Model data array.
    obs : xr.DataArray
        Observation data array.

    Returns
    -------
    model_nan : xr.Dataset
        Model dataset with the same missing values as the observation.
    obs_nan : xr.Dataset
        Observation dataset with the same missing values as the model.

    """
    if list(obs.dims) != list(model.dims):
        if len(obs.dims) > 1:
            for dim in list(obs.dims):
                model = model.transpose(dim, ...).squeeze()
                obs = obs.transpose(dim, ...).squeeze()

    for coord in ['sig', 's_rho']:
        if coord in model.coords:
            model = model.drop(coord)
        if coord in obs.coords:
            obs = obs.drop(coord)

    # .values otherwise returns all NaN for croco and topaz
    model_nan = model.where(~np.isnan(obs).values)
    obs_nan = obs.where(~np.isnan(model).values)

    list_coord_mod = list(model_nan.coords.keys())
    list_coord_obs = list(obs_nan.coords.keys())
    if sorted(list_coord_mod) != sorted(list_coord_obs):
        model_nan = model_nan.assign_coords(model.coords)
        obs_nan = obs_nan.assign_coords(obs.coords)

    # Put dimension in the right order
    obs_nan = set_dim_order(obs_nan)
    model_nan = set_dim_order(model_nan)
    return model_nan, obs_nan


def set_dim_order(ds):
    if 'lon' in list(ds.squeeze().dims):
        ds = ds.transpose('lat', 'lon', ...)
    elif 'x' in list(ds.squeeze().dims):
        ds = ds.transpose('y', 'x', ...)
    return ds


def sel_default_vars(config_obj):
    """
    Select the default and optional parameters in the model and observation datasets from the config_obj
    Parameters
    ----------
    config_obj : dict
        Meta-zone, models and observation from the parser.

    Returns
    -------
    config_obj : dict
        Meta-zone, models and observation from the parser with the selected variables.
    """
    feature = config_obj["functionality"]

    additional_vars = config_obj['meta_zones']['vars'] if 'vars' in config_obj['meta_zones'] else []
    if feature == "sst":  # F1
        default_vars_mod = ['SST']
        default_vars_obs = ['SST']

    elif feature == "prof_hydro_vessel":  # F2
        default_vars_mod = ['ptemp', 'sal', 'pdens']
        default_vars_obs = ['temp', 'sal', 'dens']
        for var in ['temp', 'ptemp', 'dens', 'pdens']:
            if var in additional_vars:
                additional_vars.remove(var)

    elif feature == "prof_hydro_mooring":  # F3
        default_vars_mod = ['ptemp', 'sal', 'pdens']
        default_vars_obs = ['temp', 'sal', 'dens']
        for var in ['temp', 'ptemp', 'dens', 'pdens']:
            if var in additional_vars:
                additional_vars.remove(var)

    elif feature == "section_hydro":  # F4
        default_vars_mod = ['ptemp', 'sal']
        default_vars_obs = ['temp', 'sal']
        for var in ['temp', 'ptemp', 'dens', 'pdens']:
            if var in additional_vars:
                additional_vars.remove(var)

    elif feature == "clim_hydro":  # F5
        default_vars_mod = ['ptemp', 'sal']
        default_vars_obs = ['temp', 'sal']
        for var in ['temp', 'ptemp', 'dens', 'pdens']:
            if var in additional_vars:
                additional_vars.remove(var)

    elif feature == "currents_hfr":  # F6
        default_vars_mod = ['current']
        default_vars_obs = ['current']

    elif feature == "currents_ADCP":  # F7
        default_vars_mod = ['current']
        default_vars_obs = ['current']

    elif feature == "currents_VMADCP":  # F8
        default_vars_mod = ['current']
        default_vars_obs = ['current']

    elif feature == "drifters":  # F9
        default_vars_mod = ['current']
        default_vars_obs = ['current']

    vars_mod = default_vars_mod + additional_vars
    vars_obs = default_vars_obs + additional_vars

    if feature == "clim_hydro":  # Calculate climatologies
        config_obj['observation']["xarray_meta"] = config_obj['observation'][
            "xarray_meta"].sel_var.selection(vars_obs)
        for i_mod, mod in enumerate(config_obj['models']):
            mod["xarray_meta"] = mod["xarray_meta"].sel_var.selection(vars_mod).groupby(
                "time.month").mean("time").rename({'month': 'time'})
            mod["xarray_meta_coloc"] = mod["xarray_meta_coloc"].sel_var.selection(vars_mod).groupby(
                "time.month").mean("time").rename({'month': 'time'}).assign_coords(
                {'time': calendar.month_name[1:13]})
            config_obj['observation']["xarray_meta_coloc"][i_mod] = \
                config_obj['observation']["xarray_meta_coloc"][i_mod].sel_var.selection(
                    vars_obs).assign_coords({'time': calendar.month_name[1:13]})
    else:
        config_obj['observation']["xarray_meta"] = config_obj['observation'][
            "xarray_meta"].sel_var.selection(vars_obs)
        for i_mod, mod in enumerate(config_obj['models']):
            mod["xarray_meta"] = mod["xarray_meta"].sel_var.selection(vars_mod)
            mod["xarray_meta_coloc"] = mod["xarray_meta_coloc"].sel_var.selection(vars_mod)
            config_obj['observation']["xarray_meta_coloc"][i_mod] = \
                config_obj['observation']["xarray_meta_coloc"][i_mod].sel_var.selection(vars_obs)

    return config_obj


def sel_one_var(observation, models, var):
    # Adjust potential / insitu variables for models and obs
    observation_var = copy.deepcopy(observation)
    models_var = copy.deepcopy(models)

    if var in ['temp', 'ptemp']:
        var_mod = 'ptemp'
        var_obs = 'temp'
    elif var in ['dens', 'pdens']:
        var_mod = 'pdens'
        var_obs = 'dens'
    else:
        var_mod = var
        var_obs = var

    observation_var['xarray_meta'] = observation_var['xarray_meta'][var_obs]
    for i_mod, mod in enumerate(models_var):
        mod["xarray_meta"] = mod["xarray_meta"][var_mod]
        mod["xarray_meta_coloc"] = mod["xarray_meta_coloc"][var_mod]
        observation_var["xarray_meta_coloc"][i_mod] = observation_var["xarray_meta_coloc"][i_mod][
            var_obs]
    observation_var['name'] = observation['name']
    return observation_var, models_var


def check_same_variables(models, observation):
    # Verify the same variables are in the model and observation
    for i, mod in enumerate(models):
        for var_mod in list(mod['xarray_meta'].keys()):
            if var_mod not in observation:
                logger.warning(f"{var_mod} is not included in the observation product ; "
                               f"it is thus removed from model {imod}")
                model = model.drop(var_mod)
        for var_obs in list(observation['xarray_meta'].keys()):
            if var_obs not in mod['xarray_meta']:
                logger.warning(f"{var_obs} is not included in model {imod} ; "
                               f"it is thus removed from observation")
                observation['xarray_meta'] = observation['xarray_meta'].drop(var_obs)
    return models, observation
