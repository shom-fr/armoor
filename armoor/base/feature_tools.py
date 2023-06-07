"""Common tools for all features"""
import os
import logging

import numpy as np
import pandas as pd
import logging

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
        figure_name = figure_name.replace(' ', '_').replace('[', '').replace(']', '').replace('/', '')
        date_now = np.datetime_as_string(np.datetime64('now'), unit='s').replace('-', '').replace(':', '')
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
        obs = observation["xarray_meta_coloc"][i]
        mod = models[i]["xarray_meta_coloc"]
        mod, obs = remove_missing_values(mod, obs)
        observation["xarray_meta_coloc"][i] = obs
        models[i]["xarray_meta_coloc"] = mod
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
    if np.size(np.unique(model.lon.data)) == np.size(model.lon.data):  # Verify no duplicates in coords
        model_nan = model.where(~np.isnan(obs))
        obs_nan = obs.where(~np.isnan(model))
        model_nan = model_nan.assign_coords(model.coords)
        if obs_nan.dims != obs.dims:
            obs_nan = obs_nan.squeeze()
        if len(list(obs_nan.coords)) <= len(list(obs.coords)):
            obs_nan = obs_nan.assign_coords(obs.coords)
        return model_nan, obs_nan
    else:
        return model, obs
