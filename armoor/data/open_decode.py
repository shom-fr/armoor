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
# def get_paths(path_files):

#     if not isinstance(path_files, (list, dict)):
#         raise ArmoorError(f"Only list or dict are allowed : {path_files}")

#     if (len(path_files) == 1) & ("*" in path_files[0]):
#         paths = glob.glob(path_files[0])
#         if len(paths) == 0:
#             raise ArmoorError(f"{path_files[0]} not found.")
#         path_files = paths
#     else:
#         paths = []
#         for path in path_files:
#             if "*" in path:
#                 paths += glob.glob(path)
#             elif not os.path.exists(path):
#                 raise ArmoorError(f"{path} does not exist.")
#             else:
#                 paths.append(path)
#         path_files = paths
    
#     return path_files


def get_paths(path_files: str, sort_results: bool = True) -> List[str]:
    """Generate absolute paths from a pattern string with wildcard and list expansion.
    
    Supports patterns like :
    - '/path/to/files/\*.txt' (standard glob)
    - '/path/to/files/\*[option1,option2].txt' (list expansion)
    
    Parameters
    ----------
    pattern : str
        Path pattern with wildcards (\*) and optional list expansions [item1,item2,...]
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

    # Convert to Path object and resolve to absolute
    pattern_path = Path(path_files).expanduser()
    
    # Check for list expansion syntax [item1,item2,...]
    list_pattern = re.compile(r'\[([^\]]+)\]')
    matches = list_pattern.findall(path_files)
    
    if not matches:
        # Simple glob pattern without list expansion
        return _glob_and_resolve(str(pattern_path), sort_results)
    
    # Handle list expansion
    expanded_patterns = _expand_list_patterns(str(pattern_path), matches)
    
    # Apply glob to each expanded pattern
    all_paths = []
    for expanded_pattern in expanded_patterns:
        paths = _glob_and_resolve(expanded_pattern, sort_results=False)
        all_paths.extend(paths)
    if len(all_paths) == 0:
        raise ArmoorError(f"{path_files} not found.")
    # Remove duplicates and sort if requested
    unique_paths = list(set(all_paths))
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
    
    cfg_files = glob.glob(
        os.path.join(ROOTDIR, "data", "cf*.cfg")
    )
    for cfg_file in cfg_files:
        logger.info(f"register {cfg_file}")
        xcf.register_cf_specs(cfg_file)

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
    register_cf()
    path_files = get_paths(path_files)

    # Open file
    if fmt== "forecaster":
        logger.info("forecaster")
        return open_forecaster(path_files, type)

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
    # if type == "scanfish":
    #     logger.info("Opening Scanfish")
    #     return open_decode_scanfish(path_files[0], steps=steps)
    # if type == "seasoar":
    #     logger.info("Opening Seasoar")
    #     return open_decode_seasoar(path_files[0], steps=steps)
    # if type == "LADCP":
    #     logger.info("Opening L-ADCP")
    #     return open_decode_l_adcp(path_files[0])
    # if type == "mouillage":
    #     logger.info("Opening Mooring")
    #     return open_decode_mouillages(path_files[0])
    # if type == "VMADCP":
    #     logger.info("Opening VMADCP")
    #     return open_decode_vmadcp(path_files[0], steps=steps)
    # if type in ['CROCO', 'CROCO_currents']:
    #     logger.info("Opening CROCO")
    #     return open_decode_croco(path_files[0])
    # if type == 'HYCOM_currents':
    #     logger.info("Opening HYCOM currents")
    #     return open_decode_hycom_currents(path_files)
    # if type == 'HYCOM_3D':
    #     logger.info("Opening HYCOM 3D")
    #     return open_decode_hycom_3d(path_files)
    # if type == 'CORA':
    #     logger.info("Opening CORA")
    #     return open_decode_cora(path_files)

    # logger.info("Opening non specific file type")
    return None  # open_decode_basic(path_files)

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
    # Open
    cfspecs = xcf.get_cf_specs("cmems_model")
    with xcf.set_cf_specs(cfspecs):
        ds = xr.open_mfdataset(path_files).xcf.decode()
        ds.close()
    ds = ds.swap_dims({"depth": "z", "lon": "x", "lat": "y"})
    if len(ds.lon.dims) == 1:
        lat, lon = xr.broadcast(ds["lat"], ds["lon"])
        ds = ds.drop_vars(["lon", "lat"])
        ds["lon"] = lon
        ds["lat"] = lat
        ds = ds.set_coords(["lon", "lat"])
    var = [var for var in ds.data_vars if len(ds[var].dims) == 4][0]
    ds["depth"] = ds["depth"].broadcast_like(ds[var])
    ds = ds.reset_coords("depth")
    ds = ds.sortby("time")
    return ds

# def open_decode_hycom(path_files):
#     """
#     Open HyCOM netcdf file(s) and store it into a ready-to-use dataset.
    
#     Parameters
#     ----------
#     path_files : str, list of str
#         Path to the netcdf files.
        
#     Returns
#     -------
#     xarray.Dataset
#         HyCOM dataset.
#     """
    
#     # Pre-sort paths once
#     sorted_paths = sorted(path_files)
    
#     # Get CF specs once
#     cfspecs = xcf.get_cf_specs("hycom")
    
#     # Initialize collections
#     variables_data = {}
#     bathymetry = None
#     velocity_u = []
#     velocity_v = []
    
#     # Process each file
#     for path in sorted_paths:
#         logger.info(path)
        
#         with xcf.set_cf_specs(cfspecs):
#             # Open and decode dataset
#             ds = xr.open_dataset(path, engine="h5netcdf", chunks="auto")#.xoa.decode()
#             # ds.close()
#             #ds = ds.compute()
#             ds = optimize_for_low_swap(ds)
#             ds = ds.xoa.decode()

#             # Extract bathymetry only once from non-velocity files
#             if bathymetry is None and "bathy" in ds and not any(var in ['u', 'v'] for var in ds.data_vars):
#                 bathymetry = ds.bathy
            
#             # Clean up coordinates and variables
#             if "dens" in ds.coords:
#                 ds = ds.reset_coords("dens")
#             if "bathy" in ds:
#                 ds = ds.drop_vars("bathy")
#             # ds = ds.compute()
#             # Process variables
#             for varname in ds.data_vars:
#                 if varname == "u":
#                     logger.info("shift u")
#                     shifted_u = ds.map_blocks(
#                         lambda d: shift(d["u"], {"x": "right"}).xoa.reloc(u=False),
#                         template=ds["u"]
#                         )
#                     # shifted_u = shifted_u.compute()
#                     velocity_u.append(shifted_u)
#                 elif varname == "v":
#                     logger.info("shift v")
#                     shifted_v = ds.map_blocks(
#                         lambda d: shift(d["v"], {"y": "top"}).xoa.reloc(v=False),
#                         template=ds["v"]
#                         )
#                     # shifted_v = shifted_v.compute()
#                     velocity_v.append(shifted_v)
#                 else:
#                     # ds[varname] = ds[varname].compute()
#                     variables_data.setdefault(varname, []).append(ds[varname])
#             ds.close()
#             del ds
#             gc.collect()
#     logger.info("concat") 
#     # Concatenate and merge datasets
#     datasets_to_merge = []
    
#     # Process regular variables
#     for varname, data_list in variables_data.items():
#         if data_list:
#             concatenated = xr.concat(data_list, dim='time')
#             concatenated = concatenated.sel(time=~concatenated.get_index("time").duplicated())
#             datasets_to_merge.append(concatenated.to_dataset())
#     del data_list
#     gc.collect()
#     # Merge all regular variables
#     #datasets = [ds.compute() for ds in datasets_to_merge]
#     merged_ds = xr.merge(datasets_to_merge) if datasets_to_merge else xr.Dataset()
#     for ds in datasets_to_merge:
#         del ds
#     gc.collect()        
#     #merged_ds =  optimize_for_low_swap(merged_ds, target_chunk_mb=128)
#     # del datasets_to_merge
#     # Add bathymetry if available
#     logger.info("Add bathymetry")
#     if bathymetry is not None:
#         merged_ds = xr.merge([merged_ds, bathymetry])
#         del bathymetry
#     # Process velocity components
#     logger.info("Add u")
#     if velocity_u:
#         u_concat = xr.concat(velocity_u, dim='time')
#         del velocity_u
#         u_concat = u_concat.sel(time=~u_concat.get_index("time").duplicated())
#         merged_ds["u"] = u_concat.assign_coords(**merged_ds.coords)
#         del u_concat
#         gc.collect()
#     logger.info("Add v")
#     if velocity_v:
#         v_concat = xr.concat(velocity_v, dim='time')
#         del velocity_v
#         v_concat = v_concat.sel(time=~v_concat.get_index("time").duplicated())
#         merged_ds["v"] = v_concat.assign_coords(**merged_ds.coords)
#         del v_concat
#         gc.collect()
#     logger.info("compute depth")
#     # Handle depth coordinates
#     if "dz" in merged_ds:
#         merged_ds.coords["depth"] = dz2depth(merged_ds.dz, centered=True)
#         merged_ds = merged_ds.drop_vars(["z", "dz"])
    
#     # Final deduplication
#     logger.info("remove duplicated time index")
#     if "time" in merged_ds.dims:
#         merged_ds = merged_ds.sel(time=~merged_ds.get_index("time").duplicated())
#     logger.info("rechunk")
#     for var in ["depth", "ssh", "sst", "sss"]:
#         if var in merged_ds:
#             good_var = merged_ds[var]
#             break
#     chunk_dict = {}
#     for dim, chunks in zip(good_var.dims, good_var.chunks):
#         chunk_dict[dim] = chunks[0]
#     merged_ds = merged_ds.chunk(chunk_dict)
#     # merged_ds = merged_ds.unify_chunks()#.persist()
#     # merged_ds = merged_ds.chunk({'time': 1})
#     logger.info("persist")
#     merged_ds = merged_ds.persist()
    
#     logger.info("End open_decode_hycom")
#     return merged_ds


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
        parallel=True,
        # compat="override"
    )

    try:
        cfspecs = xcf.get_cf_specs("hycom")
        with xcf.set_cf_specs(cfspecs):
            ds = ds.xoa.decode()
    except Exception:
        logger.warning("xoa.decode skipped (xcf not available or failed)")

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
        depth = dz2depth(ds["dz"], centered=True)
        ds = ds.assign_coords(depth=depth).drop_vars(["dz", "z"])

    ds = ds.sel(time=~ds.get_index("time").duplicated())
    for var in ["depth", "ssh", "sst", "sss"]:
        if var in ds:
            good_var = ds[var]
            break
    chunk_dict = {}
    for dim, chunks in zip(good_var.dims, good_var.chunks):
        chunk_dict[dim] = chunks[0]
    ds = ds.chunk(chunk_dict)

    gc.collect()
    return ds

# def open_decode_hycom(path_files):
#     """
#     Open HyCOM netcdf file(s) and store it into a ready-to-use dataset.
#     Parameters
#     ----------
#     path_files : str, list of str
#         Path to the netcdf files.
#     steps : float
#         Horizontal and vertical steps
#     Returns
#     -------
#     xarray.Dataset
#         HyCOM dataset.
#     """
    
#     # Open
#     cfspecs = xcf.get_cf_specs("hycom")

#     dss_var = {}
#     bathy = None
#     dsu, dsv = None, None

#     path_files.sort()
#     for path in path_files:
#         logger.info(path)
#         with xcf.set_cf_specs(cfspecs):
#             ds = (
#                 xr.open_dataset(
#                     path,
#                     chunks="auto",
#                 )
#                 .xoa.decode()
#             )
#             ds = optimize_for_low_swap(ds, target_chunk_mb=64)
#             #.isel(x=slice(None, None, 5), y=slice(None, None, 5))

#         test = any(i in ['u', 'v'] for i in ds.data_vars)
#         if (bathy is None) and (test is False) and ("bathy" in ds):
#             bathy = ds.bathy
        
#         if "dens" in ds.coords:
#             ds = ds.reset_coords("dens")

#         if "bathy" in ds:
#             ds = ds.drop_vars("bathy")

#         varname = [var for var in ds.data_vars][0]
#         if varname not in dss_var.keys():
#             dss_var[varname] = []
#         if varname == "u":
#             logger.info("shift u")
#             da_u = shift(
#                 ds["u"].squeeze(drop=True), {"x": "right"}
#             ).xoa.reloc(u=False)
#             dss_var[varname].append(da_u)
#         elif varname == "v":
#             logger.info("shift v")
#             da_v = shift(
#                 ds["v"].squeeze(drop=True), {"y": "top"}
#             ).xoa.reloc(v=False)
#             dss_var[varname].append(da_v)
#         else:
#             dss_var[varname].append(ds)

#         ds.close()

#     dss = []
#     for var in dss_var.keys():
#         ds_concat = xr.concat(dss_var[var], dim='time')
#         ds_concat = ds_concat.sel(time=~ds_concat.get_index("time").duplicated())
#         if var == 'u':
#             dsu = ds_concat
#         elif var == 'v':
#             dsv = ds_concat
#         else:
#             dss.append(ds_concat)
#         ds_concat.close()
#     del dss_var
#     ds = xr.merge(dss)
#     if bathy is not None:
#         ds = xr.merge([ds, bathy])

#     if isinstance(dsu, xr.DataArray):
#         ds["u"] = dsu.assign_coords(**ds.coords)
#         del dsu
#     if isinstance(dsv, xr.DataArray):
#         ds["v"] = dsv.assign_coords(**ds.coords)
#         del dsv
#     if "dz" in ds:
#         ds.coords["depth"] = dz2depth(ds.dz, centered=True)
#         ds = ds.drop_vars(["z", "dz"])

#     ds = ds.sel(time=~ds.get_index("time").duplicated())
#     return ds

# def open_decode_hycom(path_files):
#     """
#     Open HyCOM netcdf file(s) and store it into a ready-to-use dataset.

#     Parameters
#     ----------
#     path_files : str or list of str
#         Path to the netcdf files.

#     Returns
#     -------
#     xarray.Dataset
#         HyCOM dataset.
#     """
#     def process_file(path):
#         with xcf.set_cf_specs(xcf.get_cf_specs("hycom")):
#             # Use Dask for lazy loading
#                 ds = xr.open_dataset(path, chunks={"time": 10, "lat": 100, "lon": 100}).xoa.decode()

#         test = any(var in ['u', 'v'] for var in ds.data_vars)
#         bathy = ds.bathy if ("bathy" in ds) else None

#         if "bathy" in ds:
#             ds = ds.drop_vars("bathy")

#         varname = next(iter(ds.data_vars))
#         if varname == "u":
#             da_u = shift(ds["u"].squeeze(drop=True), {"x": "right"}).xoa.reloc(u=False)
#             return varname, da_u, bathy
#         elif varname == "v":
#             da_v = shift(ds["v"].squeeze(drop=True), {"y": "top"}).xoa.reloc(v=False)
#             return varname, da_v, bathy
#         else:
#             return varname, ds, bathy

#     # def shift(da, axis_shift):
#     #     # Implement or import the shift function as needed
#     #     pass

#     # def dz2depth(dz, centered):
#     #     # Implement or import the dz2depth function as needed
#     #     pass

#     # Use ThreadPoolExecutor to parallelize file processing
#     dss_var = {}
#     bathy = None

#     with ThreadPoolExecutor(max_workers=1) as executor:
#         futures = {executor.submit(process_file, path): path for path in sorted(path_files)}
#         for future in futures:
#             varname, data, bathy = future.result()
#             if varname not in dss_var:
#                 dss_var[varname] = []
#             dss_var[varname].append(data)
#             del data

#     # Concatenate and merge datasets
#     dss = []
#     dsu, dsv = None, None
#     for var in dss_var:
#         ds_concat = xr.concat(dss_var[var], dim='time')
#         if var == 'u':
#             dsu = ds_concat
#         elif var == 'v':
#             dsv = ds_concat
#         else:
#             dss.append(ds_concat)
#         del ds_concat

#     ds = xr.merge(dss)
#     del dss
#     if bathy is not None:
#         ds = xr.merge([ds, bathy])

#     if isinstance(dsu, xr.DataArray):
#         ds["u"] = dsu.assign_coords(**ds.coords)
#         del dsu
#     if isinstance(dsv, xr.DataArray):
#         ds["v"] = dsv.assign_coords(**ds.coords)
#         del dsv
#     if "dz" in ds:
#         ds.coords["depth"] = dz2depth(ds.dz, centered=True)
#         ds = ds.drop_vars(["z", "dz"])

#     ds = ds.sel(time=~ds.get_index("time").duplicated())
#     ds = ds.load()
#     return ds

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

    # Convert lons
    woa18 = convert_lons(woa18)

    # Convert long names
    # for var in list(woa18.keys()):
    #     if var == "sal":
    #         kw_attrs = {
    #             "long_name": "Average salinity",
    #             "units": "psu"
    #         }
    #     if var == "temp":
    #         kw_attrs = {
    #             "long_name": "Average  sea temperature",
    #             "units": "degC"
    #         }
    #     woa18[var].assign_attrs(kw_attrs)
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
    return [woa18]


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
        elif "DEPTH" in ds.dims:
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
        ds = ds.drop_vars("TRAJECTORY")
        return ds
    else:
        for ids in range(len(dss)):
            dss[ids].attrs["name"] = f"{dss[ids].attrs['platform_code']}"
        return dss
    return ds

def open_decode_l_adcp(path_file):
    """
    Open txt file form L-ADCP observation and store it in a ready-to-use dataset.
    Parameters
    ----------
    path_file : str
        Path to the L-ADCP txt file.

    Returns
    -------
    dataset : xarray.dataset
        L-ADCP observation dataset.
    """
    # Read the .txt file
    file = pd.read_csv(path_file, sep="\t", encoding="latin1")

    # List the index labels of the measurements
    idx_stations = np.unique(file["Station"])

    # Separate the measurements
    list_ds = []
    for idx in idx_stations:
        measur = file[file["Station"] == idx]
        head = measur.iloc[0]
        lat = head[" Latitude"]
        lon = head[" Longitude"]
        time = f"{head[' Mon/Day/Yr']} {head[' hh:mm']}"
        time = datetime.datetime.strptime(time, " %m/%d/%Y %H:%M")
        time = np.datetime64(time)

        measur = (
            measur[[" ud", " vd", " z"]]
            .astype(float)
            .rename(columns={" ud": "U", " vd": "V", " z": "depth"})
            .set_index("depth")
        )

        measur_ds = measur.to_xarray()
        measur_ds = measur_ds.assign_coords(lon=lon, lat=lat, time=time)
        list_ds.append(measur_ds.reset_coords())

    # Concat the dataset
    ladcp = xr.concat(list_ds, dim="time")
    ladcp = ladcp.set_coords(["lon", "lat"])

    # Add variables attributes
    ladcp["U"] = ladcp["U"].assign_attrs(
        {"long_name": "W-E current", "units": "m/s", "_FillValue": 9999999.0}
    )
    ladcp["V"] = ladcp["V"].assign_attrs(
        {"long_name": "S-N current", "units": "m/s", "_FillValue": 9999999.0}
    )

    ladcp["depth"] = ladcp["depth"].assign_attrs(
        {
            "long_name": "Instrument depth",
            "units": "m",
            "_FillValue": 9999999.0,
        }
    )

    # Decode
    ladcp = ladcp.xoa.decode()

    # Convert lons
    ladcp = convert_lons(ladcp)

    return ladcp


def open_decode_vmadcp(path_file, steps=None) -> xr.Dataset:
    """
    Open txt file form VMADCP observation and store it in dataset.
    Parameters
    ----------
    path_file : str
        Path to the VMADCP txt file.
    steps : float
        Horizontal and vertical steps
    Returns
    -------
    dataset : xarray.dataset
        VMADCP observation dataset.
    """
    # Read the .txt file
    file = pd.read_csv(path_file, sep="\t", encoding="latin1")

    # List the index labels of the measurements
    idx_stations = np.unique(file["Station"])

    # Separate the measurements
    list_ds = []
    for idx in idx_stations:
        measur = file[file["Station"] == idx]
        head = measur.iloc[0]
        lat = head["Latitude [degrees_north]"]
        lon = head["Longitude [degrees_east]"]
        time = f"{head['mon/day/yr']} {head['hh:mm:ss']}"
        time = datetime.datetime.strptime(time, "%m/%d/%Y %H:%M:%S")
        time = np.datetime64(time)

        measur = (
            measur[["U [cm/s]", "V [cm/s]", "Depth [m]"]]
            .astype(float)
            .rename(
                columns={
                    "U [cm/s]": "U",
                    "V [cm/s]": "V",
                    "Depth [m]": "depth",
                }
            )
            .set_index("depth")
        )
        measur_ds = measur.to_xarray()
        measur_ds = measur_ds.assign_coords(lon=lon, lat=lat, time=time)
        list_ds.append(measur_ds.reset_coords())

    # Concat the dataset
    vmadcp = xr.concat(list_ds, dim="time").set_coords(["lon", "lat"])

    # Add variables attributes
    vmadcp["U"] = (vmadcp["U"] / 100).assign_attrs(
        {"long_name": "W-E current", "units": "m/s", "_FillValue": 9999999.0}
    )
    vmadcp["V"] = (vmadcp["V"] / 100).assign_attrs(
        {"long_name": "S-N current", "units": "m/s", "_FillValue": 9999999.0}
    )

    vmadcp["depth"] = vmadcp["depth"].assign_attrs(
        {
            "long_name": "Instrument depth",
            "units": "m",
            "_FillValue": 9999999.0,
        }
    )

    # Decode
    vmadcp = vmadcp.xoa.decode()

    # Convert lons
    vmadcp = convert_lons(vmadcp)

    if steps and steps[1]:
        horizontal_step, vertical_step = steps
        vmadcp = set_hor_vert_step(vmadcp, horizontal_step, vertical_step)

    return vmadcp


def open_decode_mouillages(path_file):
    """
    Open txt file form mooring observation and store it in dataset.
    Parameters
    ----------
    path_file : str
        Path to the mooring txt file.

    Returns
    -------
    dataset : xarray.dataset
        mooring observation dataset.
    """
    # Read the .txt file
    file = pd.read_csv(path_file, sep="\t", encoding="latin1")

    # Rename the columns
    for col in file.columns.tolist():
        if "BinDep" in col:
            file = file.rename(columns={col: "depth"})
        elif "S-N" in col:
            file = file.rename(columns={col: "V"})
        elif "W-E" in col:
            file = file.rename(columns={col: "U"})
        elif "Ampl" in col:
            file = file.rename(columns={col: "Ampl"})
        elif "Dir" in col:
            file = file.rename(columns={col: "Dir"})

    # Get the line indexes of the start of each new measurement
    index_mesures = file[file["Cruise"].notna()].index

    # Separate the measurements
    list_ds = []
    for i in range(len(index_mesures) - 1):
        # Get coordinates
        line_deb = file.iloc[index_mesures[i]]
        lon = line_deb["Longitude [degrees_east]"]
        lat = line_deb["Latitude [degrees_north]"]
        date = line_deb["yyyy-mm-ddThh:mm:ss.sss"]
        date = np.datetime64(date, "ns")
        bottom_depth = line_deb["Bot. Depth [m]"]

        # Get measurements
        measur = file.iloc[
            index_mesures[i] + 1 : index_mesures[i + 1]
        ].set_index("depth")
        unwanted_prefixes = [
            "Cruise",
            "Station",
            "Type",
            "yyyy",
            "Lon",
            "Lat",
            "Bot",
            "Unnamed",
        ]
        columns_to_drop = measur.columns[
            measur.columns.str.startswith(tuple(unwanted_prefixes))
        ]
        measur_ds = (
            measur.drop(columns=columns_to_drop).astype(float).to_xarray()
        )
        measur_ds = measur_ds.expand_dims(lon=[lon], lat=[lat])
        measur_ds = measur_ds.assign_coords(
            time=date, bottom_depth=bottom_depth
        )
        list_ds.append(measur_ds.reset_coords())

    # Merge datasets
    mouillage = xr.concat(list_ds, dim="time").set_coords(["lon", "lat"])

    # Set variables attributes
    mouillage["U"] = mouillage["U"].assign_attrs(
        {
            "long_name": "Corrected Flow 2D W-E",
            "units": "m/s",
            "_FillValue": 9999999.0,
        }
    )
    mouillage["V"] = mouillage["V"].assign_attrs(
        {
            "long_name": "Corrected Flow 2D S-N",
            "units": "m/s",
            "_FillValue": 9999999.0,
        }
    )
    mouillage["Ampl"] = mouillage["Ampl"].assign_attrs(
        {
            "long_name": "Corrected Flow 2D Amplitude",
            "units": "m/s",
            "_FillValue": 9999999.0,
        }
    )
    mouillage["Dir"] = mouillage["Dir"].assign_attrs(
        {
            "long_name": "Corrected Flow 2D Direction",
            "units": "deg",
            "_FillValue": 9999999.0,
        }
    )
    mouillage["depth"] = mouillage["depth"].assign_attrs(
        {
            "long_name": "Instrument depth",
            "units": "m",
            "_FillValue": 9999999.0,
        }
    )

    # Decode
    mouillage = mouillage.xoa.decode()

    # Convert lons
    mouillage = convert_lons(mouillage)
    if (
        len(np.unique(mouillage.lon)) == 1
        and len(np.unique(mouillage.lat)) == 1
    ):
        lon = np.unique(mouillage.lon.data)
        lat = np.unique(mouillage.lat.data)
        mouillage = mouillage.drop_vars(["lon", "lat"]).assign_coords(
            {"lon": lon, "lat": lat}
        )
    return mouillage


def open_decode_scanfish(path_file, steps):
    """
    Open txt file form scanfish observation and store it in dataset.
    Parameters
    ----------
    path_file : str
        Path to the scanfish txt file.
    steps : float
        Horizontal and vertical steps.
    Returns
    -------
    dataset : xarray.dataset
        scanfish observation dataset.
    """
    # Read the .txt file
    file = pd.read_csv(path_file, sep="\t", encoding="latin1")
    depth = file["DepSM"]
    time = (
        (file["TimeJ"] * 24 * 3600 * np.timedelta64(1, "s"))
        + np.datetime64("1970-01-01")
        + file["TimeY"] * np.timedelta64(1, "s")
    )

    # Create the dataset
    file = file.assign(
        time=time, depth=depth, temp=file["T4990C"], sal=file["Sal00"]
    )
    file = file.set_index("time")
    scanfish = file.to_xarray()

    # Decode
    scanfish = scanfish.xoa.decode()

    # Convert lons
    scanfish = convert_lons(scanfish)

    # Add attrs
    scanfish = scanfish.assign_attrs({"type": "scanfish"})

    # Regrid
    if steps and steps[1]:
        horizontal_step, vertical_step = steps
        scanfish = set_hor_vert_step_radiales(
            scanfish, horizontal_step, vertical_step
        )
    return scanfish


def open_decode_seasoar(path_file, steps):
    """
    Open txt file form seasoar observation and store it in dataset.
    Parameters
    ----------
    path_file : str
        Path to the seasoar txt file.
    steps : float
        Horizontal and vertical steps.
    Returns
    -------
    dataset : xarray.dataset
        seasoar observation dataset.
    """
    # Read the .txt file
    file = pd.read_csv(path_file, sep="\t", encoding="latin1")
    depth = file["DepSM"]
    time = (
        (file["TimeJ"] * 24 * 3600 * np.timedelta64(1, "s"))
        + np.datetime64("2000-01-01")
        + file["TimeQ"] * np.timedelta64(1, "s")
    )

    # Create the dataset
    file = file.assign(
        time=time,
        depth=depth,
        temp=file["T190C"],
        sal=file["Sal11"],
        ptemp=file["Potemp190C"],
    )
    file = file.set_index("time")
    seasoar = file.to_xarray()

    # Decode
    seasoar = seasoar.xoa.decode()

    # Convert lons
    seasoar = convert_lons(seasoar)

    # Add attrs
    seasoar = seasoar.assign_attrs({"type": "seasoar"})

    # Regrid
    if steps and steps[1]:
        horizontal_step, vertical_step = steps
        seasoar = set_hor_vert_step_radiales(
            seasoar, horizontal_step, vertical_step
        )
    return seasoar


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
    cfspecs = xcf.get_cf_specs(fmt)
    ds = xr.open_mfdataset(path_file)
    #ds = optimize_for_low_swap(ds)
    for sig in ("s_rho", "s_w"):
        if sig in ds:
            if "formula_terms" not in ds[sig].attrs:
                logger.warning(f"No formula_terms attributes in {sig}")
                ds[sig].attrs["formula_terms"] = "s: sc_w C: Cs_w eta: zeta depth: h depth_c: hc"
            if "standard_name" not in ds[sig].attrs:
                logger.warning(f"No standard_name attributes in {sig}")
                if sig == "s_rho":
                    ds[sig].attrs["standard_name"] = "ocean_s_coordinate_g2"
                elif sig == "s_w":
                    ds[sig].attrs["standard_name"] = "ocean_s_coordinate_g2_at_w_location"

    if 'scrum_time' in ds:   
        ds = ds.drop('scrum_time')  
        
    with xcf.set_cf_specs(cfspecs):
        ds = ds.decode_sigma()
        ds = ds.xoa.decode()
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
            ds = ds.drop(v)
    for coord in ds.coords:
        if "nav_" in coord:
            coord_name = coord.replace("nav_", "")
            if coord_name in ds:
                ds = ds.drop(coord)
            ds = ds.rename({coord: coord_name})
    if "time_counter" in ds.dims:
        ds = ds.swap_dims({"time_counter": "time"})
    ds = ds.swap_dims({"sig_rho": "z"})
    ds = ds.isel(x_rho=slice(1, -1), y_rho=slice(1,-1))
    for varname in ds.data_vars:
        if varname == "u":
            dau = shift(ds["u"], {"x_u": "right"}).isel(x_u=slice(None, -1)).xoa.reloc(u="rho")
            ds["u"] = dau.assign_coords(**ds.ptemp.coords)
        if varname == "v":
            dav = shift(ds["v"], {"y_v": "top"}).isel(y_v=slice(None, -1)).xoa.reloc(v="rho")
            ds["v"] = dav.assign_coords(**ds.ptemp.coords)
    ds = ds.rename({"lon_rho": "lon", "lat_rho": "lat"})
    for dim in ("x_u", "y_v"):
        if dim in ds.dims:
            ds = ds.drop_dims(dim)
    ds = ds.swap_dims({"x_rho": "x", "y_rho": "y"})
    if "angle" in ds:
        angle = ds["angle"]
        da_u = ds["u"] * np.cos(angle) - ds["v"] * np.sin(angle)
        da_v = ds["v"] * np.cos(angle) + ds["u"] * np.sin(angle)
        ds = ds.drop_vars(["u", "v", "angle"])
        ds["u"] = da_u
        ds["v"] = da_v
    if "mask" in ds:
        ds = ds.where(ds["mask"] > 0)

    # ds = ds.where(ds.ptemp > 0)
    # ds = ds.where(ds.sal > 0)
    ds = ds.isel(z=slice(None, None, -1))
    ds = ds.assign_coords(depth=-ds.depth)

    return ds

    # # Remove variables that are never used in the features. May need to be completed.
    # list_to_keep = ["temp", "salt", "u", "v", "h", "angle", "mask_rho"]
    # for var in list(croco.keys()):
    #     if var not in list_to_keep:
    #         croco = croco.drop_vars(var)

    # # Convert currents if necessary
    # if "u" in croco:
    #     # U processing
    #     da_u = shift(croco.u, {"xi_u": "left"}).xoa.reloc(u=False)
    #     da_u = da_u.sel(xi=croco.xi_rho, method="nearest")
    #     croco["u"] = da_u

    #     # V processing
    #     da_v = shift(croco.v, {"eta_v": "left"}).xoa.reloc(v=False)
    #     da_v = da_v.sel(eta=croco.eta_rho, method="nearest")
    #     croco["v"] = da_v

    #     # Rotate currents
    #     if "angle" in croco:
    #         angle = croco["angle"]
    #         da_u = croco["u"] * np.cos(angle) - croco["v"] * np.sin(angle)
    #         da_v = croco["v"] * np.cos(angle) + croco["u"] * np.sin(angle)
    #         croco = croco.drop_vars(["u", "v", "angle"])
    #         croco["u"] = da_u
    #         croco["v"] = da_v

    #         # Remove duplicate coords
    # if "lon" in croco and "lon_rho" in croco:
    #     croco = croco.drop_vars(["lon", "lat"])

    # # Clean coordinates
    # croco = croco.rename(
    #     {
    #         "xi_rho": "x",
    #         "eta_rho": "y",
    #         "s_rho": "z",
    #         "lon_rho": "lon",
    #         "lat_rho": "lat",
    #     }
    # )
    # if "mask_rho" in list(croco.keys()):
    #     croco = croco.rename({"mask_rho": "mask"})

    # for var in [
    #     "lat_rho",
    #     "lon_rho",
    #     "xi",
    #     "eta",
    #     "lat_u",
    #     "lat_v",
    #     "lon_u",
    #     "lon_v",
    #     "xi_u",
    #     "eta_v",
    #     "depth_w",
    #     "sig",
    #     "s_w",
    # ]:
    #     if var in croco:
    #         croco = croco.drop_vars(var)

    # # Regrid if necessary
    # test_regrid = to_rect(croco)
    # if "lon" in test_regrid.dims and "lat" in test_regrid.dims:
    #     croco = test_regrid
    # elif "x" in test_regrid.dims and "y" in test_regrid.dims:
    #     croco = test_regrid

    # # Convert lons
    # croco = convert_lons(croco)

    # # Convert depths
    # croco["depth"] = croco.depth.where(abs(croco.depth) < 1e30)
    # croco = convert_depths(croco)

    # # Decode
    # croco = croco.xoa.decode()
    # if "lon_u" in croco:
    #     croco = croco.rename({"lon_u": "lon"})
    # if "lat_u" in croco:
    #     croco = croco.rename({"lat_u": "lat"})

    # # Assign croco attrs
    # croco = croco.assign_attrs({"type": "CROCO"})

    # # Rename ptemp
    # if "temp" in croco:
    #     croco = croco.rename({"temp": "ptemp"})
    # # Remove values outside mask

    # if "mask" in list(croco.keys()):
    #     croco = croco.where(croco["mask"] > 0, drop=True)

    # return croco


# def open_decode_hycom_currents(path_files):
#     """
#     Open 2D or 3D current from HYCOM model.
#     Parameters
#     ----------
#     path_files : list of str
#         List of the files to decode. The first path must refer to the h file, the following ones
#         are the variables.

#     Returns
#     -------
#     hycom : xarray.Dataset
#          Model dataset decoded.
#     """
#     logger.info("Decoding HYCOM currents")
#     if len(path_files) == 2:  # Test if 2D
#         logger.info("HYCOM 2D")
#         path_u, path_v = path_files[0], path_files[1]
#         hycom = xr.Dataset()
#     elif len(path_files) == 3:  # Test if 3D
#         logger.info("HYCOM 3D")
#         path_h, path_u, path_v = path_files[0], path_files[1], path_files[2]
#         hycom = (
#             xr.open_dataset(path_h)
#             .rename({"h": "dz"})
#             .xoa.decode()
#             .squeeze(drop=True)
#         )
#         if "level" not in hycom.variables:
#             raise ValueError(
#                 "Ooops ! Pour lire une sortie de courant du modèle HYCOM,"
#                 " vous devez renseigner les fichiers dans l'ordre suivant : h, u, v"
#             )
#         hycom.coords["depth"] = dz2depth(hycom.dz, centered=True)

#     ds_u = xr.open_dataset(path_u).xoa.decode().squeeze(drop=True)
#     ds_v = xr.open_dataset(path_v).xoa.decode().squeeze(drop=True)
#     if "u" not in ds_u.variables or "v" not in ds_v.variables:
#         raise ValueError(
#             "Ooops ! Pour lire une sortie de courant du modèle HYCOM,"
#             " vous devez renseigner les fichiers dans l'ordre suivant : h, u, v."
#         )
#     da_u = ds_u.u
#     da_v = ds_v.v

#     ut_hycom = shift(da_u, {"x": "right"}).xoa.reloc(u=False)
#     vt_hycom = shift(da_v, {"y": "top"}).xoa.reloc(v=False)
#     hycom["u"] = ut_hycom.assign_coords(**hycom.coords)
#     hycom["v"] = vt_hycom.assign_coords(**hycom.coords)

#     # Rename depth
#     if "level" in hycom:
#         hycom = hycom.rename({"level": "z"})

#     # Regrid if necessary
#     hycom = to_rect(hycom)

#     # Convert lons
#     hycom = convert_lons(hycom)

#     return hycom


# def open_decode_hycom_3d(path_files):
#     """
#     Open some 3D variables from HYCOM model.
#     Parameters
#     ----------
#     path_files : list of str
#         List of the files to decode. The first path must refer to the h file, the following ones
#         are the variables.

#     Returns
#     -------
#     hycom : xarray.Dataset
#          Model dataset decoded.

#     """
#     logger.info("Decoding HYCOM 3D")
#     # Open the file with depth values
#     path_h = path_files[0]
#     hycom = xr.open_dataset(path_h)

#     if "h" not in hycom.variables and "sigma" not in hycom.variables:
#         raise ValueError(
#             "Ooops ! To read a 3D output from the HYCOM model,"
#             " you need to provide the files in the following order: "
#             "h/sigma, variables."
#         )
#     if "h" in hycom:
#         hycom = hycom.rename({"h": "dz"}).xoa.decode().squeeze(drop=True)
#         hycom.coords["depth"] = dz2depth(hycom.dz, centered=True)
#     elif "sigma" in hycom:
#         hycom = hycom.rename({"sigma": "dens"}).xoa.decode().squeeze(drop=True)

#     # Open the variable(s) and add them to the dataset
#     for path in path_files[1:]:
#         ds_var = xr.open_dataset(path).xoa.decode().squeeze(drop=True)
#         # Get the name of the variable
#         list_coords = ["lon", "lat", "bathymetry", "time", "lev"]
#         for var in list(ds_var.keys()):
#             if var not in list_coords:
#                 var_name = var
#         hycom[var_name] = ds_var[var_name]

#     # Rename
#     hycom = hycom.rename({"level": "z"})
#     if "temp" in hycom:
#         hycom = hycom.rename({"temp": "ptemp"})

#     # Regrid if necessary
#     hycom = to_rect(hycom)

#     # Convert lons
#     hycom = convert_lons(hycom)

#     # Add dens coordinate
#     if "dens" in hycom:
#         hycom = hycom.assign_coords(dens=hycom.dens)

#     return hycom


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
    cora = depth_from_press(cora)
    cora = convert_depths(cora)

    # Convert lons
    cora = convert_lons(cora)

    return cora


def open_decode_basic(path_files):
    """
    Open netcdf file(s) and store it into a ready-to-use dataset.
    Parameters
    ----------
    path_files : str, list of str
        Path to the netcdf files.
    Returns
    -------
    xarray.Dataset
        dataset.
    """
    # Open
    if len(path_files) > 1:
        datasets = [xr.open_dataset(path) for path in path_files]
        dataset = xr.concat(datasets, dim="time")
    else:
        dataset = xr.open_dataset(path_files[0])

    list_to_remove = ["sst_dtime"]
    for var in list(dataset.keys()):
        if var in list_to_remove:
            dataset = dataset.drop_vars(var)

    # Decode
    dataset = dataset.xoa.decode()
    if "lon_longitude" in dataset:
        dataset = dataset.drop_vars(["lon_longitude", "lat_latitude"])

    if (
        "temp" in dataset
        and "potential" in dataset.temp.attrs["standard_name"]
    ):
        dataset = dataset.rename({"temp": "ptemp"})

    # Regrid if necessary
    dataset = to_rect(dataset)

    # Convert depths
    dataset = convert_depths(dataset)

    # Convert lons
    dataset = convert_lons(dataset)

    # Remove duplicate values
    if "lon" in dataset.dims:
        dataset = dataset.drop_duplicates(["lon"])
    if "lat" in dataset.dims:
        dataset = dataset.drop_duplicates(["lat"])
    return dataset


def open_forecaster(path_files, model_type=None) -> xr.Dataset:
    """

    Parameters
    ----------
    path_files
    model_type

    Returns
    -------

    """
    if model_type == "hycom":
        logger.info("Open and decode hycom")
        return open_decode_hycom(path_files)

    if model_type == "woa18":
        logger.info("woa18")
        data_set_temp = xr.open_mfdataset(path_files, decode_times=False)
        variables_to_drop = [
            "depth_bnds",
            "s_oa",
            "s_ma",
            "s_dd",
            "s_sd",
            "s_gp",
            "s_mn",
            "s_se",
            "t_oa",
            "t_ma",
            "t_dd",
            "t_sd",
            "t_gp",
            "t_mn",
            "t_se",
        ]
        for var in variables_to_drop:
            if var in data_set_temp:
                data_set_temp = data_set_temp.drop_vars(var)
        return data_set_temp

    if model_type == "rivers":
        logger.info("rivers")
        data_set_list = []
        for path_list in path_files:
            data_set_list.append(
                xr.open_mfdataset(
                    path_files[path_list],
                    drop_variables=["LATITUDE", "LONGITUDE", "POSITION_QC"],
                )
            )
        return data_set_list

    if model_type == "atmfrc/cumul":
        logger.info("atmfrc - cumul")
        cumul_gribs = path_files

        def open_dataset(grib):
            return xr.open_dataset(
                grib, engine="cfgrib", backend_kwargs={"indexpath": ""}
            )

        # Use parallel processing to load datasets
        with concurrent.futures.ThreadPoolExecutor() as executor:
            dss_cumul = list(executor.map(open_dataset, cumul_gribs))

        # Use Dask to parallelize and concatenate the datasets
        dask_dss_cumul = [
            dask.delayed(
                ds.drop_vars(["time", "surface"]).rename(
                    {
                        "longitude": "lon",
                        "latitude": "lat",
                        "valid_time": "time",
                    }
                )
            )
            for ds in dss_cumul
        ]

        # Compute the concatenated result using Dask
        ds_cumul = xr.concat(dask.compute(*dask_dss_cumul), dim="time")

        # Sort the result
        ds_cumul = ds_cumul.sortby("time")
        return ds_cumul.xoa.decode()

    if model_type == "atmfrc/insta":
        logger.info("atmfrc - insta")
        insta_gribs = path_files
        path = os.path.join(ROOTDIR, "config", "meteofrance.cfg")
        xcf.register_cf_specs(path)
        xoa.register_accessors()
        def open_dataset_for_level(grib, level):
            return xr.open_dataset(
                grib,
                engine="cfgrib",
                backend_kwargs={
                    "indexpath": "",
                    "filter_by_keys": {"edition": 2, "level": level},
                },
                drop_variables=["heightAboveGround", "meanSea", "surface"],
            )

        # Use parallel processing to load datasets
        dss_insta = []
        for grib in insta_gribs:
            dss = [
                dask.delayed(open_dataset_for_level)(grib, level)
                for level in [0, 2, 10]
            ]
            dss_insta.append(dask.compute(*dss))

        # Merge datasets for different levels
        merged_dss_insta = [
            xr.merge(ds_list, combine_attrs="override")
            for ds_list in dss_insta
        ]

        # Combine merged datasets along 'valid_time' dimension
        ds_insta = xr.concat(merged_dss_insta, dim="valid_time")
        ds_insta = ds_insta.drop_vars(["step", "time"])
        ds_insta = ds_insta.rename(
            {"longitude": "lon", "latitude": "lat", "valid_time": "time"}
        )
        ds_insta = ds_insta.swap_dims({"lon": "x", "lat": "y"})
        ds_insta = ds_insta.sortby("time").xoa.decode()
        logger.info(ds_insta)
        return ds_insta

    logger.info("Basic type")
    return open_decode_basic(path_files)


####################### Tools #######################


def decode_profiler(profiler):
    """
    Decode profiler datasets
    Returns
    -------
    xarray.dataset
        Decoded dataset
    """
    colonnes = profiler.DEPH.values

    if len(colonnes.shape) == 2:
        depth_values = np.empty(np.size(colonnes, 1))
        for i in range(np.size(colonnes, 1)):
            colonne_test = colonnes[:, i]
            colonne_test = colonne_test[~np.isnan(colonne_test)]
            depth_column = set(colonne_test)
            if (
                len(depth_column) == 1
            ):  # Tests if the depth values are all the same throughout time
                depth_values[i] = list(depth_column)[0]
            else:  # if depth is truely depth(time,z)
                return decode_depths_vmadcp(profiler)
    elif len(colonnes.shape) == 1:
        depth_values = colonnes
    else:
        logger.error("please handle this case")
    profiler = profiler.assign_coords({"depth": depth_values})
    profiler = convert_trajectory(profiler)
    return profiler


def decode_depths_vmadcp(profiler):
    """
    Decode profiler datasets
    Returns
    -------
    xarray.dataset
        Decoded dataset
    """
    profiler = profiler.drop_duplicates("time")
    profiler = profiler.rename({"depth": "z"})
    profiler = profiler.rename({"DEPH": "depth"})
    profiler = profiler.assign_coords(depth=profiler.depth)
    return profiler


def convert_trajectory(profiler):
    """
    Convert trajectories (lon/lat depend on time).
    Returns
    -------
    xarray.dataset
        Decoded dataset.
    """
    da_lon = xr.DataArray(
        profiler.lon.values, coords=[profiler.time.values], dims="time"
    )
    da_lat = xr.DataArray(
        profiler.lat.values, coords=[profiler.time.values], dims="time"
    )
    profiler = profiler.drop_vars(["lon", "lat"])
    profiler = profiler.assign_coords({"lon": da_lon})
    profiler = profiler.assign_coords({"lat": da_lat})
    return profiler


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


def convert_depths(dataset):
    """
    Convert depths to have positive values only.
    Returns
    -------
    xarray.dataset
        Dataset with positive depths.
    """
    if "depth" in dataset:
        if np.nanmean(dataset.depth.data) < 0:
            dataset["depth"] = -dataset.depth
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


def set_hor_vert_step_radiales(obs, horizontal_step, vertical_step):
    """
    Regrid the observation following the required vertical and horizontal grids for radiales.
    Parameters
    ----------
    obs : xarray.dataset
    horizontal_step : float
    vertical_step : float

    Returns
    -------
    Regridded observation.
    """
    # Seasor/scanfish binning (method from SHOM Jupyter Notebook)
    lons = obs.lon
    lats = obs.lat
    depth = obs.depth
    time = obs.time
    ptemp_in_obs = "ptemp" in obs.attrs

    # Define depth and time bins
    dist_deb_fin = (
        xgeo.haversine(
            lons.values[0], lats.values[0], lons.values[-1], lats.values[-1]
        )
        / 1000
    )
    depth_top_bottom = depth.max() - depth.min()

    n_time_bin = int(np.floor(dist_deb_fin / horizontal_step))
    n_depth_bin = int(np.floor(depth_top_bottom / vertical_step))

    i_time_bins = [
        int(np.floor(len(obs.time) / n_time_bin)) * i
        for i in range(n_time_bin)
    ]
    i_depth_bins = np.linspace(
        0, np.ceil(depth.max() / n_depth_bin) * n_depth_bin, n_depth_bin + 1
    )

    depth_bins = i_depth_bins[:-1] + i_depth_bins[1] / 2
    mean_times, mean_lons, mean_lats = [], [], []
    temp = np.full((n_time_bin - 1, n_depth_bin), np.nan)
    if ptemp_in_obs:
        ptemp = np.full((n_time_bin - 1, n_depth_bin), np.nan)
    sal = np.full((n_time_bin - 1, n_depth_bin), np.nan)

    # Binning
    for it in range(n_time_bin - 1):
        i_0, i_1 = i_time_bins[it : it + 2]
        temp[it] = np.histogram(
            depth[i_0:i_1], i_depth_bins, weights=obs["temp"][i_0:i_1]
        )[0]
        if ptemp_in_obs:
            ptemp[it] = np.histogram(
                depth[i_0:i_1], i_depth_bins, weights=obs["ptemp"][i_0:i_1]
            )[0]
        sal[it] = np.histogram(
            depth[i_0:i_1], i_depth_bins, weights=obs["sal"][i_0:i_1]
        )[0]
        denom = np.histogram(depth[i_0:i_1], i_depth_bins)[0]
        temp[it] = np.where(denom == 0, np.nan, temp[it] / denom)
        if ptemp_in_obs:
            ptemp[it] = np.where(denom == 0, np.nan, ptemp[it] / denom)
        sal[it] = np.where(denom == 0, np.nan, sal[it] / denom)
        mean_times.append(time[i_0:i_1].mean().values)
        mean_lons.append(lons[i_0:i_1].mean())
        mean_lats.append(lats[i_0:i_1].mean())

    # Create xarray dataset
    da_temp = xr.DataArray(data=temp, dims=["time", "depth"])
    if ptemp_in_obs:
        da_ptemp = xr.DataArray(data=ptemp, dims=["time", "depth"])
    da_sal = xr.DataArray(data=sal, dims=["time", "depth"])
    obs_grid = xr.Dataset()
    if ptemp_in_obs:
        obs_grid["ptemp"] = da_ptemp
    obs_grid["temp"], obs_grid["sal"] = da_temp, da_sal
    obs_grid = obs_grid.assign_coords(
        {
            "lon": ("time", mean_lons),
            "lat": ("time", mean_lats),
            "depth": ("depth", depth_bins),
            "time": ("time", mean_times),
        }
    )

    return obs_grid


def set_hor_vert_step(
    obs, horizontal_step, vertical_step, method="linear", method_z="linear"
):
    """
    Regrid the observation following the required vertical and horizontal grids.
    Parameters
    ----------
    obs : xarray.dataset
    horizontal_step : float
    vertical_step : float
    method : str
    method_z : str
    Returns
    -------
    Regridded observation.
    """
    # Horizontal gridding
    # horizontal_step = obs.meta.km_to_deg(horizontal_step)

    obs_deb, obs_end = obs.isel(time=0), obs.isel(time=-1)
    geod = Geod(ellps="WGS84")
    total_distance_obs = geod.line_length(obs.lon.data, obs.lat.data) / 1000
    total_duration_obs = obs_end.time - obs_deb.time
    time_step_grid = horizontal_step * total_duration_obs / total_distance_obs
    time_step_grid = time_step_grid.data.astype("timedelta64[s]")
    time_step_grid = str(time_step_grid).split()[0] + "S"
    time_min, time_max = obs_deb.time.values, obs_end.time.values
    time_min, time_max = np.datetime64(time_min), np.datetime64(time_max)
    # Create the new times array to select to retrieve the horizontal resolution
    tgt_time = pd.date_range(time_min, time_max, freq=time_step_grid)

    # Interpolate the observation on the targeted times
    obs_grid = obs.interp(time=tgt_time, method=method)

    # Vertical gridding
    # Define the target vertical grid
    depths = np.arange(
        np.nanmin(obs.depth.values), np.nanmax(obs.depth.values), vertical_step
    )
    depths = [depth for depth in depths if depth > 0]
    if "z" in obs.depth.dims:  # Case CMEMS data : depth(z,time)
        obs_grid = obs_grid.meta.vertical_selection_list(depths)
    else:
        obs_grid = obs_grid.interp(depth=depths, method=method_z)
    # Warning if steps too large
    if len(obs_grid.depth) == 1:
        logger.warning(
            "Caution! The vertical_step requested is too large, the targetted grid has only one depth value. The code may fail."
        )

    if len(obs_grid.time) == 1:
        logger.warning(
            "Caution! The horizontal_step requested is too large, the targetted grid has only one time value. The code may fail."
        )
    return obs_grid


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


def main():
    import glob

    path_files = glob.glob(
        os.path.join(ROOTDIR, "_samples", "CO_*_PR_PF.nc")
        # os.path.join(ROOTDIR, "_samples", "GL_PR_PF_*.nc")
        # os.path.join(ROOTDIR, "_samples", "GL_TS_MO_*.nc")
        # os.path.join(ROOTDIR, "_samples", "GL_TS_DB_*.nc")
        # os.path.join(ROOTDIR, "_samples", "cmems_glo12.nc")
        # os.path.join(ROOTDIR, "_samples", "hycom_*.nc")
    )
    ds = open_decode(path_files, "cora_insitu", platform="argo")
