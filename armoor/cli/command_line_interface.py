import argparse
import sys
import os
from xoa import cfgm

from argparse import ArgumentParser

from armoor.cli.cli_tools import int_or_string_configobj, coords_config_obj, format_cofig_obj2dict

import logging

logger = logging.getLogger(__name__)

# @suppress
from xoa.cfgm import register_validation_functions

register_validation_functions(absolute_or_relative_time=int_or_string_configobj)
register_validation_functions(coordinates=coords_config_obj)


def command_line_interface(argv=None):
    rootdir = os.path.abspath(os.path.dirname(__file__))

    cfgm_fields = cfgm.ConfigManager(os.path.join(rootdir, "cli.ini"))

    if not argv:
        argv = sys.argv[1:]

    logger.info('Retrieving parameter')
    parser = ArgumentParser(description="Bulletin de validation")
    cfg_ticket_lines, _ = cfgm_fields.arg_parse(parser=parser, getargs=True, args=argv)

    formatted_data = format_cofig_obj2dict(cfg_ticket_lines)

    return formatted_data
