from armoor import cli
from armoor import base
import armoor.cli.logger_tools as log
import logging
import pprint

def main_2():
    log.setup_logging()
    logger = logging.getLogger(__name__)

    logger.info('Retrieving parameter')
    parser = cli.command_line_interface()
    pprint.pprint(parser)
    logger.info('Applying configuration to generate plots')
    base.calls_from_dict.dict2call(parser)

def main(argv=None):
    log.setup_logging()
    logger = logging.getLogger(__name__)

    logger.info('Retrieving parameter')
    parser = cli.command_line_interface()

    logger.info('Applying configuration to generate plots')
    base.calls_from_dict.dict2call(parser)