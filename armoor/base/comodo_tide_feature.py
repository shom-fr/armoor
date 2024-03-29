"""Calulate tidal harmonics with comodo"""
import logging
import os
import xarray as xr
import numpy as np

logger = logging.getLogger(__name__)


def harmonic_analysis(ds_to_anal, var, path_nc, path_atlas, path_tools, list_waves,
                      env_comodo=''):
    """
    Run the harmonic analysis to retrive the amplitude, phase of each tidal component. Can be used
    on current or elevation.
    Parameters
    ----------
    ds_to_anal : xarray.Dataset
        Dataset on which to proceed the harmonic analysis.
    var : str
        Variable of the dataset on which to proceed the harmonic analysis.
    path_nc : str
        Path where to save the netcdf file which will be used by the detidor code to proceed the
        harmonic analysis.
    path_atlas :
        Path where to save the results of the harmonic analysis.
    path_tools :
        Path of the LEGOS tools where the comodo-detidor executable is located.
    list_waves : str
        List of the waves to include in the harmonic analysis. Ex: "M2 S2 K1 O1 P1 Q1 N2 2N2 L2 La2
        E2 L2 J1 Mu2 Nu2".
    env_comodo : str
        Commandline to load the comodo environment
    Returns
    -------
    ds_atlas : xarray.Dataset
        Dataset with the results of the harmonic analysis.
    """
    # Name of the dataset
    name = ds_to_anal.attrs['name']
    # Clean dataset
    if 'time' in ds_to_anal.lon.dims:
        lon = ds_to_anal.lon.values[0]
        lat = ds_to_anal.lat.values[0]
        ds_to_anal = ds_to_anal.drop_vars(['lon', 'lat']).assign_coords({'lon': lon, 'lat': lat})

    # Create the netcdf file to run comodo
    format_ds2nc(ds_to_anal, path_nc, var)

    path_tools_comodo_detidor = os.path.join(path_tools, 'comodo-detidor')
    cmdline = f'{path_tools_comodo_detidor} {path_nc} --only-atlases -a -1 -v {var} ' \
              f' -d {list_waves}'

    logger.info("Loading Sirocco environment.")
    os.system(env_comodo)
    logger.info("Launch of comodo-detidor.")
    logger.info(cmdline)
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
        ds_atlas = ds_atlas.assign_coords({'lon': ds_to_anal.lon})
        ds_atlas = ds_atlas.assign_coords({'lat': ds_to_anal.lat})
    else:
        ds_atlas = xr.open_dataset(os.path.join(path_atlas, 'ssh-atlas.nc')).rename({'W': 'wave'})

    # Assign name in ds
    ds_atlas = ds_atlas.assign_attrs({'name': name})

    ds_atlas.to_netcdf('comomdo_res.nc')
    return ds_atlas


def format_ds2nc(ds_to_save, path_nc, var):
    """
    Saves the dataset into a netcdf file with the specified variables.
    Parameters
    ----------
    ds_to_save : xarray.Dataset
        Dataset to convert into netcdf file.
    path_nc : str
        Path where to save the netcdf file.
    var :
        Variable of the dataset to include in the netcdf file.
    """
    ds_to_save = ds_to_save.squeeze()
    if np.size(ds_to_save.lon.values) > 1:
        lon = ds_to_save.lon.values[0]
        lat = ds_to_save.lat.values[0]
    else:
        lon = ds_to_save.lon.values
        lat = ds_to_save.lat.values

    if var == 'ssh':
        dataset = xr.Dataset({'time': ds_to_save.time, 'ssh': ds_to_save.ssh})
        dataset = dataset.assign_coords({'lon': lon, 'lat': lat})
    elif var == 'u v':
        dataset = xr.Dataset({'time': ds_to_save.time, 'u': ds_to_save.u, 'v': ds_to_save.v})
        if 'lon' not in dataset:
            dataset = dataset.assign_coords({'lon': lon, 'lat': lat})
    else:
        raise Warning("Caution: the variable to select should be either \"ssh\" or \"u v\"")
    dataset.squeeze().to_netcdf(path=path_nc)
