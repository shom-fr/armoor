import re
import pandas as pd

from armoor import ArmoorError


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
    return ds.groupby_bins(
        "time", time_bins, labels=labels, right=False
        )

def vrange(ds, vname, vbins):
    labels = [
        vbins[it] + 0.5 * (vbins[it + 1] - vbins[it])
        for it in range(len(vbins) - 1)
    ]
    return ds.groupby_bins(
        vname, vbins, labels=labels, right=False
        )
        
def get_time_bins(start, end, tbin):
    return pd.date_range(
        start=pd.to_datetime(start),
        end=pd.to_datetime(end),    
        freq=tbin,
        )