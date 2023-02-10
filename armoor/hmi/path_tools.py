import os

import logging
logger = logging.getLogger(__name__)

def get_config_reg_path(input_folder_path: str,
                        config_reg_day: str,
                        var: str) -> list:
    """
    Gets the regional configuration model path
    Parameters
    ----------
    input_folder_path : main input folder
    config_reg_day : day of production
    var : variable of interest

    Returns
    -------
    path(s) to the regional configuration model file(s)
    """
    path = f'{input_folder_path}{config_reg_day}/model/'
    logger.info(f'Regional configuration model path :')
    logger.info(f'{path}')

    files_needed_for_var = {"sst": ["sst_2D"],
                            "temp": ["h_3D", "temp_3D"],
                            "sss": ["sss_2D"],
                            "sal": ["h_3D", "saln_3D"],
                            "suv": ["u_2D", "v_2D"],
                            "uv": ["h_3D", "u_3D", "v_3D"],
                            "mld": ["h_3D", "temp_3D", "saln_3D"]
                            }
    final_paths = list()
    files_in_folder = os.listdir(path)
    for file in files_needed_for_var[var]:
        for file_in_folder in files_in_folder:
            if file in file_in_folder:
                print(f'{file_in_folder = }')
                final_paths.append(f'{path}{file_in_folder}')

    if final_paths:
        logger.debug('File(s) : ')
        logger.debug(final_paths)
        return final_paths

    logger.error(f"File not found for variable : {var}")


def get_obs_path(input_folder_path: str,
                 config_reg_day: str,
                 obs_name: str,
                 var: str) -> list:
    """
    Gets the observation path
    Parameters
    ----------
    input_folder_path : main input folder
    config_reg_day : day of production
    obs_name : observation name (also folder name)
    var : variable of interest

    Returns
    -------
    path(s) to the observation file(s)
    """
    path = f'{input_folder_path}{config_reg_day}/{obs_name}/'
    logger.info(f'Observation path :')
    logger.info(f'{path}')

    var_in_file = {"sst": "t",
                   "temp": "t",
                   "sss": "s",
                   "sal": "s"
                   }
    final_paths = list()
    for file in os.listdir(path):
        if var_in_file[var] in file.lower():
            final_paths.append(f'{path}{file}')

    if final_paths:
        logger.debug('File(s) : ')
        logger.debug(final_paths)
        return final_paths

    logger.error(f"File not found for variable : {var}")


def get_forcing_model_path(input_folder_path: str,
                           config_reg_day: str,
                           forcing_model: str,
                           var: str) -> list:
    """
    Gets the observation path
    Parameters
    ----------
    input_folder_path : main input folder
    config_reg_day : day of production
    forcing_model : forcing model name (also folder name)
        overwrite the use of the regional configuration model
    var : variable of interest

    Returns
    -------
    path(s) to the observation file(s)
    """
    path = f'{input_folder_path}{config_reg_day}/{forcing_model}/'
    logger.info(f'Forcing model path :')
    logger.info(f'{path}')

    final_paths = list()
    dirs = [f_path for f_path in os.listdir(path) if f_path[-2:] == 'nc' or f_path[-4:] == 'grib']

    if forcing_model == 'rivers':
        final_paths = sort_by_start_name(path, dirs, 17)
    else:
        if 'woa' in forcing_model:
            climato = {'temp': '_t', 'sal': '_s'}
            dirs = [file for file in dirs if climato[var] in file]
        for file in dirs:
            final_paths.append(f'{path}{file}')

    print(final_paths)
    if final_paths:
        logger.debug('File(s) : ')
        logger.debug(final_paths)
        return final_paths

    logger.error(f"File not found for variable : {var}")


def sort_by_start_name(path_folder: str, files: list, number_of_start_char: int) -> dict:
    """
    Sort files names by group, i.e. each group corresponds to a buoy
    Parameters
    ----------
    path_folder: root path of the buoys files
    files: all files from all buoys
    number_of_start_char: number of characters identical for a buoy

    Returns
    -------
    Dictionary of boys names, each buoy has a list of the corresponding files of that buoy
    """
    new_files = {}
    for file_name in files:
        if file_name[:number_of_start_char] in new_files:
            new_files[file_name[:number_of_start_char]].append(f'{path_folder}{file_name}')
        else:
            new_files.update({file_name[:number_of_start_char]: [f'{path_folder}{file_name}']})
    return new_files
