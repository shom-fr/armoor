"""
Functions to manage the creation of weather reports
"""
import datetime
import os
import json

from shapely.geometry.polygon import Polygon
from shapely.geometry import MultiPoint
import cartopy.crs as ccrs
import cartopy.feature as cfeature
import matplotlib.pyplot as plt

from armoor.cli.command_line_interface import command_line_interface
from armoor.base.calls_from_dict import dict2call
from armoor.hmi.script_tools import create_folder

import logging
logger = logging.getLogger(__name__)


def create_reports(dict_configuration: dict, output_folder_path: str) -> None:
    """
    Generates sources information (images and text) to create a weather report

    Parameters
    ----------
    dict_configuration : configuration weather report dictionary
    output_folder_path : path provided by the user

    Returns
    -------
    None
    """
    output_folder_path = os.path.join(output_folder_path, 'sources')
    create_folder(output_folder_path)

    logger.info('Reading sub configuration files')
    dict_configuration = manage_functionalities(dict_configuration,
                                                output_folder_path)
    logger.info('Creating minimap')
    dict_configuration = create_minimaps(dict_configuration,
                                         output_folder_path)
    logger.info('Creating configuration for report in json')
    create_json(format_dict(dict_configuration),
                output_folder_path)


def create_report(config_functionality: dict) -> None:
    """
    Generates plots and charts for a functionality with sub-functionalities with one meta-zone

    Parameters
    ----------
    config_functionality : dictionary as it could be provided in command line

    Returns
    -------
    None
    """
    dict2call(config_functionality)


def get_minimap_path(meta_zone_name: str, output_path_base: str) -> str:
    """
    Generates the path name for the meta-zone's minimap

    Parameters
    ----------
    meta_zone_name : Meta-zone name
    output_path_base : output path (output + sources/ )

    Returns
    -------
    None
    """
    if meta_zone_name:
        mini_map_path = os.path.join(output_path_base, f'minimap_{meta_zone_name}.png')
        return mini_map_path, f'minimap_{meta_zone_name}.png'
    return None, None


def create_minimaps(dict_configuration: dict, output_path_base: str) -> dict:
    """
    Generate the minimaps for all the meta-zones if there is a polygon provided.
    Adds the path to the meta-zone's minimap

    Parameters
    ----------
    dict_configuration : report dictionary with the meta-zones
    output_path_base : path to store the minimaps

    Returns
    -------
    The dictionary updated with the paths of the minimaps generated
    """
    for meta_zone_name in dict_configuration["meta_zones"]:
        polygon = dict_configuration["meta_zones"][meta_zone_name].get("polygon")
        meta_zone_path, mini_map_file_name = get_minimap_path(meta_zone_name, output_path_base)

        if polygon and meta_zone_path:
            meta_zone_bound, external_bound = create_bounds(polygon)
            plt.close('all')
            plt.figure(figsize=(2.5, 1.5))
            axes = plt.axes(projection=ccrs.Mercator())
            axes.set_extent(external_bound,
                            crs=ccrs.PlateCarree())
            axes.add_feature(cfeature.COASTLINE.with_scale('50m'),
                             linewidth=0.25)
            axes.add_feature(cfeature.LAND,
                             zorder=1,
                             edgecolor='k')
            # Adding meta-zone bounds
            axes.add_geometries([Polygon(meta_zone_bound)],
                                crs=ccrs.PlateCarree(),
                                facecolor=None,
                                edgecolor='blue',
                                alpha=0.8)
            logger.info(f'Saving :: {meta_zone_path}')
            plt.savefig(meta_zone_path, bbox_inches='tight', format='png')
            dict_configuration["meta_zones"][meta_zone_name]['path'] = mini_map_file_name
    return dict_configuration


def create_bounds(polygon: list, external_percentage_bound: int = 40) -> (list, tuple):
    """
    Generates meta_zone bound and external bound

    Parameters
    ----------
    polygon : List of point defining the polygon in the meta-zone
    external_percentage_bound : contour added to the meta-zone (default: 40%)

    Returns
    -------
    List of 5 tuples defining the edges of the rectangle (closed) of the meta-zone and
    4 values corresponding to 2 points defining the diagonal of the external bound.
    """
    (x00, y00, x11, y11) = MultiPoint(polygon).bounds
    meta_zone_bound = [(x00, y00), (x00, y11), (x11, y11), (x11, y00), (x00, y00)]

    buff = (external_percentage_bound / 100) * (abs(x00 - x11) + abs(y00 - y11)) / 2
    (x_min, y_min, x_max, y_max) = MultiPoint(polygon).buffer(buff).bounds
    external_bound = (x_min, x_max, y_min, y_max)

    return meta_zone_bound, external_bound


def safe_add_functionality_key(dict_configuration, metazone, key) -> dict:
    """
    Generates a new key for the functionality for a given meta-zone

    Parameters
    ----------
    dict_configuration : report dictionary with the meta-zones and functionalities
    metazone : meta-zone name where the functionality is applied
    key : functionality key

    Returns
    -------
    The dictionary updated with the new functionality key
    """
    if not dict_configuration['report'][metazone].get(key):
        dict_configuration['report'][metazone].update({key: None})
    return dict_configuration


def manage_functionalities(dict_configuration: dict, output_path_base: str) -> dict:
    """
    Generates all plots and updates to dict_configuration with the images paths generated.

    Parameters
    ----------
    dict_configuration : configuration report dictionary
    output_path_base : base path to store the plots

    Returns
    -------
    The dictionary updated with the paths of the plots
    """
    for metazone in dict_configuration['meta_zones']:
        logger.info(f'Handling meta-zone :: {metazone}')
        metazone_output_path = os.path.join(output_path_base, metazone)
        create_folder(metazone_output_path)
        dict_configuration['report'].update({metazone: {}})

        for functionality in dict_configuration['functionalities']:
            logger.info(f'Handling functionality :: {functionality}')
            if metazone in dict_configuration['functionalities'][functionality]['meta_zones']:
                try:
                    dict_configuration = safe_add_functionality_key(dict_configuration,
                                                                    metazone,
                                                                    functionality)
                    logger.info('Reading functionality configObj')
                    dict_configuration = incorporate_functionality(dict_configuration,
                                                                   functionality,
                                                                   metazone)
                    dict_configuration = update_output_path(dict_configuration,
                                                            functionality,
                                                            metazone_output_path,
                                                            metazone)

                    functionality_details = dict_configuration['report'][metazone][functionality]

                    logger.info('Creating plots for report')
                    create_report(functionality_details)
                    dict_configuration = get_output_files(dict_configuration,
                                                          functionality,
                                                          metazone_output_path,
                                                          metazone)
                    dict_configuration = set_output_path_for_report(dict_configuration,
                                                                    functionality,
                                                                    metazone)
                    logger.info(f'--- {functionality} created ---')
                except Exception as e:
                    logger.debug(f'--- Error : in {functionality} with {metazone} ---')
                    logger.debug(e)

    return dict_configuration


def incorporate_functionality(dict_configuration: dict,
                              functionality: str,
                              meta_zone: str) -> dict:
    """
    Adds information provided in the configuration files in the report

    Parameters
    ----------
    dict_configuration : configuration report dictionary
    functionality : functionality from the report dictionary process
    meta_zone : meta-zone from the report dictionary process

    Returns
    -------
    The dictionary updated with the details of the functionality
    """
    path_to_config = dict_configuration['functionalities'][functionality]['path_to_config']
    parser = command_line_interface(['--cfgfile', path_to_config])
    parser = add_meta_zone_from_name(parser, dict_configuration, meta_zone)
    dict_configuration['report'][meta_zone][functionality] = parser
    return dict_configuration


def add_meta_zone_from_name(parser: dict,
                            dict_configuration: dict,
                            meta_zone_name: str) -> dict:
    """
    Overwrites meta-zone properties with the meta-zone provided in the weather report

    Parameters
    ----------
    parser : meta-zone properties from functionality configuration file
    dict_configuration : configuration weather report dictionary
    meta_zone_name : meta-zone name

    Returns
    -------
    The dictionary updated with the right meta-zone properties for a functionality
    """
    meta_zone = dict_configuration["meta_zones"].get(meta_zone_name)
    if meta_zone:

        for key, value in [(key, value) for (key, value) in meta_zone.items() if
                           key != 'description']:
            if value:
                if key in ["time_restriction"]:
                    value = value[0], value[1]
                parser["meta_zones"][key] = value
        return parser

    raise f'Meta-zone not found {meta_zone_name}'


def update_output_path(dict_configuration: dict,
                       functionality: str,
                       output_path_base: str,
                       meta_zone: str) -> dict:
    """
    Generates output path and folder for a functionality

    Parameters
    ----------
    dict_configuration : configuration weather report dictionary
    functionality : functionality name
    output_path_base : base path
    meta_zone : meta-zone name

    Returns
    -------
    The dictionary updated with the new paths
    """
    output_path = os.path.join(output_path_base, functionality)
    create_folder(output_path)
    dict_configuration['report'][meta_zone][functionality]['output_path'] = output_path
    return dict_configuration


def set_output_path_for_report(dict_configuration: dict,
                               functionality: str,
                               meta_zone: str) -> dict:
    """
    Generates output path and folder for a functionality

    Parameters
    ----------
    dict_configuration : configuration weather report dictionary
    functionality : functionality name
    meta_zone : meta-zone name

    Returns
    -------
    The dictionary updated with the new paths
    """
    output_path = os.path.join(meta_zone, functionality)
    dict_configuration['report'][meta_zone][functionality]['output_path'] = output_path
    return dict_configuration


def get_output_files(dict_configuration: dict,
                     functionality: str,
                     output_path_base: str,
                     meta_zone: str) -> dict:
    """
    Retrieves the files names for a functionality in a meta-zone

    Parameters
    ----------
    dict_configuration : configuration weather report dictionary
    functionality : functionality name
    output_path_base : base path
    meta_zone : meta-zone name

    Returns
    -------
    The dictionary updated with the name's file of the functionality
    """
    output_path = os.path.join(output_path_base, functionality)
    new_outputs = []

    for output in dict_configuration['report'][meta_zone][functionality]["outputs"]:
        plot_name = output['plot']
        plot_folder_name = output['folder_name']
        sub_func_path = os.path.join(output_path, plot_folder_name)
        files = [f_path for f_path in os.listdir(sub_func_path) if f_path[-3:].lower() == 'png']
        files_paths = []
        for file in files:
            files_paths.append(f'{file}')
        new_outputs.append({'plot': plot_name, 'files': sorted(files_paths), 'folder_name': plot_folder_name})

    dict_configuration['report'][meta_zone][functionality]["outputs"] = new_outputs
    return dict_configuration


def format_dict(dict_configuration: dict) -> dict:
    """
    Formats the report dictionary before creating a json from it for the weather report

    Parameters
    ----------
    dict_configuration : configuration weather report dictionary

    Returns
    -------
    The dictionary formatted
    """
    meta_zones = [meta_zone for meta_zone in dict_configuration['report'] if
                  meta_zone not in ('title', 'format')]
    dict_configuration = remove_datasets_from_dict(dict_configuration, meta_zones)
    dict_configuration = remove_meta_zones_from_functionalities(dict_configuration, meta_zones)
    dict_configuration = clean_meta_zones(dict_configuration)
    dict_configuration = format_data_to_json(dict_configuration, meta_zones)

    return dict_configuration


def remove_datasets_from_dict(dict_configuration: dict, meta_zones: list) -> dict:
    """
    Removes the datasets from the dictionary

    Parameters
    ----------
    dict_configuration : configuration weather report dictionary
    meta_zones : list of meta-zones

    Returns
    -------
    The dictionary updated
    """
    for meta_zone in meta_zones:
        for functionality in dict_configuration['report'][meta_zone]:
            if 'models' in dict_configuration['report'][meta_zone][functionality]:
                dict_configuration['report'][meta_zone][functionality].pop('models')
            if 'observation' in dict_configuration['report'][meta_zone][functionality]:
                dict_configuration['report'][meta_zone][functionality].pop('observation')

    return dict_configuration


def remove_meta_zones_from_functionalities(dict_configuration: dict, meta_zones: list) -> dict:
    """
    Removes the meta-zone from the functionalities

    Parameters
    ----------
    dict_configuration : configuration weather report dictionary
    meta_zones : list of meta-zones

    Returns
    -------
    The dictionary updated
    """
    for meta_zone in meta_zones:
        for functionality in dict_configuration['report'][meta_zone]:
            dict_configuration['report'][meta_zone][functionality].pop('meta_zones')
    return dict_configuration


def clean_meta_zones(dict_configuration: dict) -> dict:
    """
    Remove None values from meta-zones

    Parameters
    ----------
    dict_configuration : configuration weather report dictionary

    Returns
    -------
    The dictionary updated
    """
    for meta_zone_name in dict_configuration['meta_zones']:
        for key, value in dict_configuration['meta_zones'][meta_zone_name].items():
            if value is None:
                dict_configuration['meta_zones'][meta_zone_name].pop(key)
    return dict_configuration


def format_data_to_json(dict_configuration: dict, meta_zones: list) -> dict:
    """
    Arrange the configuration weather report dictionary for the final report
    Adds creation date

    Parameters
    ----------
    dict_configuration : configuration weather report dictionary
    meta_zones : list of meta-zones

    Returns
    -------
    The dictionary updated
    """
    dict_configuration['report']['metazones'] = []

    for meta_zone in meta_zones:
        sub_meta = {}
        mz_properties = dict_configuration['meta_zones'].pop(meta_zone)
        mz_functionalities = dict_configuration['report'].pop(meta_zone)

        sub_meta.update({'properties': mz_properties,
                         'functionalities': mz_functionalities.values()
                         })

        dict_configuration['report']['metazones'].append(sub_meta)

    dict_configuration.pop("functionalities")
    dict_configuration.pop("meta_zones")
    dict_configuration['report']['date'] = datetime.date.today().strftime('%d/%m/%Y')

    return dict_configuration


def create_json(dict_configuration: dict, output_folder_path: str) -> None:
    """
    Creates the final configuration json for the weather report
    Parameters
    ----------
    dict_configuration : configuration weather report dictionary
    output_folder_path : path where the json file will be stored

    Returns
    -------
    None
    """
    # WRITING PRODUCTION INFO INTO JSON FILE
    json_data_path = os.path.join(output_folder_path, 'data.json')
    with open(json_data_path, 'w', encoding='utf-8') as json_file:
        json.dump(dict_configuration, json_file, indent=4, ensure_ascii=False)
