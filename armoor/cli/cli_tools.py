"""
Tools for the command line interface
"""
import json
import os
from argparse import ArgumentTypeError

from configobj import ConfigObj
from validate import Validator, VdtTypeError

import logging
logger = logging.getLogger(__name__)

path2configobj_spec = "../../config/cli/spec.ini"

# list of the available meta-zones
METAZONES = ['polygon', 'cloud', 'radius', 'quality',
             'start', 'end', 'frequency', 'times', 'time_highlight', 'interval',
             'time_restriction', 'cyclic', 'depth', 'bathy', 'density', 'vars'
             ]
# list of the variables the user can select
VARS = ["temp", "sal", "dens", "sndspd", "gbt", "mld", "uv"]

list_of_available_methods = ["linear", "nearest"]


def readText2code(path):
    """
    Read json file and return a dictionary.

    Parameters
    ----------
    path : path
        path to the json file

    Returns
    -------
    data : dict
        Dictionary with the json content.
    """
    # Opening JSON file
    try:
        rootdir = os.path.abspath(os.path.dirname(__file__))
        file = open(os.path.join(rootdir, path))
    except:
        print('Parser config file not found')

    # returns JSON object as
    # a dictionary
    data = json.load(file)

    # Closing file
    file.close()
    return data


def read_configObj(path) -> dict:
    """
    Read et check the configObj file and return a formatted dictionary.

    Parameters
    ----------
    path : path
        path to the configObj file

    Returns
    -------
    config : dict
        Dictionary with the configuration wanted.
    """

    # reading file to perform all the checking
    try:
        rootdir = os.path.abspath(os.path.dirname(__file__))
        config = ConfigObj(path, configspec=os.path.join(rootdir, path2configobj_spec))
    except:
        logger.error('You should check the information given in your .ini file or command line instructions')
        return


    # initialize validation object
    val = Validator()
    custom_validation_types = {
        'absolute_or_relative_time': int_or_string_configobj,  # @1
        'path': file_path,  # @2
        'directory': folder_path,  # @2BIS
        'force_list_path': file_force_list_path_configObj,  # @3
        'depth': depth_configObj,  # @4
        'coordinates': coords_configObj,  # @5
        'vars_list': vars_list_configObj  # @6
    }

    for type_name, type_validation_function in custom_validation_types.items():
        val.functions[type_name] = type_validation_function
    validation_test = config.validate(val)

    if validation_test:
        format_cofigObj2Dict(config)
        return config
    else:
        print(f'{validation_test = }')
        return None


def int_or_string_configobj(value):
    """ @1
    check "absolute_or_relative_time" type : in the configObj file provided by the user.

    Parameters
    ----------
    value : int or str
        path to the configObj file

    Returns
    -------
    config : dict
        Dictionary with the configuration wanted.
    """

    if not isinstance(value, (str, int)):
        # a value in the list
        # is neither an integer nor a string
        raise VdtTypeError(value)
    is_int = True
    try:
        # converting to integer
        int(value)
    except ValueError:
        is_int = False
    if is_int:
        value = int(value)
    return value


def file_path(path_name: str) -> str:
    """ @2
    use when a path is provided
    check "path" type, check if path exist.

    Parameters
    ----------
    path_name : str
        path to the file

    Returns
    -------
    path : str
        path to wanted file.
    """
    if os.path.isfile(path_name):
        return path_name
    else:
        raise FileNotFoundError(path_name)


def folder_path(path_name: str) -> str:
    """ @2BIS
    use when a directory is provided
    check "directory" type, check if path to folder exist.

    Parameters
    ----------
    path_name : str
        path to the folder

    Returns
    -------
    path : str
        path to wanted folder.
    """
    if os.path.isdir(path_name) and path_name[-1:] == '/':
        return path_name
    else:
        raise NotADirectoryError(path_name)


def file_force_list_path_configObj(path_names):
    """ @3
    use when a list of path is provided
    check "force_list_path" type, check if paths exist.

    Parameters
    ----------
    path_name : str
        path(s) to the file(s)

    Returns
    -------
    path : str or list(str)
        path(s) to wanted file(s).
    """
    if isinstance(path_names, list):
        for arg in path_names:
            file_path(arg)
        return path_names
    else:
        return file_path(path_names)


def try_str2float(value) -> float:
    """
    ensure that the output of this function is always a positive float

    Parameters
    ----------
    value : str (or float)
        value to verify and transform

    Returns
    -------
    value : float
        value as a float
    """
    if not isinstance(value, (str, int, float)):
        # a value in the list
        # is neither an integer nor a string
        raise VdtTypeError(value)
    is_float = True
    try:
        # converting to integer
        float(value)
    except ValueError:
        is_float = False
    if is_float:
        value = float(value)
        if value >= 0.0:
            return float(value)
        else:
            raise ValueError("depth or step must be positive values")
    return None


def depth_configObj(depths) -> list:
    """ @4
    if depths length is 1 : it's for the selection of a layer
    if depths length is 2 : it's for the selection of all the layers between the 2 values.
    if depths length is 3 : it's for the selection of some layers between the 2 first values,
        with a certain step (third value)

    Parameters
    ----------
    depths : str or list of depths
        1 : layer
        2 : layer min and layer max
        3 : layer min, layer max and step

    Returns
    -------
    depths : list
        depths (length from 1 to 3)
    """
    # case of sandwich depths
    if isinstance(depths, list) and len(depths) <= 3:
        depths = [try_str2float(depth) for depth in depths]
        # check if depths are in the right order
        if len(depths) >= 2 and depths[0] >= depths[1]:
            raise ValueError(f'depth {depths[0]} < {depths[1]} must be true')
        # check if step is lower the the interval between depth min and depth max
        if len(depths) == 3 and depths[1] - depths[0] <= depths[2]:
            raise ValueError(f'step {depths[2]} is too large {depths[0]} - {depths[1]} = {depths[1] - depths[0]}')
        return depths
    # case of one layer of depth
    elif isinstance(depths, str):
        return [try_str2float(depths)]
    # other cases through an error
    else:
        logger.error(f' depth_config_Obj : {type(depths) = }')
        raise ArgumentTypeError("error with depth param")


# function to check if the coordinates provided are well formatted
def coords_configObj(coordinates) -> list:
    """ @5
    use when coordinates are provided
    check "coordinates" type, check if coordinates are even and perform cleanup.

    Parameters
    ----------
    coordinates : list of coordinates
        coordinates for polygons or cloud points

    Returns
    -------
    coordinates : list
        coordinates well formatted as a list of tuples
    """
    new_coordinates = []
    if isinstance(coordinates, list):
        size = len(coordinates)
        if size % 2 != 0:
            raise VdtTypeError(coordinates)
        for i in range(0, size, 2):
            lat = coordinates[i]
            lon = coordinates[i + 1]

            # remove unwanted characters
            for blacklistchar in '{([)]}':
                lat = lat.replace(blacklistchar, '')
                lon = lon.replace(blacklistchar, '')
            coordinate = float(lat), float(lon)
            new_coordinates.append(coordinate)
        return new_coordinates
    else:
        # a value in the list
        # is neither an integer nor a string
        raise VdtTypeError(coordinates)


def vars_list_configObj(args):
    """ @6
    used when a list of the variables is provided
    check "vars_list" type, verify if the user selection of variable is in the list

    Parameters
    ----------
    args : str (or float)
        value to verify and transform

    Returns
    -------
    value : float
        value as a float
    """

    if args in VARS:
        return [args]
    elif not isinstance(args, list):
        # a value in the list
        # is neither an integer nor a string
        logger.error(f'{args} not a string or a list of strings')
        raise VdtTypeError(args)
    else:
        vars = []
        for arg in args:
            if arg in VARS:
                vars.append(arg)
            else:
                logger.error(f'{arg} is not in {VARS}')
                raise VdtTypeError(f'variable not recognized : {arg}')
        return vars


def format_cofigObj2Dict(config: dict) -> dict:
    """
    function to format configObj input to useful dictionary

    Parameters
    ----------
    config : dict
        rough dictionary

    Returns
    -------
    config : dict
        formatted dictionary
    """
    # Clean observation if method_z not provided
    observation = remove_keys_with_none_value(config.pop("observation"))
    if "method-z" in observation:
        method_z = observation.pop("method-z")
        observation.update({"method_z": method_z})
    config.update({"observation": observation})

    if "output-path" in config:
        output_path = config.pop("output-path")
        if output_path:
            config.update({"output_path": output_path})

    # models
    if "models" in config:
        models = config.pop("models")
        new_models = []
        for model in models:
            if isinstance(model, list):
                new_models.append(remove_keys_with_none_value(models[model]))
            else:
                new_models.append(remove_keys_with_none_value(models[model]))
            if "method-z" in new_models:
                method_z = new_models.pop("method-z")
                new_models.update({"method_z": method_z})
        config.update({"models": new_models})
    else:
        logger.error('No model provided')
        raise VdtTypeError('no model provided')

    # outputs
    if "outputs" in config:
        outputs = config.pop("outputs")
        new_outputs = []
        for output in outputs:
            outputs[output].update({"folder_name": output})
            new_outputs.append(remove_keys_with_none_value(outputs[output]))
        config.update({"outputs": new_outputs})
    else:
        logger.error('No output provided')
        raise VdtTypeError(f'no outputs provided')

    # clean meta-zones from None values
    if "meta-zones" in config:
        meta_zones = remove_keys_with_none_value(config.pop("meta-zones"))
        if meta_zones:
            config.update({"meta_zones": meta_zones})

        # change 2 item list of time restriction toto tuple
        if "time-restriction" in config["meta_zones"]:
            time_restriction = config["meta_zones"].pop("time-restriction")
            config["meta_zones"].update({"time_restriction": time_restriction})
        if "time-highlight" in config["meta_zones"]:
            time_restriction = config["meta_zones"].pop("time-highlight")
            config["meta_zones"].update({"time_highlight": time_restriction})
        for value in ["time_restriction"]:
            if value in config["meta_zones"]:
                aux = config["meta_zones"].pop(value)
                config["meta_zones"].update({value: (aux[0], aux[1])})
        for value in ["quality"]:
            if value in config["meta_zones"]:
                aux = config["meta_zones"].pop(value)
                config["meta_zones"].update({value: [aux[0], int(aux[1]), int(aux[2])]})

    return config


def remove_keys_with_none_value(dictionary: dict) -> dict:
    """
    function to remove all keys with None value

    Parameters
    ----------
    dictionary : dict
        rough dictionary (with none values)

    Returns
    -------
    dictionary : dict
        cleaned dictionary, all keys have values
    """
    for key, value in dict(dictionary).items():
        if value is None:
            del dictionary[key]
    return dictionary


def convert_type(input_type: str):
    """
    function to transform str type to real type

    Parameters
    ----------
    input_type : str
        rough dictionary (with none values)

    Returns
    -------
    type : real type (int, float, str, etc)
        transform str type to real type
    """
    known_types = {'int': int,
                   'str': str,
                   'float': float,
                   'file_path': file_path,
                   'folder_path': folder_path,
                   'coords': coords
                   }

    if input_type is None:
        return None
    elif input_type in known_types:
        return known_types[input_type]
    else:
        logger.error("Type not found")
        raise VdtTypeError(f'Unknown type : {input_type}')


# function to check if the coordinates provided are well formatted
def coords(s):
    try:
        lat, lon = map(float, s.split(','))
        return lat, lon
    except:
        raise ArgumentTypeError("Coordinates must be lat,lon")


def convert_nargs(input_nargs: str):
    if input_nargs is None:
        return None
    else:
        return int_or_string_configobj(input_nargs)


#       ^
#       | For configObj
########################################################################################################################
#       ||
#       \/ For parser

def format_parser(preformatted_data: dict) -> dict:
    """
    Read and check the command line inputs : return a formatted dictionary.

    Parameters
    ----------
    preformatted_data : dict
        rough dictionary with the inputs of the command line parser

    Returns
    -------
    config : dict
        Dictionary with the configuration wanted.
    """
    config = {}
    parse_formatting_functions = [format_parser_metazones,
                                  format_parser_format,
                                  format_parser_colocate,
                                  format_parser_functionality,
                                  format_parser_outputs,
                                  format_parser_observation,
                                  format_parser_models,
                                  format_output_folder]

    for function in parse_formatting_functions:
        preformatted_data, new_data = function(preformatted_data)
        if new_data:
            config.update(new_data)

    if preformatted_data == {}:
        # all formatting and parsing went well
        return config
    else:
        raise ArgumentTypeError(f"formatting command line inputs went wrong remaining : {preformatted_data} ")


def format_parser_metazones(preformatted_data: dict) -> (dict, dict):
    """
    Used to handle "meta-zones" from command line
    Check and format "meta-zones" from command line parser

    Parameters
    ----------
    preformatted_data : dict
        rough dictionary with the inputs of the command line parser

    Returns
    -------
    preformatted_data : dict
        same rough dictionary as in input but without the "meta-zones"
    new_data : list
        "meta-zones" well formatted ready to added to the final config dictionary
    """
    # Meta-zone: there is at least one meta-zone filter
    if len(set(preformatted_data).intersection(set(METAZONES))) > 0:

        new_data = {"meta_zones": {}}

        # Set meta-zone name
        meta_name = preformatted_data.pop("meta_name") if "meta_name" in preformatted_data else "Meta-zone-default-name"
        new_data["meta_zones"].update({"name": meta_name})

        # Set meta-zone filters
        for key in METAZONES:
            if key in preformatted_data:
                new_data["meta_zones"].update({key: preformatted_data.pop(key)})

        # little adjustment to the
        for value in ["time_restriction"]:
            if value in new_data["meta_zones"]:
                aux = new_data["meta_zones"].pop(value)
                new_data["meta_zones"].update({value: (aux[0], aux[1])})
        for value in ["quality"]:
            if value in new_data["meta_zones"]:
                aux = new_data["meta_zones"].pop(value)
                new_data["meta_zones"].update({value: [aux[0], int(aux[1]), int(aux[2])]})

        # check if vars are known
        if "vars" in new_data["meta_zones"]:
            # check if vars are in VARS array
            for var in new_data["meta_zones"]["vars"]:
                if var not in VARS:
                    raise ArgumentTypeError(f"{var} not in {VARS}")

        return preformatted_data, new_data
    else:
        # Nothing is done
        return preformatted_data, None


def format_parser_format(preformatted_data: dict) -> (dict, dict):
    """
    Used to handle "output format" from command line
    Check and format "output format" from command line parser

    Parameters
    ----------
    preformatted_data : dict
        rough dictionary with the inputs of the command line parser

    Returns
    -------
    preformatted_data : dict
        same rough dictionary as in input but without the "output format"
    new_data : list
        "output format" well formatted ready to added to the final config dictionary
    """
    # Format: Set output format
    output_format = preformatted_data.pop("format")
    # if there is only one value, convert it to a list
    if isinstance(output_format, str):
        output_format = [output_format]

    return preformatted_data, {"format": output_format}


def format_parser_colocate(preformatted_data: dict) -> (dict, dict):
    """
    Used to handle "colocation" from command line
    Check and format "colocation" from command line parser

    Parameters
    ----------
    preformatted_data : dict
        rough dictionary with the inputs of the command line parser

    Returns
    -------
    preformatted_data : dict
        same rough dictionary as in input but without the "colocation"
    new_data : list
        "colocation" well formatted ready to added to the final config dictionary
    """
    colocate = preformatted_data.pop("colocate")
    return preformatted_data, {"colocate": colocate}


def format_parser_functionality(preformatted_data: dict) -> (dict, dict):
    """
    Used to handle "functionality" from command line
    Check and format "functionality" from command line parser

    Parameters
    ----------
    preformatted_data : dict
        rough dictionary with the inputs of the command line parser

    Returns
    -------
    preformatted_data : dict
        same rough dictionary as in input but without the "functionality"
    new_data : list
        "functionality" well formatted ready to added to the final config dictionary
    """
    if "func" in preformatted_data:
        functionality = preformatted_data.pop("func")
        return preformatted_data, {"functionality": functionality}
    else:
        raise ArgumentTypeError("functionality not provided")


def format_parser_outputs(preformatted_data: dict) -> (dict, dict):
    """
    Used to handle "outputs" from command line
    Check and format "outputs" from command line parser

    Parameters
    ----------
    preformatted_data : dict
        rough dictionary with the inputs of the command line parser

    Returns
    -------
    preformatted_data : dict
        same rough dictionary as in input but without the "outputs"
    new_data : list
        "outputs" well formatted ready to added to the final config dictionary
    """
    # Set plot output
    if "plot" in preformatted_data:
        outputs = {}
        output_vars = ["plot", "attribute", "colormap", "vmin", "vmax"]
        for output_var in output_vars:
            if output_var in preformatted_data:
                outputs.update({output_var: preformatted_data.pop(output_var)})
        return preformatted_data, {"outputs": [outputs]}
    else:
        raise ArgumentTypeError("output choice not provided")


def format_output_folder(preformatted_data: dict) -> (dict, dict):
    """
        Used to handle "output directory" from command line
        Check and format "directory" from command line parser

        Parameters
        ----------
        preformatted_data : dict
            rough dictionary with the inputs of the command line parser

        Returns
        -------
        preformatted_data : dict
            same rough dictionary as in input but without the "output_folder"
        new_data : dict
            "directory" well formatted and checked ready to be added to the final config dictionary
        """
    if "output_path" in preformatted_data:
        directory = preformatted_data.pop("output_path")
        return preformatted_data, {"output_path": directory}
    else:
        return preformatted_data, None


def format_parser_observation(preformatted_data: dict) -> (dict, dict):
    """
    Used to handle "observation" from command line
    Check and format "observation" from command line parser

    Parameters
    ----------
    preformatted_data : dict
        rough dictionary with the inputs of the command line parser

    Returns
    -------
    preformatted_data : dict
        same rough dictionary as in input but without the "observation"
    new_data : list
        "observation" well formatted ready to added to the final config dictionary
    """
    # set Observation
    if "observation" in preformatted_data:
        observation = {}
        observation.update({"name": preformatted_data.pop("obs_name"),
                            "path": preformatted_data.pop("observation")
                            })
        if "obs_method" in preformatted_data:
            method = preformatted_data.pop("obs_method")
            if method in list_of_available_methods:
                observation.update({"method": method})
            else:
                raise ArgumentTypeError(f"method not recognise {method}")
        if "obs_method_z" in preformatted_data:
            method_z = preformatted_data.pop("obs_method_z")
            if method_z in list_of_available_methods:
                observation.update({"method_z": method_z})
            else:
                raise ArgumentTypeError(f"method not recognise {method_z}")
        return preformatted_data, {"observation": observation}
    else:
        raise ArgumentTypeError("no observation provided")


def format_parser_models(preformatted_data: dict) -> (dict, dict):
    """
    Used to handle "models" from command line
    Check and format "models" from command line parser

    Parameters
    ----------
    preformatted_data : dict
        rough dictionary with the inputs of the command line parser

    Returns
    -------
    preformatted_data : dict
        same rough dictionary as in input but without the "models"
    new_data : list
        "models" well formatted ready to added to the final config dictionary
    """
    if "models" in preformatted_data:
        new_models = []

        # models paths
        models = preformatted_data.pop("models")

        # models names
        names_exist = False
        if "mod_names" in preformatted_data:
            names = preformatted_data.pop("mod_names")
            if len(models) == len(names):
                names_exist = True
                mod_names = names
            else:
                raise ArgumentTypeError(f"number of models ({len(models)}) don't match the " +
                                        f"number of names ({len(names)}) provided")
        if not names_exist:
            mod_names = [f'model_{i}' for i, m in enumerate(models)]

        # models methods
        method_exist = False
        if "mod_methods" in preformatted_data:
            methods = preformatted_data.pop("mod_methods")
            if len(models) == len(methods):
                method_exist = True
                mod_methods = methods
            else:
                raise ArgumentTypeError(f"number of models ({len(models)}) don't match the " +
                                        f"number of methods ({len(methods)}) provided")

        # models methods z
        method_z_exist = False
        if "mod_methods_z" in preformatted_data:
            methods_z = preformatted_data.pop("mod_methods_z")
            if len(models) == len(methods_z):
                method_z_exist = True
                mod_methods_z = methods_z
            else:
                raise ArgumentTypeError(f"number of models ({len(models)}) don't match the " +
                                        f"number of methods z ({len(methods_z)}) provided")
        # add models with path, name and (method)
        for i, (model, name) in enumerate(zip(models, mod_names)):
            new_model = {}

            new_model.update({"path": model})
            new_model.update({"name": name})

            if method_exist and mod_methods[i]:
                if mod_methods[i] in list_of_available_methods:
                    new_model.update({"method": mod_methods[i]})
                else:
                    raise ArgumentTypeError(f"method not recognise {mod_methods[i]}")

            if method_z_exist and mod_methods_z[i]:
                if mod_methods_z[i] in list_of_available_methods:
                    new_model.update({"method": mod_methods_z[i]})
                else:
                    raise ArgumentTypeError(f"method not recognise {mod_methods_z[i]}")

            new_models.append(new_model)

        return preformatted_data, {"models": new_models}
    else:
        raise ArgumentTypeError("no model provided")
