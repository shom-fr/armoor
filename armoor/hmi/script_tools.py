"""
Tools for the script to run smoothly
"""
from pathlib import Path

import numpy as np
import xarray as xr


import logging
logger = logging.getLogger(__name__)

def decumulate_data(data, cut_list):
    """

    Parameters
    ----------
    data : cumulated data
    cut_list : list of chunks

    Returns
    -------
    decumulated data
    """
    end_i = 0
    tmp_list = list()

    for i in cut_list:
        start_i = end_i
        end_i = start_i + i

        aux = data[start_i:end_i, :, :]
        diff = np.diff(aux, axis=0)
        conc = np.concatenate((data[start_i:start_i + 1], diff))

        tmp_list.append(conc)

    result = np.concatenate(tmp_list)

    return result



def from_nh_to_1h(data, cumul_time_in_h):
    """

    Parameters
    ----------
    data : data to process
    cumul_time_in_h : list of accumulation times in hour(s)

    Returns
    -------
    decumulated data 1h step
    """

    size_time, size_lat, size_lon = data.shape

    repeated_cumul_lat = np.repeat(np.array([cumul_time_in_h]), size_lat, axis=0)
    repeated_cumul_lat_t = np.transpose(repeated_cumul_lat)

    repeated_cumul_lon = np.repeat(np.array([repeated_cumul_lat_t]), size_lon, axis=0)
    repeated_cumul = np.transpose(repeated_cumul_lon, axes=[1, 2, 0])

    return np.divide(data, repeated_cumul)

def retrieve_raw_paths_names(path_files: list) ->list:
    """

    Parameters
    ----------
    path_files : raw list of paths

    Returns
    -------
    list of raw names looking like : _202203090000_0001 or 202203090000_0001_
    """
    return [path[-33:-15] for path in path_files]

def retrieve_clean_paths_names(raw_names: list) ->list:
    """

    Parameters
    ----------
    raw_names : raw list of names

    Returns
    -------
    clean list of names change from : _* or *_ to *
    """
    clean_name_list = list()

    for path in raw_names:
        if path[0] == '_':
            clean_name_list.append(path[1:])
        elif path[-1] == '_':
            clean_name_list.append(path[:-1])
        else:
            logger.error(f'Unrecognised name  : {path}')

    return sorted(clean_name_list)

def gathered_names(clean_name_list: list) -> dict:
    """

    Parameters
    ----------
    clean_name_list : list of names looking like "reseau_echeance"

    Returns
    -------
    dictionary sorted by "reseau"
    """
    dict_cumul = {}
    for name in clean_name_list:
        reseau, echeance = name.split('_')
        if reseau in dict_cumul:
            dict_cumul[reseau].append(int(echeance))
        else:
            dict_cumul.update({reseau: [int(echeance)]})

    return dict_cumul

def get_cumul_list_to_cut(dict_cumul: dict) -> list:
    """

    Parameters
    ----------
    dict_cumul : dictionary of "reseau" with corresponding "echeances"

    Returns
    -------
    list of size "reseau" fragments
    """
    return [len(dict_cumul[reseau]) for reseau in dict_cumul]

def get_cumul_time_in_h(dict_cumul: dict) -> list:
    """

    Parameters
    ----------
    dict_cumul

    Returns
    -------
    list of decumulated times in hours for each "echeance"
    """
    dict_decumul = dict()
    for key, value in dict_cumul.items():
        dict_decumul.update({key : np.insert(np.diff(value), 0, value[0])})

    return np.concatenate([value for value in dict_decumul.values()])

def get_cumul_info(path_files):
    """

    Parameters
    ----------
    path_files : raw list of paths

    Returns
    -------
    list of size "reseau" fragments
    list of decumulated times in hours for each "echeance"
    """
    name_list = retrieve_raw_paths_names(path_files)
    clean_name_list = retrieve_clean_paths_names(name_list)
    dict_cumul = gathered_names(clean_name_list)

    list_cut = get_cumul_list_to_cut(dict_cumul)
    cumul_time_in_h = get_cumul_time_in_h(dict_cumul)

    return list_cut, cumul_time_in_h

def convert_k_c(data: xr.Dataset) -> xr.Dataset:
    """
    Convert temperature units into Celcius degrees.

    Returns
    -------
    xarray.DataArray
        Data array containing SST in Celcius degrees.
    """
    if 'units' in data.attrs and data.attrs['units'] == 'kelvin':
        logger.info('Converting to Celsius degrees')
        return data - 273.15
    else:
        return data


def create_folder(path: str):
    """
    Create folder without error if folder already exists
    Parameters
    ----------
    path

    Returns
    -------
    None
    """
    Path(path).mkdir(parents=True, exist_ok=True)


def format_times(times: list) -> list:
    """
    Format time from a list to be able to create filenames with formatted times
    Parameters
    ----------
    times : list of times

    Returns
    -------
    list of times formatted
    """
    new_times = []
    for time in times:
        new_times.append(time.replace(':', 'h'))
    return new_times


def get_t0(times: list, today: str) -> str:
    """
    Get the model's first time step in the production day
    Parameters
    ----------
    times : all model time steps
    today : production day

    Returns
    -------
    first time step of the model in the production day
    """
    t0_forecaster_web_interface = ""
    for time in times:
        if today in time.replace('-',''):
            t0_forecaster_web_interface = time
            break
    return t0_forecaster_web_interface
