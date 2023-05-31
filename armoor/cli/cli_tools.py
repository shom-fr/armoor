"""
Tools for the command line interface
"""
import json
import os
from argparse import ArgumentTypeError
from pprint import pprint
from xoa import cfgm

from configobj import ConfigObj
from validate import Validator, VdtTypeError

import logging
logger = logging.getLogger(__name__)


def int_or_string_configobj(value):
    """ @1
    check "absolute_or_relative_time" type : in the configObj file provided by the user.

    Parameters
    ----------
    value : int or str
        path to the configObj file

    Returns
    -------
    config : dict
        Dictionary with the configuration wanted.
    """

    if not isinstance(value, (str, int)):
        # a value in the list
        # is neither an integer nor a string
        raise VdtTypeError(value)
    is_int = True
    try:
        # converting to integer
        int(value)
    except ValueError:
        is_int = False
    if is_int:
        value = int(value)
    return value


def directory_type(path: str) -> str:
    """
    use when a directory is provided
    check "directory" type, check if path to folder exist.

    Parameters
    ----------
    path : str
        path to the directory

    Returns
    -------
    path : str
        path to wanted folder.
    """
    if os.path.isdir(path):
        return path

    raise NotADirectoryError(f"{path} is not a valid directory.")


def try_str2float(value) -> float:
    """
    ensure that the output of this function is always a positive float

    Parameters
    ----------
    value : str (or float)
        value to verify and transform

    Returns
    -------
    value : float
        value as a float
    """
    if not isinstance(value, (str, int, float)):
        # a value in the list
        # is neither an integer nor a string
        raise VdtTypeError(value)
    is_float = True
    try:
        # converting to integer
        float(value)
    except ValueError:
        is_float = False
    if is_float:
        value = float(value)
        if value >= 0.0:
            return float(value)
        else:
            raise ValueError("depth or step must be positive values")
    return None


def depth_config_obj(depths) -> list:
    """ @4
    if depths length is 1 : it's for the selection of a layer
    if depths length is 2 : it's for the selection of all the layers between the 2 values.
    if depths length is 3 : it's for the selection of some layers between the 2 first values,
        with a certain step (third value)

    Parameters
    ----------
    depths : str or list of depths
        1 : layer
        2 : layer min and layer max
        3 : layer min, layer max and step

    Returns
    -------
    depths : list
        depths (length from 1 to 3)
    """
    # case of sandwich depths
    if isinstance(depths, list) and len(depths) <= 3:
        depths = [try_str2float(depth) for depth in depths]
        # check if depths are in the right order
        if len(depths) >= 2 and depths[0] >= depths[1]:
            raise ValueError(f'depth {depths[0]} < {depths[1]} must be true')
        # check if step is lower the the interval between depth min and depth max
        if len(depths) == 3 and depths[1] - depths[0] <= depths[2]:
            raise ValueError(f'step {depths[2]} is too large {depths[0]} - {depths[1]} = {depths[1] - depths[0]}')
        return depths
    # case of one layer of depth
    elif isinstance(depths, str):
        return [try_str2float(depths)]
    # other cases through an error
    else:
        logger.error(f' depth_config_Obj : {type(depths) = }')
        raise ArgumentTypeError("error with depth param")


# function to check if the coordinates provided are well formatted
def coords_config_obj(coordinates) -> list:
    """
    Used when coordinates are provided
    check "coordinates" type, check if coordinates are even and perform cleanup.

    Parameters
    ----------
    coordinates : list of coordinates
        coordinates for polygons or cloud points

    Returns
    -------
    coordinates : list
        coordinates well formatted as a list of tuples
    """
    new_coordinates = []
    if isinstance(coordinates, list):
        size = len(coordinates)
        if size % 2 != 0:
            raise VdtTypeError(coordinates)
        for i in range(0, size, 2):
            lat = coordinates[i]
            lon = coordinates[i + 1]

            # remove unwanted characters
            for blacklistchar in '{([)]}':
                lat = lat.replace(blacklistchar, '')
                lon = lon.replace(blacklistchar, '')
            coordinate = float(lat), float(lon)
            new_coordinates.append(coordinate)
        return new_coordinates
    else:
        # a value in the list
        # is neither an integer nor a string
        raise VdtTypeError(coordinates)


def format_cofig_obj2dict(config: dict) -> dict:
    """
    function to format configObj input to useful dictionary

    Parameters
    ----------
    config : dict
        rough dictionary

    Returns
    -------
    config : dict
        formatted dictionary
    """
    # print('config   IN :::')
    # pprint(config.dict())
    # Clean observation if method_z not provided
    observation = remove_keys_with_none_value(config.pop("observation"))
    config.update({"observation": observation})

    # models
    if "models" in config:
        models = config.pop("models")
        new_models = []
        for model in models:
            if isinstance(model, list):
                new_models.append(remove_keys_with_none_value(models[model]))
            else:
                new_models.append(remove_keys_with_none_value(models[model]))
        config.update({"models": new_models})
    else:
        logger.error('No model provided')
        raise VdtTypeError('no model provided')

    # outputs
    if "outputs" in config:
        outputs = config.pop("outputs")
        new_outputs = []
        for output in outputs:
            outputs[output].update({"folder_name": output})
            new_outputs.append(remove_keys_with_none_value(outputs[output]))
        config.update({"outputs": new_outputs})
    else:
        logger.error('No output provided')
        raise VdtTypeError(f'no outputs provided')

    # clean meta-zones from None values
    if "meta-zones" in config:
        meta_zones = remove_keys_with_none_value(config.pop("meta-zones"))
        if meta_zones:
            config.update({"meta_zones": meta_zones})

    return config


def remove_keys_with_none_value(dictionary: dict) -> dict:
    """
    function to remove all keys with None value

    Parameters
    ----------
    dictionary : dict
        rough dictionary (with none values)

    Returns
    -------
    dictionary : dict
        cleaned dictionary, all keys have values
    """
    for key, value in dict(dictionary).items():
        if value is None:
            del dictionary[key]
    return dictionary




# function to check if the coordinates provided are well formatted
def coords(s):
    try:
        lat, lon = map(float, s.split(','))
        return lat, lon
    except:
        raise ArgumentTypeError("Coordinates must be lat,lon")