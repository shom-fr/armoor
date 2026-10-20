import logging
from typing import List, Optional, Tuple, Dict

import dask
import numpy as np
import pandas as pd
import xarray as xr

from armoor import stats

logger = logging.getLogger(__name__)


class StatsComp:
    """
    Statistical comparison engine for model vs reference datasets.

    Computes summary statistics (mean, std, bias, RMSE, centered RMSE, correlation)
    over specified dimensions and organizes results into `xarray.DataTree` objects.

    Parameters
    ----------
    mparams : dict
        Metadata or control parameters determining behavior (e.g. range handling).
    dsprod : xarray.Dataset
        Product dataset to evaluate.
        If it includes a ``member`` dimension, members are averaged before comparison.
    dsref : xarray.Dataset
        Reference dataset to compare against.
    dims : list of str
        Dimensions over which to compute statistics (e.g., ``["time", "z"]``).
    extra_dims : list of str or None, optional
        Additional dimensions for future processing (not directly used here).
    exclude_dims : list of str or None, optional
        Dimensions to exclude from processing.

    Attributes
    ----------
    dtref : xarray.DataTree
        Tree holding reference statistics.
    dtprod : xarray.DataTree
        Tree holding product statistics.
    dtcomps : xarray.DataTree
        Tree holding comparison results.
    """

    def __init__(
        self,
        mparams: dict,
        dsprod: xr.Dataset,
        dsref: xr.Dataset,
        dims: Optional[List[str]],
        extra_dims: Optional[List[str]] = None,
        exclude_dims: Optional[List[str]] = None,
    ):
        self.mparams = mparams
        self.dsref = dsref

        dims = list(dims) if dims else []
        # CompClim's forced "tmonth" colocation (see armoor.comp.coloc.
        # TimeColocation.tmonth) is the one time strategy that never shows up
        # as a literal metazone.cfg key ("trange_seq"/"tfreq" are both user-
        # optional and comp_clim doesn't accept either) -- so _filter_dims
        # can't recognize it from mparams alone. It does leave a distinctive
        # mark on the data though: a plain-integer "time" coordinate (the
        # 1-12 calendar month index), unlike every other strategy's
        # datetime64 "time". Detect that instead of adding a mparams key.
        is_climatology = "time" in dsref.dims and np.issubdtype(dsref["time"].dtype, np.integer)
        self.dims = self._filter_dims(dims, self.mparams, is_climatology=is_climatology)
        self.extra_dims = extra_dims
        self.exclude_dims = exclude_dims

        # "prod/data" keeps the raw, member-resolved dataset -- some outputs
        # (e.g. mvprofiles/uvprofiles) plot one line per matched member on
        # purpose. But the diff/stats math below (self.dsprod) must use the
        # matched points' mean -- unconditionally: the "diff" comp group
        # (used when self.dims is empty, e.g. otype=maps) must already be a
        # difference against that mean, not a per-member value, regardless
        # of whether further stats dims follow.
        self.dtref = xr.DataTree(name="ref")
        self.dtref.update(xr.DataTree.from_dict({"data": dsref}))
        self.dtprod = xr.DataTree(name="prod")
        self.dtprod.update(xr.DataTree.from_dict({"data": dsprod}))
        self.dtcomps = xr.DataTree(name="comps")

        if "member" in dsprod.dims:
            logger.info("Averaging product dataset across 'member' dimension.")
            dsprod = (
                dsprod.reset_coords(["lon", "lat"]).mean(dim="member").set_coords(["lon", "lat"])
            )
        self.dsprod = dsprod

    # -------------------------------------------------------------------------
    # Main execution
    # -------------------------------------------------------------------------

    def compute(self) -> Tuple[xr.DataTree, xr.DataTree, Optional[xr.DataTree]]:
        """
        Run statistical comparison.

        Returns
        -------
        tuple
            (product_tree, reference_tree, comparison_tree or None)
        """
        if not self.dims:
            logger.debug("No dimensions to reduce. Returning direct diff.")
            return self.get_diff()
        logger.debug(f"Computing statistics along dims={self.dims}")
        return self.get_stats(self.dims)

    # -------------------------------------------------------------------------

    @staticmethod
    def _filter_dims(dims: List[str], mparams: Dict, is_climatology: bool = False) -> List[str]:
        """
        Filter dimensions based on mparams context rules.

        Parameters
        ----------
        dims : list of str
            Dimensions requested by user.
        is_climatology : bool, optional
            True when "time" is a plain calendar-month index (comp_clim's
            forced "tmonth" colocation) rather than a real datetime axis --
            see the call site in `__init__`. That strategy never appears as
            a literal metazone.cfg key, so it can't be recognized below the
            same way "trange_seq" is; without this, otype=maps' explicit
            `"stat": ["time"]` request was silently dropped and a real,
            multi-month "time" dim reached pcolormesh unreduced.

        Returns
        -------
        list of str
            Filtered list of valid dimensions.
        """
        dims = list(dims)

        def safe_remove(val):
            """Remove `val` from `dims` if present; no-op otherwise."""
            if val in dims:
                dims.remove(val)

        # Time only if trange_seq (or comp_clim's tmonth climatology, see above)
        if "time" in dims and "trange_seq" not in mparams and not is_climatology:
            safe_remove("time")

        # Vertical only if vrange
        if "z" in dims and "vrange" not in mparams:
            safe_remove("z")

        # Horizontal grid only if exists
        if "x" in dims and "x" not in dims:
            safe_remove("x")
            safe_remove("y")

        return dims

    # -------------------------------------------------------------------------

    def get_stats(self, dims: List[str]):
        """
        Compute mean/std and comparison metrics along dimensions.

        All 7 statistics are built as a single lazy dask graph and computed
        in one ``dask.compute()`` call so the scheduler can share work
        (e.g. the common ``diff = dsprod - dsref``).

        Parameters
        ----------
        dims : list of str
            Dimensions to reduce.

        Returns
        -------
        tuple
            (product_tree, reference_tree, comparison_tree)
        """
        # Filter dims to only those that are actual dimensions in both datasets.
        # Scalar coordinates (e.g. z=10.0 when data is already at a fixed depth)
        # have ndim=0 and cannot be reduced — they must be excluded.
        available_dims = set(self.dsref.dims) & set(self.dsprod.dims)
        dims = [d for d in dims if d in available_dims]
        if not dims:
            logger.debug("No reducible dimensions after filtering. Returning direct diff.")
            return self.get_diff()
        logger.debug("Effective reduction dims after filtering: %s", dims)

        # Build shared lazy computations
        diff = self.dsprod - self.dsref
        ref_mean = self.dsref.mean(dim=dims)
        ref_std = self.dsref.std(dim=dims)
        prod_mean = self.dsprod.mean(dim=dims)
        prod_std = self.dsprod.std(dim=dims)
        comp_bias = diff.mean(dim=dims)
        comp_rmse = np.sqrt((diff**2).mean(dim=dims))
        cdiff = (self.dsprod - prod_mean) - (self.dsref - ref_mean)
        comp_rmsec = np.sqrt((cdiff**2).mean(dim=dims))
        comp_corr = stats.corr(self.dsprod, self.dsref, dims)

        # Single dask.compute() call for all stats
        (ref_mean, ref_std, prod_mean, prod_std, comp_bias, comp_rmse, comp_rmsec, comp_corr) = (
            dask.compute(
                ref_mean, ref_std, prod_mean, prod_std, comp_bias, comp_rmse, comp_rmsec, comp_corr
            )
        )

        # Update trees with computed results
        self._update_tree(self.dtref, "mean", ref_mean)
        self._update_tree(self.dtref, "std", ref_std)
        self._update_tree(self.dtprod, "mean", prod_mean)
        self._update_tree(self.dtprod, "std", prod_std)
        self._update_tree(self.dtcomps, "bias", comp_bias)
        self._update_tree(self.dtcomps, "rmse", comp_rmse)
        self._update_tree(self.dtcomps, "rmsec", comp_rmsec)
        self._update_tree(self.dtcomps, "corr", comp_corr)

        # Handle time aggregation for trange view
        if "trange_seq" in self.mparams and "time" in dims:
            trange_value = self.dsprod.range.trange
            if trange_value:
                logger.debug("Assigning trange time coordinate: %s", trange_value)
                self._apply_time_coord(trange_value)

        return self.dtprod, self.dtref, self.dtcomps

    # -------------------------------------------------------------------------

    @staticmethod
    def _update_tree(tree: xr.DataTree, name: str, ds: xr.Dataset):
        """Insert dataset into a DataTree child node."""
        tree.update(xr.DataTree.from_dict({name: ds}))

    @staticmethod
    def _mean_preserving_coords(ds: xr.Dataset, dim: str) -> xr.Dataset:
        """Reduce over `dim`, keeping any coordinate that depends on it.

        xarray silently drops non-index coordinates that depend on a
        reduced dimension instead of averaging them (e.g. a drifter's
        real per-observation lat/lon, which vary with "time") -- reset
        them to data variables first so they survive the reduction as
        an averaged position, then restore their coordinate status.
        """
        coord_deps = [c for c in ds.coords if c != dim and dim in ds[c].dims]
        if coord_deps:
            ds = ds.reset_coords(coord_deps)
        ds_mean = ds.mean(dim)
        if coord_deps:
            ds_mean = ds_mean.set_coords(coord_deps)
        return ds_mean

    # -------------------------------------------------------------------------

    def _apply_time_coord(self, timestamp):
        """Apply a single time coordinate after collapse."""
        for tree in [self.dtref, self.dtprod, self.dtcomps]:
            for key, node in list(tree.items()):
                if key == "data":
                    continue
                ds = node.to_dataset()
                ds = self._assign_single_time(ds, timestamp)
                tree.update(xr.DataTree.from_dict({key: ds}))

    @staticmethod
    def _assign_single_time(ds: xr.Dataset, timestamp) -> xr.Dataset:
        """
        Replace time dimension with single timestamp coordinate.

        Parameters
        ----------
        ds : xarray.Dataset
            Dataset to modify.
        timestamp : datetime-like
            Timestamp to assign.

        Returns
        -------
        xarray.Dataset
        """
        if "time" in ds.dims:
            ds = ds.drop_dims("time")
        if "time" in ds.coords:
            ds = ds.drop_vars("time")

        ds = ds.expand_dims("time")

        t1, t2 = [pd.to_datetime(t) for t in timestamp.strip('[').split('_')]
        med_time = t1 + 0.5 * (t2 - t1)

        ds = ds.assign_coords(time=[med_time.as_unit("ns")])
        return ds

    # -------------------------------------------------------------------------

    def get_diff(self):
        """
        Compute direct difference (no reduction).

        When the reference is a single-time climatology (e.g. WOA18) and the
        product has multiple time steps, their time coordinates will not align
        and a naive subtraction returns an empty dataset.  In that case we
        reduce the product over time first (temporal mean) so the comparison
        becomes spatial-only and remains meaningful.

        Returns
        -------
        tuple
            (product_tree, reference_tree, comparison_tree)
        """
        dsprod = self.dsprod
        dsref = self.dsref

        if "time" in dsprod.dims and "time" in dsref.dims:
            common_times = np.intersect1d(dsprod.time.values, dsref.time.values)
            if len(common_times) == 0:
                # No overlapping time steps — reduce both over time to obtain a
                # meaningful spatial comparison (e.g. model mean vs WOA18 month).
                logger.debug(
                    "get_diff: no common time steps between prod (%d) and ref (%d) — "
                    "reducing both over time before diff",
                    dsprod.sizes["time"],
                    dsref.sizes["time"],
                )
                dsprod_mean = self._mean_preserving_coords(dsprod, "time")
                dsref_mean = self._mean_preserving_coords(dsref, "time")
                # Store climatology month in attrs so plot.py can label axes.
                # WOA18 time is encoded as a float month index (e.g. 4.0) stored
                # without CF units, which xarray decodes as N nanoseconds — so
                # the int64 value equals the month number directly.
                if "time" in dsref.dims and dsref.sizes["time"] >= 1:
                    t_ns = int(np.int64(dsref.time.values[0]))
                    if 1 <= t_ns <= 12:
                        dsref_mean.attrs["clim_month"] = t_ns
                diff_ds = stats.diff(dsprod_mean, dsref_mean)
                self.dtprod.update(xr.DataTree.from_dict({"data": dsprod_mean}))
                self.dtref.update(xr.DataTree.from_dict({"data": dsref_mean}))
                self._update_tree(self.dtcomps, "diff", diff_ds)
                return self.dtprod, self.dtref, self.dtcomps

        diff_ds = stats.diff(dsprod, dsref)
        self._update_tree(self.dtcomps, "diff", diff_ds)
        return self.dtprod, self.dtref, self.dtcomps
