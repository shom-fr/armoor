import logging
import re

import numpy as np
import pandas as pd
import xarray as xr

from armoor import ArmoorError

logger = logging.getLogger(__name__)

def timegroups_to_list(grouped, label="trange"):
    dss = []
    for name, ds in grouped:
        dso = ds.copy()
        if label == "time":
            tlabel = pd.to_datetime(name)
            dso.attrs[label] = f"{tlabel:%Y-%m-%dT%H:%M:%S}"
        else:
            dso.attrs[label] = f"[{name.left:%Y-%m-%dT%H:%M:%S}_{name.right:%Y-%m-%dT%H:%M:%S}["
        dss.append(dso)
    return dss
   
def tfreq(ds):
    grouped = ds.groupby("time")
    return timegroups_to_list(grouped, label="time")
    
def trange_seq(ds, tstart, tend, tbin):
    regex = re.compile(r"[0-9][M-Y]")
    if regex.fullmatch(tbin):
        raise ArmoorError(
            "Use trange=1MS, 2MS... to specify a  monthly sequential range."
            )
    time_bins = pd.date_range(start=tstart, end=tend, freq=tbin)
    grouped = ds.groupby_bins(
        "time", time_bins, right=False
        )
    return timegroups_to_list(grouped, label="trange")
    

def vrange(dssi, vname, vbins):
    dss = []
    for dsi in dssi:
        var = dsi[vname]
        for vbin in vbins:
            low, high = vbin[0], vbin[1]
            mask = ((var >= low) & (var <= high))
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
                logger.info(
                    f"Skipping vlevel {vlevel:.1f} -- no valid data anywhere"
                    )
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
    return pd.date_range(
        start=pd.to_datetime(start),
        end=pd.to_datetime(end),
        freq=tbin,
        )
