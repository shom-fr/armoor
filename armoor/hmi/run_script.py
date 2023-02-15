"""
Create images needed for the web interface
"""
import logging
import os
import sys
import argparse
import time

import armoor.hmi.script_tools as st
import armoor.hmi.script as s

import armoor.cli.logger_tools as log

def folder_path(path_name: str) -> str:
    """ @2BIS
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


def file_path(path_name: str) -> str:
    """ @2
    use when a path is provided
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


def read_args(argv):
    """
    Read arguments needed to create the web interface images
    Parameters
    ----------
    argv : command line parameters

    Returns
    -------
    The paths to the needed parameters output folder, input folder and input configuration file.
    """

    parser = argparse.ArgumentParser(description='Command to create images needed'
                                                 ' for the web interface')
    parser.add_argument('-o', '--output-folder',
                        type=folder_path,
                        help='Folder path to store outputs created by the script'
                             ' for the web interface')
    parser.add_argument('-i', '--input-folder',
                        type=folder_path,
                        help='Root folder path from which the data is retrieved'
                             ' to creating the web interface images')
    parser.add_argument('-c', '--input-configuration',
                        type=file_path,
                        help='File with details on the models and configurations'
                             ' to be generate')
    paths = vars(parser.parse_args(argv))

    output_folder_path = paths['output_folder']
    input_folder_path = paths['input_folder']
    input_configuration_path = paths['input_configuration']

    return output_folder_path, input_folder_path, input_configuration_path


def main(argv=None):
    """
    Calls the function with the arguments provided by the user to generate the web interface images
    Returns
    -------
    None
    """
    log.setup_logging()
    logger = logging.getLogger(__name__)
    start_time = time.time()

    if not argv:
        argv = sys.argv[1:]
    output_folder_path, input_folder_path, input_configuration_path = read_args(argv)
    spec_config_file = "../../config/hmi/spec.ini"

    logger.info(f'details of configuration from file : {input_configuration_path}')
    dict_configuration = st.return_dict(input_configuration_path, spec_config_file)

    logger.info(f'saved in folder : {output_folder_path}')
    logger.info(f'data comes from : {input_folder_path}')

    s.create_images(dict_configuration, input_folder_path, output_folder_path)
    logger.info(f"--- {time.time() - start_time} seconds ---")
