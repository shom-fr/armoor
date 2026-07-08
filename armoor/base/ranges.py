import logging
import re

import pandas as pd
import xarray as xr

from armoor import ArmoorError

logger = logging.getLogger(__name__)

def timegroups_to_list(grouped, label="trange"):
    dss = []
    for name, ds in grouped:
        dso = ds.copy()
        tlabel = pd.to_datetime(name)
        dso.attrs[label] = f"{tlabel:%Y-%m-%dT%H:%M:%S}"
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
    labels = [
        time_bins[it] + 0.5 * (time_bins[it + 1] - time_bins[it])
        for it in range(len(time_bins) - 1)
        ]
    grouped = ds.groupby_bins(
        "time", time_bins, labels=labels, right=False
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
            dso = dsi.isel(z=[ivlevel]).copy()
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
