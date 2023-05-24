from armoor import cli
from armoor import base
import armoor.cli.logger_tools as log
import logging
import pprint

def main(argv=None):
    log.setup_logging()
    logger = logging.getLogger(__name__)

    logger.info('Retrieving parameter')
    parser = cli.command_line_interface()

    if functionality:
        parser.update({"functionality" : functionality})

    print(f'{ parser = }')
    logger.info('Applying configuration to generate plots')
    base.calls_from_dict.dict2call(parser)


def script_p_sst():
    main('sst')

def script_p_prof_hydro_vessel():
    main('prof_hydro_vessel')

def script_p_prof_hydro_mooring():
    main('prof_hydro_mooring')

def script_p_section_hydro():
    main('section_hydro')

def script_p_clim_hydro():
    main('clim_hydro')

def script_p_currents_hfr():
    main('currents_hfr')

def script_p_currents_ADCP():
    main('currents_ADCP')

def script_p_currents_VMADCP():
    main('currents_VMADCP')

def script_p_drifters():
    main('drifters')