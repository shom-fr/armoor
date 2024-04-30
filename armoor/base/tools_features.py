"""Common tools for all features"""
import os
import logging
import copy
import calendar
import numpy as np
import math
import matplotlib.pyplot as plt

logger = logging.getLogger(__name__)


def manage_output(figure_name, folder_path):
    """

    Parameters
    ----------
    figure_name
    folder_path

    Returns
    -------

    """
    if folder_path:
        figure_name = figure_name.replace(' ', '_').replace('[', '').replace(']', '').replace('/',
                                                                                              '')
        path = os.path.join(folder_path, f'{figure_name}.png')
        path = path.replace(':', '-')
        path = path.replace(' ', '')
        logger.info('Saving :: %s', path)
        plt.savefig(path, bbox_inches='tight', format='png')
        plt.close('all')
    else:
        plt.show()


def remove_missing_values_ds(models, observation, i, vars):
    """
    Remove the missing values in model and observation to retrieve the two datasets
    on the exact same extents.
    Parameters
    ----------
    models : list of xarray.dataset
    observation : dict of xarray.dataset
    i : int
        Index of the model to consider.
    vars_mod : list
        List of the variables to consider in the model.
    vars_obs : list
        List of the variables to consider in the observation.

    """
    # Remove missing values
    if len(vars) == 1 and vars != 'mld':
        obs = observation["xarray_meta_coloc"][i][vars[0]]
        mod = models[i]["xarray_meta_coloc"][vars[0]]

        mod, obs = remove_missing_values(mod, obs)
        observation["xarray_meta_coloc"][i][vars[0]] = obs
        models[i]["xarray_meta_coloc"][vars[0]] = mod
    else:
        for i_var, var in enumerate(vars):
            if var != 'mld':
                obs = observation["xarray_meta_coloc"][i][var]
                mod = models[i]["xarray_meta_coloc"][var]
                mod, obs = remove_missing_values(mod, obs)
                observation["xarray_meta_coloc"][i][var] = obs
                models[i]["xarray_meta_coloc"][var] = mod

    return models, observation


def angle_between_vectors(pointA, pointB, pointC):
    """
    Calculate the angle in degrees between vectors AB and AC.
    Parameters
    ----------
    Args:
        pointA : xarray.dataset
            Coordinates of point A as a tuple (lon, lat).
        pointB : xarray.dataset
            Coordinates of point B as a tuple (lon, lat).
        pointC : xarray.dataset
            Coordinates of point C as a tuple (lon, lat).

    Returns:
        float: The angle in degrees between vectors AB and AC.

    """
    # Calculate vectors AB and AC
    vectorAB = (pointB.lon.data - pointA.lon.data, pointB.lat.data - pointA.lat.data)
    vectorAC = (pointC.lon.data - pointA.lon.data, pointC.lat.data - pointA.lat.data)

    # Calculate the dot product of vectors AB and AC
    dot_product = vectorAB[0] * vectorAC[0] + vectorAB[1] * vectorAC[1]

    # Calculate the magnitudes of vectors AB and AC
    magnitude_AB = math.sqrt(vectorAB[0] ** 2 + vectorAB[1] ** 2)
    magnitude_AC = math.sqrt(vectorAC[0] ** 2 + vectorAC[1] ** 2)

    # Calculate the angle in radians between vectors AB and AC using the dot product formula
    cosine_theta = dot_product / (magnitude_AB * magnitude_AC)
    if cosine_theta > 1:
        cosine_theta = 1
    theta_rad = math.acos(cosine_theta)

    # Convert the angle to degrees
    theta_deg = math.degrees(theta_rad)

    return theta_deg


def remove_missing_values(model, obs):
    """
    Remove the missing values in model and observation to retrieve the two datasets
    on the exact same extents.
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
                model = model.transpose(dim, ...)
                obs = obs.transpose(dim, ...)

    # if the shapes are not the same between datarrays:
    if obs.shape == model.shape[:-1]:
        model = model.squeeze()

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


def set_dim_order(dataset):
    """
    Clean the dimension order to ensure maps will be correctly plotted.
    Parameters
    ----------
    dataset : xarray.dataset
    """
    if 'lon' in list(dataset.squeeze().dims):
        dataset = dataset.transpose('lat', 'lon', ...)
    elif 'x' in list(dataset.squeeze().dims):
        dataset = dataset.transpose('y', 'x', ...)
    return dataset


def sel_default_vars(config_obj):
    """
    Select the default and optional parameters in the model and observation datasets
    from the config_obj
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
        default_vars = ['SST']

    elif feature == "prof_hydro_vessel":  # F2
        default_vars = ['ptemp', 'sal', 'pdens']

    elif feature == "prof_hydro_mooring":  # F3
        default_vars = ['ptemp', 'sal', 'pdens']

    elif feature == "section_hydro":  # F4
        default_vars = ['ptemp', 'sal']

    elif feature == "clim_hydro":  # F5
        default_vars = ['ptemp', 'sal']

    elif feature == "currents_hfr":  # F6
        default_vars = ['current', 'current_res']

    elif feature == "currents_ADCP":  # F7
        default_vars = ['current', 'current_res']

    elif feature == "currents_VMADCP":  # F8
        default_vars = ['current']

    elif feature == "drifters":  # F9
        default_vars = ['current']

    vars = default_vars + additional_vars

    if feature == "clim_hydro":  # Calculate climatologies
        config_obj['observation']["xarray_meta"] = config_obj['observation'][
            "xarray_meta"].sel_var.selection(vars)
        for i_mod, mod in enumerate(config_obj['models']):
            mod["xarray_meta"] = mod["xarray_meta"].sel_var.selection(vars).groupby(
                "time.month").mean("time").rename({'month': 'time'})

            # Get month names
            mod["xarray_meta_coloc"] = mod["xarray_meta_coloc"].sel_var.selection(vars).groupby(
                "time.month").mean("time").rename({'month': 'time'})
            months = [calendar.month_name[i] for i in mod["xarray_meta_coloc"].time.data]
            mod["xarray_meta_coloc"] = mod["xarray_meta_coloc"].assign_coords({'time': months})

            config_obj['observation']["xarray_meta_coloc"][i_mod] = \
                config_obj['observation']["xarray_meta_coloc"][i_mod].sel_var.selection(
                    vars).assign_coords({'time': months})
    else:
        config_obj['observation']["xarray_meta"] = config_obj['observation'][
            "xarray_meta"].sel_var.selection(vars)
        for i_mod, mod in enumerate(config_obj['models']):
            mod["xarray_meta"] = mod["xarray_meta"].sel_var.selection(vars)
            mod["xarray_meta_coloc"] = mod["xarray_meta_coloc"].sel_var.selection(vars)
            config_obj['observation']["xarray_meta_coloc"][i_mod] = \
                config_obj['observation']["xarray_meta_coloc"][i_mod].sel_var.selection(vars)

    return config_obj


def sel_one_var(observation, models, var, depth=None):
    """
    Select a variable in the model and observation
    Parameters
    ----------
    models : list of xarray.dataset
    observation : dict of xarray.dataset
    var : str
    """
    # Avoid deep copy
    observation_var = dict()
    observation_var["xarray_meta_coloc"] = []

    models_var = [dict() for _ in models]
    for key in ['name', 'method', 'xarray']:
        if key in list(observation.keys()):
            observation_var[key] = observation[key]
        for i_mod, mod in enumerate(models):
            if key in list(mod.keys()):
                models_var[i_mod][key] = mod[key]

    # Select variable and add mod/obs name, in meta products
    if var in observation['xarray_meta']:
        observation_var['xarray_meta'] = observation['xarray_meta'][var].assign_attrs(
            {'name': observation['name']})
        for i_mod, mod in enumerate(models):
            models_var[i_mod]["xarray_meta"] = mod["xarray_meta"][var].assign_attrs(
                {'name': mod['name']})

    # Select variable and add mod/obs name, in meta coloc products
    for i_mod, mod in enumerate(models):
        models_var[i_mod]["xarray_meta_coloc"] = mod["xarray_meta_coloc"][var].assign_attrs(
            {'name': mod['name']})
        observation_var["xarray_meta_coloc"].append(
            observation["xarray_meta_coloc"][i_mod][var].assign_attrs(
                {'name': observation['name']}))

    # Select depth if needed
    if depth:
        observation_var['xarray_meta'] = observation_var['xarray_meta'].sel(depth=depth,
                                                                            method='nearest')
        for i_mod, mod in enumerate(models_var):
            models_var[i_mod]["xarray_meta"] = models_var[i_mod]["xarray_meta"].sel(depth=depth,
                                                                                    method='nearest')
            models_var[i_mod]["xarray_meta_coloc"] = models_var[i_mod]["xarray_meta_coloc"].sel(
                depth=depth, method='nearest')
            observation_var["xarray_meta_coloc"][i_mod] = observation_var["xarray_meta_coloc"][
                i_mod].sel(depth=depth, method='nearest')

    # Bathy thresh in attrs if needed
    list_attrs = ["bathy_thresh", "radius", "depth_meta_zone", "cloud", "echeances"]
    for attr in list_attrs:
        if attr in observation["xarray_meta"].attrs:
            attr_name = observation['xarray_meta'].attrs[attr]
            observation_var['xarray_meta'] = observation_var['xarray_meta'].assign_attrs({attr:attr_name})
            for i_mod, mod in enumerate(models_var):
                models_var[i_mod]["xarray_meta"] = models_var[i_mod]["xarray_meta"].assign_attrs({attr:attr_name})
                observation_var['xarray_meta_coloc'][i_mod] = observation_var[
                    'xarray_meta_coloc'][i_mod].assign_attrs({attr:attr_name})

    return observation_var, models_var


def check_same_variables(models, observation):
    """
    Verify that the model and observation have the same variables
    Parameters
    ----------
    models : list of xarray.dataset
    observation : dict of xarray.dataset

    """
    # Verify the same variables are in the model and observation
    for imod, mod in enumerate(models):
        for var_mod in list(mod['xarray_meta'].keys()):
            if var_mod not in observation:
                logger.warning("%s is not included in the observation product ; "
                               "it is thus removed from model %s", var_mod, imod)
                model = model.drop(var_mod)
        for var_obs in list(observation['xarray_meta'].keys()):
            if var_obs not in mod['xarray_meta']:
                logger.warning("%s is not included in the observation product ; "
                               "it is thus removed from model %s", var_obs, imod)
                observation['xarray_meta'] = observation['xarray_meta'].drop(var_obs)
    return models, observation
