"""Decode the config file to plot the required outputs"""

import xarray as xr
from armoor import base

import logging
logger = logging.getLogger(__name__)

def dict2call(config_obj: dict):
    """
    Parse dictionary to call the appropriate methods and functions.

    Parameters
    ----------
    config_obj : dict
        Dictionary specifying the observation, models, functionality, output etc.
        Can be formatted out of a json file using cli.command_line_interface.

    """
    config_obj = get_observation_models_meta(config_obj)
    features = {"sst": base.feature_sst,
                "prof_hydro_vessel": base.feature_prof_hydro_vessel,
                "prof_hydro_mooring": base.feature_prof_hydro_mooring,
                "section_hydro": base.feature_section_hydro,
                "clim_hydro": base.feature_clim_hydro,
                "currents_hfr": base.feature_currents_hfr,
                "currents_ADCP": base.feature_currents_ADCP,
                "currents_VMADCP": base.feature_currents_VMADCP,
                "drifters": base.feature_drifters
                }

    selected_feature = config_obj["functionality"]

    if selected_feature in features:
        logger.info(f'Feature selected :: {selected_feature}')
        features[config_obj["functionality"]].plot(config_obj)
    else:
        logger.debug(f'Feature {selected_feature} not found')


def get_observation_models_meta(config_obj: dict):
    """
    Replace the path to a netCDF into the actual xarray, then apply the meta-zone filters,
    finally return the filtered observation and the models.

    Parameters
    ----------
    config_obj : dict
        Parser with paths to observation and models.

    Returns
    -------
    config_obj : dict
        Dictionary with observations and models names and xarray.Dataarrays.
    """

    # Open dataset from path then decode dataset and apply meta-zone
    observation = config_obj["observation"]
    models = config_obj["models"]

    logger.info(f"Using functionality : {config_obj['functionality']}")

    # Get observation type to read txt observation files
    logger.info(f"Reading observation files")

    obs_type = config_obj['observation'].get('type')
    if "ADCP" in config_obj['functionality'] and obs_type is None:
        logger.warning("Pour lire les fichiers ADCP, vous devriez préciser le format dans la variable \"type\" du "
                       "fichier de paramètres. Cette variable peut être \"LADCP\", \"VMADCP\" ou "
                       "\"mouillage\". ")

    # Read observations
    logger.info(f"Opening observation from file(s)")
    observation.update({"xarray": base.open_file(observation.pop("path"), config_obj['functionality'], obs_type)})
    logger.info(f"Applying : decode and meta zone on observation")
    observation.update({"xarray_meta": apply_metas2dataset(observation["xarray"].read.decode(),
                                                           config_obj,
                                                           get_method(observation))
                        })

    logger.info(f"File(s) read")
    # Set initial colocation flags
    temporal_colocation_flag = True
    vertical_colocation_flag = True
    horizontal_colocation_flag = True

    # Open dataset from path then decode dataset and apply meta-zone
    for imod, model in enumerate(models):
        logger.info(f"Reading model : {imod}")

        # Get type of model (in case HYCOM)
        if "type" in model:
            mod_type = model['type']
        else:
            mod_type = None
        logger.info(f"Opening model from file(s)")
        model.update({"xarray": base.open_file(model.pop("path"), config_obj['functionality'], mod_type)})
        logger.info(f"Applying : decode and meta zone on model")
        model.update({"xarray_meta": apply_metas2dataset(model["xarray"].read.decode(),
                                                         config_obj,
                                                         get_method(model))
                      })

        if 'depth' not in model["xarray_meta"] or model["xarray_meta"].depth.values.dtype == 'float32':
            vertical_colocation_flag = False
        elif 'depth' not in model["xarray_meta"]:
            vertical_colocation_flag = False
        logger.info(f"File(s) read for model {imod}")

    observation.update({"xarray_meta_coloc": []})

    # Colocation for functionality 2
    if config_obj["functionality"] == "prof_hydro_vessel":
        vertical_colocation_flag = True
        horizontal_colocation_flag = True
        temporal_colocation_flag = True

    # Colocation for functionnality 3
    if config_obj["functionality"] == "prof_hydro_mooring":
        vertical_colocation_flag = True
        horizontal_colocation_flag = True
        temporal_colocation_flag = True

    # Colocation for functionnality 4
    if config_obj["functionality"] == "section_hydro":
        vertical_colocation_flag = True
        horizontal_colocation_flag = True
        temporal_colocation_flag = True

    # Colocation for functionnality 5
    if config_obj["functionality"] == "clim_hydro":
        temporal_colocation_flag = False

    # Colocation for functionnality 6
    if config_obj["functionality"] == "currents_hfr":
        vertical_colocation_flag = False

    # Colocation for functionnality 7
    if config_obj["functionality"] == "currents_ADCP":
        temporal_colocation_flag = True
        vertical_colocation_flag = True
        horizontal_colocation_flag = False

    logger.info(f"Collocating model(s) and observation")
    for index_model, model in enumerate(models):
        # Colocation per model
        obs_coloc, mod_coloc = base.colocate_all(observation["xarray_meta"],
                                                 model["xarray_meta"],
                                                 horizontal_colocation_flag,
                                                 vertical_colocation_flag,
                                                 temporal_colocation_flag,
                                                 coloc_method=get_method(model),
                                                 opt_grid=config_obj["colocate"])

        observation["xarray_meta_coloc"].append(obs_coloc)
        model.update({"xarray_meta_coloc": mod_coloc})

        logger.info(f"Collocation done for model {index_model}")

        # Interval temporels successifs
        if 'interval' in config_obj["meta_zones"]:
            logger.info('Découpage par intervalles temporels...')
            if horizontal_colocation_flag or vertical_colocation_flag:
                interval = config_obj["meta_zones"]["interval"]
                model["xarray_meta"] = model["xarray_meta"].meta.time_selection_interval(interval)
                model["xarray_meta_coloc"] = model["xarray_meta_coloc"].meta.time_selection_interval(interval)
                observation["xarray_meta_coloc"][index_model] = observation["xarray_meta_coloc"][
                    index_model].meta.time_selection_interval(interval)
            else:
                interval = config_obj["meta_zones"]["interval"]
                model["xarray_meta"] = model["xarray_meta"].meta.time_selection_interval(interval)
        else:  # no interval
            if horizontal_colocation_flag or vertical_colocation_flag:
                model.update({"xarray_meta_coloc": mod_coloc})

        # Tranches verticales
        if 'slice' in config_obj["meta_zones"]:
            if 'depth' in config_obj["meta_zones"]:
                var_slice = 'depth'
            elif 'dens' in config_obj["meta_zones"]:
                var_slice = 'dens'

            logger.info(f'Découpage par tranches verticales sur la variable {var_slice}...')
            if horizontal_colocation_flag or vertical_colocation_flag:
                slice = config_obj["meta_zones"]["slice"]
                model["xarray_meta"] = model["xarray_meta"].meta.vertical_selection_slice(slice, var_slice)
                model["xarray_meta_coloc"] = model["xarray_meta_coloc"].meta.vertical_selection_slice(slice, var_slice)
                observation["xarray_meta"] = observation["xarray_meta"].meta.vertical_selection_slice(slice, var_slice)
                observation["xarray_meta_coloc"][index_model] = observation["xarray_meta_coloc"][
                    index_model].meta.vertical_selection_slice(slice, var_slice)
            else:
                slice = config_obj["meta_zones"]["slice"]
                model["xarray_meta"] = model["xarray_meta"].meta.vertical_selection_slice(slice, var_slice)

    if 'interval' in config_obj["meta_zones"].keys():
        interval = config_obj["meta_zones"]["interval"]
        observation["xarray_meta"] = observation["xarray_meta"].meta.time_selection_interval(interval)

    return config_obj


def get_method(data) -> str:
    """
    Get the method to use.
    Parameters
    ----------
    data : dict
        Parser.
    method : str
        Method to use.
    Returns
    -------
        str
        Method to use.
    """
    method = data.get('method')

    if method is None:
        logger.warning(f'No method provided for {data.get("name")}')

    return method


def apply_metas2dataset(xarray_obj: xr.Dataset, meta_zones: dict, method: str) -> xr.Dataset:
    """
    Apply meta zone to subset dataset.

    Parameters
    ----------
    xarray_obj : dict
        Parser defined by user, containing xarray.Datasets.
    meta_zones : dict
        Meta-zone from the parser, defines the regions and periods to study.
    method : str
        Method to interpolate / select data.

    Returns
    -------
    res_xarray_obj : xarray.Dataset
        Subset dataset.

    """
    logger.info("Applying meta zone")

    filters = {
        "quality": lambda obj: obj.meta.quality_filter,
        "vars": lambda obj: obj.meta.var_selection,
        "depth": lambda obj: obj.meta.vertical_selection_depth,
        "dens": lambda obj: obj.meta.vertical_selection_dens,
        "polygon": lambda obj: obj.meta.horizontal_selection_polygon,
        "start": lambda obj: obj.meta.time_selection_start,
        "end": lambda obj: obj.meta.time_selection_end,
        "times": lambda obj: obj.meta.time_selection_list,
        "frequency": lambda obj: obj.meta.time_selection_freq,
        "time_restriction": lambda obj: obj.meta.time_restriction,
        "cyclic": lambda obj: obj.meta.time_selection_climatological
        }

    if "meta_zones" in meta_zones:
        # we apply the filters one after the other
        for name, filter in filters.items():
            if name in meta_zones["meta_zones"]:
                logger.info(f"Applying : {name}")
                xarray_obj = filter(xarray_obj)(meta_zones["meta_zones"][name])

        ##################################################################################################
        radius = meta_zones["meta_zones"]["radius"] if "radius" in meta_zones["meta_zones"] else None
        if "cloud" in meta_zones["meta_zones"]:
            logger.info(f"Applying : cloud")
            points = meta_zones["meta_zones"]["cloud"]
            xarray_obj = xarray_obj.meta.horizontal_selection_cloud_dots(points, radius, method)
        ##################################################################################################

    return xarray_obj
