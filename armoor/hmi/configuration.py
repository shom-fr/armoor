"""
Functions to retrieve the right dataset
"""

import logging
import os

import numpy as np
import pandas
import xarray as xr
from xoa.geo import get_extent

import armoor.base.meta_zone
from armoor.base.sel_var import convert_K_C
from armoor.base.open_decode import open_decode
from armoor.hmi.path_tools import (
    get_config_reg_path,
    get_forcing_model_path,
    get_obs_path,
)
from armoor.hmi.script_tools import get_t0

logger = logging.getLogger(__name__)


def get_model(input_folder_path, model_name, config_reg, production_day, var):
    """
    Retrieve dataset for a given variable
    Parameters
    ----------
    input_folder_path : main folder where the day productions are.
    config_reg : the target regional configuration
    production_day : day production (today)
    var : variable of interest

    Returns
    -------
    dataset
    """
    logger.info("Retrieving model")
    config_reg_path = get_config_reg_path(
        os.path.join(input_folder_path, f"{config_reg}_{production_day}"), model_name, [var]
    )
    return read_netcdfs(config_reg_path, data_type="hycom")


def get_obs(input_folder_path, config_reg, production_day, obs_name, var):
    """

    Parameters
    ----------
    input_folder_path
    config_reg
    production_day
    obs_name
    var

    Returns
    -------

    """
    logger.info("Retrieving obs")
    config_reg_path = get_obs_path(
        input_folder_path, f"{config_reg}_{production_day}", obs_name, var
    )
    return read_netcdfs(config_reg_path, data_type=obs_name)


def get_forcing_model(
    input_folder_path, config_reg, production_day, forcing_model, var
):
    """

    Parameters
    ----------
    input_folder_path
    config_reg
    production_day
    forcing_model
    var

    Returns
    -------

    """
    logger.info("Retrieving forcing model")
    forcing_model_path = get_forcing_model_path(
        input_folder_path, f"{config_reg}_{production_day}", forcing_model, var
    )
    return (
        read_netcdfs(forcing_model_path, data_type=forcing_model),
        forcing_model_path,
    )


def get_time_spacial_extent(input_folder_path, model_name, config_reg, production_day):
    """
    Get model times and geographical extent
    As it's the same for all variables we work here only with sst to retrieve the values
    Parameters
    ----------
    input_folder_path : main folder where the day productions are.
    config_reg : the target regional configuration
    production_day : production day (today)

    Returns
    -------
    t0_fwi, times, geo_extent

    forecater web interface starting time,
    all regional configuration time steps,
    geographical extent
    """
    config_reg_xr = get_model(
        input_folder_path, model_name, config_reg, production_day, "sst"
    )

    times = np.datetime_as_string(
        list(config_reg_xr["time"].data),#.isel(time=slice(None, None, 24)).data),
        unit="m"
    )
    logger.info(times)
    logger.info(config_reg_xr)
    geo_extent = get_extent(config_reg_xr)
    geo_extent = {
        "lon_min": geo_extent[0],
        "lon_max": geo_extent[1],
        "lat_min": geo_extent[2],
        "lat_max": geo_extent[3],
    }
    t0_fwi = get_t0(times, production_day)
    if t0_fwi == "":
        t0_fwi = np.datetime_as_string(
            config_reg_xr.sel(
                time=pandas.to_datetime(production_day), method="nearest"
            )["time"].data,
            unit="m",
        )
    config_reg_xr.close()
    return t0_fwi, times, geo_extent


def apply_custom_metazone(
    param_xr: xr.Dataset,
    depth: dict = None,
    extent: dict = None,
    variable: list = None,
    config_reg_extent: dict = None,
) -> xr.Dataset:
    """
    Apply meta-zone, selecting variables, extent and depth
    Parameters
    ----------
    config_reg_extent : extent of the model (Parameter 1 sst)
    param_xr : data to filter
    depth : depth selected
    extent : extent provided by the user
    variable : variables of interest

    Returns
    -------
    Dataset filtered
    """
    logger.info("Applying meta-zone and selecting variables of interest")
    # SELECT VAR
    if variable is not None:
        logger.info(f"{variable}")
        param_xr = select_var(param_xr, variable)
        logger.info(f"Variable selected")

    # SELECT EXTENT
    if extent is not None or config_reg_extent is not None:
        param_xr = select_extent(param_xr, config_reg_extent, extent)
        logger.info(f"Extent selected")
    # SELECT DEPTH
    if depth is not None:
        # param_xr = param_xr.meta.vertical_selection_ponct(depth)
        depth_name = list(depth.keys())[0]
        depth_values = list(depth.values())[0]
        param_xr = param_xr.meta.vertical_selection_levels(
            depth_name, depth_values
        )
        logger.info(f"Depth selected: {depth_values}")
    return param_xr


def select_var(param_xr: xr.Dataset, variables: list) -> xr.Dataset:
    """
    Rename and select the variables that remains for the plot
    Parameters
    ----------
    param_xr : data to filter
    variable : variables of interest

    Returns
    -------
    Dataset with less variables
    """
    vars2keep = []
    for variable in variables:
        if variable == "sst":
            vars2keep.append("ptemp")
        elif variable == "sss":
            vars2keep.append('sal')
        elif variable in ("uv", "suv"):
            vars2keep += ["u", "v"]
        elif "mld" in variable:
            vars2keep += ["sal", "ptemp"]
        else:
            vars2keep.append(variable)
    param_xr = param_xr[vars2keep]
    if "ptemp" in param_xr:
        param_xr = convert_K_C(param_xr, "ptemp")
    return param_xr


def rename_vars(param_xr: xr.Dataset) -> xr.Dataset:
    """
    Rename variables to unify how the variables are used for the plots
    Parameters
    ----------
    param_xr : dataset where the variables need to be renamed

    Returns
    -------
    dataset with the variables renamed
    """
    variables2rename = {
        "uair": "u",
        "vair": "v",
        "ptemp": "temp",
        "analysed_sst": "sst",
        "s_an": "sss",
        "t_an": "temp",
    }

    for var in variables2rename:
        try:
            param_xr = param_xr.rename({var: variables2rename[var]})
        except:
            pass

    return param_xr


def select_extent(
    param_xr: xr.Dataset, config_reg_extent: dict = None, extent: dict = None
) -> xr.Dataset:
    """
    Select extent from regional configuration (model param 1) and select other extent if provided
    Parameters
    ----------
    config_reg_extent : extent of the model (Parameter 1)
    param_xr : dataset where the extent must be reduced
    extent : extent provided by the user

    Returns
    -------
    dataset with the new extent applied
    """
    extent_mask = True
    config_reg_extent_mask = True
    if extent:
        mask_lon = (param_xr.lon >= extent["lon_min"]) & (
            param_xr.lon <= extent["lon_max"]
        )
        mask_lat = (param_xr.lat >= extent["lat_min"]) & (
            param_xr.lat <= extent["lat_max"]
        )
        extent_mask = mask_lon & mask_lat
        extent_mask = extent_mask.compute()
        
    if config_reg_extent:
        mask_lon = (param_xr.lon >= config_reg_extent["lon_min"]) & (
            param_xr.lon <= config_reg_extent["lon_max"]
        )

        mask_lat = (param_xr.lat >= config_reg_extent["lat_min"]) & (
            param_xr.lat <= config_reg_extent["lat_max"]
        )
        config_reg_extent_mask = mask_lon & mask_lat
        config_reg_extent_mask = config_reg_extent_mask.compute()
    param_xr = param_xr.where(config_reg_extent_mask & extent_mask, drop=True)
    return param_xr


def read_netcdfs(paths: list, data_type: str = None) -> xr.Dataset:
    """
    open netcdf form multiple files

    Parameters
    ----------
    data_type : if there is a spacial function to use when opening files
        ex : HYCOM_currents to read current from HYCOM
    paths : str "path/part_*.nc"
            or
            str_list ["path/part_1.nc", "path/part_2.nc", etc]

    Returns
    -------
        xarray.Dataset
             Dataset with decoded parameters
    """
    logger.info("Opening file(s)")
    xarray_obj = open_decode(paths, "forecaster", type=data_type)
    logger.info(xarray_obj)
    return xarray_obj
