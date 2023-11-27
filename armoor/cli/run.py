import logging
from armoor.cli.command_line_interface import command_line_interface
from armoor.base.calls_from_dict import dict2call
from armoor.cli.logger_tools import setup_logging

def main(functionality :str = None):
    setup_logging()
    logger = logging.getLogger(__name__)

    logger.info('Retrieving parameter')
    parser = command_line_interface()

    if functionality:
        parser.update({"functionality" : functionality})

    print(f'{ parser = }')
    logger.info('Applying configuration to generate plots')
    dict2call(parser)


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

def script_p_currents_adcp():
    main('currents_ADCP')

def script_p_currents_vmadcp():
    main('currents_VMADCP')

def script_p_drifters():
    main('drifters')
