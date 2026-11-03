import logging
import re

import numpy as np
import pandas as pd
import xarray as xr

from armoor import ArmoorError

logger = logging.getLogger(__name__)

#: Size-1 dimension carried by variables averaged over the whole colocated
#: time window (the metazone's ``tbound``), e.g. comp_alti's mke/mke_geos.
#: Such variables cannot share the "time" axis of the other variables, are
#: never split by `trange_seq`/`tfreq`, and are saved in their own
#: ``*_period_<t0>_<tN>.zarr`` coloc files (see `tag_period`).
PERIOD_DIM = "period"


def period_label(ds):
    """Return the ``<t0>_<tN>`` label of the time window covered by `ds`.

    Parameters
    ----------
    ds : xarray.Dataset
        Dataset with a datetime-like "time" coordinate.

    Returns
    -------
    str
    """
    tt = pd.to_datetime(ds["time"].values)
    return f"{tt[0]:%Y-%m-%dT%H:%M:%S}_{tt[-1]:%Y-%m-%dT%H:%M:%S}"


def tag_period(ds, label):
    """Tag a `PERIOD_DIM` dataset with its averaging window.

    Drops the ``time``/``trange`` attrs inherited from the full dataset --
    they would otherwise give this dataset the same output filename suffix
    as the "time"-dependent one it was split from (see
    `armoor.io.output_suffix`) -- and sets ``attrs["period"]`` instead.

    Parameters
    ----------
    ds : xarray.Dataset
    label : str
        See `period_label`.

    Returns
    -------
    xarray.Dataset
        A shallow copy of `ds`, retagged.
    """
    attrs = {k: v for k, v in ds.attrs.items() if k not in ("time", "trange")}
    attrs["period"] = label
    out = ds.copy()
    out.attrs = attrs
    return out


def timegroups_to_list(grouped, label="trange"):
    """Turn a ``groupby``/``groupby_bins`` result into a list of datasets.

    Each returned dataset carries its own group value tagged as an attr
    (a single timestamp for ``label="time"``, a bracketed ``[start_end[``
    range otherwise), so a later stage can recover it without reopening
    the dataset (see `armoor.io.output_suffix`).

    Parameters
    ----------
    grouped : xarray.core.groupby.DatasetGroupBy
        Result of `ds.groupby("time")` or `ds.groupby_bins("time", ...)`.
    label : str
        Attr name to tag each dataset with -- "time" for a single-timestamp
        group, "trange" for a bin range.

    Returns
    -------
    list of xarray.Dataset
    """
    dss = []
    for name, ds in grouped:
        dso = ds.copy()
        if label == "time":
            # A single time step has no range: drop the whole-window trange
            # tagged by the time colocation (armoor.comp.coloc.TimeColocation),
            # which would otherwise win over "time" in plot labels and give
            # every time step's figure the same name.
            dso.attrs.pop("trange", None)
            tlabel = pd.to_datetime(name)
            dso.attrs[label] = f"{tlabel:%Y-%m-%dT%H:%M:%S}"
        else:
            dso.attrs[label] = f"[{name.left:%Y-%m-%dT%H:%M:%S}_{name.right:%Y-%m-%dT%H:%M:%S}["
        dss.append(dso)
    return dss


def tfreq(ds):
    """Split a dataset into one subset per native time step.

    Parameters
    ----------
    ds : xarray.Dataset

    Returns
    -------
    list of xarray.Dataset
        One dataset per unique "time" value, each tagged with its own
        timestamp (see `timegroups_to_list`).
    """
    grouped = ds.groupby("time")
    return timegroups_to_list(grouped, label="time")


def trange_seq(ds, tstart, tend, tbin):
    """Split a dataset into sequential time bins.

    Parameters
    ----------
    ds : xarray.Dataset
    tstart, tend : str or datetime-like
        Start/end of the range to bin over.
    tbin : str
        A pandas frequency alias (e.g. "7D", "1MS") for the bin width.

    Returns
    -------
    list of xarray.Dataset
        One dataset per time bin, each tagged with its own ``[start_end[``
        range (see `timegroups_to_list`).

    Raises
    ------
    ArmoorError
        If `tbin` looks like a bare month/year count (e.g. "1M") instead
        of the required "start"-anchored alias (e.g. "1MS").
    """
    regex = re.compile(r"[0-9][M-Y]")
    if regex.fullmatch(tbin):
        raise ArmoorError("Use trange=1MS, 2MS... to specify a  monthly sequential range.")
    time_bins = pd.date_range(start=tstart, end=tend, freq=tbin)
    grouped = ds.groupby_bins("time", time_bins, right=False)
    return timegroups_to_list(grouped, label="trange")


def vrange(dssi, vname, vbins):
    """Mask each dataset onto one or more vertical (depth) bins.

    Parameters
    ----------
    dssi : list of xarray.Dataset
        Datasets to split.
    vname : str
        Name of the vertical coordinate/variable to bin on (e.g. "depth").
    vbins : list of (float, float)
        ``(low, high)`` bounds, inclusive, for each bin.

    Returns
    -------
    list of xarray.Dataset
        One dataset per (input dataset, bin) pair, with "z"-dependent
        variables masked outside the bin and tagged with a
        ``"vrange"`` attr (``"<low>-<high>"``).
    """
    dss = []
    for dsi in dssi:
        var = dsi[vname]
        for vbin in vbins:
            low, high = vbin[0], vbin[1]
            mask = (var >= low) & (var <= high)
            daos = []
            for v in dsi.data_vars:
                dai = dsi[v]
                if "z" in dai.dims:
                    dao = dai.where(mask)
                else:
                    dao = dai.copy()
                daos.append(dao)
            dso = xr.merge(daos)
            dso = dso.assign_coords(dsi.coords)
            dso.attrs = dsi.attrs
            dso.attrs["vrange"] = f"{low}-{high}"
            dss.append(dso)
    return dss


def vlevels(dssi, vname):
    """Split each dataset into one subset per vertical (depth) level.

    Parameters
    ----------
    dssi : list of xarray.Dataset
        Datasets to split.
    vname : str
        Name of the vertical coordinate/variable to split on (e.g. "depth").

    Returns
    -------
    list of xarray.Dataset
        One dataset per (input dataset, level) pair, each tagged with a
        ``"vlevel"`` attr (the level's own value, formatted to 1 decimal).
        Levels with no valid data anywhere are skipped.
    """
    dss = []
    for dsi in dssi:
        var = dsi[vname]
        for ivlevel in range(var.sizes["z"]):
            vlevel = var.isel(z=ivlevel).values
            # vname (e.g. "depth") can carry leftover non-"z" dims (e.g. a
            # spurious "time" dim from concatenating multiple native files)
            # even though the actual level is constant along them -- reduce
            # to a plain scalar so it can be used as a label. Take the first
            # *finite* value: the first grid point may be masked (land),
            # which would otherwise label every level "nan".
            vlevel = np.asarray(vlevel, dtype=float).reshape(-1)
            finite = vlevel[np.isfinite(vlevel)]
            vlevel = float(finite[0]) if finite.size else float("nan")
            dso = dsi.isel(z=[ivlevel]).copy()
            data_vars = [v for v in dso.data_vars if v != vname]
            if data_vars and all(bool(dso[v].isnull().all()) for v in data_vars):
                # Deepest native levels of a global-ocean model routinely
                # have no valid data at all over a shallow/shelf regional
                # subset (below the seafloor everywhere in it) -- skip
                # rather than emit an empty group that later otypes
                # (maps, profiles, diagts) can't render.
                logger.info(f"Skipping vlevel {vlevel:.1f} -- no valid data anywhere")
                continue
            # vname itself can be broadcast to leftover non-"z" dims from
            # loading (e.g. armoor.data.open_decode's cmems_model loader
            # broadcasts "depth" to the full (time,z,y,x) shape) -- now
            # that this is a single level, replace it with a clean
            # (z,)-only coordinate so downstream code isn't handed a
            # "depth" that still varies along time/x/y/npts.
            vname_attrs = dso[vname].attrs
            dso = dso.assign_coords({vname: ("z", [vlevel])})
            dso[vname] = dso[vname].assign_attrs(**vname_attrs)
            dso.attrs = dsi.attrs
            dso.attrs["vlevel"] = f"{vlevel:.1f}"
            dss.append(dso)
    return dss


def get_time_bins(start, end, tbin):
    """Build the sequence of bin-edge timestamps for a time range.

    Parameters
    ----------
    start, end : str or datetime-like
    tbin : str
        A pandas frequency alias (e.g. "7D", "1MS") for the bin width.

    Returns
    -------
    pandas.DatetimeIndex
    """
    return pd.date_range(
        start=pd.to_datetime(start),
        end=pd.to_datetime(end),
        freq=tbin,
    )
