"""ds.range accessor — thin facade over armoor.ranges and armoor.data.range.

All computation lives in those modules; this accessor only wires them
onto xr.Dataset.

    ds.range.tfreq(freq)               # → data.range.process_time_range
    ds.range.vertical(vname, vrange)   # → data.range.process_vertical_range
    ds.range.trange_seq(t0, t1, tbin)  # → base.ranges.trange_seq  (returns list)
    ds.range.vrange(vname, vbins)      # → base.ranges.vrange       (returns list)
    ds.range.vlevels(vname)            # → base.ranges.vlevels      (returns list)
    ds.range.by_time()                 # → base.ranges.tfreq        (returns list)
    ds.range.time / .trange / .vlevel / .vrange_value  # read back the attrs above
    ds.range.suffix                    # → base.io.output_suffix
"""

import xarray as xr

from armoor import ranges as _ranges
from armoor.io import output_suffix as _output_suffix
from armoor.data.range import process_time_range, process_vertical_range


@xr.register_dataset_accessor("range")
class RangeAccessor:
    """Range accessor for xr.Dataset.

    High-level methods (``tfreq``, ``vertical``) return a single
    :class:`xr.Dataset` with an extra dimension; they delegate to
    :mod:`armoor.data.range`.

    Low-level split methods (``trange_seq``, ``vrange``, ``vlevels``,
    ``by_time``) return a **list** of :class:`xr.Dataset`; they delegate
    to :mod:`armoor.ranges`.
    """

    def __init__(self, obj):
        self._obj = obj

    # ------------------------------------------------------------------
    # High-level — return xr.Dataset
    # ------------------------------------------------------------------

    def tfreq(self, freq) -> xr.Dataset:
        """Split the dataset into time bins of *freq* and concatenate along
        a new ``trange`` dimension.

        Delegates to :func:`armoor.data.range.process_time_range`.

        Parameters
        ----------
        freq : str
            Pandas frequency string (e.g. ``"1D"``, ``"1MS"``).

        Returns
        -------
        xr.Dataset
            Dataset with a ``trange`` dimension (one element per bin) and a
            ``time_range`` coordinate describing each bin's bounds.
        """
        return process_time_range(self._obj, freq)

    def vertical(self, vname, vrange) -> xr.Dataset:
        """Mask 3-D variables outside the vertical range *[vrange[0], vrange[1]]*.

        2-D variables (without a ``z`` dimension) are kept unchanged.
        Delegates to :func:`armoor.data.range.process_vertical_range`.

        Parameters
        ----------
        vname : str
            Name of the vertical coordinate (e.g. ``"depth"``).
        vrange : tuple or list of length 2
            ``(vmin, vmax)`` — values outside this interval are masked (NaN).

        Returns
        -------
        xr.Dataset
            Dataset with a ``vertical_range`` coordinate added.
        """
        return process_vertical_range(self._obj, vname, vrange)

    # ------------------------------------------------------------------
    # Low-level — return list[xr.Dataset]
    # ------------------------------------------------------------------

    def by_time(self) -> list:
        """Split the dataset into one subset per unique time step.

        Delegates to :func:`armoor.ranges.tfreq`.

        Returns
        -------
        list of xr.Dataset
            One dataset per unique time value, each carrying a ``"time"``
            attribute.
        """
        return _ranges.tfreq(self._obj)

    def trange_seq(self, tstart, tend, tbin) -> list:
        """Split the dataset into sequential time bins.

        Delegates to :func:`armoor.ranges.trange_seq`.

        Parameters
        ----------
        tstart : date-like
            Start of the first bin.
        tend : date-like
            End of the last bin.
        tbin : str
            Pandas frequency string defining bin width.

        Returns
        -------
        list of xr.Dataset
            One dataset per bin, each carrying a ``"trange"`` attribute.
        """
        return _ranges.trange_seq(self._obj, tstart, tend, tbin)

    def vrange(self, vname, vbins) -> list:
        """Apply vertical range masking for a list of bins.

        Delegates to :func:`armoor.ranges.vrange`.

        Parameters
        ----------
        vname : str
            Name of the vertical variable used for filtering.
        vbins : list of (low, high) tuples
            Each tuple defines one vertical range bin.

        Returns
        -------
        list of xr.Dataset
            One dataset per bin, each carrying a ``"vrange"`` attribute.
        """
        return _ranges.vrange([self._obj], vname, vbins)

    def vlevels(self, vname) -> list:
        """Split the dataset into one subset per vertical level.

        Delegates to :func:`armoor.ranges.vlevels`.

        Parameters
        ----------
        vname : str
            Name of the vertical coordinate variable.

        Returns
        -------
        list of xr.Dataset
            One dataset per ``z`` index, each carrying a ``"vlevel"`` attribute.
        """
        return _ranges.vlevels([self._obj], vname)

    # ------------------------------------------------------------------
    # Read-side properties — read back attrs set by the methods above
    # ------------------------------------------------------------------

    @property
    def time(self):
        """The ``"time"`` attr set by `by_time`, or None."""
        return self._obj.attrs.get("time")

    @property
    def trange(self):
        """The ``"trange"`` attr set by `trange_seq`, or None."""
        return self._obj.attrs.get("trange")

    @property
    def vlevel(self):
        """The ``"vlevel"`` attr set by `vlevels`, or None."""
        return self._obj.attrs.get("vlevel")

    @property
    def vrange_value(self):
        """The ``"vrange"`` attr set by `vrange`, or None.

        Named ``vrange_value`` (not ``vrange``) to avoid shadowing the
        `vrange` splitting method above.
        """
        return self._obj.attrs.get("vrange")

    @property
    def suffix(self) -> str:
        """The ``_<time-or-trange>_<vlevel-or-vrange>`` output filename suffix.

        Delegates to :func:`armoor.io.output_suffix`.
        """
        return _output_suffix(self._obj.attrs)
