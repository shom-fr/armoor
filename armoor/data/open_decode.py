"""
Open files and decode data.
"""

import concurrent.futures
import warnings
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

import time
import dask
import gsw
import numpy as np
import pandas as pd
import xarray as xr
import xoa
import xoa.meta as xmeta
from xoa.meta.general import MetaSpecs
import xoa.geo as xgeo
from pyproj import Geod
from xoa.grid import dz2depth, shift, to_rect

from armoor import ROOTDIR, ArmoorError
from armoor.base.interp import regrid
from armoor.base.misc import optimize_for_low_swap

logger = logging.getLogger(__name__)

# argopy is an unused transitive dependency (pulled in by the "shoot" eddy
# decoder) that registers an xarray backend; xarray imports it eagerly to
# build its plugin registry on the first open_dataset/open_mfdataset call,
# which logs noise even though the backend then fails to load.
logging.getLogger("argopy").setLevel(logging.WARNING)

xoa.register_accessors(meta=True, decode_sigma=True)
xr.set_options(keep_attrs=True)


def get_paths(path_files: str, sort_results: bool = True) -> List[str]:
    """Generate absolute paths from a pattern string with wildcard and list expansion.
    
    Supports patterns like :
    - '/path/to/files/\*.txt' (standard glob)
    - '/path/to/files/\*[option1,option2].txt' (list expansion)
    
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
    cfg_files = glob.glob(
        os.path.join(ROOTDIR, "data", "cf_*.cfg")
    )
    for cfg_file in cfg_files:
        logger.info(f"register {cfg_file}")
        mycfspecs = MetaSpecs(cfg_file, default=True, user=False)
        xmeta.register_meta_specs(mycfspecs)
    
def _normalize_geo_coords(ds):
    """Ensure lon/lat coordinates carry standard_name so xoa can locate them."""
    if isinstance(ds, list):
        return [_normalize_geo_coords(d) for d in ds]
    for coord, std_name, axis in [
        ("lon", "longitude", "X"),
        ("lat", "latitude", "Y"),
    ]:
        if coord in ds.coords:
            ds.coords[coord].attrs.setdefault("standard_name", std_name)
            ds.coords[coord].attrs.setdefault("axis", axis)
    return ds


_DECODER_REGISTRY = {}  # fmt string -> Decoder instance


class Decoder:
    """One armoor-data input format.

    Subclasses register themselves under every fmt string listed in
    ``fmts`` (several fmt values can share one decoder, e.g. hycom/hycom3d).
    """

    name = None
    fmts = ()

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        if cls.name is not None:
            instance = cls()
            for fmt in cls.fmts:
                _DECODER_REGISTRY[fmt] = instance

    def decode(self, path_files, fmt, platform=None):
        """Decode `path_files` into a dataset. Must be overridden.

        Parameters
        ----------
        path_files : list of str
            Absolute paths to the input files (already resolved via
            `get_paths`).
        fmt : str
            The exact fmt string that was requested (some decoders use it
            internally, e.g. SstSatelliteDecoder).
        platform : str, optional
            Type of in-situ platform (argo/glider/mooring/drifter), used
            only by the cmems_insitu/cora_insitu decoders.

        Returns
        -------
        xarray.Dataset
            Decoded dataset.

        Raises
        ------
        NotImplementedError
            Always, in the base class.
        """
        raise NotImplementedError


class CmemsInsituDecoder(Decoder):
    """CMEMS in-situ observations (argo/glider/mooring/drifter)."""

    name = "cmems_insitu"
    fmts = ("cmems_insitu",)

    def decode(self, path_files, fmt, platform=None):
        """Decode CMEMS in-situ files for a given platform.

        Parameters
        ----------
        path_files : list of str
            Absolute paths to the input files.
        fmt : str
            Unused (kept for a uniform `Decoder.decode` signature).
        platform : str, optional
            Platform type: ``"argo"``, ``"glider"``, ``"mooring"`` or
            ``"drifter"``.

        Returns
        -------
        xarray.Dataset
            See `open_decode_cmems_insitu`.
        """
        logger.info("Opening/decoding insitu cmems files")
        return open_decode_cmems_insitu(path_files, platform=platform)


class CoraInsituDecoder(Decoder):
    """CORA in-situ observations."""

    name = "cora_insitu"
    fmts = ("cora_insitu",)

    def decode(self, path_files, fmt, platform=None):
        """Decode CORA in-situ files for a given platform.

        Parameters
        ----------
        path_files : list of str
            Absolute paths to the input files.
        fmt : str
            Unused (kept for a uniform `Decoder.decode` signature).
        platform : str, optional
            Platform type.

        Returns
        -------
        xarray.Dataset
            See `open_decode_cora_insitu`.
        """
        logger.info("Opening/decoding insitu cmems files")
        return open_decode_cora_insitu(path_files, platform=platform)


class OdarDecoder(Decoder):
    """ODAR-processed towed/glider CTD sections (seasoar, scanfish,
    rapidcast, MVP -- distinguished by each file's own
    ``ODAR_DATASET_TYPE`` attr, not by `platform`)."""

    name = "odar"
    fmts = ("odar",)

    def decode(self, path_files, fmt, platform=None):
        """Decode ODAR section files.

        Parameters
        ----------
        path_files : list of str
            Absolute paths to the input files.
        fmt : str
            Unused (kept for a uniform `Decoder.decode` signature).
        platform : str, optional
            Unused: the instrument type is read from each file's own
            ``ODAR_DATASET_TYPE`` attr, not asserted externally.

        Returns
        -------
        list of xarray.Dataset
            See `open_decode_odar`.
        """
        logger.info("Opening/decoding ODAR files")
        return open_decode_odar(path_files)


class CmemsModelDecoder(Decoder):
    """CMEMS gridded model output."""

    name = "cmems_model"
    fmts = ("cmems_model",)

    def decode(self, path_files, fmt, platform=None):
        """Decode CMEMS model files.

        Parameters
        ----------
        path_files : list of str
            Absolute paths to the input files.
        fmt : str
            Unused (kept for a uniform `Decoder.decode` signature).
        platform : str, optional
            Unused.

        Returns
        -------
        xarray.Dataset
            See `open_decode_cmems_model`.
        """
        logger.info("Opening/decoding model cmems files")
        return open_decode_cmems_model(path_files)


class ArmoorDecoder(Decoder):
    """Already-armoor-formatted netcdf files (pass-through decode)."""

    name = "armoor"
    fmts = ("armoor",)

    def decode(self, path_files, fmt, platform=None):
        """Open already-armoor-formatted files with no format conversion.

        Parameters
        ----------
        path_files : list of str
            Absolute paths to the input files.
        fmt : str
            Unused (kept for a uniform `Decoder.decode` signature).
        platform : str, optional
            Unused.

        Returns
        -------
        xarray.Dataset
            The multi-file dataset, with ``depth`` reset to a data
            variable if it was a coordinate.
        """
        logger.info("Opening armoor files")
        ds = xr.open_mfdataset(path_files, engine="netcdf4", chunks={})
        if "depth" in ds:
            ds = ds.reset_coords("depth")
        return ds


class SstSatelliteDecoder(Decoder):
    """Satellite SST products (cmems_sst_l4, cmems_sst_l3, cersat_sst_l3)."""

    name = "sst_satellite"
    fmts = ("cmems_sst_l4", "cmems_sst_l3", "cersat_sst_l3")

    def decode(self, path_files, fmt, platform=None):
        """Decode satellite SST files.

        Parameters
        ----------
        path_files : list of str
            Absolute paths to the input files.
        fmt : str
            The exact fmt requested (``"cmems_sst_l4"``, ``"cmems_sst_l3"``
            or ``"cersat_sst_l3"``); used to look up the matching CF meta
            specs.
        platform : str, optional
            Unused.

        Returns
        -------
        xarray.Dataset
            See `open_decode_sst_satellite`.
        """
        logger.info("Opening/decoding sst satellite files")
        return open_decode_sst_satellite(path_files, fmt)


class HycomDecoder(Decoder):
    """HYCOM ocean-model output (hycom, hycom3d)."""

    name = "hycom"
    fmts = ("hycom", "hycom3d")

    def decode(self, path_files, fmt, platform=None):
        """Decode HYCOM files.

        Parameters
        ----------
        path_files : list of str
            Absolute paths to the input files.
        fmt : str
            Unused (``"hycom"`` and ``"hycom3d"`` share this decoder and
            need no internal branching).
        platform : str, optional
            Unused.

        Returns
        -------
        xarray.Dataset
            See `open_decode_hycom`.
        """
        logger.info("Opening/decoding hycom files")
        return open_decode_hycom(path_files)


class CrocoDecoder(Decoder):
    """CROCO ocean-model output (croco, croco_xios)."""

    name = "croco"
    fmts = ("croco", "croco_xios")

    def decode(self, path_files, fmt, platform=None):
        """Decode CROCO files.

        Parameters
        ----------
        path_files : list of str
            Absolute paths to the input files.
        fmt : str
            The exact fmt requested (``"croco"`` or ``"croco_xios"``);
            forwarded for routing but not consumed internally.
        platform : str, optional
            Unused.

        Returns
        -------
        xarray.Dataset
            See `open_decode_croco`.
        """
        logger.info("Opening/decoding croco files")
        return open_decode_croco(path_files, fmt)


class SloopDecoder(Decoder):
    """Sloop output files."""

    name = "sloop"
    fmts = ("sloop",)

    def decode(self, path_files, fmt, platform=None):
        """Decode Sloop files.

        Parameters
        ----------
        path_files : list of str
            Absolute paths to the input files.
        fmt : str
            Unused (kept for a uniform `Decoder.decode` signature).
        platform : str, optional
            Unused.

        Returns
        -------
        xarray.Dataset
            See `open_decode_sloop`.
        """
        logger.info("Opening/decoding sloop files")
        return open_decode_sloop(path_files)


class ArpegeInstaDecoder(Decoder):
    """Instantaneous Arpege GRIB2 atmospheric forcing files."""

    name = "arpege_insta"
    fmts = ("arpege_insta",)

    def decode(self, path_files, fmt, platform=None):
        """Decode instantaneous Arpege files.

        Parameters
        ----------
        path_files : list of str
            Absolute paths to the input files.
        fmt : str
            Unused (kept for a uniform `Decoder.decode` signature).
        platform : str, optional
            Unused.

        Returns
        -------
        xarray.Dataset
            See `open_decode_arpege_insta`.
        """
        logger.info("Opening/decoding instantaneous arpege files")
        return open_decode_arpege_insta(path_files)


class Woa18Decoder(Decoder):
    """WOA18 climatology."""

    name = "woa18"
    fmts = ("woa18",)

    def decode(self, path_files, fmt, platform=None):
        """Decode WOA18 climatology files.

        Parameters
        ----------
        path_files : list of str
            Absolute paths to the input files.
        fmt : str
            Unused (kept for a uniform `Decoder.decode` signature).
        platform : str, optional
            Unused.

        Returns
        -------
        xarray.Dataset
            See `open_decode_woa18`.
        """
        logger.info("Opening/decoding woa18 climato")
        return open_decode_woa18(path_files)


class BobyclimDecoder(Decoder):
    """Bobyclim climatology."""

    name = "bobyclim"
    fmts = ("bobyclim",)

    def decode(self, path_files, fmt, platform=None):
        """Decode Bobyclim climatology files.

        Parameters
        ----------
        path_files : list of str
            Absolute paths to the input files.
        fmt : str
            Unused (kept for a uniform `Decoder.decode` signature).
        platform : str, optional
            Unused.

        Returns
        -------
        xarray.Dataset
            See `open_decode_bobyclim`.
        """
        logger.info("Opening/decoding Bobyclim climato")
        return open_decode_bobyclim(path_files)


class EddyPetDecoder(Decoder):
    """py-eddy-tracker eddy detection netcdf output."""

    name = "eddy_pet"
    fmts = ("eddy_pet",)

    def decode(self, path_files, fmt, platform=None):
        """Decode py-eddy-tracker eddy detection netcdf files.

        Parameters
        ----------
        path_files : list of str
            Absolute paths to the input files.
        fmt : str
            Unused (kept for a uniform `Decoder.decode` signature).
        platform : str, optional
            Unused.

        Returns
        -------
        xarray.Dataset
            See `open_decode_eddy_pet`.
        """
        logger.info("Opening/decoding py-eddy-tracker eddy detection netcdf")
        return open_decode_eddy_pet(path_files)


class EddySacsoDecoder(Decoder):
    """Sacso eddy detection text file output."""

    name = "eddy_sacso"
    fmts = ("eddy_sacso",)

    def decode(self, path_files, fmt, platform=None):
        """Decode sacso eddy detection text files.

        Parameters
        ----------
        path_files : list of str
            Absolute paths to the input files.
        fmt : str
            Unused (kept for a uniform `Decoder.decode` signature).
        platform : str, optional
            Unused.

        Returns
        -------
        xarray.Dataset
            See `open_decode_eddy_sacso`.
        """
        logger.info("Opening/decoding sacso eddy detection text file")
        return open_decode_eddy_sacso(path_files)


class EddyShootDecoder(Decoder):
    """Shoot eddy detection netcdf output."""

    name = "eddy_shoot"
    fmts = ("eddy_shoot",)

    def decode(self, path_files, fmt, platform=None):
        """Decode shoot eddy detection netcdf files.

        Parameters
        ----------
        path_files : list of str
            Absolute paths to the input files.
        fmt : str
            Unused (kept for a uniform `Decoder.decode` signature).
        platform : str, optional
            Unused.

        Returns
        -------
        xarray.Dataset
            See `open_decode_eddy_shoot`.
        """
        logger.info("Opening/decoding shoot eddy detection netcdf")
        return open_decode_eddy_shoot(path_files)


def get_decoder(fmt) -> Decoder:
    """Look up the Decoder for a data.ini/comp.ini `fmt` value.

    Parameters
    ----------
    fmt : str
        Input format identifier.

    Returns
    -------
    Decoder
        The registered instance for `fmt`.

    Raises
    ------
    ArmoorError
        If no `Decoder` subclass is registered under `fmt`.
    """
    if fmt not in _DECODER_REGISTRY:
        raise ArmoorError(f"Unknown format: {fmt!r}")
    return _DECODER_REGISTRY[fmt]


def open_decode(path_files, fmt, platform=None) -> xr.Dataset:
    """
    Open a netcdf/txt file and store it into a dataset

    Parameters
    ----------
    path_files : str, list of str
        Path to the netcdf files.
    fmt : str
        Input format identifier (see Decoder subclasses in this module).
    platform : str, optional
        Type of in-situ platform (argo/glider/mooring/drifter), used by
        the cmems_insitu/cora_insitu decoders.

    Returns
    -------
    xarray.Dataset
        Model or observation dataset.

    Raises
    ------
    ArmoorError
        If `fmt` is not a registered format (see `get_decoder`).
    """
    path_files = get_paths(path_files)
    result = get_decoder(fmt).decode(path_files, fmt, platform=platform)
    return _normalize_geo_coords(result)


def open_decode_arpege_insta(path_files):
    """Open and decode instantaneous Arpege GRIB2 atmospheric forcing files.

    Merges the 0/2/10 m levels for each file, concatenates over time, and
    renames coordinates to the armoor convention (lon/lat/time).

    Parameters
    ----------
    path_files : list of str
        Paths to the GRIB2 files.

    Returns
    -------
    xarray.Dataset
        Decoded, time-sorted dataset.
    """
    logger.info("atmfrc - insta")
    insta_gribs = path_files
    cfspecs = xmeta.get_meta_specs("meteofrance")
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
    # matches open_decode_sst_satellite's broadcast -- downstream plotting assumes 2D lon/lat
    lat, lon = xr.broadcast(ds_insta["lat"], ds_insta["lon"])
    ds_insta = ds_insta.drop_vars(["lon", "lat"])
    ds_insta["lon"] = lon
    ds_insta["lat"] = lat
    ds_insta = ds_insta.set_coords(["lon", "lat"])
    ds_insta = cfspecs.decode(ds_insta.sortby("time"))
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
    cfspecs = xmeta.get_meta_specs(f"{fmt}")
    ds = cfspecs.decode(xr.open_mfdataset(path_files, decode_timedelta=True).chunk(chunks={}))
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
        ds = cfspecs.decode(ds)
        if "bathy" in ds.data_vars:
            ds = ds[["bathy"]]
        ds = ds.swap_dims({"lon": "x", "lat": "y"})
        if "depth" in ds.dims:
            ds = ds.swap_dims({"depth": "z"})
        if len(ds.lon.dims) == 1:
            lat, lon = xr.broadcast(ds["lat"], ds["lon"])
            ds = ds.drop_vars(["lon", "lat"])
            ds["lon"] = lon
            ds["lat"] = lat
            ds = ds.set_coords(["lon", "lat"])
        if "depth" in ds.coords and len(ds.depth.dims) == 1:
            ref_vars = [v for v in ds.data_vars if len(ds[v].dims) == 4]
            if ref_vars:
                ds = ds.assign_coords(depth=ds["depth"].broadcast_like(ds[ref_vars[0]]))
        return ds
    # Open
    cfspecs = xmeta.get_meta_specs("cmems_model")
    sorted_paths = sorted(map(str, path_files))
    n_files = len(sorted_paths)
    open_kw = dict(
        engine="netcdf4",
        chunks={"time": 30,
                "depth": 100, "z": 100,
                "lat": 1024, "lon": 1024,
                "y": 1024, "x": 1024},
        cache=False,
        decode_times=True,
        decode_coords=True,
        decode_cf=True,
        mask_and_scale=True,
    )
    # Open each file individually and keep explicit references so that the
    # underlying netCDF4 file handles are not garbage-collected before dask
    # computes.  Using open_mfdataset with combine="nested"+concat_dim=None
    # was causing "RuntimeError: NetCDF: Not a valid ID" on some xarray
    # versions because the internal per-file datasets were GC'd too early.
    _handles = [xr.open_dataset(p, **open_kw) for p in sorted_paths]
    _processed = [preprocess_cmems_model(d) for d in _handles]
    if n_files == 1:
        ds = _processed[0]
    else:
        ds = xr.merge(_processed, compat="no_conflicts")
    if "depth" in ds.data_vars:
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
    logger.debug(f"sorted_paths : {sorted_paths}")

    n_files = len(sorted_paths)
    _t = time.perf_counter()

    # Group files by their exact time range (n_steps, first, last) so that
    # per-variable files covering the same period are MERGED (not concat'd),
    # while sequential time files are concatenated.
    # Example: [h_202509, h_202510, temp_202509, temp_202510] → two groups
    # {202509: [h, temp], 202510: [h, temp]}, merge within each, concat across.
    def _time_key(path):
        """Return (n, t0, t1) identifying the time axis of a NetCDF file."""
        try:
            import netCDF4 as _nc4
            with _nc4.Dataset(path) as _d:
                for dimname in list(_d.dimensions):
                    if "time" in dimname.lower():
                        n = len(_d.dimensions[dimname])
                        tvar = _d.variables.get(dimname)
                        if tvar is not None and n > 0:
                            return (n, float(tvar[0]), float(tvar[-1]))
                        return (n, None, None)
        except Exception:
            pass
        return None

    _open_kw = dict(
        engine="netcdf4",
        chunks={"time": 30, "Y": 1024, "X": 1024, "lev": 100},
        cache=False,
        decode_times=True,
        decode_coords=True,
        decode_cf=True,
        mask_and_scale=True,
    )

    # Build groups: {time_key: [path, ...]}
    from collections import OrderedDict
    _groups: dict = OrderedDict()
    for p in sorted_paths:
        k = _time_key(p)
        _groups.setdefault(k, []).append(p)

    _needs_merge = any(len(v) > 1 for v in _groups.values())

    if not _needs_merge:
        # All files have distinct time ranges: plain nested concat (fast path)
        logger.info("open_decode_hycom: sequential files — nested concat")
        ds = xr.open_mfdataset(
            sorted_paths,
            combine="nested",
            concat_dim="time",
            preprocess=preprocess_hycom,
            parallel=n_files > 1,
            data_vars='minimal',
            coords='minimal',
            **_open_kw,
        )
    else:
        # Some time ranges are shared across files (per-variable organisation):
        # merge within each group, then concat groups along time.
        logger.info(f"open_decode_hycom: {len(_groups)} time group(s), merging per-variable files")
        _group_ds = []
        for _key, _paths in _groups.items():
            if len(_paths) == 1:
                _ds = xr.open_dataset(_paths[0], **_open_kw)
                _ds = preprocess_hycom(_ds)
            else:
                _parts = []
                for p in _paths:
                    _ds0 = xr.open_dataset(p, **_open_kw)
                    _ds0 = preprocess_hycom(_ds0)
                    _parts.append(_ds0)
                _ds = xr.merge(_parts, join="inner", compat="no_conflicts", combine_attrs="override")
            _group_ds.append(_ds)
        if len(_group_ds) == 1:
            ds = _group_ds[0]
        else:
            ds = xr.concat(_group_ds, dim="time", data_vars="all")
    logger.info(f"  [timing] open_mfdataset: {time.perf_counter()-_t:.1f}s"); _t = time.perf_counter()

    cfspecs = xmeta.get_meta_specs("hycom")
    ds = cfspecs.decode(ds)
    logger.info(f"  [timing] xoa.decode:     {time.perf_counter()-_t:.1f}s"); _t = time.perf_counter()

    ds = ds.unify_chunks()
    logger.info(f"  [timing] unify_chunks:   {time.perf_counter()-_t:.1f}s"); _t = time.perf_counter()

    if "bathy" in ds:
        bathy = ds["bathy"]
        ds = ds.drop_vars("bathy")
    else:
        bathy = None

    if "u" in ds:
        ds["u"] = ds.map_blocks(shift_u_block, template=ds["u"])
    if "v" in ds:
        ds["v"] = ds.map_blocks(shift_v_block, template=ds["v"])
    logger.info(f"  [timing] map_blocks u/v: {time.perf_counter()-_t:.1f}s"); _t = time.perf_counter()

    if bathy is not None:
        ds = xr.merge([ds, bathy.to_dataset(name="bathy")])
    if "dz" in ds:
        depth = dz2depth(ds.dz, centered=True)
        ds = ds.assign_coords(depth=depth).drop_vars(["dz", "z"])
    logger.info(f"  [timing] dz2depth:       {time.perf_counter()-_t:.1f}s"); _t = time.perf_counter()

    ds = ds.sel(time=~ds.get_index("time").duplicated()).sortby("time")
    logger.info(f"  [timing] dedup time:     {time.perf_counter()-_t:.1f}s"); _t = time.perf_counter()

    good_var = None
    for var in ["depth", "ssh", "ptemp"]:
        if var in ds:
            good_var = ds[var]
            break
    chunk_dict = {}
    if good_var is None:
        good_var = next(iter(ds.data_vars.values()))
    for dim, dim_chunks in zip(good_var.dims, good_var.chunks):
        dim_size = good_var.sizes[dim]
        if dim == 'time':
            chunk_dict[dim] = dim_chunks[0]  # keep 1 time step per chunk
        else:
            # Keep the large chunks set at open time; fall back to native if
            # they are somehow still small (unknown dim name was ignored).
            chunk_dict[dim] = min(dim_size, max(dim_chunks[0], 1024))
    ds = ds.chunk(chunk_dict)
    logger.info(f"  [timing] final rechunk:  {time.perf_counter()-_t:.1f}s")
    return ds

def open_decode_sloop(path_files):
    """Open and decode Sloop output files.

    Parameters
    ----------
    path_files : list of str
        Paths to NetCDF files.

    Returns
    -------
    xarray.Dataset
        Decoded Sloop dataset with armoor-standard variable names and
        dimensions (z, y, x, time).
    """
    cfspecs = xmeta.get_meta_specs("sloop")
    sorted_paths = sorted(map(str, path_files))
    n_files = len(sorted_paths)
    open_kw = dict(
        engine="netcdf4",
        decode_times=True,
        decode_coords=True,
        decode_cf=True,
        mask_and_scale=True,
    )
    _handles = [xr.open_dataset(p, **open_kw) for p in sorted_paths]
    _processed = []
    for ds in _handles:
        ds = cfspecs.decode(ds)
        if "Y" in ds.dims:
            ds = ds.swap_dims({"Y": "y"})
        if "X" in ds.dims:
            ds = ds.swap_dims({"X": "x"})
        if "depth" in ds.dims:
            ds = ds.swap_dims({"depth": "z"})
        if "depth" in ds.coords and len(ds.depth.dims) == 1:
            ref_vars = [v for v in ds.data_vars if len(ds[v].dims) == 4]
            if ref_vars:
                ds = ds.assign_coords(depth=ds["depth"].broadcast_like(ds[ref_vars[0]]))
        _processed.append(ds)
    if n_files == 1:
        return _processed[0]
    return xr.merge(_processed)


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
        combine_attrs="drop_conflicts",
        compat="no_conflicts",
        data_vars="all",
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
    # The original "months since ..." units/calendar attrs survive the
    # arithmetic above even though the values no longer mean that -- left
    # in place, they mislead xarray into writing them back out verbatim
    # (and then failing to CF-decode them) the next time this dataset is
    # saved and reopened (e.g. armoor.data.output's intermediate files).
    woa18["time"].attrs = {}
    woa18["time"].encoding = {}
    if "temp" in woa18 and "sal" in woa18:
        # Derive canonical "ptemp" (potential temp) from in-situ "temp" --
        # .compute() avoids chaining it lazily onto the raw open_mfdataset
        # graph, which corrupted dask's task graph downstream once wrapped
        # in further dask.delayed/compute calls with fusion enabled.
        woa18["ptemp"] = woa18.oceanvars.sel_ptemp().compute()
        woa18 = woa18.drop_vars("pres", errors="ignore")
    return woa18


def open_decode_bobyclim(path_files):
    """Open Bobyclim netcdf files and store into a ready-to-use dataset.

    Parameters
    ----------
    path_files : str, list of str
        Path to the netcdf files.

    Returns
    -------
    xarray.Dataset
        Bobyclim dataset with time axis normalised to monthly indices 1–12.
    """
    warnings.warn(
        "open_decode_bobyclim() has not been tested against real Bobyclim files. "
        "Variable names and axis encoding are assumed — this function may crash or "
        "produce incorrect results. Please validate before use in production.",
        UserWarning,
        stacklevel=2,
    )
    ds = xr.open_mfdataset(path_files, combine_attrs="drop_conflicts")

    # Rename variables to canonical names (adjust if source names differ)
    rename_map = {}
    for src, dst in [("temperature", "temp"), ("salinity", "sal"),
                     ("TEMP", "temp"), ("SAL", "sal"),
                     ("votemper", "temp"), ("vosaline", "sal")]:
        if src in ds and dst not in ds:
            rename_map[src] = dst
    if rename_map:
        ds = ds.rename(rename_map)

    ds = convert_lons(ds)

    # Build 2D (y, x) grid from 1D lon/lat if needed
    if "lon" in ds.coords and ds["lon"].ndim == 1 and "lat" in ds.coords and ds["lat"].ndim == 1:
        lon2d, lat2d = np.meshgrid(ds["lon"].values, ds["lat"].values)
        ds = ds.swap_dims({"lon": "x", "lat": "y"})
        ds = ds.drop_vars(["lon", "lat"])
        ds["lon"] = xr.DataArray(lon2d, dims=["y", "x"])
        ds["lat"] = xr.DataArray(lat2d, dims=["y", "x"])
        ds = ds.set_coords(["lon", "lat"])

    # Normalise time axis to monthly indices 1–12
    if "time" in ds.coords:
        time_vals = ds["time"].values
        if np.issubdtype(time_vals.dtype, np.floating) or np.issubdtype(time_vals.dtype, np.integer):
            # Already numeric — apply same formula as WOA18
            ds["time"] = np.ceil(ds["time"]) - 12.0 * np.trunc(
                np.ceil(ds["time"]) / 12.0
            )
            ds["time"] = ds["time"].where(ds["time"] != 0., 12.)
        else:
            # datetime-like: extract month number
            ds["time"] = xr.DataArray(
                ds["time"].dt.month.values, dims=["time"]
            )

    return ds


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
    cfspecs = xmeta.get_meta_specs(f"cora_{platform}")
    dss = []
    for path in path_files:
        ds = cfspecs.decode(xr.open_dataset(path))
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
    cfspecs = xmeta.get_meta_specs(f"cmems_{platform}")
    dss = []
    for path in path_files:
        ds = cfspecs.decode(xr.open_dataset(path, chunks={}))
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
                ds = xr.combine_nested(dssi, "time", data_vars="all")
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
            ds = xr.merge(dss0, compat='override')
            ds = ds.sortby("time")
            ds.attrs["name"] = f"{ds.attrs['platform_code']}"
            dss.append(ds)
        return dss


def open_decode_odar(path_files):
    """Open ODAR-processed towed/glider CTD section file(s).

    ODAR (the in-house processing tool behind ``odar-seasoar``/``odar-
    scanfish``/etc.) already emits armoor-friendly variable names (``temp``,
    ``pres``, ``conduct``, ``depth``, ``lon``, ``lat``, ``time``) matching
    the generic CF meta specs, so -- unlike `open_decode_cmems_insitu` --
    no per-platform variable reshaping is needed. Two things still need
    fixing by hand:

    - ``time`` is encoded as ``"nanoseconds since <reference>"``, a unit
      `cftime`/xarray's CF decoder rejects outright (it only accepts
      seconds/minutes/hours/days) -- decoded manually here instead.
    - Practical salinity isn't in the file, only raw ``conduct`` (mS/cm) --
      kept as-is here and derived later, lazily, by
      `armoor.base.oceanvars.OceanVarsAccessor.sel_sal` (on the tiny
      colocated subset, not eagerly on the full section: computing it here
      on the still dask-backed decode output corrupted the task graph --
      ``ValueError: Missing dependency ('open_dataset-conduct-...')`` --
      confirmed against the real ``seasoar.nc`` sample; deferring the
      computation is also the established pattern for every other derived
      oceanvar, see `armoor.comp.coloc._prepare_dataset`'s docstring).

    Parameters
    ----------
    path_files : list of str
        Absolute paths to the input files. Each file is one section (one
        towed-instrument transect or glider mission), like
        `open_decode_cmems_insitu`'s glider/mooring/drifter platforms --
        not grouped further.

    Returns
    -------
    list of xarray.Dataset
        One dataset per input file, with ``z`` as the vertical dim
        (``depth`` demoted to a coordinate along it), ``lon``/``lat``/
        ``depth`` as coordinates, and ``sal`` added when derivable.
    """
    cfspecs = xmeta.get_meta_specs("generic")
    dss = []
    for path in path_files:
        ds = cfspecs.decode(xr.open_dataset(path, chunks={}, decode_times=False))

        units = ds["time"].attrs.get("units", "")
        if "nanoseconds since" in units:
            ref = pd.Timestamp(units.split("nanoseconds since", 1)[1].strip())
            ds = ds.assign_coords(
                time=("time", (ref + pd.to_timedelta(ds["time"].values, unit="ns")).values)
            )

        if "depth" in ds.dims:
            ds = ds.swap_dims({"depth": "z"})

        ds = ds.set_coords([c for c in ("lon", "lat", "depth") if c in ds.variables])
        ds.attrs.setdefault("name", Path(path).stem)
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
    cfspecs = xmeta.get_meta_specs("croco")

    def _find_grid_file(files):
        """Return the first file with grid vars and no time dim (separate grid file)."""
        import netCDF4 as _nc4
        required_vars = {"lon_rho", "mask_rho", "h"}
        for f in files:
            try:
                with _nc4.Dataset(f) as _d:
                    if required_vars.issubset(_d.variables.keys()):
                        if "time" not in _d.dimensions:
                            return f
            except Exception:
                pass
        return None

    def _find_grid_source(files):
        """Return the first file containing grid vars (may also have time)."""
        import netCDF4 as _nc4
        required_vars = {"lon_rho", "mask_rho", "h"}
        for f in files:
            try:
                with _nc4.Dataset(f) as _d:
                    if required_vars.issubset(_d.variables.keys()):
                        return f
            except Exception:
                pass
        return None

    grid_file = _find_grid_file(path_file)
    has_separate_grid = grid_file is not None
    if not has_separate_grid:
        # No separate grid file: grid vars are embedded in data files (standard CROCO output)
        grid_file = _find_grid_source(path_file)
        if grid_file is None:
            raise ValueError("No croco grid variables found in input files.")
        logger.info(f"Grid variables found in data file: {grid_file}")
    else:
        logger.info(f"Separate grid file detected: {grid_file}")

    _t = time.perf_counter()

    ds_grid = xr.open_dataset(grid_file)
    # Separate grid file is excluded from data files; embedded grid files are kept
    data_files = [f for f in path_file if f != grid_file] if has_separate_grid else list(path_file)
    n_files = len(data_files)

    # Use native file dim names (pre-decode: eta_rho/xi_rho, not y_rho/x_rho)
    # and large chunks to minimise dask task count.
    nx = ds_grid.sizes["xi_rho"]
    ny = ds_grid.sizes["eta_rho"]
    chunk_x = min(nx, 1024)
    chunk_y = min(ny, 1024)
    chunks = {
        "time": 1,
        "eta_rho": chunk_y,
        "xi_rho": chunk_x,
        "eta_v": chunk_y,
        "xi_u": chunk_x,
    }

    ds = xr.open_mfdataset(
        data_files,
        combine="nested",
        concat_dim="time",
        chunks=chunks,
        parallel=n_files > 1,
        data_vars="minimal",
        coords="minimal",
        compat="override",
        engine="netcdf4",
        cache=False,
        decode_times=True,
        decode_coords=True,
        decode_cf=True,
        mask_and_scale=True,
    )
    logger.info(f"  [timing] open_mfdataset:   {time.perf_counter()-_t:.1f}s"); _t = time.perf_counter()

    if "auxil" in ds.dims:
        ds = ds.drop_dims("auxil")

    # Override grid coordinates (handles MPINOLAND and ensures consistent grid)
    for var in ["xi_rho", "eta_rho", "xi_u", "eta_v", "lon_rho", "lat_rho", "lon_u", "lat_v", "mask_rho"]:
        if var in ds_grid:
            ds[var] = ds_grid[var]
    ds_grid.close()

    # Deduplicate time via pandas index (avoids np.unique which forces eager compute)
    ds = ds.sel(time=~ds.get_index("time").duplicated())
    logger.info(f"  [timing] dedup time:       {time.perf_counter()-_t:.1f}s"); _t = time.perf_counter()

    if 'scrum_time' in ds:
        ds = ds.drop_vars('scrum_time')

    ds = cfspecs.decode(ds)
    logger.info(f"  [timing] xoa.decode:       {time.perf_counter()-_t:.1f}s"); _t = time.perf_counter()

    with xmeta.set_meta_specs(cfspecs):
        for sig in ("sig_rho", "sig_w"):
            if sig in ds:
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
    logger.info(f"  [timing] decode_sigma:     {time.perf_counter()-_t:.1f}s"); _t = time.perf_counter()

    ds = ds.unify_chunks()
    logger.info(f"  [timing] unify_chunks:     {time.perf_counter()-_t:.1f}s"); _t = time.perf_counter()

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
        "sst_skin",
        "hbl",
        ]:
        if v in ds:
            ds = ds.drop_vars(v)

    for coord in list(ds.coords):
        if "nav_" in coord:
            coord_name = coord.replace("nav_", "")
            if coord_name in ds:
                ds = ds.drop_vars(coord)
            else:
                ds = ds.rename({coord: coord_name})

    if "time_counter" in ds.dims:
        ds = ds.swap_dims({"time_counter": "time"})
    if "sig_rho" in ds.dims:
        ds = ds.swap_dims({"sig_rho": "z"})

    ds = ds.isel(x_rho=slice(1, -1), y_rho=slice(1, -1))

    if "u" in ds.data_vars:
        mask_u = (ds["u"] != 0) & (ds["u"] != -999)
        u = ds["u"].where(mask_u, drop=False)
        u.encoding = ds["u"].encoding.copy()
        dau = shift(u, {"x_u": "right"}).isel(x_u=slice(None, -1)).xoa.reloc(u="rho")
        ds["u"] = dau.assign_coords(**ds.ptemp.coords)
    if "v" in ds.data_vars:
        mask_v = (ds["v"] != 0) & (ds["v"] != -999)
        v = ds["v"].where(mask_v, drop=False)
        v.encoding = ds["v"].encoding.copy()
        dav = shift(v, {"y_v": "top"}).isel(y_v=slice(None, -1)).xoa.reloc(v="rho")
        ds["v"] = dav.assign_coords(**ds.ptemp.coords)
    logger.info(f"  [timing] u/v shift:        {time.perf_counter()-_t:.1f}s"); _t = time.perf_counter()

    if "z" in ds.dims:
        ds = ds.rename({"lon_rho": "lon", "lat_rho": "lat", "depth_rho": "depth"})
    else:
        ds = ds.rename({"lon_rho": "lon", "lat_rho": "lat"})

    for dim in ("x_u", "y_v"):
        if dim in ds.dims:
            ds = ds.drop_dims(dim)

    ds = ds.swap_dims({"x_rho": "x", "y_rho": "y"})
    for coord in ("x_rho", "y_rho"):
        if coord in ds.coords:
            ds = ds.drop_vars(coord)

    if "angle" in ds and (set(("u", "v")).issubset(ds.data_vars)):
        angle = ds["angle"]
        da_u = ds["u"] * np.cos(angle) - ds["v"] * np.sin(angle)
        da_v = ds["v"] * np.cos(angle) + ds["u"] * np.sin(angle)
        ds = ds.drop_vars(["u", "v", "angle"])
        ds["u"] = da_u
        ds["v"] = da_v

    logger.info(f"Dataset: {ds}")

    if "mask_rho" in ds:
        ds = ds.where(ds["mask_rho"] > 0, drop=False)
        ds = ds.rename({"mask_rho": "mask"})

    if "z" in ds.dims:
        ds = ds.isel(z=slice(None, None, -1))
        ds = ds.assign_coords(depth=-ds.depth)

    # Final rechunk: large spatial chunks now that sigma coords are decoded
    good_var = None
    for var in ["depth", "ptemp", "sal"]:
        if var in ds:
            good_var = ds[var]
            break
    if good_var is None and ds.data_vars:
        good_var = next(iter(ds.data_vars.values()))
    if good_var is not None and good_var.chunks:
        chunk_dict = {}
        for dim, dim_chunks in zip(good_var.dims, good_var.chunks):
            dim_size = good_var.sizes[dim]
            if dim == "time":
                chunk_dict[dim] = dim_chunks[0]
            else:
                chunk_dict[dim] = min(dim_size, max(dim_chunks[0], 512))
        ds = ds.chunk(chunk_dict)
    logger.info(f"  [timing] final rechunk:    {time.perf_counter()-_t:.1f}s")

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


def open_decode_eddy_pet(path_files):
    """
    Open py-eddy-tracker netcdf file(s) and store it in dataset.

    Parameters
    ----------
    path_files : str, list of str
        Path to the netcdf files.

    Returns
    -------
    xarray.Dataset
        dataset
    """
    outputs = []
    all_paths = [path for path in path_files if 'Cyclonic' in path]

    for file in all_paths:
        cyclones = xr.open_dataset(file)
        anticyclones = xr.open_dataset(file.replace("Cyclonic", "Anticyclonic"))

        ds_cyclones = xr.Dataset(
            {
                "contour_lat": (["obs", "nb_sample"], cyclones.speed_contour_latitude.data),
                "contour_lon": (["obs", "nb_sample"], cyclones.speed_contour_longitude.data),
                "center_lat": (["obs"], cyclones.latitude.data),
                "center_lon": (["obs"], cyclones.longitude.data),
                "eddy_type": (
                    ["obs"],
                    np.zeros(cyclones.obs.shape[0]) - 1,
                    {'comment': '-1 if cyclone, +1 if anticyclone'
                     }),
                "vmax_area": (
                    ["obs"],
                    np.pi * cyclones.speed_radius.data**2 / 1e6,
                    {'comment': 'Area of the vmax contour',
                     'units': 'km2'
                     }),
            },
            coords={
                "nb_sample": (["nb_sample"], cyclones.NbSample.data),
            }
        )

        ds_anticyclones = xr.Dataset(
            {
                "contour_lat": (["obs", "nb_sample"], anticyclones.speed_contour_latitude.data),
                "contour_lon": (["obs", "nb_sample"], anticyclones.speed_contour_longitude.data),
                "center_lat": (["obs"], anticyclones.latitude.data),
                "center_lon": (["obs"], anticyclones.longitude.data),
                "eddy_type": (
                    ["obs"],
                    np.zeros(anticyclones.obs.shape[0]) + 1,
                    {'comment': '-1 if cyclone, +1 if anticyclone'
                     }),
                "vmax_area": (
                    ["obs"],
                    np.pi * anticyclones.speed_radius.data**2 / 1e6,
                    {'comment': 'Area of the vmax contour',
                     'units': 'km2'
                     }),
            },
            coords={
                "nb_sample": (["nb_sample"], anticyclones.NbSample.data),
            }
        )

        da = xr.concat([ds_cyclones, ds_anticyclones], dim="obs")

        outputs += [
            da.assign_coords(
                time=("obs", [datetime.datetime.strptime(file[-11:-3], '%Y%m%d')] * da.obs.shape[0])
            )
        ]

    ds = xr.concat(outputs, "obs")

    return ds


def open_decode_eddy_sacso(path_files):
    """
    Open sacso text file(s) and store it in dataset.

    Parameters
    ----------
    path_files : str, list of str
        Path to the netcdf files.

    Returns
    -------
    xarray.Dataset
        dataset
    """
    # Initialize
    all_points = []; current_block = []; eddy_type = []
    center_lat = []; center_lon = []; dates = []; surfaces = []
    suffix_date = 'Date' + ' ' * 33
    suffix_type = 'Sens_de_rotation' + ' ' * 21       # suffix+spaces = 37
    suffix_center = 'Centre(lon/lat)' + ' ' * 22
    suffix_surface = 'Surface(km2)' + ' ' * 25

    content = []
    for path in path_files:
        with open(path, "r") as file:
            content += file.readlines()

    start_reading = False
    for line in content:
        line = line.strip()  # remove spaces and line breaks

        if "Date" in line:
            dates.append(datetime.datetime.strptime(line[len(suffix_date):], '%Y-%m-%d/%H:%M'))

        # Check if new list of coordinates
        if line == "Liste_Points(lon/lat)":
            if current_block:
                # Pass full block to all_points
                all_points.append(np.array(current_block))
                current_block = []  # clean for next block
            start_reading = True
            continue

        if start_reading and line:
            if "Sens_de_rotation" in line:
                rotation = line[len(suffix_center):-4].lower() + 'e'  # cyclone or anticyclone
                if rotation == 'cyclone':
                    eddy_type.append(-1)
                elif rotation == 'anticyclone':
                    eddy_type.append(1)
            elif "Centre(lon/lat)" in line:
                center = line[len(suffix_center):]
                center_lon.append(float(center[:center.find('/')]))
                center_lat.append(float(center[center.find('/') + 1:]))
            elif "Surface(km2)" in line:
                surfaces.append(float(line[len(suffix_surface):]))
            else:
                try:
                    lon, lat = map(float, line.split('/'))
                    current_block.append([lon, lat])
                except ValueError:
                    pass

    if current_block:  # make sure everything is saved
        all_points.append(np.array(current_block))

    if not all_points:  # empty = no eddies detected
        logger.info('No eddies detected in file(s).')
    else:
        max_length = max(len(block) for block in all_points)

        # Create matrices of same dimension for every set of coordinates
        lats = np.full((len(all_points), max_length), np.nan)  # (obs, nb_sample)
        lons = np.full((len(all_points), max_length), np.nan)  # (obs, nb_sample)

        for i, block in enumerate(all_points):
            lons[i, :len(block)] = block[:, 0]
            lats[i, :len(block)] = block[:, 1]

        ds = xr.Dataset(
            {
                "contour_lat": (["obs", "nb_sample"], lats),
                "contour_lon": (["obs", "nb_sample"], lons),
                "center_lat": (["obs"], np.array(center_lat)),
                "center_lon": (["obs"], np.array(center_lon)),
                "eddy_type": (
                    ["obs"],
                    np.array(eddy_type),
                    {'comment': '-1 if cyclone, +1 if anticyclone'
                     }),
                "vmax_area": (
                    ["obs"],
                    np.array(surfaces),
                    {'comment': 'Area of the vmax contour',
                     'units': 'km2'
                     })
            },
            coords={
                "nb_sample": np.arange(max_length)
            }
        ).assign_coords(
            time=("obs", np.array(dates))
        )
        ds['time'].encoding = {
            'units': 'nanoseconds since 1970-01-01',
            'dtype': 'float64'
        }
        return ds


def open_decode_eddy_shoot(path_files):
    """
    Open shoot netcdf file(s) and store it in dataset.

    Parameters
    ----------
    path_files : str, list of str
        Path to the netcdf files.

    Returns
    -------
    xarray.Dataset
        dataset
    """
    # Open
    def preprocessing(ds):
        return ds.set_coords("time")

    da = xr.open_mfdataset(path_files, combine='nested', concat_dim='obs', preprocess=preprocessing)

    # Keep only variables of interest and formatting
    list_vars = [a for a in da.data_vars if
                 'vmax_contour' not in a
                 and 'eddy_type' not in a
                 and 'x_cen' not in a
                 and 'y_cen' not in a
                 and 'vmax_radius' not in a]    # time is already included in coordinates = will be kept
    da = (
        da.drop_vars(list_vars)
          .drop_attrs()
          .rename({'x_vmax_contour': 'contour_lon', 'y_vmax_contour': 'contour_lat',
                   'x_cen': 'center_lon', 'y_cen': 'center_lat'})
          .load()
          .assign_coords(nb_sample=("nb_sample", da.nb_sample.data))
    )

    da["eddy_type"] = xr.DataArray(np.where(da["eddy_type"] == 'cyclone', -1, 1), dims='obs').assign_attrs({
        'comment': '-1 if cyclone, +1 if anticyclone'})

    da["vmax_area"] = np.pi * da.vmax_radius**2 / 1e6
    da["vmax_area"] = da["vmax_area"].assign_attrs({
        'comment': 'Area of the vmax contour',
        'units': 'km2'
    })
    da = da.drop_vars('vmax_radius')

    return da


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
