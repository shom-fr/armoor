import logging
import os
import sys
from argparse import ArgumentParser

from armoor.cli.cli_tools import (
    coords_config_obj,
    format_cofig_obj2dict,
    int_or_string_configobj,
)
from armoor.base.open_decode import register_cf

logger = logging.getLogger(__name__)

# @suppress
from xoa.cfgm import ConfigManager, register_validation_functions

register_validation_functions(
    absolute_or_relative_time=int_or_string_configobj
)
register_validation_functions(coordinates=coords_config_obj)

register_cf()

def command_line_interface(argv=None):
    rootdir = os.path.abspath(os.path.dirname(__file__))

    cfgm_fields = ConfigManager(os.path.join(rootdir, "cli.ini"))

    if not argv:
        argv = sys.argv[1:]

    logger.info("Retrieving parameter")
    parser = ArgumentParser()
    cfg_ticket_lines, _ = cfgm_fields.arg_parse(
        parser=parser,
        getargs=True,
        args=argv,
    )
    formatted_data = format_cofig_obj2dict(cfg_ticket_lines)

    return formatted_data
