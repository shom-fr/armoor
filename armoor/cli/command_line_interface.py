import argparse
import sys
from armoor import cli

path2text2code = "code_text.json"

import logging
logger = logging.getLogger(__name__)

def command_line_interface(args=None):
    """
    Convert json file into dictionary to specify functionality, observation and models products, meta-zones,
    outputs, formats and more.

    Parameters
    ----------
    args : list of strings
        Path to json file.

    Returns
    -------
    validation_bulletin : dict
        Dictionary containing specifications for observation, models, output products etc.

    Examples
    --------
    parser = cli.command_line_interface(['--file', "data/json_files/cli_diag_disp.json"])
    """

    # This, is to be able to run test, as command line without actually typing every time
    if not args:
        args = sys.argv[1:]

    # Initialize argparser
    parser = argparse.ArgumentParser(description='read from command line or from file')

    # Step 1 of 3
    # reading arguments from command line
    # All the details of how must be use the commend lines are in the code_text.json file
    # Here we add to the parser the TYPE (type checking), CHOICES (limit choices if applicable),
    # NARGS (the number of arguments expected), DEFAULT (default value if applicable) and
    # HELP (description to help the user)
    data_parser = cli.cli_tools.readText2code(path2text2code)
    for dp in data_parser:
        # retrieve elements for the parser
        dp_arg = data_parser[dp].get("argument")
        dp_type = data_parser[dp].get("type")
        dp_choices = data_parser[dp].get("choices")
        dp_nargs = data_parser[dp].get("nargs")
        dp_help = data_parser[dp].get("help")
        dp_default = data_parser[dp].get("default")

        # convert string type to real type
        if dp_type is not None:
            dp_type = cli.cli_tools.convert_type(dp_type)
        # convert string number to int
        if dp_nargs is not None:
            dp_nargs = cli.cli_tools.convert_nargs(dp_nargs)

        # add it to the parser to be able to get the argument in the command line
        parser.add_argument(dp_arg,
                            type=dp_type,
                            choices=dp_choices,
                            nargs=dp_nargs,
                            default=dp_default,
                            help=dp_help)

    # change none iterable Namespace object to dict
    preformated_data = cli.remove_keys_with_none_value(vars(parser.parse_args(args)))

    # All parameters come from configObj file
    if "file" in preformated_data.keys():
        logger.info('Parameters from configObj file')
        path_file = preformated_data["file"]
        if path_file[-3:] == 'ini':
            data = cli.cli_tools.read_configObj(path_file)
        else:
            print('extension not manage')
    # All parameters come from command line
    else:
        # format argparser to the right template
        logger.info('Parameters from command line')
        data = cli.cli_tools.format_parser(preformated_data)
        # if error print argparser help
        if data == {}:
            parser.print_help()

    # Next step from here : process data
    return data
