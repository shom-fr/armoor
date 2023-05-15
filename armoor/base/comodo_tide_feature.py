"""Calulate tidal harmonics with comodo"""
import xarray as xr
import os
import numpy as np

import logging

logger = logging.getLogger(__name__)


def harmonic_analysis(ds, var, path_nc, path_atlas, path_tools, list_waves, name):
    """
    Run the harmonic analysis to retrive the amplitude, phase of each tidal component. Can be used on current or
    elevation.
    Parameters
    ----------
    ds : xarray.Dataset
        Dataset on which to proceed the harmonic analysis.
    var : str
        Variable of the dataset on which to proceed the harmonic analysis.
    path_nc : str
        Path where to save the netcdf file which will be used by the detidor code to proceed the harmonic analysis.
    path_atlas :
        Path where to save the results of the harmonic analysis.
    path_tools :
        Path of the LEGOS tools where the comodo-detidor executable is located.
    list_waves : str
        List of the waves to include in the harmonic analysis. Ex: "M2 S2 K1 O1 P1 Q1 N2 2N2 L2 La2 E2 L2 J1 Mu2 Nu2".
    name : str
        Model or observation name to be used in the result file name.

    Returns
    -------
    ds_atlas : xarray.Dataset
        Dataset with the results of the harmonic analysis.
    """
    # Clean dataset
    ds = ds.fillna(0)
    if 'time' in ds.lon.dims:
        lon = ds.lon.values[0]
        lat = ds.lat.values[0]
        ds = ds.drop(['lon', 'lat']).assign_coords({'lon': lon, 'lat': lat})

    # Create the netcdf file to run comodo
    format_ds2nc(ds, path_nc, var)

    path_tools_comodo_detidor = os.path.join(path_tools, 'comodo-detidor')
    cmdline = f'{path_tools_comodo_detidor} {path_nc} --only-atlases -a -1 -v {var}  -d {list_waves}'

    logger.info("Launch of comodo-detidor.")
    print(cmdline)
    os.system(cmdline)
    logger.info("Comodo-detidor : Done.")

    # Read the result file
    if var == 'u v':
        local_u_atlas = os.path.join(path_atlas, f'{name}_u-atlas.nc')
        local_v_atlas = os.path.join(path_atlas, f'{name}_v-atlas.nc')

        os.system(f'mv u-atlas.nc {local_u_atlas}')
        os.system(f'mv v-atlas.nc {local_v_atlas}')

        ds_u = xr.open_dataset(local_u_atlas).rename({'W': 'wave'})
        ds_v = xr.open_dataset(local_v_atlas).rename({'W': 'wave'})
        ds_v['u_a'] = ds_u['u_a']
        ds_v['u_G'] = ds_u['u_G']
        ds_atlas = ds_v
        ds_atlas = ds_atlas.assign_coords({'lon': ds.lon})
        ds_atlas = ds_atlas.assign_coords({'lat': ds.lat})
    else:
        ds_atlas = xr.open_dataset(os.path.join(path_atlas, 'ssh-atlas.nc')).rename({'W': 'wave'})

    return ds_atlas


def format_ds2nc(ds, path_nc, var):
    """
    Saves the dataset into a netcdf file with the specified variables.
    Parameters
    ----------
    ds : xarray.Dataset
        Dataset to convert into netcdf file.
    path_nc : str
        Path where to save the netcdf file.
    var :
        Variable of the dataset to include in the netcdf file.
    """
    ds = ds.squeeze()
    if np.size(ds.lon.values) > 1:
        lon = ds.lon.values[0]
        lat = ds.lat.values[0]
    else:
        lon = ds.lon.values
        lat = ds.lat.values

    if var == 'ssh':
        dataset = xr.Dataset({'time': ds.time, 'ssh': ds.ssh})
        dataset = dataset.assign_coords({'lon': lon, 'lat': lat})
    elif var == 'u v':
        dataset = xr.Dataset({'time': ds.time, 'u': ds.u, 'v': ds.v})
        if 'lon' not in dataset:
            dataset = dataset.assign_coords({'lon': lon, 'lat': lat})
    else:
        raise Warning("Caution: the variable to select should be either \"ssh\" or \"u v\"")
    dataset.squeeze().to_netcdf(path=path_nc)
