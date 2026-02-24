import logging
from typing import List, Optional, Tuple, Dict

import dask
import numpy as np
import pandas as pd
import xarray as xr

from armoor.base import stats

logger = logging.getLogger(__name__)


class StatsComp:
    """
    Statistical comparison engine for model vs reference datasets.

    Computes summary statistics (mean, std, bias, RMSE, centered RMSE)
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
        self.dims = self._filter_dims(dims, self.mparams)
        self.extra_dims = extra_dims
        self.exclude_dims = exclude_dims
        
        # Mean over ensemble members if present
        if "member" in dsprod.dims and len(self.dims) > 0:
            logger.info("Averaging product dataset across 'member' dimension.")
            dsprod = (
                dsprod.reset_coords(["lon", "lat"])
                .mean(dim="member")
                .set_coords(["lon", "lat"])
                )
        self.dsprod = dsprod

        self.dtref = xr.DataTree(name="ref")
        self.dtref.update(
            xr.DataTree.from_dict({"data": dsref})
        )
        self.dtprod = xr.DataTree(name="prod")
        self.dtprod.update(
            xr.DataTree.from_dict({"data": dsprod})
        )
        self.dtcomps = xr.DataTree(name="comps")

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
    def _filter_dims(dims: List[str], mparams: Dict) -> List[str]:
        """
        Filter dimensions based on mparams context rules.

        Parameters
        ----------
        dims : list of str
            Dimensions requested by user.

        Returns
        -------
        list of str
            Filtered list of valid dimensions.
        """
        dims = list(dims)

        def safe_remove(val):
            if val in dims:
                dims.remove(val)

        # Time only if trange_seq
        if "time" in dims and "trange_seq" not in mparams:
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
        # Build shared lazy computations
        diff = self.dsprod - self.dsref

        ref_mean = self.dsref.mean(dim=dims)
        ref_std = self.dsref.std(dim=dims)
        prod_mean = self.dsprod.mean(dim=dims)
        prod_std = self.dsprod.std(dim=dims)
        comp_bias = diff.mean(dim=dims)
        comp_rmse = np.sqrt((diff ** 2).mean(dim=dims))
        cdiff = (self.dsprod - prod_mean) - (self.dsref - ref_mean)
        comp_rmsec = np.sqrt((cdiff ** 2).mean(dim=dims))

        # Single dask.compute() call for all stats
        (ref_mean, ref_std, prod_mean, prod_std,
         comp_bias, comp_rmse, comp_rmsec) = dask.compute(
            ref_mean, ref_std, prod_mean, prod_std,
            comp_bias, comp_rmse, comp_rmsec
        )

        # Update trees with computed results
        self._update_tree(self.dtref, "mean", ref_mean)
        self._update_tree(self.dtref, "std", ref_std)
        self._update_tree(self.dtprod, "mean", prod_mean)
        self._update_tree(self.dtprod, "std", prod_std)
        self._update_tree(self.dtcomps, "bias", comp_bias)
        self._update_tree(self.dtcomps, "rmse", comp_rmse)
        self._update_tree(self.dtcomps, "rmsec", comp_rmsec)

        # Handle time aggregation for trange view
        if "trange_seq" in self.mparams and "time" in dims:
            trange_value = self.dsprod.attrs.get("trange")
            if trange_value:
                logger.debug("Assigning trange time coordinate: %s", trange_value)
                self._apply_time_coord(trange_value)

        return self.dtprod, self.dtref, self.dtcomps

    # -------------------------------------------------------------------------

    @staticmethod
    def _update_tree(tree: xr.DataTree, name: str, ds: xr.Dataset):
        """Insert dataset into a DataTree child node."""
        tree.update(xr.DataTree.from_dict({name: ds}))

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
        ds = ds.assign_coords(time=[pd.to_datetime(timestamp).as_unit("ns")])
        return ds

    # -------------------------------------------------------------------------

    def get_diff(self):
        """
        Compute direct difference (no reduction).

        Returns
        -------
        tuple
            (product_tree, reference_tree, comparison_tree)
        """
        self._update_tree(self.dtcomps, "diff", stats.diff(self.dsprod, self.dsref))
        return self.dtprod, self.dtref, self.dtcomps