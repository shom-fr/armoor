import logging
import re
import pandas as pd
import xarray as xr

from armoor import ArmoorError

logger = logging.getLogger(__name__)


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


def main_comp(ncs, metazones):
    
    for metazone, params in metazones.items():
        logger.info(f"Start comparaison for {metazone}")
        
        for prod, ncins in ncs.get(metazone).items():
            logger.info(f"Product: {prod}")
            
            ncprod = [ncin for ncin in ncins if prod in ncin.name][0]
            logger.info(f"ncprod: {ncprod}")
            ncref = [ncin for ncin in ncins if prod not in ncin.name][0]
            logger.info(f"ncref: {ncref}")
            
            dsprod = xr.open_dataset(ncprod)
            dsref = xr.open_dataset(ncref)
            
            dims_stat = []
            if "trange_seq" in params:
                dims_stat.append("time")
                tbin = params['trange_seq'][0]
                tstart = params['tbound'][0]
                tend = params['tbound'][1]
                logger.info(f"trange_seq: {tbin}")
                dsprod = trange_seq(dsprod, tstart, tend, tbin)
                dsref = trange_seq(dsref, tstart, tend, tbin)

            if "vrange" in params:
                dims_stat.append("z")
                vbins = params["vrange"][1]
                vname = params["vrange"][0]
                
