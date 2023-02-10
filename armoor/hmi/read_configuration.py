"""
Functions tools to read and format a configObj from path
"""
import os

from configobj import ConfigObj
from validate import Validator
import armoor.cli.cli_tools as cl

import logging
logger = logging.getLogger(__name__)

def read_config_obj(path: str, spec_file: str) -> dict:
    """
    Read et check the configObj file and return a formatted dictionary.

    Parameters
    ----------
    spec_file :
    path : path
        path to the configObj file

    Returns
    -------
    config : dict
        Dictionary with the configuration wanted.
    """

    # reading file to perform all the checking
    logger.info(f'Using spec file :: {os.path.abspath(os.path.dirname(__file__))}/{spec_file}')

    rootdir = os.path.abspath(os.path.dirname(__file__))
    config = ConfigObj(path, configspec=os.path.join(rootdir, spec_file))

    # initialize validation object
    val = Validator()
    custom_validation_types = {
        'folder_path': cl.folder_path,
        'absolute_or_relative_time': cl.int_or_string_configobj,
        'path': cl.file_path,
        'directory': cl.folder_path,
        'force_list_path': cl.file_force_list_path_configObj,
        'depth': cl.depth_configObj,
        'coordinates': cl.coords_configObj,
        'vars_list': cl.vars_list_configObj
    }

    for type_name, type_validation_function in custom_validation_types.items():
        val.functions[type_name] = type_validation_function
    validation_test = config.validate(val)

    if validation_test and 'parameters' in config:
        return clean_configobj(config)

    if validation_test:
        return config

    # config obj error
    logger.debug(f'{validation_test = }')
    return None


def clean_configobj(configobj: dict) -> dict:
    """
    Clean configobj, future modify this function using xoa
    Parameters
    ----------
    configobj

    Returns
    -------

    """
    for parameter in configobj['parameters']:
        if not configobj['parameters'][parameter]['extent']:
            configobj['parameters'][parameter].pop('extent')
    return configobj


def file_path(path_name: str) -> str:
    """
    Used when a path is provided
    check "path" type, check if path exist.

    Parameters
    ----------
    path_name : str
        path to the file

    Returns
    -------
    path : str
        path to wanted file.
    """
    if os.path.isfile(path_name):
        return path_name

    raise FileNotFoundError(path_name)


def folder_path(path_name: str) -> str:
    """
    use when a directory is provided
    check "directory" type, check if path to folder exist.

    Parameters
    ----------
    path_name : str
        path to the folder

    Returns
    -------
    path : str
        path to wanted folder.
    """
    if os.path.isdir(path_name) and path_name[-1:] == '/':
        return path_name

    raise NotADirectoryError(path_name)
