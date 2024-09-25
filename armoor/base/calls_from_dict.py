"""Decode the config file to plot the required outputs"""

import logging, sys
import copy
import xarray as xr
from armoor.base.__init__ import FILTERS
from armoor.base import feature_sst, feature_prof_hydro_vessel, feature_prof_hydro_mooring, \
    feature_section_hydro, feature_clim_hydro, feature_currents_hfr, feature_currents_ADCP, \
    feature_currents_VMADCP, feature_drifters
from armoor.base.open_decode import open_decode
import armoor.base.colocation as coloc
import armoor.base.meta_zone
import armoor.base.sel_var

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

    features = {"sst": feature_sst, "prof_hydro_vessel": feature_prof_hydro_vessel,
                "prof_hydro_mooring": feature_prof_hydro_mooring,
                "section_hydro": feature_section_hydro, "clim_hydro": feature_clim_hydro,
                "currents_hfr": feature_currents_hfr, "currents_ADCP": feature_currents_ADCP,
                "currents_VMADCP": feature_currents_VMADCP, "drifters": feature_drifters
                }

    selected_feature = config_obj["functionality"]

    if selected_feature in features:
        logger.info('Feature selected :: %s', selected_feature)
        features[config_obj["functionality"]].plot(config_obj)
    else:
        logger.debug('Feature %s not found', selected_feature)
    

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

    if cfg["metazone"]["radius"] == None:
        raise TypeError(
            "armoor needs a radius."
            "Please, fill your configuration file."
        )
    observation = cfg["observation"]
    models = cfg["models"]

    logger.info("Using functionality : %s", cfg['functionality'])

    logger.info("Reading observation files")

    # Open observation dataset from path then decode dataset and apply meta-zone
    logger.info("Opening observation from file(s)")
    ds =  open_decode(
        observation.pop("path"),
        cfg['observation'].get('fmt'),
        platform=cfg['observation'].get('platform'),
        
    )
    ds = ds.assign_attrs({'name': observation.get("name")})
    observation.update({"ds": ds})
    ds.close()

    logger.info("Applying : decode and meta zone on observation")
    ds = apply_metas2dataset(
        observation["ds"],
        cfg,
    )
    observation.update({
        "ds_metazone": ds.assign_attrs({'name': observation.get("name")})
    })
    del ds
    logger.info("File(s) read for observation")
    # Open model dataset from path then decode dataset and apply meta-zone
    for imod, model in enumerate(models):
        logger.info(f"Reading model : {imod}")

        logger.info("Opening and decode model from file(s)")
        ds = open_decode(
            models[model].get("path"),
            models[model].get("fmt")
        )
        ds = ds.assign_attrs({'name': models[model].get("name")})
        models[model].update({"ds": ds})

        logger.info("Applying meta zone on model")
        ds = apply_metas2dataset(
            models[model]["ds"],
            cfg,
        )
        models[model].update({"ds_metazone": ds})
        del ds
        del models[model]["ds"]
    del observation["ds"]
    #colocation
    logger.info("Colocation")
    if cfg["functionality"] == "prof_hydro_vessel":
        observation.update({
            "ds_coloc": {},
        })
        for model in models:
            observation["ds_coloc"].update(
                {model: observation["ds_metazone"]}
            )
            ds = coloc.obs_coords(
                observation["ds_metazone"],
                models[model]["ds_metazone"],
                cfg["metazone"]["radius"]
            )
            models[model].update({
                "ds_coloc": ds.assign_attrs({
                    'name': models[model].get("name"),
                    "radius": cfg["metazone"]["radius"],
                })
            })
            del ds
            observation["ds_coloc"].update(
                {model: observation["ds_metazone"].assign_attrs({
                    "tbound": cfg["metazone"]["tbound"],
                    "radius": cfg["metazone"]["radius"],
                })}
            )
            vrange = cfg["metazone"].get("vrange")
            if vrange:
                if "depth" in vrange:
                    vlevel ="depth"
                vref = cfg["metazone"]["vref"]
                if not vref:
                    raise TypeError(
                    f"armoor needs a vref to perform vertical ranging : model or obs"
                        "Please, fill your configuration file."
                    )

                logger.info(f"Vertical reference is {vref}")
                if vref == "model":
                    ds = coloc.vertical(
                        observation["ds_coloc"][model],
                        models[model]["ds_coloc"][vlevel]
                    )
                    observation["ds_coloc"].update(
                        {model: ds.assign_attrs(
                            {'name': observation.get("name"),
                             **observation["ds_coloc"][model].attrs}
                        )}
                    )
                else:
                    ds = coloc.vertical(
                        models[model]["ds_coloc"],
                        observation["ds_coloc"][model][vlevel]
                    )
                    models[model].update({
                        "ds_coloc": ds.assign_attrs(
                            {'name': models[model].get("name")}
                        )
                    })   
            else:
                observation["ds_coloc"].update(
                    {model: observation["ds_coloc"][model]}
                )
            del models[model]["ds_metazone"]
            del observation["ds_metazone"]
            
    # #vrange
    # for model in models:
    #     ds = apply_vrange(observation["ds_coloc"][model], cfg["metazone"])
    #     observation["ds_coloc"].update({model: ds})
    #     ds = apply_vrange(models[model]["ds_coloc"], cfg["metazone"])
    #     models[model].update({"ds_coloc": ds})
    #     del ds

    # #trange
    # for model in models:
    #     ds = apply_trange(observation["ds_coloc"][model], cfg["metazone"])
    #     observation["ds_coloc"].update({model: ds})
    #     ds = apply_trange(models[model]["ds_coloc"], cfg["metazone"])
    #     models[model].update({"ds_coloc": ds})

    
    
    return cfg



    # # Set colocation flags
    # steps = config_obj.get('horizontal_step'), config_obj.get('vertical_step')
    # flags = set_coloc_flags(config_obj)
    # _, horizontal_colocation_flag, vertical_colocation_flag = flags

    # # Colocate
    # observation.update({"xarray_meta_coloc": []})
    # logger.info("Collocating model(s) and observation")
    # for index_model, model in enumerate(models):
    #     # Colocation per model
    #     obs_coloc, mod_coloc = colocate_all(observation["xarray_meta"], model["xarray_meta"], flags,
    #                                         tgt_grid=config_obj["colocate"],
    #                                         coloc_method=get_method(model),
    #                                         coloc_method_z=get_method(model, z_dim=True))
    #     observation["xarray_meta_coloc"].append(obs_coloc)
    #     model.update({"xarray_meta_coloc": mod_coloc})

    #     logger.info("Collocation done for model %s", index_model)

    #     # Interval temporels successifs
    #     if 'interval' in config_obj["meta_zones"]:
    #         if 'start' not in config_obj["meta_zones"] or 'end' not in config_obj["meta_zones"]:
    #             start = observation["xarray"].time.data[0]
    #             end = observation["xarray"].time.data[-1]
    #         else:
    #             start = config_obj["meta_zones"]["start"]
    #             end = config_obj["meta_zones"]["end"]

    #         logger.info('Temporal interval segmentation...')
    #         interval = config_obj["meta_zones"]["interval"]
    #         model["xarray_meta"] = model["xarray_meta"].meta.time_selection_interval(interval, start, end)
    #         model["xarray_meta_coloc"] = model["xarray_meta_coloc"].meta.time_selection_interval(
    #             interval, start, end)
    #         observation["xarray_meta_coloc"][index_model] = observation["xarray_meta_coloc"][
    #             index_model].meta.time_selection_interval(interval, start, end)

    #         # Tranches verticales
    #     if 'slice' in config_obj["meta_zones"]:
    #         if 'depth' in config_obj["meta_zones"]:
    #             var_slice = 'depth'
    #         elif 'dens' in config_obj["meta_zones"]:
    #             var_slice = 'dens'
    #         else:
    #             var_slice = 'depth'

    #         logger.info('Vertical slicing on variable %s', var_slice)

    #         vert_slice = config_obj["meta_zones"]["slice"]
    #         model["xarray_meta"] = model["xarray_meta"].meta.vertical_selection_slice(vert_slice,
    #                                                                                   var_slice)
    #         model["xarray_meta_coloc"] = model["xarray_meta_coloc"].meta.vertical_selection_slice(
    #             vert_slice, var_slice)
    #         observation["xarray_meta_coloc"][index_model] = observation["xarray_meta_coloc"][
    #             index_model].meta.vertical_selection_slice(vert_slice, var_slice)
            
    #     outputs = config_obj['outputs']
    #     vars_to_plot = [output['attribute'][0] for output in outputs if 'attribute' in output]
    #     mld_var = False
    #     if 'mld_ptemp' in vars_to_plot:
    #         mld_var = 'ptemp'
    #     elif 'mld_pdens' in vars_to_plot:
    #         mld_var = 'pdens'
    #     if mld_var:
    #         observation["xarray_meta_coloc"][index_model] = merge_no_fail([observation["xarray_meta_coloc"][index_model], observation["xarray_meta_coloc"][index_model].sel_var.sel_mixed_layer_depth(mld_var)])
    #         if model.get("type") == 'CROCO':
    #             model["xarray_meta_coloc"] = merge_no_fail([model["xarray_meta_coloc"], model["xarray_meta_coloc"].drop_vars(["x", "y", "level"]).sel_var.sel_mixed_layer_depth(mld_var)])
    #         else:
    #             model["xarray_meta_coloc"] = merge_no_fail([model["xarray_meta_coloc"], model["xarray_meta_coloc"].sel_var.sel_mixed_layer_depth(mld_var)])

    # # Obs meta is out of the loop for each mod
    # if 'interval' in config_obj["meta_zones"]:
    #     observation["xarray_meta"] = observation["xarray_meta"].meta.time_selection_interval(
    #         interval, start, end)

    # if 'slice' in config_obj["meta_zones"]:
    #     vert_slice = config_obj["meta_zones"]["slice"]
    #     observation["xarray_meta"] = observation["xarray_meta"].meta.vertical_selection_slice(
    #         vert_slice, var_slice)

    # return config_obj


def set_coloc_flags(config_obj):
    """
    Set the colocation flags from the config obj that indicate if the dimension on which to colocate
    the model and observation .
    Parameters
    ----------
    config_obj : dict
        Dictionary specifying the observation, models, functionality, output etc.
        Can be formatted out of a json file using cli.command_line_interface.

    Returns
    -------
    flags : list of bools
        time, vertical and horizontal colocation flags.

    """
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
        if 'depth' in config_obj['meta_zones'] :
            vertical_colocation_flag = False
        else:
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
        temporal_colocation_flag = True
        vertical_colocation_flag = True
        horizontal_colocation_flag = True

    if 'tide' in config_obj['outputs'][0]["plot"] or 'harm' in config_obj['outputs'][0]["plot"]:
        temporal_colocation_flag = False

    if 'depth' in config_obj['meta_zones']:
        vertical_colocation_flag = False
    if 'dens' in config_obj['meta_zones']:
        vertical_colocation_flag = False
    if 'cloud' in config_obj['meta_zones']:
        horizontal_colocation_flag = False
    if 'times' in config_obj['meta_zones'] and config_obj["functionality"] != "prof_hydro_mooring":
        temporal_colocation_flag = False

    flags = temporal_colocation_flag, horizontal_colocation_flag, vertical_colocation_flag

    return flags


def get_method(data, z_dim=False) -> str:
    """
    Get the method to use.
    Parameters
    ----------
    data : dict
        Parser.
    z_dim : bool
        If True, the vertical method is retrieved.
    Returns
    -------
        str
        Method to use.
    """
    if z_dim:
        method = data.get('method_z')

    else:
        method = data.get('method')

    if method is None:
        logger.warning('No method provided for %s', data.get("name"))
        method = 'linear'
    return method


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
    if {'min_depth', 'max_depth', 'min_dens', 'max_dens'} & set(config_obj["metazone"].keys()):
        if config_obj["functionality"] == "currents_ADCP":
            msg = 'For the functionality "currents_ADCP", the use of '\
                  '"min_depth", "max_depth", "min_dens" or "max_dens" '\
                  'within the "metazone" configuration is not permitted.'
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
        # if ("vlevel" not in metazone) and ("vrange" not in metazone):
        #     raise TypeError(
        #         "pro_hydro_vessel needs to have depth or vrange to be processed."
        #         "Please, fill your configuration file."
        #     )
        
        meta = [
            "tbound", "trange_seq",
            "polygon", "radius",
            "vlevel", "vrange", "vref",
            "vars"
        ]
    for k, v in metazone.items():
        if (k != "name") and (k not in meta):
            raise TypeError(
                f"{k} cannot be defined for {cfg['functionality']}: {meta}"
            )
    #time
    time_meta = [
        "tbound", "terms", "trange_cut"
    ]
    for k in time_meta:
        if k in metazone.keys():
            ds = FILTERS[k](ds)(*metazone[k])
    #horizontal
    horizontal_meta = [
        "polygon", "bathy", "coords",
    ]
    for k in horizontal_meta:
        if k in metazone.keys():
            ds = FILTERS[k](ds)(*metazone[k])
    #vertical
    vertical_meta = [
        "vlevel",
    ]
    for k in vertical_meta:
        if k in metazone.keys():
            ds = FILTERS[k](ds)(*metazone[k].items()[0])
    
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


def merge_no_fail(list_ds):
    """
    list_ds : list of xr.dataset
        First dataset must contain the correct attributes
    """

    xarray_obj_tmp = xr.Dataset()
    for ds in list_ds:
        if isinstance(ds, xr.DataArray):
            xarray_obj_tmp[ds.name] = ds
        else:
            for var in ds:
                xarray_obj_tmp[var] = ds[var]
    attrs = list_ds[0].attrs
    xarray_obj = xarray_obj_tmp.assign_attrs(attrs)

    return xarray_obj
