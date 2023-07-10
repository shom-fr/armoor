"""Decode the config file to plot the required outputs"""

import xarray as xr
from armoor import base
import numpy as np
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
    features = {"sst": base.feature_sst, "prof_hydro_vessel": base.feature_prof_hydro_vessel,
                "prof_hydro_mooring": base.feature_prof_hydro_mooring, "section_hydro": base.feature_section_hydro,
                "clim_hydro": base.feature_clim_hydro, "currents_hfr": base.feature_currents_hfr,
                "currents_ADCP": base.feature_currents_ADCP, "currents_VMADCP": base.feature_currents_VMADCP,
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

    logger.info("Reading observation files")

    # Open observation dataset from path then decode dataset and apply meta-zone
    logger.info("Opening observation from file(s)")
    obs_type = config_obj['observation'].get('type')
    observation.update({"xarray": base.open_decode(observation.pop("path"), config_obj['functionality'], obs_type)})
    logger.info("Applying : decode and meta zone on observation")
    observation.update({"xarray_meta": apply_metas2dataset(observation["xarray"], config_obj, get_method(observation))
                        })
    logger.info("File(s) read for observation")

    # Open model dataset from path then decode dataset and apply meta-zone
    for imod, model in enumerate(models):
        logger.info(f"Reading model : {imod}")

        # Get type of model (in case HYCOM)
        mod_type = model.get('type')

        logger.info("Opening model from file(s)")
        model.update({"xarray": base.open_decode(model.pop("path"), config_obj['functionality'], mod_type)})

        logger.info("Applying : decode and meta zone on model")
        model.update({"xarray_meta": apply_metas2dataset(model["xarray"], config_obj, get_method(model), mod_obs='mod')
                      })

        logger.info(f"File(s) read for model {imod}")

    # Set colocation flags
    flags = set_coloc_flags(config_obj)
    temporal_colocation_flag, horizontal_colocation_flag, vertical_colocation_flag = flags

    # Colocate
    observation.update({"xarray_meta_coloc": []})
    logger.info("Collocating model(s) and observation")
    vertical_step = config_obj.get('vertical_step')
    horizontal_step = config_obj.get('horizontal_step')
    for index_model, model in enumerate(models):
        # Colocation per model
        obs_coloc, mod_coloc = base.colocate_all(observation["xarray_meta"], model["xarray_meta"], flags,
                                                 tgt_grid=config_obj["colocate"], vertical_step=vertical_step,
                                                 horizontal_step=horizontal_step, coloc_method=get_method(model),
                                                 coloc_method_z=get_method(model, z=True))

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


def set_coloc_flags(config_obj):
    # Set initial colocation flags
    temporal_colocation_flag = True
    vertical_colocation_flag = True
    horizontal_colocation_flag = True

    # Colocation for functionality 1
    if config_obj["functionality"] == "sst":
        vertical_colocation_flag = False
        horizontal_colocation_flag = True
        temporal_colocation_flag = True

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
        horizontal_colocation_flag = True

    # Colocation for functionnality 9
    if config_obj["functionality"] == "drifters":
        temporal_colocation_flag = False
        vertical_colocation_flag = False
        horizontal_colocation_flag = True

    flags = temporal_colocation_flag, horizontal_colocation_flag, vertical_colocation_flag

    return flags


def get_method(data, z=False) -> str:
    """
    Get the method to use.
    Parameters
    ----------
    data : dict
        Parser.
    Returns
    -------
        str
        Method to use.
    """
    if z:
        method = data.get('method_z')
        if method is None:
            method = data.get('method')
    else:
        method = data.get('method')

    if method is None:
        logger.warning(f'No method provided for {data.get("name")}')

    return method


def apply_metas2dataset(xarray_obj: xr.Dataset, config_obj: dict, method: str, mod_obs='obs') -> xr.Dataset:
    """
    Apply meta zone to subset dataset.

    Parameters
    ----------
    xarray_obj : dict
        Parser defined by user, containing xarray.Datasets.
    config_obj : dict
        Meta-zone from the parser, defines the regions and periods to study.
    method : str
        Method to interpolate / select data.
    mod_obs : str
        Indicates if the model or the obs is being meta-zoned.

    Returns
    -------
    res_xarray_obj : xarray.Dataset
        Subset dataset.

    """
    logger.info("Applying meta zone")

    # Add default meta-zone
    if config_obj['functionality'] == "sst":
        if 'depth' not in config_obj["meta_zones"]:
            config_obj["meta_zones"]["depth"] = [0]

    filters = {"quality": lambda obj: obj.meta.quality_filter, "depth": lambda obj: obj.meta.vertical_selection_depth,
               "dens": lambda obj: obj.meta.vertical_selection_dens,
               "polygon": lambda obj: obj.meta.horizontal_selection_polygon,
               "start": lambda obj: obj.meta.time_selection_start, "end": lambda obj: obj.meta.time_selection_end,
               "times": lambda obj: obj.meta.time_selection_list, "frequency": lambda obj: obj.meta.time_selection_freq,
               "time_restriction": lambda obj: obj.meta.time_restriction,
               "cyclic": lambda obj: obj.meta.time_selection_climatological
               }

    if "meta_zones" in config_obj:
        # Cloud horizontal selection
        if "cloud" in config_obj["meta_zones"]:
            radius = config_obj["meta_zones"]["radius"] if "radius" in config_obj["meta_zones"] else None
            logger.info("Applying : cloud")
            points = config_obj["meta_zones"]["cloud"]
            xarray_obj = xarray_obj.meta.horizontal_selection_cloud_dots(points, radius, method)

        # Bathymetry threshold
        if 'h' in xarray_obj:
            xarray_obj = xarray_obj.rename({'h': 'bathy'})

        if 'bathy_min' in config_obj["meta_zones"] or 'bathy_max' in config_obj["meta_zones"]:
            logger.info("Applying : bathymetry threshold")
            if 'bathy' in xarray_obj:
                min_bath = config_obj["meta_zones"]["bathy_min"] if "bathy_min" in config_obj["meta_zones"] else None
                max_bath = config_obj["meta_zones"]["bathy_max"] if "bathy_max" in config_obj["meta_zones"] else None

                xarray_obj = xarray_obj.meta.horizontal_selection_bathy(minimum=min_bath, maximum=max_bath)

        # Radius for ADCP feature
        if "radius" in config_obj["meta_zones"] and mod_obs == 'mod' and config_obj["functionality"] in ['ADCP']:
            xarray_obj = xarray_obj.meta.horizontal_selection_from_obs_radius(config_obj)

        # Other meta-zones, one by one
        for name, filter in filters.items():
            if name in config_obj["meta_zones"]:
                logger.info(f"Applying : {name}")
                xarray_obj = filter(xarray_obj)(config_obj["meta_zones"][name])

    return xarray_obj
