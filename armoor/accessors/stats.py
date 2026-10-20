"""ds.stats accessor - thin facade over armoor.stats and armoor.comp.stats.

All computation lives in those modules; this accessor only wires them
onto xr.Dataset and handles the ``dim=None`` (point-wise) fallback.

    ds.stats.mean(dim="time")            # base.stats.mean
    ds.stats.std(dim="time")             # base.stats.std
    ds.stats.bias(ds_ref)                # base.stats.diff  (point-wise)
    ds.stats.bias(ds_ref, dim="time")    # base.stats.bias
    ds.stats.rmse(ds_ref, dim="time")    # base.stats.rms
    ds.stats.rmsec(ds_ref, dim="time")   # base.stats.crms
    ds.stats.corr(ds_ref, dim="time")    # base.stats.corr
    ds.stats.compare(ds_ref, dims=[...]) # comp.stats.StatsComp
"""

import numpy as np
import xarray as xr

from armoor import stats as _stats


@xr.register_dataset_accessor("stats")
class StatsAccessor:
    """Statistical accessor for xr.Dataset.

    Simple reductions (mean, std) return an xr.Dataset and support chaining
    (e.g. ``ds.stats.mean(dim="time").plot.maps()``).

    Comparison metrics (bias, rmse, rmsec, corr) accept a reference dataset.
    When *dim* is omitted they return a point-wise result (same shape as the
    input); when *dim* is given they reduce along that dimension.

    :meth:`compare` delegates to :class:`armoor.comp.stats.StatsComp` for the
    full bias / RMSE / centered-RMSE DataTree workflow.
    """

    def __init__(self, obj):
        self._obj = obj

    # ------------------------------------------------------------------
    # Reductions
    # ------------------------------------------------------------------

    def mean(self, dim=None) -> xr.Dataset:
        """Mean over *dim* (all dims if omitted).

        Delegates to :func:`armoor.stats.mean`.
        """
        return _stats.mean(self._obj, dim)

    def std(self, dim=None) -> xr.Dataset:
        """Standard deviation over *dim* (all dims if omitted).

        Delegates to :func:`armoor.stats.std`.
        """
        return _stats.std(self._obj, dim)

    # ------------------------------------------------------------------
    # Comparison metrics
    # ------------------------------------------------------------------

    def bias(self, ds_ref: xr.Dataset, dim=None) -> xr.Dataset:
        """Bias (prod - ref).

        * ``dim=None`` - point-wise difference via :func:`armoor.stats.diff`.
        * ``dim=...``  - mean bias via :func:`armoor.stats.bias`.
        """
        if dim is None:
            return _stats.diff(self._obj, ds_ref)
        return _stats.bias(self._obj, ds_ref, dim)

    def rmse(self, ds_ref: xr.Dataset, dim=None) -> xr.Dataset:
        """Root-mean-square error.

        * ``dim=None`` - point-wise ``|prod - ref|`` via :func:`armoor.stats.diff`.
        * ``dim=...``  - RMSE via :func:`armoor.stats.rms`.
        """
        if dim is None:
            return np.sqrt(_stats.diff(self._obj, ds_ref) ** 2)
        return _stats.rms(self._obj, ds_ref, dim)

    def rmsec(self, ds_ref: xr.Dataset, dim=None) -> xr.Dataset:
        """Centered (unbiased) RMSE.

        * ``dim=None`` - point-wise via :func:`armoor.stats.diff` on anomalies.
        * ``dim=...``  - centered RMSE via :func:`armoor.stats.crms`.
        """
        if dim is None:
            d = _stats.diff(self._obj - self._obj.mean(), ds_ref - ds_ref.mean())
            return np.sqrt(d**2)
        return _stats.crms(self._obj, ds_ref, dim)

    def corr(self, ds_ref: xr.Dataset, dim=None) -> xr.Dataset:
        """Pearson correlation with the reference over *dim* (all dims if omitted).

        Delegates to :func:`armoor.stats.corr`.
        """
        return _stats.corr(self._obj, ds_ref, dim)

    # ------------------------------------------------------------------
    # Full comparison workflow
    # ------------------------------------------------------------------

    def compare(self, ds_ref: xr.Dataset, dims=None, mparams=None):
        """Full statistical comparison via :class:`armoor.comp.stats.StatsComp`.

        Parameters
        ----------
        ds_ref : xr.Dataset
            Reference dataset.
        dims : list of str, optional
            Dimensions to reduce (e.g. ``["time", "z"]``).
        mparams : dict, optional
            Metadata parameters forwarded to ``StatsComp`` (controls which dims
            are actually reduced).  Defaults to ``{}``.

        Returns
        -------
        tuple
            ``(dtprod, dtref, dtcomps)`` - three :class:`xr.DataTree` objects.
        """
        from armoor.comp.stats import StatsComp

        return StatsComp(
            mparams=mparams or {},
            dsprod=self._obj,
            dsref=ds_ref,
            dims=dims,
        ).compute()
