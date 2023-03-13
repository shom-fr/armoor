"""Calculate trajectories with OpenDrift"""
from opendrift.readers import reader_netCDF_CF_generic
from opendrift.readers import reader_shape
from opendrift.models.oceandrift import OceanDrift
import cartopy.io.shapereader as shpreader
import xarray as xr
import numpy as np

import logging
logger = logging.getLogger(__name__)


def format_opendrift(mod, path_model):
    """
    Save the model dataset into a netcdf file with the right attributes
    Parameters
    ----------
    mod : xarray.Dataset
        Model dataset to be used for OpenDrift.
    path_model : str
        Path where to save the netcdf file to be used for OpenDrift.

    """
    logger.info(f"Formatting dataset")

    mod = mod['xarray_meta'].rename({'u': 'x_sea_water_velocity', 'v': 'y_sea_water_velocity'})
    mod['x_sea_water_velocity'].attrs = {'standard_name': "eastward_sea_water_velocity",
                                         'long_name': "Eastward velocity", 'units': "m s-1"
                                         }
    mod['y_sea_water_velocity'].attrs = {'standard_name': "northward_sea_water_velocity",
                                         'long_name': "Northward velocity", 'units': "m s-1"
                                         }
    if not check_delta_constant(mod):
        mod = regrid_constant_delta(mod)

    mod.squeeze().to_netcdf(path_model)


def check_delta_constant(mod):
    """
    Checks if the lon / lat are on a regular grid. OpenDrift works with regular grids.
    Parameters
    ----------
    mod : xarray.Dataset
        Model dataset to be used for OpenDrift.
    Returns
    -------
        bool
        Indicates if the lon / lat are on a regular grid
    """

    delta_lon_0 = mod.lon.data[1] - mod.lon.data[0]
    delta_lat_0 = mod.lat.data[1] - mod.lat.data[0]
    delta_lon_1 = mod.lon.data[2] - mod.lon.data[1]
    delta_lat_1 = mod.lat.data[2] - mod.lat.data[1]
    return (delta_lat_1 == delta_lat_0 and delta_lon_1 == delta_lon_0)


def regrid_constant_delta(mod):
    """
    Convert the model into a regular grid. OpenDrift works with regular grids.
    Parameters
    ----------
    mod : xarray.Dataset
        Model dataset to be used for OpenDrift.
    Returns
    -------
    mod : xarray.Dataset
        Formatted model dataset to be used for OpenDrift.
    """
    min_lon, max_lon = mod.lon.min(), mod.lon.max()
    step_lon = (max_lon - min_lon) / np.size(mod.lon)
    min_lat, max_lat = mod.lat.min(), mod.lat.max()
    step_lat = (max_lat - min_lat) / np.size(mod.lat)

    tgt_lon = np.arange(min_lon, max_lon, step_lon)
    tgt_lat = np.arange(min_lat, max_lat, step_lat)

    mod = mod.interp(lon=tgt_lon, lat=tgt_lat)

    return mod


def calculate_trajectory(path_model, lons, lats, times, time_step, nb_step, output_file):
    """
    Calculate the trajectories of the drifting particules with OpenDrift. The particules are dropped at each observation
    date and location.

    Parameters
    ----------
    path_model : str
        path to the netcdf file
    lons : array
        longitudes where to drop the particules.
    lats : array
        latitudes where to drop the particules.
    times : array
        times when to drop the particules.
    time_step : float
        time step for the calculation (in s).
    nb_step : int
        number of time step to compute.
    output_file : str
        path to the

    Returns
    -------
    trajectory : xarray.Dataset
        Trajectories of the drifting particules.
    """
    logger.info(f"Computing trajectory")

    # Initialise the OpenDrift model
    o = OceanDrift(loglevel=20)

    # Read the model
    reader_analysis = reader_netCDF_CF_generic.Reader(path_model)
    shpfilename = shpreader.natural_earth(resolution='110m', category='cultural', name='admin_0_countries')
    reader_natural = reader_shape.Reader.from_shpfiles(shpfilename)
    o.add_reader([reader_natural, reader_analysis])
    o.set_config('general:use_auto_landmask', False)  # Disabling the automatic GSHHG landmask
    o.set_config('general:coastline_action', 'stranding')

    # Run calculation
    o.seed_elements(lons, lats, time=times)
    o.run(steps=nb_step, time_step=time_step, outfile=output_file)

    # Open file result in dataset
    trajectory = xr.open_dataset(output_file)
    trajectory = trajectory.where(trajectory.lon < 1e+30, drop=True)

    return trajectory
