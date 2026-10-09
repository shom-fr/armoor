import gc
import logging
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Dict, List, Optional, Any, Union

import numpy as np
import pandas as pd
import xarray as xr

from armoor.__init__ import ArmoorError
from armoor.io import get_zarr_encoding, sort_ncs_by_suffix
from armoor.misc import optimize_for_low_swap, validate_metazone_params
import armoor.ranges as ranges
from armoor.data import INTERP_PARAMS_USER
from armoor.data.datatype import get_data_type_by_name
from armoor.data.interp import (
    process_time_interpolation,
    process_horizontal_interpolation,
    process_vertical_interpolation,
)

logger = logging.getLogger(__name__)


def _pooled_mean_std(n, s, ss):
    """Mean/std from pooled (count, sum, sum-of-squares)."""
    mean = s / n
    var = max(ss / n - mean**2, 0.0)
    return mean, var**0.5


def _merge_minmax_dicts(a, b):
    """Merge two {var: (min, max)} dicts into a new one."""
    merged = dict(a)
    for var, (vmin, vmax) in b.items():
        if var in merged:
            pmin, pmax = merged[var]
            vmin, vmax = min(vmin, pmin), max(vmax, pmax)
        merged[var] = (vmin, vmax)
    return merged


def _merge_nss_dicts(a, b):
    """Merge two {var: (n, sum, sumsq)} dicts into a new one."""
    merged = dict(a)
    for var, (n, s, ss) in b.items():
        if var in merged:
            n0, s0, ss0 = merged[var]
            n, s, ss = n0 + n, s0 + s, ss0 + ss
        merged[var] = (n, s, ss)
    return merged


def _level_key(attrs):
    """Vertical-level key for clim/cbar_group/series pooling: vlevel if
    set, else vrange, else None (no "z" at all, e.g. satellite SST) --
    keeps e.g. a model's 500m level from being pooled together with its
    own (or a sibling source's) surface level."""
    if "vlevel" in attrs:
        return ("vlevel", attrs["vlevel"])
    if "vrange" in attrs:
        return ("vrange", attrs["vrange"])
    return None


def _level_depth(level_key):
    """Sort key approximating depth for a `_level_key` result -- the
    vlevel value itself, or a vrange bin's lower bound."""
    kind, val = level_key
    if kind == "vlevel":
        return float(val)
    return float(val.split("-")[0])


def _merge_zless_into_shallowest(pooled, merge_fn):
    """Fold a z-less group (level_key=None, e.g. satellite SST -- no
    vertical structure at all) into its shallowest depth-resolved
    sibling's bucket within the same (metazone, name) pooling prefix, in
    place.

    Without this, a z-less source configured with "cbar_group"/"clim"
    alongside a depth-split one (e.g. a model with several vlevels) would
    never pool with any of it: its own bucket's key (None) never equals
    any of the sibling's ("vlevel", ...)/("vrange", ...) keys, even though
    the intent (e.g. comparing SST against a model's own surface) is that
    they should share one color scale. Both the z-less key and the
    shallowest sibling key are left pointing at the same merged value, so
    either can look it up.

    Parameters
    ----------
    pooled : dict
        Mapping of (metazone, name, level_key) to a per-var accumulator
        dict, modified in place.
    merge_fn : callable
        ``merge_fn(a, b) -> merged`` combining two per-var accumulator
        dicts of the same shape (e.g. {var: (min, max)} or
        {var: (n, sum, sumsq)}).

    Returns
    -------
    None
    """
    prefixes: Dict[Any, List[Any]] = {}
    for metazone, name, level_key in pooled:
        prefixes.setdefault((metazone, name), []).append(level_key)

    for (metazone, name), level_keys in prefixes.items():
        if None not in level_keys:
            continue
        depth_keys = [lk for lk in level_keys if lk is not None]
        if not depth_keys:
            continue
        shallowest = min(depth_keys, key=_level_depth)
        orphan_key = (metazone, name, None)
        target_key = (metazone, name, shallowest)
        merged = merge_fn(pooled[target_key], pooled[orphan_key])
        pooled[target_key] = merged
        pooled[orphan_key] = merged


def get_dim_stats(dsin: xr.Dataset, dim: Optional[List[str]], mparams: dict) -> Optional[List[str]]:
    """Filter which dims to reduce mean/std over, based on metazone config.

    Mirrors `armoor.comp.stats.StatsComp._filter_dims`: "time" is only
    reduced if `mparams` declares ``trange_seq``, "z" only if it declares
    ``vrange``, and "x"/"y" only if `dsin` actually has an "x" dim.

    Parameters
    ----------
    dsin : xarray.Dataset
    dim : list of str or None
        Candidate dims requested by the caller.
    mparams : dict
        Metazone config parameters.

    Returns
    -------
    list of str or None
        `dim`, filtered; None if `dim` was falsy.
    """
    if dim:
        dim_stats = dim.copy()
        if ("time" in dim) and ("trange_seq" not in mparams):
            dim_stats.remove("time")
        if ("z" in dim) and ("vrange" not in mparams):
            dim_stats.remove("z")
        if ("x" in dim) and ("x" not in dsin.dims):
            dim_stats.remove("x")
            dim_stats.remove("y")
        return dim_stats
    else:
        return None


def set_time_range(ds: xr.Dataset, time: str) -> xr.Dataset:
    """Assign a single "time" coordinate at the midpoint of a bracketed range.

    Parameters
    ----------
    ds : xarray.Dataset
        A dataset already reduced over "time" (no "time" dim left).
    time : str
        A ``"[start_end["``-bracketed range (see `armoor.ranges.trange_seq`).

    Returns
    -------
    xarray.Dataset
        `ds` with a new "time" dim/coordinate at the range's midpoint.
    """
    if "time" not in ds.dims:  # mean/std groups
        if "time" in ds.coords:
            ds = ds.drop_vars("time")
        ds = ds.expand_dims(dim="time")

        t1, t2 = [pd.to_datetime(t) for t in time.strip('[').split('_')]
        med_time = t1 + 0.5 * (t2 - t1)

        ds["time"] = xr.DataArray(data=[med_time], dims="time")
        del t1, t2, med_time

        ds = ds.set_coords("time")
    return ds


def get_datatrees(
    dsins: List[xr.Dataset], dim: Optional[List[str]], mparams: dict
) -> List[xr.DataTree]:
    """Build one `xr.DataTree` per dataset, with "data"/"mean"/"std" groups.

    Parameters
    ----------
    dsins : list of xarray.Dataset
        Datasets to wrap, one per data source.
    dim : list of str or None
        Candidate dims to reduce over for mean/std (see `get_dim_stats`).
    mparams : dict
        Metazone config parameters, used both to filter `dim` and to tag
        each "trange_seq"-configured tree with its own time range (see
        `set_time_range`).

    Returns
    -------
    list of xarray.DataTree
        One tree per input dataset, named after its ``data_name`` attr.
    """
    dts = []
    for ds in dsins:
        for coord in ["lon", "lat", "depth"]:
            if coord in ds.coords:
                if "time" in ds[coord].dims:
                    ds = ds.reset_coords("depth")
        dt = xr.DataTree(name=ds.attrs["data_name"])
        dt.update(xr.DataTree.from_dict({"data": ds}))
        dim = get_dim_stats(ds, dim, mparams)
        if dim:
            dt.update(xr.DataTree.from_dict({"mean": ds.mean(dim=dim)}))
            dt.update(xr.DataTree.from_dict({"std": ds.std(dim=dim)}))
        xdim = {}
        if "trange_seq" in mparams:
            xdim.update({"time": ds.attrs["trange"]})
        for k, v in xdim.items():
            for data_name, dt0 in dt.items():
                ds0 = dt0.to_dataset()
                ds0 = ds0.assign_attrs({"trange_seq": mparams['trange_seq']['tfreq']})
                if dim:
                    if ("time" in dim) and (k == "time"):
                        ds0 = set_time_range(ds0, v)
                dt.update(xr.DataTree.from_dict({data_name: ds0}))
        dts.append(dt)
        del dt, ds
    return dts


def validate_interpolation(metazones: dict) -> dict:
    """Validate that only one of the two parameters is defined for each metazone.

    This function checks if either param1 or param2 is defined, but not both,
    for each metazone in the metazones dictionary.

    Parameters
    ----------
    metazones (dict): A dictionary of metazones with their parameters.
    param1: str
        The first parameter to check.
    param2: str
        The second parameter to check.

    Raises
    ------
    ArmoorError: If both parameters are defined or neither is defined.
    """
    return validate_metazone_params(metazones, INTERP_PARAMS_USER, label="interpolation")


def get_interpolation_params(metazones: dict) -> dict:
    """
    Retrieve colocation parameters for each metazone based on given parameters.

    This function takes two dictionaries as input: `metazones` and `params`. It
    returns a dictionary where each key is a metazone and each value is a
    dictionary containing the colocation parameters ("time", "horizontal",
    "vertical") that were found in `metazones` using the parameter candidates
    specified in `params`.

    Parameters
    ----------
    metazones: dict
        A dictionary where each key is the name of a metazone
        and each value is a dictionary containing the
        parameters of that metazone.
    params_user: dict
        A dictionary defined by users where each key is a type of interpolation
        ("time", "horizontal", "vertical") and each value is a
        list of parameter candidates to search for in `metazones`.
    params_default: dict
        A dictionary where each key is a type of colocation
        ("time", "horizontal", "vertical") and each value is a
        list of default parameters.

    Returns
    -------
    dict
        A dictionary where each key is a metazone and each value is a
        dictionary containing the colocation parameters found for that
        metazone.
    """
    interp_params = {}
    for mz_name, mz_params in metazones.items():
        if mz_params:
            interp_params[mz_name] = {
                interp: (param_candidate, mz_params.get(param_candidate))
                for interp in ("time", "horizontal", "vertical")
                for param_candidate in INTERP_PARAMS_USER.get(interp, [])
                if (mz_params.get(param_candidate) is not None)
            }
        else:
            interp_params[mz_name] = None
    return interp_params


def validate_and_get_params(metazones: dict) -> dict:
    """Validate and get colocation parameters.

    Parameters
    ----------
    metazones: dict
        Dictionary containing metazone information.

    Returns
    -------
    dict
        Colocation parameters.
    """
    metazones = validate_interpolation(metazones)
    interp_params = get_interpolation_params(metazones)
    return interp_params


def save_datasets(dsprod: xr.Dataset, dirout: Path, prod_name: str, ofmt: list) -> Path:
    """Save dataset to NetCDF files.

    Parameters
    ----------
    dsprod: xr.Dataset
        Product dataset to save.
    dirout: Path
        Directory to save the datasets.
    prod_name: str
        Name for the product dataset file.
    ofmt: list
        Formats to save outputs.

    Returns
    -------
    tuple
        Paths to the saved reference and product NetCDF files.
    """
    ncname = dsprod.range.suffix
    ncout_prod = dirout / f"prod{ncname}.zarr"
    dsprod = dsprod.chunk("auto")
    encoding = get_zarr_encoding(dsprod)
    if 'netcdf' in ofmt:
        dsprod.to_netcdf(
            dirout / f'prod{ncname}.nc',
            compute=True,
        )
    # Save as zarr anyway, whether it's in ofmt or not
    dsprod.to_zarr(
        store=ncout_prod,
        mode="w",
        encoding=encoding,
    )
    dsprod.close()
    return ncout_prod


class OutputProcessor:
    """
    A class to handle NetCDF data processing including interpolation and output generation.
    """

    def __init__(self, target_chunk_mb: int = 512):
        """
        Initialize the DataProcessor.

        Parameters
        ----------
        target_chunk_mb
            Target chunk size in MB for memory optimization
        """
        self.target_chunk_mb = target_chunk_mb
        self._clim_ranges: Dict[Any, Dict[str, tuple]] = {}
        self._cbar_ranges: Dict[Any, Dict[str, tuple]] = {}
        self._series_stats: Dict[Any, Dict[str, tuple]] = {}

    def process_datasets(
        self, ncs: List[str], metazones: Dict[str, Any], outputs: Dict[str, Any]
    ) -> Dict[str, Dict[str, List[Path]]]:
        """
        Main processing function for NetCDF datasets.

        Parameters
        ----------
        ncs
            List of NetCDF file paths to process
        metazones
            Dictionary containing metazone configurations
        outputs
            Dictionary containing output configurations (will be modified)

        Returns
        -------
        Dictionary mapping output names to metazones to list of output files

        Raises
        ------
        ArmoorError
            When processing fails
        """
        # Remove 'fmt' from outputs as it's not needed downstream, but keep
        # its value: save_datasets uses it to decide whether to also save
        # a netcdf copy alongside the zarr output.
        ofmt = outputs.pop("fmt", None) or []
        outputs.pop("vminmax", None)

        # Validate and prepare interpolation parameters
        interp_params = self._prepare_interpolation_params(metazones)
        ncouts = {}

        # Pre-passes for mapseries: resolve clim/cbar_group/series ranges
        # before the main loop, since ncs mixes every [data] source in no
        # particular order.
        self._clim_ranges = self._resolve_clim_ranges(ncs, metazones, outputs, interp_params)
        self._cbar_ranges = self._resolve_cbar_ranges(ncs, metazones, outputs, interp_params)
        self._series_stats = self._resolve_series_ranges(ncs, metazones, outputs, interp_params)

        # Process each NetCDF file
        for nc_file in ncs:
            logger.info(f"Processing {nc_file}")
            ncouts = self._process_single_netcdf(
                nc_file, metazones, interp_params, outputs, ncouts, ofmt
            )

        return ncouts

    def _prepare_interpolation_params(self, metazones: Dict[str, Any]) -> Dict[str, Optional[Dict]]:
        """
        Validate metazones and prepare interpolation parameters.

        Parameters
        ----------
        metazones
            Dictionary containing metazone configurations

        Returns
        -------
        Dictionary mapping metazone names to interpolation parameters
        """
        interp_check = validate_and_get_params(metazones)
        interp_params = {}

        for metazone, params in interp_check.items():
            if not params:
                logger.info(f"{metazone}: no interpolation required.")
                interp_params[metazone] = None
            else:
                interp_params[metazone] = params

        return interp_params

    def _flatten_fouts(self, fouts: Union[List[Path], Dict[str, List[Path]]]) -> List[Path]:
        """Flatten a `_process_metazone` result into a single list of
        paths, regardless of which section (if any) each came from --
        used by the clim/cbar/series pre-passes, which pool statistics
        across every file for a metazone without caring about section
        identity."""
        if isinstance(fouts, dict):
            return [fout for section_fouts in fouts.values() for fout in section_fouts]
        return fouts

    def _resolve_clim_ranges(
        self,
        ncs: List[str],
        metazones: Dict[str, Any],
        outputs: Dict[str, Any],
        interp_params: Dict[str, Optional[Dict]],
    ) -> Dict[Any, Dict[str, tuple]]:
        """
        Resolve per-variable (min, max) for every climatology referenced by
        an output's "clim" setting, interpolated onto each metazone exactly
        like a normal source would be.

        Used by `mapseries` to draw a "clim" row in its min/max table (see
        `_process_sorted_group`), sourced generically from a `[data]` entry
        rather than a hardcoded climatology path/format.

        Parameters
        ----------
        ncs
            List of NetCDF file paths to process (every [data] source, not
            just climatologies).
        metazones
            Dictionary containing metazone configurations
        outputs
            Output configurations (mapping of oname to its config dict)
        interp_params
            Interpolation parameters per metazone, as returned by
            `_prepare_interpolation_params`

        Returns
        -------
        Dictionary mapping (metazone, clim_name, level_key) to a dict of
        {var: (min, max)} -- see `_level_key`. Empty if no output
        configures "clim".
        """
        clim_names = {o["clim"] for o in outputs.values() if isinstance(o, dict) and o.get("clim")}
        if not clim_names:
            return {}

        clim_ranges: Dict[Any, Dict[str, tuple]] = {}
        for nc_file in ncs:
            dsin = self._load_and_prepare_dataset(nc_file)
            try:
                data_name = dsin.attrs.get("data_name")
                if data_name not in clim_names:
                    continue
                is_climatology = get_data_type_by_name(dsin.attrs.get("data_type")).is_climatology
                for metazone, params in interp_params.items():
                    fouts = self._process_metazone(
                        dsin, metazone, metazones[metazone], params, dsin.attrs, [], is_climatology
                    )
                    for fout in self._flatten_fouts(fouts):
                        dsf = xr.open_dataset(fout)
                        try:
                            key = (metazone, data_name, _level_key(dsf.attrs))
                            ranges_mz = clim_ranges.setdefault(key, {})
                            for var in dsf.data_vars:
                                vmin = float(dsf[var].min())
                                vmax = float(dsf[var].max())
                                if var in ranges_mz:
                                    pmin, pmax = ranges_mz[var]
                                    vmin, vmax = min(vmin, pmin), max(vmax, pmax)
                                ranges_mz[var] = (vmin, vmax)
                        finally:
                            dsf.close()
            finally:
                dsin.close()
        _merge_zless_into_shallowest(clim_ranges, _merge_minmax_dicts)
        return clim_ranges

    def _resolve_cbar_ranges(
        self,
        ncs: List[str],
        metazones: Dict[str, Any],
        outputs: Dict[str, Any],
        interp_params: Dict[str, Optional[Dict]],
    ) -> Dict[Any, Dict[str, tuple]]:
        """
        Pool a shared min/max envelope, per (metazone, cbar_group) pair,
        across every non-climatology [data] source -- used by mapseries()
        to put e.g. an obs and a model series of the same variable on the
        same color scale, instead of each computing its own from its own
        series alone.

        mapseries's outputs_params has no mparams_pro/mparams_con, so
        (climatology aside) every ocean-model-shaped source is eligible
        for any mapseries output regardless of its metazone config --
        pooling therefore doesn't need to re-run the full compatibility
        check, only the is_climatology exclusion also enforced in
        `_validate_output_compatibility`.

        Parameters
        ----------
        ncs
            List of NetCDF file paths to process (every [data] source).
        metazones
            Dictionary containing metazone configurations
        outputs
            Output configurations (mapping of oname to its config dict)
        interp_params
            Interpolation parameters per metazone, as returned by
            `_prepare_interpolation_params`

        Returns
        -------
        Dictionary mapping (metazone, cbar_group, level_key) to a dict of
        {var: (min, max)} -- see `_level_key`. Empty if no mapseries
        output configures "cbar_group".
        """
        cbar_groups = {
            o["cbar_group"]
            for o in outputs.values()
            if isinstance(o, dict) and o.get("otype") == "mapseries" and o.get("cbar_group")
        }
        if not cbar_groups:
            return {}

        cbar_ranges: Dict[Any, Dict[str, tuple]] = {}
        for nc_file in ncs:
            dsin = self._load_and_prepare_dataset(nc_file)
            try:
                if get_data_type_by_name(dsin.attrs.get("data_type")).is_climatology:
                    continue
                for metazone, params in interp_params.items():
                    fouts = self._process_metazone(
                        dsin, metazone, metazones[metazone], params, dsin.attrs, []
                    )
                    for fout in self._flatten_fouts(fouts):
                        dsf = xr.open_dataset(fout)
                        try:
                            level_key = _level_key(dsf.attrs)
                            for cbar_group in cbar_groups:
                                ranges_mz = cbar_ranges.setdefault(
                                    (metazone, cbar_group, level_key), {}
                                )
                                for var in dsf.data_vars:
                                    vmin = float(dsf[var].min())
                                    vmax = float(dsf[var].max())
                                    if var in ranges_mz:
                                        pmin, pmax = ranges_mz[var]
                                        vmin, vmax = min(vmin, pmin), max(vmax, pmax)
                                    ranges_mz[var] = (vmin, vmax)
                        finally:
                            dsf.close()
            finally:
                dsin.close()
        _merge_zless_into_shallowest(cbar_ranges, _merge_minmax_dicts)
        return cbar_ranges

    def _resolve_series_ranges(
        self,
        ncs: List[str],
        metazones: Dict[str, Any],
        outputs: Dict[str, Any],
        interp_params: Dict[str, Optional[Dict]],
    ) -> Dict[Any, Dict[str, tuple]]:
        """
        Pool each non-climatology source's own mean/std, per (metazone,
        data_name), across its whole series -- mapseries saves one zarr
        per (time, z) group rather than one holding the full series, so
        the color scale can no longer be computed from a single zarr
        alone (see armoor.data.plot._cbar_range's series_mean/series_std).

        "cspeed" (sqrt(u**2+v**2)) is pooled too when u/v are present,
        since it's non-linear and can't be derived from u's/v's stats.

        Returns
        -------
        Dictionary mapping (metazone, data_name, level_key) to
        {var: (mean, std)} -- see `_level_key`. Empty if no output has
        otype "mapseries".
        """
        if not any(isinstance(o, dict) and o.get("otype") == "mapseries" for o in outputs.values()):
            return {}

        accum: Dict[Any, Dict[str, tuple]] = {}
        for nc_file in ncs:
            dsin = self._load_and_prepare_dataset(nc_file)
            try:
                if get_data_type_by_name(dsin.attrs.get("data_type")).is_climatology:
                    continue
                data_name = dsin.attrs.get("data_name")
                for metazone, params in interp_params.items():
                    fouts = self._process_metazone(
                        dsin, metazone, metazones[metazone], params, dsin.attrs, []
                    )
                    for fout in self._flatten_fouts(fouts):
                        dsf = xr.open_dataset(fout)
                        try:
                            acc = accum.setdefault((metazone, data_name, _level_key(dsf.attrs)), {})
                            das = dict(dsf.data_vars)
                            if "u" in das and "v" in das:
                                das["cspeed"] = np.sqrt(dsf["u"] ** 2 + dsf["v"] ** 2)
                            for var, da in das.items():
                                arr = np.asarray(da.values, dtype="float64").ravel()
                                arr = arr[~np.isnan(arr)]
                                if arr.size == 0:
                                    continue
                                n, s, ss = arr.size, float(arr.sum()), float((arr**2).sum())
                                if var in acc:
                                    n0, s0, ss0 = acc[var]
                                    n, s, ss = n0 + n, s0 + s, ss0 + ss
                                acc[var] = (n, s, ss)
                        finally:
                            dsf.close()
            finally:
                dsin.close()

        _merge_zless_into_shallowest(accum, _merge_nss_dicts)
        return {
            key: {var: _pooled_mean_std(n, s, ss) for var, (n, s, ss) in acc.items()}
            for key, acc in accum.items()
        }

    def _attach_clim_range(self, ds: xr.Dataset, metazone: str, output: Dict[str, Any]) -> None:
        """
        Inject clim_min_<var>/clim_max_<var> attrs on `ds`, in place, from
        the ranges resolved by `_resolve_clim_ranges` -- no-op unless this
        output's config sets "clim".

        Parameters
        ----------
        ds
            Dataset about to be saved (already carries the output's other
            config keys as attrs, via `_process_tree_dataset`).
        metazone
            Metazone name.
        output
            Output configuration (otype plus any optional output params).

        Returns
        -------
        None
        """
        clim_name = output.get("clim")
        if not clim_name:
            return
        key = (metazone, clim_name, _level_key(ds.attrs))
        clim_range = self._clim_ranges.get(key, {})
        if not clim_range:
            logger.warning(
                f"clim={clim_name!r} configured but not resolved for {metazone} ({key[2]})"
            )
        for var, (cmin, cmax) in clim_range.items():
            if var in ds.data_vars:
                ds.attrs[f"clim_min_{var}"] = cmin
                ds.attrs[f"clim_max_{var}"] = cmax

    def _attach_cbar_range(self, ds: xr.Dataset, metazone: str, output: Dict[str, Any]) -> None:
        """
        Inject cbar_min_<var>/cbar_max_<var> attrs on `ds`, in place, from
        the pooled ranges resolved by `_resolve_cbar_ranges` -- no-op
        unless this output's config sets "cbar_group".

        Parameters
        ----------
        ds
            Dataset about to be saved (already carries the output's other
            config keys as attrs, via `_process_tree_dataset`).
        metazone
            Metazone name.
        output
            Output configuration (otype plus any optional output params).

        Returns
        -------
        None
        """
        cbar_group = output.get("cbar_group")
        if not cbar_group:
            return
        key = (metazone, cbar_group, _level_key(ds.attrs))
        cbar_range = self._cbar_ranges.get(key, {})
        if not cbar_range:
            logger.warning(
                f"cbar_group={cbar_group!r} configured but not resolved for {metazone} ({key[2]})"
            )
        for var, (cmin, cmax) in cbar_range.items():
            if var in ds.data_vars:
                ds.attrs[f"cbar_min_{var}"] = cmin
                ds.attrs[f"cbar_max_{var}"] = cmax

    def _attach_series_range(
        self, ds: xr.Dataset, metazone: str, prod_name: str, output: Dict[str, Any]
    ) -> None:
        """
        Inject series_mean_<var>/series_std_<var> attrs on `ds`, in place,
        from `_resolve_series_ranges` -- no-op unless `output`'s otype is
        "mapseries".
        """
        if output.get("otype") != "mapseries":
            return
        key = (metazone, prod_name, _level_key(ds.attrs))
        stats = self._series_stats.get(key, {})
        if not stats:
            logger.warning(f"No series stats resolved for {prod_name!r} ({metazone}, {key[2]})")
        for var, (mean, std) in stats.items():
            if var == "cspeed" or var in ds.data_vars:
                ds.attrs[f"series_mean_{var}"] = mean
                ds.attrs[f"series_std_{var}"] = std

    def _process_single_netcdf(
        self,
        nc_file: str,
        metazones: Dict[str, Any],
        interp_params: Dict[str, Optional[Dict]],
        outputs: Dict[str, Any],
        ncouts: Dict[str, Dict[str, List[Path]]],
        ofmt: List[str],
    ) -> Dict[str, Dict[str, List[Path]]]:
        """
        Process a single NetCDF file for all metazones.

        Parameters
        ----------
        nc_file
            Path to NetCDF file
        metazones
            Metazone configurations
        interp_params
            Interpolation parameters for each metazone
        outputs
            Output configurations
        ncouts
            Accumulator for output file paths
        ofmt
            Formats to save intermediate interpolated outputs (e.g. also
            write netcdf alongside zarr)

        Returns
        -------
        Updated ncouts dictionary
        """
        # Load and prepare dataset
        dsin = self._load_and_prepare_dataset(nc_file)
        attrs_in = dsin.attrs
        prod_name = attrs_in.get("data_name")
        data_type = get_data_type_by_name(attrs_in.get("data_type"))
        outputs_params = data_type.outputs_params
        is_climatology = data_type.is_climatology

        try:
            # Process each metazone
            for metazone, params in interp_params.items():
                fouts = self._process_metazone(
                    dsin, metazone, metazones[metazone], params, attrs_in, ofmt, is_climatology
                )

                if isinstance(fouts, dict):
                    for section_name, section_fouts in fouts.items():
                        ncouts = self._generate_outputs(
                            section_fouts,
                            metazone,
                            metazones[metazone],
                            outputs,
                            prod_name,
                            ncouts,
                            outputs_params,
                            is_climatology,
                            section_name=section_name,
                        )
                else:
                    # Generate outputs for this metazone
                    ncouts = self._generate_outputs(
                        fouts,
                        metazone,
                        metazones[metazone],
                        outputs,
                        prod_name,
                        ncouts,
                        outputs_params,
                        is_climatology,
                    )

        finally:
            dsin.close()

        return ncouts

    def _load_and_prepare_dataset(self, nc_file: str) -> xr.Dataset:
        """
        Load and prepare a NetCDF dataset for processing.

        Parameters
        ----------
        nc_file
            Path to NetCDF file

        Returns
        -------
        Loaded and prepared xarray Dataset
        """
        dsin = xr.open_dataset(nc_file)

        # Handle depth coordinate if it has time dimension
        if "depth" in dsin.coords and "time" in dsin["depth"].dims:
            dsin = dsin.reset_coords("depth")

        # Optimize chunking for memory efficiency
        dsin = optimize_for_low_swap(dsin, target_chunk_mb=self.target_chunk_mb)

        return dsin

    def _process_metazone(
        self,
        dsin: xr.Dataset,
        metazone: str,
        mparams: Dict[str, Any],
        params: Optional[Dict],
        attrs_in: Dict[str, Any],
        ofmt: List[str],
        is_climatology: bool = False,
    ) -> Union[List[Path], Dict[str, List[Path]]]:
        """
        Process a dataset for a specific metazone.

        Parameters
        ----------
        dsin
            Input dataset
        metazone
            Name of the metazone
        mparams
            Metazone parameters
        params
            Interpolation parameters
        attrs_in
            Original dataset attributes
        ofmt
            Formats to save intermediate interpolated outputs
        is_climatology
            Whether this dataset's DataType is flagged as a climatology --
            forwarded to skip time interpolation/range-splitting, which
            don't apply to its month-of-year "time" axis.

        Returns
        -------
        List of output file paths, or a dict of {section_name: paths}
        when this metazone's horizontal interpolation is a multi-section
        ``section`` (see `_apply_interpolations`).
        """
        ds = dsin.copy()

        # Apply interpolations if needed
        if params:
            ds = self._apply_interpolations(ds, params, mparams, is_climatology)
        else:
            logger.info("No interpolation required")

        if isinstance(ds, dict):
            return {
                section_name: self._finalize_metazone_dataset(
                    ds_section,
                    metazone,
                    mparams,
                    attrs_in,
                    ofmt,
                    is_climatology,
                    section_name=section_name,
                )
                for section_name, ds_section in ds.items()
            }

        return self._finalize_metazone_dataset(
            ds, metazone, mparams, attrs_in, ofmt, is_climatology
        )

    def _finalize_metazone_dataset(
        self,
        ds: xr.Dataset,
        metazone: str,
        mparams: Dict[str, Any],
        attrs_in: Dict[str, Any],
        ofmt: List[str],
        is_climatology: bool = False,
        section_name: Optional[str] = None,
    ) -> List[Path]:
        """
        Restore attributes, clean up, range-process and save one metazone's
        interpolated dataset.

        Parameters
        ----------
        ds
            Interpolated dataset (a single metazone's, or one of a
            ``section`` horizontal interpolation's named datasets).
        metazone
            Name of the metazone
        mparams
            Metazone parameters
        attrs_in
            Original dataset attributes
        ofmt
            Formats to save intermediate interpolated outputs
        is_climatology
            Whether this dataset's DataType is flagged as a climatology
        section_name
            Name of the section this dataset was interpolated onto, if
            any -- forwarded to `_save_processed_datasets` as its own
            path segment, so multiple sections of the same metazone don't
            overwrite each other's output.

        Returns
        -------
        List of output file paths
        """
        ds.attrs.update(attrs_in)
        ds = self._cleanup_dataset(ds)

        # Compute and process ranges
        # with setup_dask_client():
        ds = ds.compute()
        dss = self._apply_range_processing(ds, mparams, is_climatology)

        # Save processed datasets
        return self._save_processed_datasets(dss, metazone, ofmt, section_name=section_name)

    def _apply_interpolations(
        self,
        ds: xr.Dataset,
        params: Dict[str, Any],
        mparams: Dict[str, Any],
        is_climatology: bool = False,
    ) -> xr.Dataset:
        """
        Apply various interpolations to the dataset.

        Parameters
        ----------
        ds
            Dataset to interpolate
        params
            Interpolation parameters
        mparams
            Metazone parameters
        is_climatology
            Whether this dataset's DataType is flagged as a climatology --
            its "time" isn't a real calendar date, so time interpolation
            is skipped for it regardless of the metazone's configuration.

        Returns
        -------
        Interpolated dataset
        """
        logger.info("Start interpolation")

        # Time interpolation -- ignored (not rejected) for a climatology
        # (see _apply_range_processing's identical guard).
        if params.get("time") and not is_climatology:
            ds = process_time_interpolation(ds, params.get("time"), mparams.get("tbound"))
            gc.collect()

        # Horizontal interpolation
        if params.get("horizontal"):
            ds = process_horizontal_interpolation(ds, params.get("horizontal"))
            gc.collect()

        if isinstance(ds, dict):
            return {
                name: self._apply_vertical_interpolation(ds_section, params)
                for name, ds_section in ds.items()
            }

        return self._apply_vertical_interpolation(ds, params)

    def _apply_vertical_interpolation(self, ds: xr.Dataset, params: Dict[str, Any]) -> xr.Dataset:
        """
        Apply vertical interpolation to a single dataset, if configured.

        Parameters
        ----------
        ds
            Dataset to interpolate
        params
            Interpolation parameters

        Returns
        -------
        Interpolated dataset
        """
        # Ignored for a dataset with no "z" at all (e.g. satellite SST),
        # even if the metazone configures it for the sake of another,
        # depth-resolved source.
        if params.get("vertical") and "z" in ds.dims:
            ds = process_vertical_interpolation(ds, params.get("vertical"))
            gc.collect()
        return ds

    def _cleanup_dataset(self, ds: xr.Dataset) -> xr.Dataset:
        """
        Remove unnecessary variables from dataset.

        Parameters
        ----------
        ds
            Dataset to clean up

        Returns
        -------
        Cleaned dataset
        """
        vars_to_drop = []
        for varname in ("bathy", "mask"):
            if varname in ds:
                vars_to_drop.append(varname)

        return ds.drop_vars(vars_to_drop, errors='ignore')

    def _apply_range_processing(
        self, ds: xr.Dataset, mparams: Dict[str, Any], is_climatology: bool = False
    ) -> List[xr.Dataset]:
        """
        Apply time and vertical range processing to dataset.

        Parameters
        ----------
        ds
            Dataset to process
        mparams
            Metazone parameters
        is_climatology
            Whether this dataset's DataType is flagged as a climatology --
            its "time" isn't a real calendar date, so tfreq/trange_seq are
            skipped for it regardless of the metazone's configuration.

        Returns
        -------
        List of processed datasets
        """
        # Time range processing -- ignored (not rejected) for a
        # climatology: its "time" is a month-of-year index, not a real
        # calendar date, so it can't be meaningfully split by day/range.
        if "tfreq" in mparams and not is_climatology:
            dss = ranges.tfreq(ds)
        elif "trange_seq" in mparams and not is_climatology:
            logger.info('Applying trange_seq...')
            try:
                dss = ranges.trange_seq(ds, *mparams.get("tbound"), mparams["trange_seq"]["tfreq"])
            except Exception:
                logger.info('Error for trange_seq. Maybe tbound was not defined in metazones.')
                sys.exit(1)
        else:
            dss = [ds]

        # Vertical level processing -- ignored (not rejected) for a
        # dataset with no "z" at all (e.g. satellite SST), even if the
        # metazone configures vlevel/vrange for another, depth-resolved
        # source.
        has_z = any("z" in ds0.dims for ds0 in dss)
        if "vlevel" in mparams and has_z:
            vname = mparams["vlevel"]["vname"]
            dss = ranges.vlevels(dss, vname)
        elif "vrange" in mparams and has_z:
            vname = mparams["vrange"]["vname"]
            vbins = list(zip(mparams["vrange"]["bins_min"], mparams["vrange"]["bins_max"]))
            dss = ranges.vrange(dss, vname, vbins)
        elif has_z:
            # Neither vlevel nor vrange configured: fall back to the
            # dataset's own native vertical levels (still one dataset per
            # level, like ranges.vlevels), so plots get one figure per
            # level instead of overlaying every native z index as a line.
            vname = next(
                (c for c in ("depth", "pres") if c in dss[0].coords or c in dss[0].data_vars),
                None,
            )
            if vname and not dss[0].attrs.get("fixed_levels", 1):
                # Terrain-following/hybrid grid (e.g. CROCO, HYCOM -- see
                # Decoder.fixed_levels): a native "z" index is not a depth
                # level, so splitting by it would flatten the real 3D depth
                # into one arbitrary value per index -- keep it whole.
                logger.info(
                    "Not splitting by native vertical levels: they are not "
                    "at fixed depths for this format. "
                    "Configure vlevel or vrange to select depths."
                )
            elif vname:
                dss = ranges.vlevels(dss, vname)

        return dss

    def _save_processed_datasets(
        self,
        dss: List[xr.Dataset],
        metazone: str,
        ofmt: List[str],
        section_name: Optional[str] = None,
    ) -> List[Path]:
        """
        Save processed datasets to disk.

        Parameters
        ----------
        dss
            List of datasets to save
        metazone
            Metazone name for directory structure
        ofmt
            Formats to save intermediate interpolated outputs
        section_name
            Name of the section these datasets were interpolated onto, if
            any -- inserted as its own path segment (``data_name`` is left
            untouched) so multiple sections of the same metazone land in
            separate directories instead of overwriting one another.

        Returns
        -------
        List of saved file paths
        """
        logger.info("Save interpolated data")

        # One thread per dataset-to-save, capped at --dask-nworkers and at
        # the number of datasets (same pattern as grid2loc()/
        # process_datasets()). With no vlevel/vrange configured,
        # _apply_range_processing() falls back to one dataset per native z
        # level -- dozens for a source like WOA18 (~57 levels) -- and each
        # was being written to its own zarr file one at a time: small,
        # independent, I/O-bound writes that used to run fully serially.
        import dask

        n_workers = max(min(dask.config.get('num_workers', default=1), len(dss)), 1)

        def _dirout(dsprod):
            if section_name is not None:
                return Path(f"data/interp/{metazone}/{section_name}/{dsprod.attrs['data_name']}")
            return Path(f"data/interp/{metazone}/{dsprod.attrs['data_name']}")

        # Every dataset is written in parallel with mode="w": two of them
        # mapping to the same file would wipe each other's zarr chunks
        # mid-write (surfacing as an obscure FileNotFoundError on a chunk
        # name like '0.0') -- fail early and clearly instead.
        targets = [_dirout(d) / f"prod{d.range.suffix}" for d in dss]
        dups = sorted({str(t) for t in targets if targets.count(t) > 1})
        if dups:
            raise ArmoorError(
                f"Several interpolated datasets would be saved to the same "
                f"file(s) {dups} for metazone {metazone!r}: their "
                "time/vlevel/vrange labels are not distinct."
            )

        def _save_one(dsprod):
            dirout = _dirout(dsprod)
            dirout.mkdir(parents=True, exist_ok=True)

            t0 = time.perf_counter()
            fout_prod = save_datasets(dsprod, dirout, dsprod.attrs['data_name'], ofmt)
            logger.debug(
                f"save_datasets({dsprod.attrs['data_name']!r}) took {time.perf_counter() - t0:.1f}s"
            )
            dsprod.close()
            return fout_prod

        try:
            with ThreadPoolExecutor(max_workers=n_workers) as pool:
                fouts = list(pool.map(_save_one, dss))
        finally:
            del dss

        return fouts

    def _generate_outputs(
        self,
        fouts: List[Path],
        metazone: str,
        mparams: Dict[str, Any],
        outputs: Dict[str, Any],
        prod_name: str,
        ncouts: Dict[str, Dict[str, List[Path]]],
        outputs_params: Dict[str, Any],
        is_climatology: bool = False,
        section_name: Optional[str] = None,
    ) -> Dict[str, Dict[str, List[Path]]]:
        """
        Generate output files for a metazone.

        Parameters
        ----------
        fouts
            List of intermediate file paths
        metazone
            Metazone name
        mparams
            Metazone parameters
        outputs
            Output configurations
        prod_name
            Product name
        ncouts
            Accumulator for output paths
        outputs_params
            Per-otype processing params for this dataset's data type
            (DataType.outputs_params -- see armoor.data.datatype)
        is_climatology
            Whether this dataset's DataType is flagged as a climatology
            (DataType.is_climatology) -- excludes it from otypes that
            shouldn't render a climatology's own series (see
            `_validate_output_compatibility`).
        section_name
            Name of the section `fouts` was interpolated onto, if any --
            forwarded to `_process_output_type` as its own path segment.

        Returns
        -------
        Updated ncouts dictionary
        """
        for oname, output in outputs.items():
            logger.info(f"Processing output: {oname}")

            # Check if output type is allowed and compatible
            if not self._validate_output_compatibility(
                output, mparams, metazone, outputs_params, is_climatology
            ):
                continue

            # Process this output type
            output_files = self._process_output_type(
                fouts,
                output,
                metazone,
                mparams,
                prod_name,
                oname,
                outputs_params,
                section_name=section_name,
            )

            # Add to results
            otype = output.get("otype")
            if output_files:
                if otype not in ncouts:
                    ncouts[otype] = {}
                if metazone not in ncouts[otype]:
                    ncouts[otype][metazone] = []
                ncouts[otype][metazone].extend(output_files)

        return ncouts

    def _validate_output_compatibility(
        self,
        output: Dict[str, Any],
        mparams: Dict[str, Any],
        metazone: str,
        outputs_params: Dict[str, Any],
        is_climatology: bool = False,
    ) -> bool:
        """
        Validate if an output type is compatible with the metazone parameters.

        Parameters
        ----------
        output
            Output configuration
        mparams
            Metazone parameters
        metazone
            Metazone name
        outputs_params
            Per-otype processing params for this dataset's data type
        is_climatology
            Whether this dataset's DataType is flagged as a climatology.

        Returns
        -------
        True if compatible, False otherwise
        """
        oparams = outputs_params.get(output.get("otype"))
        if not oparams:
            logger.warning(f"Skip {output.get('otype')}: forbidden")
            return False

        # A climatology is meant to be referenced by name (see "clim" in
        # data.ini) as a reference for other sources' mapseries, not to
        # render its own per-timestep series -- DataWoa18/DataBobyclim
        # deliberately don't fork outputs_params for this (see
        # test_datatype.py), so the exclusion lives here instead.
        if is_climatology and output.get("otype") == "mapseries":
            logger.info(f"Skip mapseries for climatology source ({metazone})")
            return False

        # Check required parameters
        if oparams.get("mparams_pro"):
            for dim, param in oparams.get("mparams_pro").items():
                if not bool(set(param) & set(mparams.keys())):
                    logger.info(
                        f"{output} cannot be processed for {metazone} due to missing {param}"
                    )
                    return False

        # Check conflicting parameters
        if oparams.get("mparams_con"):
            for dim, param in oparams.get("mparams_con").items():
                if bool(set(param) & set(mparams.keys())):
                    logger.info(
                        f"{output} cannot be processed for {metazone} due to conflicting {param}"
                    )
                    return False

        return True

    def _process_output_type(
        self,
        fouts: List[Path],
        output: Dict[str, Any],
        metazone: str,
        mparams: Dict[str, Any],
        prod_name: str,
        oname: str,
        outputs_params: Dict[str, Any],
        section_name: Optional[str] = None,
    ) -> List[Path]:
        """
        Process a specific output type.

        Parameters
        ----------
        fouts
            Input file paths
        output
            Output configuration
        metazone
            Metazone name
        mparams
            Metazone parameters
        prod_name
            Product name
        oname
            Output name
        outputs_params
            Per-otype processing params for this dataset's data type
        section_name
            Name of the section `fouts` was interpolated onto, if any --
            forwarded to `_process_sorted_group` as its own path segment.

        Returns
        -------
        List of generated output files
        """
        oparams = outputs_params.get(output.get("otype"))
        logger.info(f"Output parameters: {oparams}")

        sort_dim = oparams.get("sort")
        concat_dim = oparams.get("concat")

        fins_dict_sorted = sort_ncs_by_suffix(fouts, sort_dim=sort_dim)

        # One thread per sorted group, capped at --dask-nworkers and at the
        # number of groups (same pattern as grid2loc()/process_datasets()/
        # _save_processed_datasets()). A metazone with e.g. one otype
        # output per native z level (see _apply_range_processing) can have
        # dozens of independent groups here, each reading its own input
        # files and writing its own output path -- these used to run one
        # at a time.
        import dask

        n_workers = max(min(dask.config.get('num_workers', default=1), len(fins_dict_sorted)), 1)

        def _process_one(item):
            name_sort, fins_sorted = item
            logger.info(f"Processing sorted group: {name_sort}")
            return self._process_sorted_group(
                fins_sorted,
                oparams,
                mparams,
                output,
                metazone,
                oname,
                name_sort,
                prod_name,
                concat_dim,
                section_name=section_name,
            )

        with ThreadPoolExecutor(max_workers=n_workers) as pool:
            output_files = [f for f in pool.map(_process_one, fins_dict_sorted.items()) if f]

        return output_files

    def _process_sorted_group(
        self,
        fins_sorted: List[Path],
        oparams: Dict[str, Any],
        mparams: Dict[str, Any],
        output: Dict[str, Any],
        metazone: str,
        oname: str,
        name_sort: str,
        prod_name: str,
        concat_dim: List[str],
        section_name: Optional[str] = None,
    ) -> Optional[Path]:
        """
        Process a sorted group of files to create a single output.

        Parameters
        ----------
        fins_sorted
            Sorted list of input files
        oparams
            Output parameters
        mparams
            Metazone parameters
        output
            Output configuration (otype plus any optional output params,
            e.g. used by `_compute_diags` for otype-specific diagnostics)
        metazone
            Metazone name
        oname
            Output name
        name_sort
            Sorted group name
        prod_name
            Product name
        concat_dim
            Concatenation dimensions
        section_name
            Name of the section these files were interpolated onto, if
            any -- forwarded to `_save_datatree_output` as its own path
            segment.

        Returns
        -------
        Path to generated output file, or None if failed
        """
        # Load datasets
        dss = [xr.open_dataset(fin) for fin in fins_sorted]

        try:
            # Get data trees with statistics
            dts0 = get_datatrees(dss, oparams.get("stat"), mparams)
            del dss

            # Process each dataset in the tree
            dsouts = {}
            for ds_name in dts0[0].keys():
                ds = self._process_tree_dataset(dts0, ds_name, concat_dim, output)
                self._attach_clim_range(ds, metazone, output)
                self._attach_cbar_range(ds, metazone, output)
                self._attach_series_range(ds, metazone, prod_name, output)
                dsouts[ds_name] = ds

            del dts0

            # Save as zarr
            return self._save_datatree_output(
                dsouts,
                metazone,
                oname,
                name_sort,
                prod_name,
                section_name=section_name,
            )

        except Exception as e:
            logger.error(f"Failed to process sorted group {name_sort}: {e}")
            return None

    def _process_tree_dataset(
        self, dts0: List[Any], ds_name: str, concat_dim: List[str], output: Dict[str, Any]
    ) -> xr.Dataset:
        """
        Process a single dataset from the data tree.

        Parameters
        ----------
        dts0
            List of data trees
        ds_name
            Name of dataset to extract
        concat_dim
            Concatenation dimensions
        output
            Output configuration (otype plus any optional output params)

        Returns
        -------
        Processed dataset
        """
        dss0 = [dt[ds_name].to_dataset() for dt in dts0]

        if concat_dim == ["time"]:
            # Handle time concatenation
            if dss0[0].sizes["time"] > 1:
                # Split multi-time datasets into individual time slices
                dss1 = []
                for ds0 in dss0:
                    dss1.extend([ds0.isel(time=itime) for itime in range(ds0.sizes["time"])])
                dss0 = dss1

            ds = xr.concat(dss0, "time")
            ds = self._recompute_trange_attr(ds)

            # Handle vrange attributes specifically
            if dss0[0].range.vrange_value:
                vrange_attrs = [ds0.range.vrange_value for ds0 in dss0]
                ds.attrs["vrange"] = vrange_attrs

        elif concat_dim == ["obs"]:
            ds = xr.concat(dss0, "obs").sortby("time")

        elif concat_dim and set(concat_dim) <= {"time", "z"}:
            ds = self._concat_time_z(dss0, concat_dim)

        elif len(dss0) == 1:
            ds = dss0[0]
        else:
            raise ArmoorError("Multi-dataset concatenation not implemented")

        ds = self._compute_diags(ds, output["otype"])

        attrs = {k: v for k, v in output.items() if k != "otype"}
        ds = ds.assign_attrs(attrs)

        return ds

    def _concat_time_z(self, dss0: List[xr.Dataset], concat_dim: List[str]) -> xr.Dataset:
        """
        Merge datasets split along "time" and/or "z" back into one.

        Each input in `dss0` is one time-group and/or one vlevel-group
        produced upstream by `_apply_range_processing` (via `ranges.tfreq`/
        `trange_seq` and `ranges.vlevels`); this reassembles them along
        whichever of "time"/"z" is requested so an otype like ``mdiagts``
        can render a single figure over the full dataset with no residual
        splitting and no per-dim looping in the plot function itself.

        Parameters
        ----------
        dss0
            Datasets to merge, one per upstream time/z group.
        concat_dim
            Subset of ``["time", "z"]`` naming the dims to reassemble.

        Returns
        -------
        xarray.Dataset
            A single dataset spanning every group along `concat_dim`.
        """
        dss = dss0
        if "time" in concat_dim:
            expanded = []
            for ds0 in dss:
                if ds0.sizes.get("time", 1) > 1:
                    expanded.extend(ds0.isel(time=[itime]) for itime in range(ds0.sizes["time"]))
                else:
                    expanded.append(ds0)
            dss = expanded

        if "z" in concat_dim:
            if "time" in concat_dim:
                groups = {}
                for ds0 in dss:
                    key = pd.Timestamp(ds0.time.values[0])
                    groups.setdefault(key, []).append(ds0)
                dss = [self._merge_z_group(g) for g in groups.values()]
            else:
                dss = [self._merge_z_group(dss)]

        if "time" in concat_dim:
            dss = sorted(dss, key=lambda d: pd.Timestamp(d.time.values[0]))
            ds = xr.concat(dss, "time")
            ds = self._recompute_trange_attr(ds)
            if dss[0].range.vrange_value:
                ds.attrs["vrange"] = [d0.range.vrange_value for d0 in dss]
        else:
            ds = dss[0]

        return ds

    def _merge_z_group(self, group: List[xr.Dataset]) -> xr.Dataset:
        """Merge one time-slice's z-split fragments back into one dataset.

        Native/explicit vlevel fragments (tagged via ``attrs["vlevel"]``)
        each cover a distinct, non-overlapping depth -- concatenating them
        along "z" reconstructs the full profile. vrange bins (tagged via
        ``attrs["vrange"]``) instead each keep the *same* full native
        depth range, just NaN-masked outside their own bin -- concatenating
        those along "z" would duplicate every depth value instead of
        reconstructing anything, so they're combined with `combine_first`
        (first non-null value wins) instead.

        Parameters
        ----------
        group
            Datasets covering the same time-slice, one per z-fragment.

        Returns
        -------
        xarray.Dataset
            A single dataset spanning every fragment's depth.
        """
        if len(group) == 1:
            return group[0]
        if "depth" in group[0].variables:
            depths = [tuple(np.round(np.asarray(g["depth"]).ravel(), 6)) for g in group]
            if len(set(depths)) == 1:
                merged = group[0]
                for g in group[1:]:
                    merged = merged.combine_first(g)
                merged.attrs = group[0].attrs
                return merged

        def by_vlevel(ds0: xr.Dataset) -> float:
            """Sort key: a fragment's own "vlevel" attr (0 if unset)."""
            return float(ds0.attrs.get("vlevel", 0))

        ds = xr.concat(sorted(group, key=by_vlevel), dim="z")
        # xr.concat keeps attrs from just the first fragment by default,
        # so "vlevel" would otherwise still name that one native/explicit
        # level even though every level has now been merged into one
        # full profile -- drop it so titles/filenames built from attrs
        # don't claim a single depth that no longer applies.
        ds.attrs.pop("vlevel", None)
        return ds

    def _recompute_trange_attr(self, ds: xr.Dataset) -> xr.Dataset:
        """Recompute a stale "trange" attr after merging along "time".

        `xr.concat` keeps attrs from just the first input by default, so a
        "trange" tag (set per trange_seq bucket by `ranges.trange_seq`)
        would otherwise still show only the first bucket's bounds once
        every bucket has been merged into one otype like `mvprofiles` --
        recompute it from the actual merged "time" span instead.

        Parameters
        ----------
        ds
            Dataset just concatenated along "time".

        Returns
        -------
        xarray.Dataset
            `ds`, with "trange" (if present) reflecting the full span.
        """
        if "trange" in ds.attrs and "time" in ds.dims and ds.sizes["time"] > 1:
            t1 = pd.Timestamp(ds.time.min().values)
            t2 = pd.Timestamp(ds.time.max().values)
            ds.attrs["trange"] = f"[{t1:%Y-%m-%dT%H:%M:%S}_{t2:%Y-%m-%dT%H:%M:%S}["
        return ds

    def _compute_diags(self, ds: xr.Dataset, output_type: str) -> xr.Dataset:
        """
        Compute any armoor.diags statistics appropriate for this output type.

        Each diagnostic is added as new variable(s) in the dataset.

        Parameters
        ----------
        ds
            Dataset to augment.
        output_type
            The output's otype (e.g. ``"pdf_eddies"``).

        Returns
        -------
        xarray.Dataset
            `ds`, with any applicable diagnostics added.
        """
        from armoor.diags.eddies import compute_vars

        ds = compute_vars(ds)

        if output_type == "pdf_eddies":
            from armoor.diags.eddies import pdf

            ds = pdf(ds)

        return ds

    def _save_datatree_output(
        self,
        dsouts: Dict[str, xr.Dataset],
        metazone: str,
        oname: str,
        name_sort: str,
        prod_name: str,
        section_name: Optional[str] = None,
    ) -> Path:
        """
        Save processed datasets as a DataTree zarr file.

        Parameters
        ----------
        dsouts
            Dictionary of datasets to save
        metazone
            Metazone name
        oname
            Output name
        name_sort
            Sorted group name
        prod_name
            Product name
        section_name
            Name of the section these datasets were interpolated onto, if
            any -- inserted as its own path segment (so multiple sections
            of the same metazone don't overwrite each other's output) and
            recorded as a ``section_name`` attr on each dataset (read back
            by `armoor.data.plot.PlotOceanModel.vsections` for the title
            and filename).

        Returns
        -------
        Path to saved file
        """
        if section_name is not None:
            dirout = Path(f"data/output/{metazone}/{oname}/{section_name}/{name_sort}/")
            for ds_out in dsouts.values():
                ds_out.attrs["section_name"] = section_name
        else:
            dirout = Path(f"data/output/{metazone}/{oname}/{name_sort}/")
        dirout.mkdir(parents=True, exist_ok=True)

        # Create DataTree and save
        dt = xr.DataTree()
        dt.update(xr.DataTree.from_dict(dsouts))

        ncout = dirout / f"{prod_name}.zarr"
        encoding = get_zarr_encoding(dt)

        logger.info(f"Saving output: {ncout}")
        dt.to_zarr(ncout, mode="w", encoding=encoding)

        return ncout


# Convenience function for backward compatibility
def main_output(
    ncs: List[str], metazones: Dict[str, Any], outputs: Dict[str, Any]
) -> Dict[str, Dict[str, List[Path]]]:
    """
    Main function for processing NetCDF datasets with interpolation and output generation.

    This function processes a list of NetCDF files according to specified metazone
    configurations and generates various output formats.

    Parameters
    ----------
    ncs
        List of paths to NetCDF files to process
    metazones
        Dictionary containing metazone configurations with parameters
              for interpolation, time/vertical ranges, etc.
    outputs
        Dictionary containing output configurations. The 'fmt' key will
            be removed if present.

    Returns
    -------
    Dictionary mapping output names to metazones to lists of output file paths.
    Structure
        {output_name: {metazone_name: [file_path1, file_path2, ...]}}

    Raises
    ------
    ArmoorError
        When processing fails due to configuration or data issues

    Examples
    --------
    >>> ncs = ['data1.nc', 'data2.nc']
    >>> metazones = {
    ...     'zone1': {'tbound': ['2020-01-01', '2020-12-31']},
    ...     'zone2': {'vlevel': ['surface']}
    ... }
    >>> outputs = {'monthly': {'otype': 'timeseries'}}
    >>> result = main_output(ncs, metazones, outputs)
    >>> print(result)
    {'timeseries': {'zone1': [Path('data/output/zone1/monthly/...')], ...}}
    """
    processor = OutputProcessor()
    return processor.process_datasets(ncs, metazones, outputs)
