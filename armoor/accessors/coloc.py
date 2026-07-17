"""ds.coloc accessor — colocation with a reference dataset.

Usage
-----
>>> session = ds_prod.coloc.with_ref(ds_ref)
>>> ds_prod2, ds_ref2 = session.time(("trange_seq", {"tfreq": "3D", "tref": "reference"}), tbound=tbound)
>>> session2 = session.time(...).horizontal(...)
>>> ds_prod3, ds_ref3 = session2.vertical(("vrange", {"vref": "reference", "vname": "depth", ...}))

ColocSession supports chaining and iteration unpacking:
>>> ds_p, ds_r = ds_prod.coloc.with_ref(ds_ref).time(param)
"""

import xarray as xr

from armoor.comp.coloc import (
    process_horizontal_colocation,
    process_time_colocation,
    process_vertical_colocation,
)


class ColocSession:
    """Holds a (prod, ref) pair through the colocation pipeline.

    Supports method chaining and direct unpacking:
    >>> prod, ref = session.time(param, tbound)
    """

    def __init__(self, ds_prod: xr.Dataset, ds_ref: xr.Dataset):
        self._prod = ds_prod
        self._ref = ds_ref

    # ------------------------------------------------------------------
    # Iteration unpacking: prod, ref = session
    # ------------------------------------------------------------------

    def __iter__(self):
        return iter((self._prod, self._ref))

    # ------------------------------------------------------------------
    # Colocation steps — each returns a new ColocSession for chaining
    # ------------------------------------------------------------------

    def time(self, param, tbound=None):
        """Apply time colocation.

        Parameters
        ----------
        param : tuple
            E.g. ``("trange_seq", {"tfreq": "3D", "tref": "reference"})`` or
            ``("tfreq", [...])``
        tbound : list or tuple, optional
            Time bounds ``[start, end]``.

        Returns
        -------
        ColocSession
        """
        dsref, dsprod = process_time_colocation(
            self._ref, self._prod, param, tbound
        )
        return ColocSession(dsprod, dsref)

    def horizontal(self, param):
        """Apply horizontal colocation.

        Parameters
        ----------
        param : tuple
            E.g. ``("grid2loc", [...])``

        Returns
        -------
        ColocSession
        """
        dsref, dsprod = process_horizontal_colocation(
            self._ref, self._prod, param
        )
        return ColocSession(dsprod, dsref)

    def vertical(self, param):
        """Apply vertical colocation.

        Parameters
        ----------
        param : tuple
            E.g. ``("vrange", {"vref": "reference", "vname": "depth", ...})``

        Returns
        -------
        ColocSession
        """
        dsref, dsprod = process_vertical_colocation(
            self._ref, self._prod, param
        )
        return ColocSession(dsprod, dsref)


@xr.register_dataset_accessor("coloc")
class ColocAccessor:
    """Colocation accessor for xr.Dataset.

    Examples
    --------
    >>> prod, ref = ds_prod.coloc.with_ref(ds_ref).time(param, tbound=tbound)
    >>> session = ds_prod.coloc.with_ref(ds_ref).time(param).horizontal(param2)
    """

    def __init__(self, obj):
        self._obj = obj

    def with_ref(self, ds_ref: xr.Dataset) -> ColocSession:
        """Start a colocation session against a reference dataset.

        Parameters
        ----------
        ds_ref : xr.Dataset
            Reference dataset.

        Returns
        -------
        ColocSession
        """
        return ColocSession(self._obj, ds_ref)
