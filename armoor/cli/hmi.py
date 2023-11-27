"""
Create images needed for the web interface
"""
import logging
import os
import sys
import argparse
import time
from xoa import cfgm

from armoor.hmi.script import create_images
from armoor.cli.cli_tools import directory_type

from armoor.cli.logger_tools import setup_logging


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
                        type=directory_type,
                        help='Folder path to store outputs created by the script'
                             ' for the web interface')
    parser.add_argument('-i', '--input-folder',
                        type=directory_type,
                        help='Root folder path from which the data is retrieved'
                             ' to creating the web interface images')
    parser.add_argument('-c', '--input-configuration',
                        type=argparse.FileType('r'),
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
    setup_logging()
    logger = logging.getLogger(__name__)
    start_time = time.time()

    if not argv:
        argv = sys.argv[1:]
    output_folder_path, input_folder_path, input_configuration_path = read_args(argv)

    logger.info(f'details of configuration from file : {input_configuration_path}')

    rootdir = os.path.abspath(os.path.dirname(__file__))
    cfgm_hmi_script = cfgm.ConfigManager(os.path.join(rootdir, "..", "hmi", "hmi.ini"))

    dict_configuration = cfgm_hmi_script.load(input_configuration_path)

    dict_configuration = format_hmi_dict(dict_configuration)

    logger.info(f'saved in folder : {output_folder_path}')
    logger.info(f'data comes from : {input_folder_path}')

    create_images(dict_configuration, input_folder_path, output_folder_path)
    logger.info(f"--- {time.time() - start_time} seconds ---")



def format_hmi_dict(dict_configuration: dict) -> dict:

    for parameter in dict_configuration['parameters']:
        extent = dict_configuration['parameters'][parameter]['extent']

        if all(value is None for value in extent.values()):
            dict_configuration['parameters'][parameter].pop('extent')
        elif any(value is None for value in extent.values()):
            raise ValueError(f'Extent value error : {extent}')


    return dict_configuration
