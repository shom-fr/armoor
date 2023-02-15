"""
Create images needed for the web interface
"""
import logging
import sys
import argparse
import time

import armoor.hmi.script_tools as st
import armoor.hmi.read_configuration as rc
import armoor.bull.script as s

from .report import Report

import armoor.cli.logger_tools as log

def read_args(argv):
    """
    Read arguments needed to create the weather report
    Parameters
    ----------
    argv : command line parameters

    Returns
    -------
    The paths to the needed parameters output folder and input configuration file.
    """

    parser = argparse.ArgumentParser(description='Command to create images and files needed'
                                                 ' for the weather report')
    parser.add_argument('-o', '--output-folder',
                        type=rc.folder_path,
                        help='Folder path to store outputs created by the script'
                             ' for the weather report')
    parser.add_argument('-c', '--input-configuration',
                        type=rc.file_path,
                        help='File with configurations details to generate the weather report')
    paths = vars(parser.parse_args(argv))

    output_folder_path = paths['output_folder']
    input_configuration_path = paths['input_configuration']

    return output_folder_path, input_configuration_path


def main(argv=None):
    """
    Calls the function with the arguments provided by the user
    to generate the weather report images and files
    Returns
    -------
    None
    """
    log.setup_logging()
    logger = logging.getLogger(__name__)

    start_time = time.time()

    if not argv:
        argv = sys.argv[1:]
    output_folder_path, input_configuration_path = read_args(argv)
    spec_config_file = '../../config/bull/spec.ini'

    logger.info(f'details of configuration from file : {input_configuration_path}')
    dict_configuration = st.return_dict(input_configuration_path, spec_config_file)

    s.create_reports(dict_configuration, output_folder_path)
    logger.info(f'Done - all images for report in : {output_folder_path}sources')

    logger.info('Creating report from sources.')
    report = Report(output_folder_path)
    report.generate_report()

    logger.info(f"Done in {time.time() - start_time} seconds ")


def only_report(argv):
    """
    Calls the function with the arguments provided by the user
    to generate the weather report
    Returns
    -------
    None
    """
    log.setup_logging()
    logger = logging.getLogger(__name__)

    start_time = time.time()

    if not argv:
        argv = sys.argv[1:]
    output_folder_path, _ = read_args(argv)

    logger.info('Creating report from sources.')
    report = Report(output_folder_path)
    report.generate_report()

    logger.info(f"Done in {time.time() - start_time} seconds ")
