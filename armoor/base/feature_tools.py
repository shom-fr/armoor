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
        figure_name = figure_name.replace(':', '-')
        figure_name = figure_name.replace(' ', '')
        path = os.path.join(folder_path, f'{figure_name}.png')
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
        obs_nan = obs_nan.assign_coords(obs.coords)
        return model_nan, obs_nan
    else:
        return model, obs


def set_hor_vert_step(config_obj, models, observation):
    """
    The model and obs have already been colocated to match the observation location, here we create the projection
    for the figure.
    Parameters
    ----------
    config_obj: dict
        Dictionary with observations and models names and DataSets.
    observation : dict
        Dictionary with observations.
    models: dict
        Dictionary with models.
    Returns
    -------
    models : dict
        Dictionnary with models with the updated projection grid.
    observation : dict
        Dictionnary with models with the updated projection grid.
    """
    for i_mod, mod in enumerate(models):
        tgt_name = config_obj["colocate"]
        tgt = mod["xarray_meta_coloc"] if tgt_name == 'model' else observation["xarray_meta_coloc"][i_mod]

        # Horizontal colocation
        if config_obj["horizontal_step"]:
            hor_step = float(config_obj["horizontal_step"])
            hor_step = observation["xarray_meta_coloc"][i_mod].meta.km_to_deg(hor_step)

            # Calculate the time step and distance step in the data
            pos0, pos1 = mod["xarray_meta_coloc"].isel(time=0), mod["xarray_meta_coloc"].isel(time=1)
            time_step_data = pos1.time.data - pos0.time.data
            dist_step = np.sqrt((pos1.lon - pos0.lon) ** 2 + (pos1.lat - pos0.lat) ** 2)
            time_step = time_step_data * hor_step / dist_step
            time_step = time_step.data.astype('timedelta64[s]')
            time_step = str(time_step).split()[0] + 'S'
            time_min, time_max = mod["xarray_meta_coloc"].time[0].data, mod["xarray_meta_coloc"].time[-1].data
            time_min, time_max = np.datetime64(time_min), np.datetime64(time_max)

            # Create the new times array to select to retrieve the horizontal resolution
            tgt_time = pd.date_range(time_min, time_max, freq=time_step)

            # Interpolate the model and obs on the targeted times
            mod["xarray_meta_coloc"] = mod["xarray_meta_coloc"].interp(time=tgt_time, method='linear')
            observation["xarray_meta_coloc"][i_mod] = observation["xarray_meta_coloc"][i_mod].interp(time=tgt_time,
                                                                                                     method='linear')

        # Vertical colocation
        if config_obj["vertical_step"]:
            vert_step = config_obj["vertical_step"]
            depth_min, depth_max = tgt.depth.min(), tgt.depth.max()
            tgt_depth = np.arange(depth_min, depth_max, vert_step)
            if 'depth' in mod["xarray_meta_coloc"].dims:
                mod["xarray_meta_coloc"] = mod["xarray_meta_coloc"].interp(depth=tgt_depth, method="linear")
            if 'depth' in observation["xarray_meta_coloc"][i_mod].dims:
                observation["xarray_meta_coloc"][i_mod] = observation["xarray_meta_coloc"][i_mod].interp(
                    depth=tgt_depth, method="linear")

    return models, observation
