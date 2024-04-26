"""Create figures for feature 9:drifters"""
import os
import copy
import logging
import pandas
import numpy as np
from armoor.hmi.script_tools import create_folder
from armoor.base import plot_features, opendrift_trajectory
from armoor.base.colocation import convert_curv_rect

logger = logging.getLogger(__name__)


def plot(config_obj):
    """
        Plot figures required in functionality 9 : drifters.

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

    # Currents not always necessary in obs
    for i_mod, mod in enumerate(models):
        mod["xarray_meta"] = mod["xarray_meta"].sel_var.selection(['current']).assign_attrs(
            {'name': mod['name']})
        mod["xarray_meta_coloc"] = mod["xarray_meta_coloc"].sel_var.selection(
            ['current']).assign_attrs({'name': mod['name']})

    # PLOT
    for output in outputs:
        if output_path:
            sub_func_output_folder = os.path.join(output_path, output["folder_name"])
            create_folder(sub_func_output_folder)
        else:
            sub_func_output_folder = output_path
        
        # PLOTS
        ############################################################################################
        # MAP CURRENTS TRAJECTORY
        plot_map_current_traj = {"map_current_trajectory": 'map_current_trajectory'}
        if output["plot"] in plot_map_current_traj:
            # Select current in obs
            observation["xarray_meta"] = observation["xarray_meta"].sel_var.selection(
                ['current']).assign_attrs({'name': observation['name']})
            for i_mod, mod in enumerate(models):
                # observation["xarray_meta_coloc"][i_mod] = observation["xarray_meta_coloc"][
                #     i_mod].sel_var.selection(['current']).assign_attrs(
                #     {'name': observation['name']})
                
                # Determine which obs depth contains data
                if ('depth' in observation["xarray_meta"].dims) and ('depth' in mod["xarray_meta_coloc"].dims):
                    depth_with_data = None
                    # Loop over every depth
                    for i, d in enumerate(observation["xarray_meta"].depth):
                        ids = observation["xarray_meta"].isel(depth=i)
                        # Pick the first depth that isn't full of nodata values
                        if not np.all(np.isnan(ids.u)):
                            depth_with_data = i
                            break
                        if depth_with_data is None:
                            logger.warning("No data on obs")
                    # Subset obs and mod to select the right depth
                    observation["xarray_meta"] = observation["xarray_meta"].isel(depth=depth_with_data)
                    print('mod["xarray_meta_coloc"] has type', type(mod["xarray_meta_coloc"]))
                    mod["xarray_meta_coloc"]= mod["xarray_meta_coloc"].isel(depth=depth_with_data) 
                
                # Plot
                plot_features.plot_map_current_trajectory(observation, mod,
                                                          output_path=sub_func_output_folder)

        ############################################################################################
        # MAP TRAJECTORY
        plot_map_traj = {"map_trajectory": 'map_trajectory'}
        if output["plot"] in plot_map_traj:
            # Define path where to save the trajectories
            if 'path_results_traj' in output:
                path_results = output["path_results_traj"]
                create_folder(path_results)
            else:
                raise ValueError("Oops, pour calculer les trajectoires vous devriez spécifier"
                                 " le chemin où sauvegarder les fichiers résultats...")

            # Retrieve the common period
            date_start = max(observation["xarray_meta"].time[0].values,
                             models[0]["xarray_meta_coloc"].time[0].values)
            date_end = min(observation["xarray_meta"].time[-1].values,
                           models[0]["xarray_meta_coloc"].time[-1].values)
            observation['xarray_meta'] = observation['xarray_meta'].sel(
                time=slice(date_start, date_end))

            # Get the parameters for the OpenDrift calculation
            lons, lats, times, time_step, nb_step = param_pour_opendrift(observation)

            # Define the duration of simulated trajectories to plot
            if 'traj_duration_plot' in output:
                traj_duration_plot = output["traj_duration_plot"]
            else:
                traj_duration_plot = int(36000 / time_step)
                logger.warning("You should specify the duration (in s) for the trajectories "
                               "to display. It is arbitrarily set at 10 hours")

            # Define the frequency of simulated trajectories to plot (ex: plot 1 traj every 5h)
            if 'traj_freq_plot' in output:
                traj_freq_plot = output["traj_freq_plot"]
            else:
                traj_freq_plot = 1
                logger.warning("You should specify the frequency (in s) for the trajectories "
                               "to display. All simulated trajectories will be displayed.")

            # Calculate the trajectories
            for i_mod, mod in enumerate(models):
                # If curviliear data, regrid
                mod_meta = mod['xarray_meta']
                if 'x' in mod_meta.dims:
                    lon_tgt = np.linspace(mod_meta.lon.min(skipna=True),
                                          mod_meta.lon.max(skipna=True), len(mod_meta.x))
                    lat_tgt = np.linspace(mod_meta.lat.min(skipna=True),
                                          mod_meta.lat.max(skipna=True), len(mod_meta.y))
                    mod['xarray_meta'] = convert_curv_rect(mod_meta, lon_tgt, lat_tgt)

                # Create the formatted file for OpenDrift
                output_file = os.path.join(path_results,
                                           f'trajectory_{observation.name}_{mod.name}.nc')
                path_model = os.path.join(path_results, f'{mod.name}.nc')
                opendrift_trajectory.format_opendrift(mod, path_model)

                # Calculate the trajectories from the model
                mod_traj = opendrift_trajectory.calculate_trajectory(path_model, lons, lats, times,
                                                                     time_step, nb_step,
                                                                     output_file)
                models[i_mod]['traj'] = mod_traj

            # Plot the trajectories
            plot_features.plot_map_trajectory(observation, models, traj_duration_plot,
                                              traj_freq_plot, time_step,
                                              output_path=sub_func_output_folder)

        ############################################################################################
        # PLOT DIFFERENCE DISTANCE DIRECTION
        plot_diff_traj = {"plot_diff_traj_dist": 'distance', "plot_diff_traj_dir": 'direction'
                          }
        if output["plot"] in plot_diff_traj:
            # Define path where to save the trajectories
            if 'path_results_traj' in output:
                path_results = output["path_results_traj"]
                create_folder(path_results)
            else:
                raise ValueError("Oops, pour calculer les trajectoires vous devriez spécifier"
                                 " le chemin où sauvegarder les fichiers résultats...")

            # Retrieve the common period
            date_start = max(observation["xarray_meta"].time[0].values,
                             models[0]["xarray_meta_coloc"].time[0].values)
            date_end = min(observation["xarray_meta"].time[-1].values,
                           models[0]["xarray_meta_coloc"].time[-1].values)
            observation['xarray_meta'] = observation['xarray_meta'].sel(
                time=slice(date_start, date_end))

            # Get the parameters for the OpenDrift calculation
            lons, lats, times, time_step, nb_step = param_pour_opendrift(observation)

            # Calculate the trajectories
            for i_mod, mod in enumerate(models):
                # Create the formatted file for OpenDrift
                output_file = os.path.join(path_results,
                                           f'trajectory_{observation.name}_{mod.name}.nc')
                path_model = os.path.join(path_results, f'{mod.name}.nc')
                opendrift_trajectory.format_opendrift(mod, path_model)

                # Calculate the trajectories from the model
                mod_traj = opendrift_trajectory.calculate_trajectory(path_model, lons, lats, times,
                                                                     time_step, nb_step,
                                                                     output_file)
                models[i_mod]['traj'] = mod_traj.assign_attrs({'name': mod['name']})

                # Plot the trajectories
                plot_features.plot_difference_trajectory(observation['xarray_meta'],
                                                         models[i_mod]['traj'],
                                                         output_path=sub_func_output_folder)


####################################################################################################


def param_pour_opendrift(observation):
    """
    Retreive the parameter for the calculation of the trajectories with the opendrift tool.
    Parameters
    ----------
    observation : : xarray.Dataset
        Observation dataset from which to retrieve the calculation parameters.

    Returns
    -------
    lons : array
        Longitudes where to drop the particules
    lats : array
        Latitudes where to drop the particules
    times : array
        Times when to drop the particules
    time_step : float
        Time step to use in the trajectory calculation
    nb_step : int
        Number of time step to run in the calculation

    """
    duration = (observation["xarray_meta"].time[-1].values - observation["xarray_meta"].time[
        0].values).astype('timedelta64[s]').item().total_seconds()
    nb_step = len(observation["xarray_meta"].time)
    time_step = duration / nb_step
    lons = observation["xarray_meta"].lon.values
    lats = observation["xarray_meta"].lat.values
    times = []
    for time in observation["xarray_meta"].time.values:
        times.append(pandas.to_datetime(time))
    return lons, lats, times, time_step, nb_step
