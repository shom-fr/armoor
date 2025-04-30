"""Decode the config file to plot the required outputs"""

import logging

import numpy as np
import xarray as xr

from dask import compute, delayed
from dask.distributed import Client, LocalCluster

import armoor.base.meta_zone
import armoor.base.sel_var
from armoor.algo.calculation import ensemble_mean
from armoor.base import (  #; feature_currents_hfr,; feature_currents_ADCP,; feature_currents_VMADCP,; feature_drifters
    feature_clim_hydro,
    feature_prof_hydro_mooring,
    feature_prof_hydro_vessel,
    feature_section_hydro,
    feature_sst,
)
from armoor.base.__init__ import FILTERS

from armoor.base.colocation import (
    horizontal_regrid,
    obs_coords,
    obs_coords_radius,
    vertical,
)
from armoor.base.open_decode import open_decode

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

    features = {
        "sst": feature_sst,
        "prof_hydro_vessel": feature_prof_hydro_vessel,
        "prof_hydro_mooring": feature_prof_hydro_mooring,
        "section_hydro": feature_section_hydro,
        "clim_hydro": feature_clim_hydro,
        # "currents_hfr": feature_currents_hfr,
        # "currents_ADCP": feature_currents_ADCP,
        # "currents_VMADCP": feature_currents_VMADCP,
        # "drifters": feature_drifters
    }

    selected_feature = config_obj["functionality"]

    if selected_feature in features:
        logger.info("Feature selected :: %s", selected_feature)
        features[config_obj["functionality"]].plot(config_obj)
    else:
        logger.debug("Feature %s not found", selected_feature)


def get_observation_models_meta(cfg: dict):
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

    observation = cfg["observation"]
    models = cfg["models"]

    logger.info("Using functionality : %s", cfg["functionality"])

    logger.info("Reading observation files")

    # Open observation dataset from path then decode dataset and apply meta-zone
    logger.info("Opening and decode observation from file(s)")
    dss_obs = open_decode(
        observation.pop("path"),
        cfg["observation"].get("fmt"),
        platform=cfg["observation"].get("platform"),
    )
    for ids in range(len(dss_obs)):
        if not "name" in dss_obs[ids].attrs:
            dss_obs[ids].attrs["name"] = observation.get("name")
    logger.info("Applying : meta zone on observation")
    for ids, ds in enumerate(dss_obs):
        logger.info(f"{ds.attrs['name']}")
        logger.info(
            f"Time bounds: [{ds.time.min().values}, {ds.time.max().values}]"
        )
        logger.info(
            f"Lon bounds: [{ds.lon.min().values}, {ds.lon.max().values}]"
        )
        logger.info(
            f"Lat bounds: [{ds.lat.min().values}, {ds.lat.max().values}]"
        )
        if "depth" in ds:
            logger.info(
                f"Depth bounds: [{ds.depth.min().values}, {ds.depth.max().values}]"
            )
        ds0 = apply_metas2dataset(ds, cfg)
        with Client() as client:
            ds0 = ds0.compute()
        dss_obs[ids] = ds0
        if ds0 != None:
            dss_obs[ids].assign_attrs({"name": ds.attrs["name"]})
        ds.close()
    dss_obs = [ds for ds in dss_obs if ds != None]
    if len(dss_obs) == 0:
        raise TypeError("Metazone filters on observation leads to None.")

    logger.info("File(s) read for observation")
    # Open model dataset from path then decode dataset and apply meta-zone
    dss_model = []
    for imod, model in enumerate(models):
        logger.info(f"Reading model : {imod}")
        logger.info("Opening and decode model from file(s)")
        ds0 = open_decode(models[model].get("path"), models[model].get("fmt"))
        if ds0.nbytes < 1e6:
            logger.info(
                f"Time bounds: [{ds0.time.min().values}, {ds0.time.max().values}]"
            )
            logger.info(
                f"Lon bounds: [{ds0.lon.min().values}, {ds0.lon.max().values}]"
            )
            logger.info(
                f"Lat bounds: [{ds0.lat.min().values}, {ds0.lat.max().values}]"
            )
            if ("depth" in ds0) and (ds0.nbytes < 1e6):
                logger.info(
                    f"Depth bounds: [{ds0.depth.min().values}, {ds0.depth.max().values}]"
                )
            logger.info("Applying meta zone on model")
        ds0 = apply_metas2dataset(ds0, cfg)
        if ds0 != None:
            with Client() as client:
                ds0 = ds0.compute()
            ds0 = ds0.assign_attrs({"name": models[model].get("name")})
            dss_model.append(ds0)
            ds0.close()
        else:
            raise TypeError("Metazone filters on {model} leads to None.")
    # colocation
    logger.info("Colocation")
    if cfg["functionality"] == "prof_hydro_vessel":
        if cfg["metazone"]["radius"] == None:
            raise TypeError(
                "armoor needs a radius."
                "Please, fill your configuration file."
            )
        observation.update(
            {
                "ds_coloc": {},
            }
        )
        for imodel, model in enumerate(models):
            ds_model = dss_model[imodel]
            ds_obs = dss_obs[0]
            if ds_model.xindexes.get("depth") == None:
                ds_model = ds_model.reset_coords("depth")
            ds_model = ds_model.interp(
                time=ds_obs.time, method="nearest"
            )
            ds_obs, ds_model = obs_coords_radius(
                ds_obs, ds_model, cfg["metazone"]["radius"]
            )
            models[model].update(
                {
                    "ds_coloc": ds_model.assign_attrs(
                        {
                            "name": models[model].get("name"),
                            "radius": cfg["metazone"]["radius"],
                        }
                    )
                }
            )
            del ds_model
            observation["ds_coloc"].update(
                {
                    model: ds_obs.assign_attrs(
                        {
                            "tbound": cfg["metazone"]["tbound"],
                            "radius": cfg["metazone"]["radius"],
                            "name": observation.get("name"),
                        }
                    )
                }
            )
            del ds_obs
            vrange = cfg["metazone"].get("vrange")
            if vrange:
                if "depth" in vrange:
                    vlevel = "depth"
                vref = cfg["metazone"]["vref"]
                if not vref:
                    raise TypeError(
                        "armoor needs a vref to perform vertical ranging : model or obs"
                        "Please, fill your configuration file."
                    )

                logger.info(f"Vertical reference is {vref}")
                if vref == "model":
                    ds = vertical(
                        observation["ds_coloc"][model],
                        models[model]["ds_coloc"][vlevel],
                    )
                    observation["ds_coloc"].update(
                        {
                            model: ds.assign_attrs(
                                {
                                    "name": observation.get("name"),
                                    **observation["ds_coloc"][model].attrs,
                                }
                            )
                        }
                    )
                else:
                    ds = vertical(
                        models[model]["ds_coloc"],
                        observation["ds_coloc"][model][vlevel],
                    )
                    models[model].update(
                        {
                            "ds_coloc": ds.assign_attrs(
                                {"name": models[model].get("name")}
                            )
                        }
                    )
            else:
                observation["ds_coloc"].update(
                    {model: observation["ds_coloc"][model]}
                )
    elif cfg["functionality"] == "sst":
        if (cfg["metazone"].get("href") != None) & (
            cfg["metazone"].get("coord") != None
        ):
            raise TypeError(
                "Please, choose href or coord colocation."
                "Both colocation is not possible."
            )
        if (cfg["metazone"].get("tfreq") != None) & (
            cfg["metazone"].get("tref") != None
        ):
            raise TypeError(
                "Please, choose tfreq or tref colocation."
                "Both colocation is not possible."
            )
        if (cfg["metazone"].get("href") == None) & (
            cfg["metazone"].get("coord") == None
        ):
            raise TypeError("Please, choose href or coord colocation.")
        if (cfg["metazone"].get("tref") == None) & (
            cfg["metazone"].get("tfreq") == None
        ):
            raise TypeError("Please, choose tref or tfreq colocation.")
        observation.update(
            {
                "ds_coloc": {},
            }
        )
        for imodel, model in enumerate(models):
            ds_model = dss_model[imodel]
            ds_obs = dss_obs[0]
            if "z" in ds_model.dims:
                ds_model = ds_model.isel(z=0).squeeze()
            if cfg["metazone"].get("tfreq"):
                ds_model = ds_model.meta.time_selection_terms(
                    start=cfg["metazone"].get("tbound")[0],
                    end=cfg["metazone"].get("tbound")[-1],
                    freq=cfg["metazone"].get("tfreq"),
                )
                ds_obs = ds_obs.meta.time_selection_terms(
                    start=cfg["metazone"].get("tbound")[0],
                    end=cfg["metazone"].get("tbound")[-1],
                    freq=cfg["metazone"].get("tfreq"),
                )
            elif cfg["metazone"].get("tref") in ("obs", "model"):
                if cfg["metazone"].get("tref") == "obs":
                    ds_model = ds_model.interp(
                        time=ds_obs.time, method="linear"
                    )
                elif cfg["metazone"].get("tref") == "model":
                    ds_obs = ds_obs.interp(time=ds_model.time, method="linear")
            if cfg["metazone"].get("href") in ("obs", "model"):
                logger.info("Regrid :")
                if cfg["metazone"].get("href") == "obs":
                    logger.info("model on obs")
                    ds_model, ds_obs = horizontal_regrid(ds_model, ds_obs)
                elif cfg["metazone"].get("href") == "model":
                    logger.info("obs on model")
                    ds_obs, ds_model = horizontal_regrid(ds_obs, ds_model)
            elif cfg["metazone"].get("coord"):
                coord = cfg["metazone"].get("coord")
                logger.info(f"Grid2loc obs on coords: {coord}")
                ds_obs = ds_obs.meta.horizontal_selection_coords(coord)
                ds_model = ds_model.meta.horizontal_selection_coords(coord)
            observation["ds_coloc"].update(
                {
                    model: ds_obs.assign_attrs(
                        {
                            "tbound": cfg["metazone"]["tbound"],
                            "name": observation.get("name"),
                        }
                    )
                }
            )
            models[model].update(
                {
                    "ds_coloc": ds_model.assign_attrs(
                        {
                            "name": models[model].get("name"),
                        }
                    )
                }
            )
            del ds_model
            del ds_obs
    elif cfg["functionality"] == "prof_hydro_mooring":
        logger.info("Colocation for prof_hydro_mooring")
        if cfg["metazone"]["radius"] == None:
            raise TypeError(
                "armoor needs a radius."
                "Please, fill your configuration file."
            )
        if (cfg["metazone"].get("tref") == None) & (
            cfg["metazone"].get("tfreq") == None
        ):
            raise TypeError("Please, choose tref or tfreq colocation.")
        dss_obs_coloc = []
        dss_model_coloc = []
        for iobs in range(len(dss_obs)):
            dss_obs_coloc.append([])
            dss_model_coloc.append([])
            ds0_obs = dss_obs[iobs]
            logger.info(
                f"Start colocation for observation: {ds0_obs.attrs['name']}"
            )
            for imodel, model in enumerate(models):
                ds0_model = dss_model[imodel]
                if cfg["metazone"].get("tfreq"):
                    ds_model = ds0_model.meta.time_selection_terms(
                        start=cfg["metazone"].get("tbound")[0],
                        end=cfg["metazone"].get("tbound")[-1],
                        freq=cfg["metazone"].get("tfreq"),
                    )
                    ds_obs = ds0_obs.meta.time_selection_terms(
                        start=cfg["metazone"].get("tbound")[0],
                        end=cfg["metazone"].get("tbound")[-1],
                        freq=cfg["metazone"].get("tfreq"),
                    )
                elif cfg["metazone"].get("tref") in ("obs", "model"):
                    if cfg["metazone"].get("tref") == "obs":
                        ds_model = ds0_model.interp(
                            time=ds0_obs.time, method="linear"
                        )
                        ds_obs = ds0_obs
                    elif cfg["metazone"].get("tref") == "model":
                        ds_obs = ds0_obs.interp(
                            time=ds0_model.time, method="linear"
                        )
                        ds_model = ds0_model
                ds_obs, ds_model = obs_coords_radius(
                    ds_obs, ds_model, cfg["metazone"]["radius"]
                )
                ds_model = ensemble_mean(ds_model)
                ds_model = vertical(ds_model, ds_obs.depth)  # .isel(time=0)
                dss_model_coloc[iobs].append(
                    ds_model.assign_attrs(
                        {
                            "name": models[model].get("name"),
                            "radius": cfg["metazone"]["radius"],
                        }
                    )
                )
                dss_obs_coloc[iobs].append(
                    ds_obs.assign_attrs(
                        {
                            "tbound": cfg["metazone"]["tbound"],
                            "radius": cfg["metazone"]["radius"],
                            "name": ds0_obs.attrs["name"],
                        }
                    )
                )
                del ds0_model
            del ds0_obs
        logger.info("End of colocation")
        nobs = len(dss_obs_coloc)
        del dss_model
        del dss_obs
        observation["ds_coloc"] = {}
        for imodel, model in enumerate(models):
            for iobs in range(nobs):
                if iobs == 0:
                    models[model]["ds_coloc"] = []
                    observation["ds_coloc"].update({model: []})
                models[model]["ds_coloc"].append(
                    dss_model_coloc[iobs][imodel].assign_attrs(
                        {
                            "name": models[model].get("name"),
                        }
                    )
                )
                observation["ds_coloc"][model].append(
                    dss_obs_coloc[iobs][imodel].assign_attrs(
                        {
                            "tbound": cfg["metazone"]["tbound"],
                        }
                    )
                )
        del dss_obs_coloc
        del dss_model_coloc
    elif cfg["functionality"] == "section_hydro":
        vfreq = cfg["metazone"].get("vfreq")
        vfreq = [k for k in vfreq.items()][0]
        vfreq_name, vfreq = vfreq[0], vfreq[1]
        if vfreq_name not in ("depth", "pdens"):
            raise TypeError(
                f"{vfreq_name} vertical colocation not implemented."
            )
        if isinstance(vfreq, float) == False:
            raise TypeError(f"{vfreq} is expected to be a float.")
        dss_obs_coloc = []
        dss_model_coloc = []
        for iobs in range(len(dss_obs)):
            dss_obs_coloc.append([])
            dss_model_coloc.append([])
            ds0_obs = dss_obs[iobs]
            logger.info(f"Obs: {ds0_obs.name}")
            dav = xr.DataArray(
                np.arange(
                    ds0_obs[vfreq_name].min(), ds0_obs[vfreq_name].max(), vfreq
                ),
                dims="z",
                name="depth",
            )
            ds_obs = vertical(ds0_obs, dav)
            ds_obs = ds_obs.isel(z=slice(None, None, -1))
            for imodel, model in enumerate(models):
                logger.info(f"Model: {model}")
                ds0_model = dss_model[imodel]
                ds_model = obs_coords(ds0_obs, ds0_model)
                ds_model = vertical(ds_model, dav)
                ds_model = ds_model.isel(z=slice(None, None, -1))
                dss_model_coloc[iobs].append(
                    ds_model.assign_attrs(
                        {
                            "name": models[model].get("name"),
                        }
                    )
                )
                dss_obs_coloc[iobs].append(
                    ds_obs.assign_attrs(
                        {
                            "name": ds0_obs.attrs["name"],
                        }
                    )
                )
                del ds0_model
            del ds0_obs

        nobs = len(dss_obs)
        del dss_model
        del dss_obs
        observation["ds_coloc"] = {}
        for imodel, model in enumerate(models):
            for iobs in range(nobs):
                if iobs == 0:
                    models[model]["ds_coloc"] = []
                    observation["ds_coloc"].update({model: []})
                models[model]["ds_coloc"].append(
                    dss_model_coloc[iobs][imodel].assign_attrs(
                        {
                            "name": models[model].get("name"),
                        }
                    )
                )
                observation["ds_coloc"][model].append(
                    dss_obs_coloc[iobs][imodel].assign_attrs(
                        {
                            "tbound": cfg["metazone"]["tbound"],
                            "name": dss_obs_coloc[iobs][imodel].attrs["name"],
                        }
                    )
                )
        del dss_obs_coloc
        del dss_model_coloc
    elif cfg["functionality"] == "clim_hydro":
        if (cfg["metazone"].get("href") != None) & (
            cfg["metazone"].get("coord") != None
        ):
            raise TypeError(
                "Please, choose href or coord colocation."
                "Both colocation is not possible."
            )
        if cfg["metazone"].get("trange_clim") == None:
            raise TypeError("Please, choose a monthly trange_clim")
        observation.update(
            {
                "ds_coloc": {},
            }
        )
        for imodel, model in enumerate(models):
            ds_model = dss_model[imodel].groupby(
                "time.month"
            ).mean(
                "time"
            ).rename({
                "month": "time"
            })
            ds_obs = dss_obs[0]
            if cfg["metazone"].get("href") in ("obs", "model"):
                logger.info("Regrid :")
                if cfg["metazone"].get("href") == "obs":
                    logger.info("model on obs")
                    ds_model, ds_obs = horizontal_regrid(ds_model, ds_obs)
                elif cfg["metazone"].get("href") == "model":
                    logger.info("obs on model")
                    ds_obs, ds_model = horizontal_regrid(ds_obs, ds_model)
            elif cfg["metazone"].get("coord"):
                coord = cfg["metazone"].get("coord")
                logger.info(f"Grid2loc obs on coords: {coord}")
                ds_obs = ds_obs.meta.horizontal_selection_coords(coord)
                ds_model = ds_model.meta.horizontal_selection_coords(coord)
            observation["ds_coloc"].update(
                {
                    model: ds_obs.assign_attrs(
                        {
                            "tbound": cfg["metazone"]["tbound"],
                            "name": observation.get("name"),
                        }
                    )
                }
            )
            models[model].update(
                {
                    "ds_coloc": ds_model.assign_attrs(
                        {
                            "name": models[model].get("name"),
                        }
                    )
                }
            )
            del ds_model
            del ds_obs   
    cfg["observation"] = observation
    cfg["models"] = models
    return cfg


def handle_errors(config_obj: dict) -> Exception:
    """
    Function to manage compatibility between parameters and functionalities.

    Parameters
    ----------
    config_obj : dict
        Configuration file dictating the actions to be performed by the armoor library.

    Returns
    -------
    Exceptions
    """
    # Raise errors for min/max depth/dens
    if {"min_depth", "max_depth", "min_dens", "max_dens"} & set(
        config_obj["metazone"].keys()
    ):
        if config_obj["functionality"] == "currents_ADCP":
            msg = (
                'For the functionality "currents_ADCP", the use of '
                '"min_depth", "max_depth", "min_dens" or "max_dens" '
                'within the "metazone" configuration is not permitted.'
            )
            logger.error(msg)
            raise ValueError(msg)


def apply_metas2dataset(ds: xr.Dataset, cfg: dict) -> xr.Dataset:
    """
    Apply meta zone to subset dataset.

    Parameters
    ----------
    ds: dict
        Parser defined by user, containing xarray.Datasets.
    cfg: dict
        Meta-zone from the parser, defines the regions and periods to study.

    Returns
    -------
    xarray.Dataset

    """
    logger.info("Applying meta zone")

    # Add default meta-zone
    # if config_obj['functionality'] in ["sst", "currents_hfr", 'drifters']:
    #     if 'depth' not in config_obj["meta_zones"]:
    #         logger.warning(f"For feature {config_obj['functionality']}, no depth can be specified !")

    metazone = cfg["metazone"]
    for k, v in metazone.items():
        if v == None:
            del metazone[k]
    if "tbound" not in metazone:
        raise TypeError(
            "armoor needs to have start and end dates to continue."
            "Please, fill your configuration file."
        )
    if cfg["functionality"] == "prof_hydro_vessel":

        meta = [
            "tbound",
            "trange_seq",
            "polygon",
            "radius",
            "vlevel",
            "vrange",
            "vref",
            "vars",
        ]
    elif cfg["functionality"] == "sst":

        meta = [
            "tbound",
            "trange_seq",
            "tfreq",
            "tref",
            "polygon",
            "href",
            "coord",
            "vars",
        ]
    elif cfg["functionality"] == "prof_hydro_mooring":

        meta = [
            "tbound",
            "trange_seq",
            "tfreq",
            "tref",
            "polygon",
            "radius",
            "vars",
        ]
    elif cfg["functionality"] == "section_hydro":

        meta = [
            "tbound",
            "polygon",
            "vfreq",
            "vars",
        ]
    elif cfg["functionality"] == "clim_hydro":

        meta = [
            "tbound",
            "trange_clim",
            "polygon",
            "href",
            "coord",
            "vlevel",
            "vars",
        ]

    for k, v in metazone.items():
        if (k != "name") and (k not in meta):
            raise TypeError(
                f"{k} cannot be defined for {cfg['functionality']}: {meta}"
            )
    # time
    time_meta = ["tbound", "terms", "trange_cut"]
    for k in time_meta:
        if k in metazone.keys():
            if "climatology" not in ds.time.attrs:
                logger.info(k)
                ds = FILTERS[k](ds)(*metazone[k])
            if ds is None:
                return None

    # horizontal
    horizontal_meta = [
        "polygon",
        "bathy",
    ]
    for k in horizontal_meta:
        if k in metazone.keys():
            logger.info(k)
            if k == "polygon":
                args = metazone["polygon"]
            else:
                args = (*metazone[k],)
            ds = FILTERS[k](ds)(args)
            if ds is None:
                return None
    # vertical
    vertical_meta = [
        "vlevel",
    ]
    for k in vertical_meta:
        if k in metazone.keys():
            logger.info(k)
            ds = FILTERS[k](ds)(*metazone[k].items()[0])
            if ds is None:
                return None
    return ds

    # filters = {"quality": lambda obj: obj.meta.quality_filter,
    #            "start": lambda obj: obj.meta.time_selection_bounds,
    #            "terms": lambda obj: obj.meta.time_selection_terms,
    #            "range_seq": lambda obj: obj.meta.time_selection_range_seq,
    #            "range_clim": lambda obj: obj.meta.time_selection_range_clim,
    #            "cut": lambda obj: obj.meta.time_selection_cut,
    #            "polygon": lambda obj: obj.meta.horizontal_selection_polygon,
    #            "coords": lambda obj: obj.meta.horizontal_selection_coords,
    #            "radius": lambda obj: obj.meta.horizontal_selection_coords,
    #            }

    # if "meta_zones" in config_obj:
    #     # Calculate vars before meta-zone
    #     outputs = config_obj['outputs']
    #     vars_to_plot = [output['attribute'][0] for output in outputs if 'attribute' in output]
    #     if 'current_bc' in vars_to_plot:
    #         xarray_obj = merge_no_fail([xarray_obj, xarray_obj.sel_var.sel_current_barocline()])

    #     # Cloud horizontal selection
    #     if "cloud" in config_obj["meta_zones"]:
    #         radius = config_obj["meta_zones"].get('radius')
    #         logger.info("Applying : cloud")
    #         points = config_obj["meta_zones"]["cloud"]
    #         xarray_obj = xarray_obj.meta.horizontal_selection_cloud_dots(points, radius, method)
    #         xarray_obj = xarray_obj.assign_attrs({"cloud": points})
    #         if radius: xarray_obj = xarray_obj.assign_attrs({"radius": f"{radius}"})

    #     # Calculate current_res after cloud before time
    #     if 'current_res' in vars_to_plot:
    #         filter = outputs[0]['low_pass_filter']
    #         xarray_obj = merge_no_fail([xarray_obj, xarray_obj.sel_var.sel_current_res(filter)])

    #     # Bathymetry threshold
    #     if 'h' in xarray_obj:
    #         xarray_obj = xarray_obj.rename({'h': 'bathy'})
    #     if 'bathy_min' in config_obj["meta_zones"] or 'bathy_max' in config_obj["meta_zones"]:
    #         logger.info("Applying : bathymetry threshold")
    #         min_bath = config_obj["meta_zones"].get('bathy_min')
    #         max_bath = config_obj["meta_zones"].get("bathy_max")
    #         xarray_obj = xarray_obj.assign_attrs({"bathy_thresh": f"{min_bath}_to_{max_bath}"})

    #         if 'bathy' in xarray_obj:
    #             xarray_obj = xarray_obj.meta.horizontal_selection_bathy(minimum=min_bath,
    #                                                                     maximum=max_bath)
    #         else:
    #             logger.warning("Caution ! No bathymetry variable was found in the product.")

    #     # Radius for ADCP feature
    #     if "radius" in config_obj["meta_zones"] and mod_obs == 'mod' and config_obj[
    #         "functionality"] in ['ADCP']:
    #         radius = config_obj["meta_zones"].get('radius')
    #         xarray_obj = xarray_obj.meta.horizontal_selection_from_obs_radius(config_obj)
    #         xarray_obj = xarray_obj.assign_attrs({"radius": f"{radius}"})

    #     # Radius for data selection
    #     if "radius" in config_obj["meta_zones"] and "radius" not in xarray_obj.attrs:
    #         radius = config_obj["meta_zones"].get('radius')
    #         xarray_obj = xarray_obj.assign_attrs({"radius": f"{radius}"})

    #     # Density selection
    #     if 'dens' in config_obj["meta_zones"]:
    #         dens = config_obj["meta_zones"]["dens"]
    #         ref_dens = config_obj.get("reference_density")
    #         xarray_obj = xarray_obj.meta.vertical_selection_dens(dens, ref_dens)
    #     if "min_dens" in config_obj["meta_zones"] or "max_dens" in config_obj["meta_zones"]:
    #         min_dens = config_obj["meta_zones"].get("min_dens")
    #         max_dens = config_obj["meta_zones"].get("max_dens")
    #         ref_dens = config_obj.get("reference_density")
    #         if min_dens:
    #             xarray_obj = xarray_obj.meta.vertical_selection_min_dens(min_dens,
    #                                                                      ref_dens=ref_dens)
    #         if max_dens:
    #             xarray_obj = xarray_obj.meta.vertical_selection_max_dens(max_dens,
    #                                                                      ref_dens=ref_dens)
    #         xarray_obj = xarray_obj.assign_attrs({"density_meta_zone": f"{min_dens}_to_{max_dens}"})

    #     # Depth selection
    #     if 'depth' in config_obj["meta_zones"]:
    #         if config_obj["functionality"] != "section_hydro":
    #             # For feature 4, we need to keep all depths to compute geo currents
    #             depth = config_obj["meta_zones"]["depth"]
    #             xarray_obj = xarray_obj.meta.vertical_selection_depth(depth)
    #             xarray_obj = xarray_obj.assign_attrs({"depth_meta_zone": depth})

    #     if 'times' in config_obj["meta_zones"]:
    #         xarray_obj = xarray_obj.assign_attrs({"echeances": config_obj["meta_zones"]["times"]})
    #     if 'time_highlight' in config_obj["meta_zones"]:
    #         xarray_obj = xarray_obj.assign_attrs({"echeances": config_obj["meta_zones"]["time_highlight"]})

    #     if config_obj['functionality'] in ["sst", "currents_hfr", 'drifters']:
    #         if 'depth' in config_obj["meta_zones"]:
    #             logger.warning(
    #                 f"For feature {config_obj['functionality']}, no depth can be specified ! Surface value is taken into account")
    #         if "depth" in xarray_obj and config_obj['functionality'] in ["sst", "currents_hfr"]:
    #             depth = [0]
    #             xarray_obj = xarray_obj.meta.vertical_selection_depth(depth)

    #     # Other meta-zones, one by one
    #     for name, meta_filter in filters.items():
    #         if name in config_obj["meta_zones"]:
    #             logger.info("Applying : %s", name)
    #             xarray_obj = meta_filter(xarray_obj)(config_obj["meta_zones"][name])

    #     # Assign depth attrs
    #     if 'min_depth' in config_obj["meta_zones"] and 'max_depth' in config_obj["meta_zones"]:
    #         min_depth = config_obj["meta_zones"].get('min_depth')
    #         max_depth = config_obj["meta_zones"].get("max_depth")
    #         xarray_obj = xarray_obj.assign_attrs({"depth_meta_zone": f"{min_depth}_to_{max_depth}"})
    #     elif 'min_depth' in config_obj["meta_zones"] and not 'max_depth' in config_obj["meta_zones"]:
    #         logger.error("You've indicated a min depth, please indicate max depth in meta zone. By default entire dataset is considered.")
    #     elif 'max_depth' in config_obj["meta_zones"] and not 'min_depth' in config_obj["meta_zones"]:
    #         logger.error("You've indicated a max depth, please indicate min depth in meta zone. By default entire dataset is considered.")

    # return xarray_obj
