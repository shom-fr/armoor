import argparse
import sys
import os
from xoa import cfgm

from argparse import ArgumentParser

from armoor import cli

import logging
logger = logging.getLogger(__name__)


# @suppress
from xoa.cfgm import register_validation_functions

register_validation_functions(absolute_or_relative_time=cli.cli_tools.int_or_string_configobj)
register_validation_functions(path=cli.cli_tools.file_path)
register_validation_functions(directory=cli.cli_tools.folder_path)
register_validation_functions(force_list_path=cli.cli_tools.file_force_list_path_configObj)
register_validation_functions(depth=cli.cli_tools.depth_configObj)
register_validation_functions(coordinates=cli.cli_tools.coords_configObj)
register_validation_functions(vars_list=cli.cli_tools.vars_list_configObj)

def command_line_interface(argv=None):

    rootdir = os.path.abspath(os.path.dirname(__file__))

    cfgm_fields = cfgm.ConfigManager(os.path.join(rootdir, "cli.ini"))

    if not argv:
        argv = sys.argv[1:]

    logger.info('Retrieving parameter')
    parser = ArgumentParser(description="Bulletin de validation")
    cfg_ticket_lines, _ = cfgm_fields.arg_parse(parser=parser,
                                                getargs=True,
                                                args=argv)

    formated_data = cli.cli_tools.format_cofigObj2Dict(cfg_ticket_lines)

    return formated_data