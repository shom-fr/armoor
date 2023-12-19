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

import armoor.cli.logger_tools as log


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
    parser.add_argument('-l', '--legend-configuration',
                        type=argparse.FileType('r'),
                        help='File to overwrite internal legend configuration file')
    paths = vars(parser.parse_args(argv))

    output_folder_path = paths['output_folder']
    input_folder_path = paths['input_folder']
    input_configuration_path = paths['input_configuration']
    legend_configuration_path = paths.get('legend_configuration')

    return output_folder_path, input_folder_path, input_configuration_path, legend_configuration_path


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
    output_folder_path, input_folder_path, input_configuration_path, legend_configuration_path = read_args(argv)

    logger.info(f'details of configuration from file : {input_configuration_path}')

    rootdir = os.path.abspath(os.path.dirname(__file__))
    cfgm_hmi_script = cfgm.ConfigManager(os.path.join(rootdir, "..", "hmi", "hmi.ini"))

    dict_configuration = cfgm_hmi_script.load(input_configuration_path)
    dict_configuration = format_hmi_dict(dict_configuration)

    with open(os.path.join(rootdir, "..", "hmi", "hmi_plot.ini"), "r", encoding="utf-8") as hmi_plot_spec:
        cfgm_plots = cfgm.ConfigManager(hmi_plot_spec)
    if legend_configuration_path:
        logger.info(f'Using custom configuration file for legends : {legend_configuration_path}')
        legend_configuration = cfgm_plots.load(legend_configuration_path)
    else:
        logger.info(f'Using internal configuration file for legends')
        with open(os.path.join(rootdir, '..', '..', 'config', 'hmi_plot.cfg'), "r", encoding="utf-8") as hmi_plot_config:
            legend_configuration = cfgm_plots.load(hmi_plot_config)

    logger.info(f'saved in folder : {output_folder_path}')
    logger.info(f'data comes from : {input_folder_path}')

    create_images(dict_configuration, input_folder_path, output_folder_path, legend_configuration)
    logger.info(f"--- {time.time() - start_time} seconds ---")


def format_hmi_dict(dict_configuration: dict) -> dict:
    for parameter in dict_configuration['parameters']:
        extent = dict_configuration['parameters'][parameter]['extent']

        if all(value is None for value in extent.values()):
            dict_configuration['parameters'][parameter].pop('extent')
        elif any(value is None for value in extent.values()):
            raise ValueError(f'Extent value error : {extent}')

    return dict_configuration
