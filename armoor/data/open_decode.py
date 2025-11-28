"""
Open files and decode data.
"""

import concurrent.futures
import datetime
import gc
import glob
import logging
import os
import re
import sys
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Dict, List, Union

import dask
import gsw
import numpy as np
import pandas as pd
import xarray as xr
import xoa
import xoa.cf as xcf
import xoa.geo as xgeo
from pyproj import Geod
from xoa.grid import dz2depth, shift, to_rect

from armoor.__init__ import ROOTDIR, ArmoorError
from armoor.base.interp import regrid
from armoor.base.misc import optimize_for_low_swap

logger = logging.getLogger(__name__)

xoa.register_accessors(xcf=True, decode_sigma=True)
xr.set_options(keep_attrs=True)


def get_paths(path_files: str, sort_results: bool = True) -> List[str]:
    """Generate absolute paths from a pattern string with wildcard and list expansion.
    
    Supports patterns like :
    - '/path/to/files/*.txt' (standard glob)
    - '/path/to/files/*[option1,option2].txt' (list expansion)
    
    Parameters
    ----------
    pattern : str
        Path pattern with wildcards (*) and optional list expansions [item1,item2,...]
    sort_results : bool, default True
        Whether to sort the resulting paths alphabetically
        
    Returns
    -------
    List[str]
        List of absolute paths matching the pattern
        
    Raises
    ------
    ValueError
        If the pattern contains malformed list syntax
    FileNotFoundError
        If the base directory doesn't exist
    """
    if not path_files:
        raise ArmoorError("Pattern cannot be empty")
    if "*" in path_files or "[" in path_files:
        # Convert to Path object and resolve to absolute
        pattern_path = Path(path_files).expanduser()
        
        # Check for list expansion syntax [item1,item2,...]
        list_pattern = re.compile(r'\[([^\]]+)\]')
        matches = list_pattern.findall(path_files)
        
        if not matches:
            # Simple glob pattern without list expansion
            files = _glob_and_resolve(str(pattern_path), sort_results)
            if len(files) > 0 :
                return files
            else:
                raise ArmoorError(f"{path_files} not found.")
        
        # Handle list expansion
        expanded_patterns = _expand_list_patterns(str(pattern_path), matches)
    elif "*" not in path_files and "," in path_files:
        expanded_patterns = path_files.split(',')
    else:
        expanded_patterns = [path_files]
    # Apply glob to each expanded pattern
    all_paths = []
    for expanded_pattern in expanded_patterns:
        paths = _glob_and_resolve(expanded_pattern, sort_results=False)
        all_paths.extend(paths)
    if len(all_paths) == 0:
        raise ArmoorError(f"{path_files} not found.")
    # Remove duplicates and sort if requested
    unique_paths = list(set(all_paths))
    if len(unique_paths) > 0:
        return sorted(unique_paths) if sort_results else unique_paths


def _expand_list_patterns(pattern: str, matches: List[str]) -> List[str]:
    """
    Expand list patterns like [item1,item2] into multiple pattern strings.
    
    Parameters
    ----------
    pattern : str
        Original pattern with list syntax
    matches : List[str]
        List of matched content inside brackets
        
    Returns
    -------
    List[str]
        List of expanded patterns
    """
    expanded_patterns = [pattern]
    
    for match in matches:
        # Split items and clean whitespace
        items = [item.strip() for item in match.split(',')]
        if not items or any(not item for item in items):
            raise ValueError(f"Invalid list syntax in pattern: [{match}]")
        
        # Expand current patterns with each item
        new_patterns = []
        for current_pattern in expanded_patterns:
            for item in items:
                # Replace first occurrence of [match] with item
                new_pattern = current_pattern.replace(f'[{match}]', item, 1)
                new_patterns.append(new_pattern)
        
        expanded_patterns = new_patterns

    return expanded_patterns


def _glob_and_resolve(pattern: str, sort_results: bool = True) -> List[str]:
    """
    Apply glob pattern matching and resolve to absolute paths.
    
    Parameters
    ----------
    pattern : str
        Glob pattern
    sort_results : bool
        Whether to sort results
        
    Returns
    -------
    List[str]
        List of absolute paths
    """
    try:
        # Use glob to find matching files
        matched_paths = glob.glob(pattern, recursive=True)
        
        # Convert to absolute paths
        absolute_paths = [str(Path(path).resolve()) for path in matched_paths]
        
        return sorted(absolute_paths) if sort_results else absolute_paths
    
    except Exception as e:
        # Check if base directory exists for better error messages
        base_dir = Path(pattern).parent
        while '*' in str(base_dir) or '[' in str(base_dir):
            base_dir = base_dir.parent
        
        if not base_dir.exists():
            raise FileNotFoundError(f"Base directory does not exist: {base_dir}")
        
        raise e

def register_cf():
    xcf.reset_cache()
    cfg_files = glob.glob(
        os.path.join(ROOTDIR, "data", "cf_*.cfg")
    )
    for cfg_file in cfg_files:
        logger.info(f"register {cfg_file}")
        mycfspecs = xcf.CFSpecs(cfg_file, default=False, user=False)
        xcf.register_cf_specs(mycfspecs)
    
def open_decode(
    path_files, fmt, platform=None, func=None, type=None
) -> xr.Dataset:
    """
    Open a netcdf/txt file and store it into a dataset
    Parameters
    ----------
    path_files : str, list of str
        Path to the netcdf files.
    func : str
       Poste 1 : functionnality.
    type : str
       type of txt file or model.
    steps : float
       Horizontal and vertical steps.

    Returns
    -------
    xarray.Dataset
        Model or observation dataset.
    """
    # Xoa initialisation
    # register_cf()
    path_files = get_paths(path_files)
    # Open file
    if fmt == "cmems_insitu":
        logger.info("Opening/decoding insitu cmems files")
        return open_decode_cmems_insitu(path_files, platform=platform)
    elif fmt == "cora_insitu":
        logger.info("Opening/decoding insitu cmems files")
        return open_decode_cora_insitu(path_files, platform=platform)
    elif fmt == "cmems_model":
        logger.info("Opening/decoding model cmems files")
        return open_decode_cmems_model(path_files)
    elif fmt == "armoor":
        logger.info("Opening armoor files")
        ds = xr.open_mfdataset(path_files)#, chunks="auto")
        if "depth" in ds:
            ds = ds.reset_coords("depth")
        return ds
    elif "_sst_l" in fmt:
        logger.info("Opening/decoding sst satellite files")
        return open_decode_sst_satellite(path_files, fmt)
    elif (fmt == "hycom") or (fmt == "hycom3d"):
        logger.info("Opening/decoding hycom files")
        return open_decode_hycom(path_files)
    elif (fmt == "croco") or (fmt == "croco_xios"):
        logger.info("Opening/decoding croco files")
        return open_decode_croco(path_files, fmt)
    elif fmt == "arpege_insta":
        logger.info("Opening/decoding instantaneous arpege files")
        return open_decode_arpege_insta(path_files)
    elif fmt == "woa18":
        logger.info("Opening/decoding woa18 climato")
        return open_decode_woa18(path_files)
    else:
        raise logger.error("Unknow format")
    

def open_decode_arpege_insta(path_files):
    logger.info("atmfrc - insta")
    insta_gribs = path_files
    cfspecs = xcf.get_cf_specs("meteofrance")
    dss = []
    for grib in insta_gribs:
        ds = []
        for level in [0, 2, 10]:
            ds0 = xr.open_dataset(
                grib,
                engine="cfgrib",
                backend_kwargs={
                    "indexpath": "",
                    "filter_by_keys": {"edition": 2, "level": level},
                },
                drop_variables=[
                    "heightAboveGround",
                    "meanSea",
                    "surface",
                ],
            )
            ds.append(ds0)
        dss.append(xr.merge(ds, combine_attrs="override"))
    ds_insta = xr.concat(dss, dim="valid_time")
    ds_insta = ds_insta.drop_vars(["step", "time"])
    ds_insta = ds_insta.rename(
        {"longitude": "lon", "latitude": "lat", "valid_time": "time"}
    )
    ds_insta = ds_insta.swap_dims({"lon": "x", "lat": "y"})
    with xcf.set_cf_specs(cfspecs):
        ds_insta = ds_insta.sortby("time").xcf.decode()
    logger.info(ds_insta)
    return ds_insta

def open_decode_sst_satellite(path_files, fmt):
    """
    Open SST satellite netcdf file(s) and store it into a ready-to-use dataset.
    Parameters
    ----------
    path_files : str, list of str
        Path to the netcdf files.
    steps : float
       Horizontal and vertical steps
    Returns
    -------
    xarray.Dataset
        CMEMS dataset.
    """
    # Open
    # path = os.path.join(ROOTDIR, "config", f"{fmt}.cfg")
    cfspecs = xcf.get_cf_specs(f"{fmt}")
    with xcf.set_cf_specs(cfspecs):
        ds = xr.open_mfdataset(path_files).chunk(chunks={}).xcf.decode()
    for var in ds.coords:
        if "or_" in var:
            ds = ds.drop_vars(var)
    ds = ds.swap_dims({"lon": "x", "lat": "y"})
    lat, lon = xr.broadcast(ds["lat"], ds["lon"])
    ds = ds.drop_vars(["lon", "lat"])
    ds["lon"] = lon
    ds["lat"] = lat
    ds = ds.set_coords(["lon", "lat"])
    ds["ptemp"] -= 273.15
    ds["ptemp"].attrs["units"] = "degrees C"
    if "ptemp_qc" in ds:
        ds = ds[["ptemp", "ptemp_qc", "lon", "lat"]]
    else:
        ds = ds[["ptemp", "lon", "lat"]]
    return ds

def open_decode_cmems_model(path_files):
    """
    Open CMEMS netcdf file(s) and store it into a ready-to-use dataset.
    Parameters
    ----------
    path_files : str, list of str
        Path to the netcdf files.
    steps : float
       Horizontal and vertical steps
    Returns
    -------
    xarray.Dataset
        CMEMS dataset.
    """
    def preprocess_cmems_model(ds):
        with xcf.set_cf_specs(cfspecs):
            ds = ds.xoa.decode()
        ds = ds.swap_dims({"depth": "z", "lon": "x", "lat": "y"})
        if len(ds.lon.dims) == 1:
            lat, lon = xr.broadcast(ds["lat"], ds["lon"])
            ds = ds.drop_vars(["lon", "lat"])
            ds["lon"] = lon
            ds["lat"] = lat
            ds = ds.set_coords(["lon", "lat"])
        if "time" in ds.dims:
            var = [var for var in ds.data_vars if len(ds[var].dims) == 4][0]
            ds["depth"] = ds["depth"].broadcast_like(ds[var])
            ds = ds.reset_coords("depth")
        return ds
    # Open
    cfspecs = xcf.get_cf_specs("cmems_model")
    sorted_paths = sorted(map(str, path_files))
    # ds = xr.open_mfdataset(
    #     sorted_paths,
    #     combine="by_coords",
    #     engine="netcdf4",
    #     chunks={"time": 1, "lat": 100, "lon": 100},
    #     parallel=True,
    #     cache=False,
    #     # lock=False,
    #     )
    ds = xr.open_mfdataset(#sorted_paths)
        sorted_paths,
        combine="by_coords",
        engine="netcdf4",
        chunks={"time": 1, "lat": 100, "lon": 100},
        parallel=False,#True,        # Avoid threading issues with netCDF4
        cache=False,       # Cache can be disabled for huge datasets
        # lock=False,
        decode_times=True,     # Decode times properly
        decode_coords=True,    # Decode coordinates
        # Optimize I/O
        decode_cf=True,
        mask_and_scale=True,
        # CRITICAL: Limit data variables to prevent reading everything at once
        data_vars='minimal',   # Only load data variables, not coordinates as data
        coords='minimal',      # Minimize coordinate loading
        preprocess=preprocess_cmems_model,
        autoclose=True
        )
    ds = ds.set_coords("depth")
    return ds

def open_decode_hycom(path_files):#, chunk_size_time=1, chunk_size_xy=200):
    """
    Fast and memory-efficient HyCOM NetCDF reader.

    Parameters
    ----------
    path_files : list of str or Path
        Paths to NetCDF files (can contain corrupted or non-NetCDF files, they will be skipped).
    chunk_size_time : int, optional
        Chunk size for time dimension.
    chunk_size_xy : int, optional
        Chunk size for horizontal (x,y) dimensions.

    Returns
    -------
    xarray.Dataset
        Merged and decoded HyCOM dataset.
    """
    
    def preprocess_hycom(ds):
        # Clean density coord if present
        if "dens" in ds.coords:
            ds = ds.reset_coords("dens")

        # Drop lon/lat for u and v files to avoid merge conflict
        if any(var in ds.data_vars for var in ["u", "v"]):
            for coord in ["lon", "lat"]:
                if coord in ds:
                    ds = ds.drop_vars(coord)

        # Drop bathy if present (we'll handle separately)
        if "bathy" in ds:
            ds = ds.drop_vars("bathy")

        return ds
    
    def shift_u_block(d):
        return shift(d["u"], {"x": "right"}).xoa.reloc(u=False)

    def shift_v_block(d):
        return shift(d["v"], {"y": "top"}).xoa.reloc(v=False)

    sorted_paths = sorted(map(str, path_files))

    logger.info(f"Using {len(sorted_paths)} files.")

    ds = xr.open_mfdataset(
        sorted_paths,
        combine="by_coords",
        engine="netcdf4",         # works with classic and netcdf4
        chunks={"time": 1, "lat": 200, "lon": 200},
        preprocess=preprocess_hycom,
        # parallel=True,        # Avoid threading issues with netCDF4
        cache=False,       # Cache can be disabled for huge datasets
        # lock=False,
        decode_times=True,     # Decode times properly
        decode_coords=True,    # Decode coordinates
        # Optimize I/O
        decode_cf=True,
        mask_and_scale=True,
        # CRITICAL: Limit data variables to prevent reading everything at once
        data_vars='minimal',   # Only load data variables, not coordinates as data
        coords='minimal',      # Minimize coordinate loading
        autoclose=True
    )

    cfspecs = xcf.get_cf_specs("hycom")
    with xcf.set_cf_specs(cfspecs):
        ds = ds.xoa.decode()

    ds = ds.unify_chunks()

    if "bathy" in ds:
        bathy = ds["bathy"]
        ds = ds.drop_vars("bathy")
    else:
        bathy = None

    if "u" in ds:
        ds["u"] = ds.map_blocks(shift_u_block, template=ds["u"])
    if "v" in ds:
        ds["v"] = ds.map_blocks(shift_v_block, template=ds["v"])

    if bathy is not None:
        ds = xr.merge([ds, bathy.to_dataset(name="bathy")])
    if "dz" in ds:
        depth = dz2depth(ds.dz, centered=True)
        ds = ds.assign_coords(depth=depth).drop_vars(["dz", "z"])

    ds = ds.sel(time=~ds.get_index("time").duplicated())
    for var in ["depth", "ssh", "ptemp"]:
        if var in ds:
            good_var = ds[var]
            break
    chunk_dict = {}
    for dim, chunks in zip(good_var.dims, good_var.chunks):
        chunk_dict[dim] = chunks[0]
    ds = ds.chunk(chunk_dict)
    return ds

def open_decode_woa18(path_files):
    """
    Open WOA18 netcdf files and store it into a ready-to-use dataset.
    Parameters
    ----------
    path_files : str, list of str
        Path to the netcdf files.
    Returns
    -------
    xarray.Dataset
        WOA18 dataset.
    """
    # Open
    woa18 = xr.open_mfdataset(
        path_files,
        decode_times=False,
        combine_attrs="drop_conflicts"
    )
    # Decode
    vars_to_drop = ["_dd", "_gp", "_oa", "_sd", "_se", "_ma", "bnds", "bounds", "crs"]
    for var in list(woa18.keys()):
        if any(item in var for item in vars_to_drop):
            woa18 = woa18.drop_vars(var)

    if "s_an" in woa18:
        woa18 = woa18.rename({"s_an": "sal"})
        if "s_mn" in woa18:
            woa18 = woa18.drop_vars({"s_mn"})
    elif "s_mn" in woa18:
        woa18 = woa18.rename({"s_mn": "sal"})

    if "t_an" in woa18:
        woa18 = woa18.rename({"t_an": "temp"})
        if "t_mn" in woa18:
            woa18 = woa18.drop_vars({"t_mn"})
    elif "t_mn" in woa18:
        woa18 = woa18.rename({"t_mn": "temp"})

    woa18 = convert_lons(woa18)

    woa18 = woa18.swap_dims({
        "lon": "x",
        "lat": "y",
        "depth": "z"
    })
    lon, lat = np.meshgrid(woa18["lon"], woa18["lat"])
    woa18 = woa18.drop_vars(["lon", "lat"])
    woa18["lon"] = xr.DataArray(lon, dims=["y", "x"])
    woa18["lat"] = xr.DataArray(lat, dims=["y", "x"])
    woa18 = woa18.set_coords(["lon", "lat"])
    woa18["time"] = np.ceil(woa18["time"]) - 12.0 * np.trunc(
        np.ceil(woa18["time"]) / 12.0
    )
    woa18["time"] = woa18.time.where(woa18.time != 0., 12.)
    return woa18


def open_decode_cora_insitu(path_files, platform):
    """
    Open CMEMS netcdf file(s) and store it into a ready-to-use dataset.
    Parameters
    ----------
    path_files : str, list of str
        Path to the netcdf files.
    steps : float
       Horizontal and vertical steps
    Returns
    -------
    xarray.Dataset
        CORA dataset.
    """
    # Open
    cmems_coords = ["time", "lon", "lat", "depth"]
    cfspecs = xcf.get_cf_specs(f"cora_{platform}")
    dss = []
    for path in path_files:
        with xcf.set_cf_specs(cfspecs):
            ds = xr.open_dataset(path).xcf.decode()
        ds = ds.swap_dims({"N_PROF": "time", "level": "z"})
        for coord in ds.coords:
            if coord not in cmems_coords:
                ds = ds.reset_coords(coord)
        if ("depth" not in ds) and ("pres" in ds):
            ds = depth_from_pres(ds)
        for var in ds.data_vars:
            if var in cmems_coords:
                ds = ds.set_coords(var)
        ds["depth"] = -ds["depth"]
        dss.append(ds)
    if platform == "argo":
        ds = concat_argo(dss)
        return ds
    else:
        return dss

def open_decode_cmems_insitu(path_files, platform):
    """
    Open CMEMS netcdf file(s) and store it into a ready-to-use dataset.
    Parameters
    ----------
    path_files : str, list of str
        Path to the netcdf files.
    steps : float
       Horizontal and vertical steps
    Returns
    -------
    xarray.Dataset
        CMEMS dataset.
    """
    # Open
    cmems_coords = ["time", "lon", "lat", "depth"]
    cfspecs = xcf.get_cf_specs(f"cmems_{platform}")
    dss = []
    for path in path_files:
        with xcf.set_cf_specs(cfspecs):
            ds = xr.open_dataset(path).load().xcf.decode()
        object_vars = [var for var in ds.data_vars if ds[var].dtype == 'object']
        ds = ds.drop_vars(object_vars)
        vars2drop = []
        for var in ds.data_vars:
            if var.isupper():
                vars2drop.append(var)
        ds = ds.drop_vars(vars2drop)
        if "depth" in ds.dims:
            ds = ds.swap_dims({"depth": "z"})
        elif ("DEPTH" in ds.dims) or ("depth" in ds.dims):
            ds = ds.swap_dims({"DEPTH": "z"})
        if "DEPH" in ds.coords:
            ds = ds.rename({"DEPH": "depth"})
        if (
            ("lon" in ds.lon.dims) and (ds.sizes["time"] == ds.sizes["lon"])
        ) or (("lat" in ds.lon.dims) and (ds.sizes["time"] == ds.sizes["lat"])):
            # ds = ds.drop_dims("POSITION")
            lon_ds = ds.lon.assign_coords(lon=ds.time.data).rename(
                {"lon": "time"}
            )
            lat_ds = ds.lat.assign_coords(lat=ds.time.data).rename(
                {"lat": "time"}
            )
            ds = ds.drop_vars(["lon", "lat"])
            if platform == "mooring":
                ds["lat"] = lat_ds.isel(time=0)
                ds["lon"] = lon_ds.isel(time=0)
            else:
                ds["lat"] = lat_ds
                ds["lon"] = lon_ds
        ds.set_coords(["lon", "lat"])
        for coord in ds.coords:
            if coord not in cmems_coords:
                ds = ds.reset_coords(coord)
        if ("depth" not in ds) and ("pres" in ds):
            ds = depth_from_pres(ds)
            if platform == "glider":
                ds = ds.drop_vars("pres")
        if "depth" in ds:
            if platform == "argo":
                dssi = []
                for itime in range(ds.sizes["time"]):
                    dsi = ds.isel(time=[itime])
                    if dsi.depth.min() < -10.0:
                        dssi.append(dsi)
                if len(dssi) == 0:
                    continue
                ds = xr.combine_nested(dssi, "time")
                ds["depth"] = -1 * ds["depth"]
            if platform == "glider":
                if ds["depth"].dims == ("z",):
                    ds["depth"] = ds["depth"].broadcast_like(ds["temp"])
                if ds.depth.min() < 0:
                    ds["depth"] = -1 * ds["depth"]
            if platform == "mooring":
                if "time" in ds.depth.dims:
                    continue
                iz2keep = []
                for iz in range(ds.sizes["z"]):
                    if (
                        (np.isfinite(ds.isel(z=iz).depth))
                        and (ds.isel(z=iz).depth > 0.0)
                        and (np.all(np.isfinite(ds.isel(z=iz).temp)))
                    ):
                        iz2keep.append(iz)
                ds = ds.isel(z=iz2keep)
                if ds.depth.sizes["z"] == 0:
                    continue
            if platform == "drifter":
                ds = ds.isel(z=[-1])
                if "time" in ds.depth.dims:
                    ds["depth"] = ds.depth.isel(time=1)
                if "u" not in ds.data_vars:
                    ds["u"] = (
                        ds.lon.differentiate("time", datetime_unit="s")
                        * xgeo.EARTH_RADIUS * np.pi / 180
                        )
                    ds["u"] *= np.cos(np.radians(ds.lat.values))
                    ds["v"] = (
                        ds.lat.differentiate("time", datetime_unit="s")
                        * xgeo.EARTH_RADIUS * np.pi / 180
                        )
        for var in ds.data_vars:
            if var in cmems_coords:
                ds = ds.set_coords(var)
        dss.append(ds)
        ds.close()
    if platform == "argo":
        ds = concat_argo(dss)
        if "TRAJECTORY" in ds:
            ds = ds.drop_vars("TRAJECTORY")
        return ds
    else:
        dss_by_platform = dict()
        for ds in dss:
            platform_code = ds.attrs.get("platform_code")
            if platform_code not in dss_by_platform.keys():
                dss_by_platform.update({platform_code: []})
            dss_by_platform[platform_code].append(ds)
        dss = []
        for platform_code, dss0 in dss_by_platform.items():
            ds = xr.merge(dss0)
            ds = ds.sortby("time")
            ds.attrs["name"] = f"{ds.attrs['platform_code']}"
            dss.append(ds)
        return dss

def open_decode_croco(path_file, fmt="croco"):
    """
    Open netcdf file from CROCO model.
    Parameters
    ----------
    path_file : list of str
        List of the file to decode.

    Returns
    -------
    croco : xarray.Dataset
         Model dataset decoded.
    """
    cfspecs = xcf.get_cf_specs("croco")
    ds = xr.open_mfdataset(path_file)
    if 'scrum_time' in ds:   
        ds = ds.drop_vars('scrum_time') 
    with xcf.set_cf_specs(cfspecs):
        ds = ds.xcf.decode()
        for sig in ("sig_rho", "sig_w"):
            if sig in ds:
                # if "formula_terms" not in ds[sig].attrs:
                logger.warning(f"No formula_terms attributes in {sig}")
                if "hc" not in ds.data_vars:
                    ds["hc"] = float(ds.attrs.get("hc"))
                if sig == "sig_w":
                    ds[sig].attrs["formula_terms"] = "s: sig_w C: cs_w eta: ssh depth: bathy depth_c: hc"
                elif sig == "sig_rho":
                    if "cs_r" in ds:
                        cs_rho = "cs_r"
                    elif "cs_rho" in ds:
                        cs_rho = "cs_rho"
                    else:
                        raise ArmoorError("cs_r and cs_rho are missing. Armoor should find one of them.")
                    ds[sig].attrs["formula_terms"] = f"s: sig_rho C: {cs_rho} eta: ssh depth: bathy depth_c: hc"
                if "standard_name" not in ds[sig].attrs:
                    logger.warning(f"No standard_name attributes in {sig}")
                    if sig == "sig_rho":
                        ds[sig].attrs["standard_name"] = "ocean_s_coordinate_g2"
                    elif sig == "sig_w":
                        ds[sig].attrs["standard_name"] = "ocean_s_coordinate_g2_at_w_location"
        ds = ds.decode_sigma()
    
    for v in [
        "sig_rho",
        "sig_w",
        "cs_r",
        "cs_w",
        "sc_r",
        "sc_w",
        "time_centered_bounds",
        "time_counter_bounds",
        "hc",
        "theta_s",
        "theta_b",
        "Tcline",
        "Vtransform",
        "corio",
        "ex",
        "ey",
        "akv",
        "akt",
        "ubar",
        "vbar",
        "w",
        "sustr",
        "svstr",
        "spherical",
        "xl",
        "el",
        "tke",
        "gls",
        "time_step",
        "depth_w",
        "s_w",
        "cs_rho",
        ]:
        if v in ds:
            ds = ds.drop_vars(v)
    for coord in ds.coords:
        if "nav_" in coord:
            coord_name = coord.replace("nav_", "")
            if coord_name in ds:
                ds = ds.drop(coord)
            ds = ds.rename({coord: coord_name})
    if "time_counter" in ds.dims:
        ds = ds.swap_dims({"time_counter": "time"})
    ds = ds.swap_dims({"sig_rho": "z"})
    # ds = ds.swap_dims({"sig_w": "z_w"})
    ds = ds.isel(x_rho=slice(1, -1), y_rho=slice(1,-1))
    for varname in ds.data_vars:
        if varname == "u":
            dau = shift(ds["u"], {"x_u": "right"}).isel(x_u=slice(None, -1)).xoa.reloc(u="rho")
            ds["u"] = dau.assign_coords(**ds.ptemp.coords)
        if varname == "v":
            dav = shift(ds["v"], {"y_v": "top"}).isel(y_v=slice(None, -1)).xoa.reloc(v="rho")
            ds["v"] = dav.assign_coords(**ds.ptemp.coords)
    ds = ds.rename({"lon_rho": "lon", "lat_rho": "lat", "depth_rho": "depth"})
    for dim in ("x_u", "y_v"):
        if dim in ds.dims:
            ds = ds.drop_dims(dim)
    ds = ds.swap_dims({"x_rho": "x", "y_rho": "y"})
    if "angle" in ds and (set(("u", "v")).issubset(ds.data_vars)):
        angle = ds["angle"]
        da_u = ds["u"] * np.cos(angle) - ds["v"] * np.sin(angle)
        da_v = ds["v"] * np.cos(angle) + ds["u"] * np.sin(angle)
        ds = ds.drop_vars(["u", "v", "angle"])
        ds["u"] = da_u
        ds["v"] = da_v
    if "mask" in ds:
        ds = ds.where(ds["mask"] > 0)
    ds = ds.isel(z=slice(None, None, -1))
    ds = ds.assign_coords(depth=-ds.depth)
    return ds

def open_decode_cora(path_files):
    """
    Open CORA netcdf files and store it into a ready-to-use dataset.
    Parameters
    ----------
    path_files : str, list of str
        Path to the netcdf files.
    Returns
    -------
    xarray.Dataset
        CORA dataset.
    """
    # Open
    if len(path_files) > 1:
        list_ds_cora = []
        for path in path_files:
            dataset = xr.open_dataset(path)
            dataset = dataset.drop_dims(["N_HISTORY", "N_CALIB", "N_PARAM"])
            # Variables to drop/rename to prevent random behaviours
            for var in list(dataset.keys()):
                if "POSITION" in var or "LOCATION" in var:
                    dataset = dataset.drop_vars(var)
                elif var[-3:] == "_QC":
                    dataset = dataset.rename({var: f"QC_{var[:-3]}"})
                if len(var) == 4:
                    if f"{var}_ADJUSTED" in dataset:
                        dataset = dataset.drop_vars(f"{var}_ADJUSTED")
                    if f"{var}_ADJUSTED_ERROR" in dataset:
                        dataset = dataset.drop_vars(f"{var}_ADJUSTED_ERROR")
            for var in list(dataset.keys()):
                if "N_PROF" not in list(
                    dataset[var].dims
                ) and "N_LEVELS" not in list(dataset[var].dims):
                    dataset = dataset.drop_vars(var)

            # Decode
            dataset = dataset.xoa.decode()

            # Rename time
            dataset = dataset.assign_coords({"N_prof": dataset.time.values})
            dataset = dataset.drop_vars("time")
            dataset = dataset.rename({"N_prof": "time"})

            list_ds_cora.append(dataset)

        cora = concat_cora(list_ds_cora)
    else:
        cora = xr.open_dataset(path_files[0])

        cora = cora.drop_dims(["N_HISTORY", "N_CALIB", "N_PARAM"])
        # Variables to drop/rename to prevent random behaviours
        for var in list(cora.keys()):
            if "POSITION" in var or "LOCATION" in var:
                cora = cora.drop_vars(var)
            elif var[-3:] == "_QC":
                cora = cora.rename({var: f"QC_{var[:-3]}"})
            if len(var) == 4:
                if f"{var}_ADJUSTED" in cora:
                    cora = cora.drop_vars(f"{var}_ADJUSTED")
                if f"{var}_ADJUSTED_ERROR" in cora:
                    cora = cora.drop_vars(f"{var}_ADJUSTED_ERROR")
        for var in list(cora.keys()):
            if "N_PROF" not in list(cora[var].dims) and "N_LEVELS" not in list(
                cora[var].dims
            ):
                cora = cora.drop_vars(var)

        # Decode
        cora = cora.xoa.decode()

        # Rename time
        cora = cora.assign_coords({"N_prof": cora.time.values})
        cora = cora.drop_vars("time")
        cora = cora.rename({"N_prof": "time"})

    # Convert depths
    cora = cora.rename({"N_levels": "depth"})
    cora = depth_from_pres(cora)

    # Convert lons
    cora = convert_lons(cora)

    return cora


####################### Tools #######################

def convert_lons(dataset):
    """
    Convert latitudes in case they go 0 -> 360°
    Returns
    -------
    xarray.dataset
        Dataset with homogeneous longitudes
    """
    if np.nanmax(dataset.lon.where(dataset.lon < 1e30).data) > 180:
        dataset = dataset.assign_coords(
            {"lon": (((dataset.lon + 180) % 360) - 180)}
        )
    return dataset

def depth_from_pres(ds):
    """
    Calculate depth values from pressure.

    Returns
    -------
    xarray.Dataset
        Formatted dataset.

    """
    alat = ds.lat.broadcast_like(ds.pres)
    adepth = gsw.z_from_p(ds.pres, alat)
    # adepth = adepth.where(adepth.notnull(), adepth.min())
    adepth.attrs.update({"long_name": "Depth", "units": "m"})
    ds["depth"] = adepth
    return ds

def concat_cmems(list_ds):
    times = np.unique([len(ds.TIME.data) for ds in list_ds])
    depths = np.unique([len(ds.DEPTH.data) for ds in list_ds])

    # Cas où on concat plusieurs fichiers d'1 instrument, même nombre de depth et time dans tous les fichiers
    if len(depths) == 1 and len(times) == 1:
        cmems = xr.concat(list_ds, dim="TIME")

    # Cas où on concat plusieurs instruments
    else:
        # Compute same DEPTH
        nb_depth_max = np.nanmax(depths)
        common_depths = list(range(nb_depth_max))

        # Compute same TIME
        common_times = [ds.TIME.data for ds in list_ds]
        common_times = np.unique(np.concatenate(common_times))

        for i_ds, ds in enumerate(list_ds):
            if "POSITION" in ds.dims:
                ds = ds.drop_dims("POSITION")
            # Clean lon/lat
            lon, lat = ds.LONGITUDE, ds.LATITUDE

            # Put all datasets on the same depth
            depths_in_ds = ds.DEPTH.data
            ds = ds.assign_coords({"DEPTH": ds.DEPTH.data})
            ds = ds.sel(DEPTH=common_depths, method="nearest")
            ds = ds.assign_coords({"DEPTH": common_depths})
            ds = ds.drop_vars(["LONGITUDE", "LATITUDE"])
            ds = ds.where(ds.DEPTH.isin(depths_in_ds))
            ds = ds.assign_coords({"LONGITUDE": lon, "LATITUDE": lat})
            # Put all TIMES on the same values
            times_in_ds = ds.TIME.data
            ds = ds.drop_duplicates("TIME")
            ds = ds.sel(TIME=common_times, method="nearest")
            ds = ds.assign_coords({"TIME": common_times})
            ds = ds.where(ds.TIME.isin(times_in_ds))

            list_ds[i_ds] = ds
        cmems = xr.concat(list_ds, dim="instr")
        cmems = cmems.drop_vars(names="DEPTH")

    return cmems

def concat_cora(list_ds_cora):
    """
    Concat several Datasets from CORA observations
    Parameters
    ----------
    list_ds_cora : list
        List of xarray.Dataset
    Returns
    -------
    Concatenated observations as one xarray.dataset.
    """
    times = np.unique([len(ds.time.data) for ds in list_ds_cora])
    depths = np.unique([len(ds.N_levels.data) for ds in list_ds_cora])

    # Cas où on concat plusieurs fichiers d'1 instrument, même nombre de depth et time dans tous les fichiers
    if len(depths) == 1 and len(times) == 1:
        cora = xr.concat(list_ds_cora, dim="time")

    # Cas où on concat plusieurs instruments
    else:
        # Compute same DEPTH
        nb_depth_max = np.nanmax(depths)
        common_depths = list(range(nb_depth_max))

        # Compute same TIME
        common_times = [ds.time.data for ds in list_ds_cora]
        common_times = np.unique(np.concatenate(common_times))

        for i_ds, ds in enumerate(list_ds_cora):
            if "POSITION" in ds.dims:
                ds = ds.drop_dims("POSITION")

            # Put all datasets on the same depth
            depths_in_ds = ds.N_levels.data
            ds = ds.assign_coords({"N_levels": ds.N_levels.data})
            ds = ds.drop_duplicates("N_levels")
            ds = ds.sel(N_levels=common_depths, method="nearest")
            ds = ds.assign_coords({"N_levels": common_depths})
            ds = ds.where(ds.N_levels.isin(depths_in_ds))

            # Put all TIMES on the same values
            times_in_ds = ds.time.data
            ds = ds.assign_coords({"time": ds.time.data})
            ds = ds.drop_duplicates("time")
            ds = ds.sel(time=common_times, method="nearest")
            ds = ds.assign_coords({"time": common_times})
            ds = ds.where(ds.time.isin(times_in_ds))

            list_ds_cora[i_ds] = ds

        cora = xr.concat(list_ds_cora, dim="instr")

    return cora


def concat_argo(list_ds):
    dim_z = np.max([ds.sizes["z"] for ds in list_ds])
    for ids, dsin in enumerate(list_ds):
        dsin = dsin.reset_coords("depth")
        if dsin.sizes["z"] != dim_z:
            das = []
            for var in dsin.data_vars:
                if "z" in dsin[var].dims:
                    arr1 = dsin[var].values
                    dim_z_to_fill = dim_z - arr1.shape[1]
                    arr2 = np.nan * np.ones((arr1.shape[0], dim_z_to_fill))
                    arr3 = np.concatenate((arr1, arr2), axis=1)
                    das.append(
                        xr.DataArray(
                            data=arr3,
                            dims=["time", "z"],
                            name=var,
                            coords={
                                "time": dsin.time,
                                "lon": dsin.lon,
                                "lat": dsin.lat,
                            },
                            attrs=dsin[var].attrs,
                        )
                    )
                else:
                    das.append(dsin[var])
            ds = xr.merge(das)
            ds = ds.set_coords("depth")
            list_ds[ids] = ds
    ds = xr.combine_nested(list_ds, "time")
    return ds.sortby("time")
