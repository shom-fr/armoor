import itertools
import logging
import re
import pandas as pd
import xarray as xr

from armoor import ArmoorError
from armoor.comp import OUTPUTS_PARAMS, OUTPUTS_VARS
from armoor.comp.plot import PlotComp

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

def check_output(func_name, outputs):
    for output in outputs.values():
        if output.get('otype') not in OUTPUTS_PARAMS[func_name].keys():
            raise ArmoorError(
                f"Not implemented output for {func_name}: {output}"
                )

def process_output(ocfg, func_comp):
    
    metazone = ''.join(ocfg[0].keys())
    output = ''.join(ocfg[1].keys())
    mparams, oparams = ocfg[0][metazone], ocfg[1][output]
    
    logger.info(f"{metazone} -- {output}")
    plot = PlotComp(mparams, oparams, func_comp, metazone)
    plot.__post_init__()
    plot.call(oparams.get("otype"))    
    

def main_output(ncs, metazones, output_ins, func_comp):
    
    check_output(func_comp, output_ins)
    
    for metazone in metazones:
        metazones[metazone].update({
            "ncins": ncs.get(metazone),
            "vars": OUTPUTS_VARS[func_comp]
            })
    metazones = [{key: value} for key, value in metazones.items()]
    output_ins = [{key: value} for key, value in output_ins.items()]
    outputs = list(itertools.product(metazones, output_ins))
    
    for output in outputs:
        process_output(output, func_comp)
        logger.info("----------")
        
            
            
            
            # if
            # for prod, ncins in ncs.get(metazone).items():
            #     logger.info(f"Product: {prod}")
                
            #     ncprod = [ncin for ncin in ncins if prod in ncin.name][0]
            #     logger.info(f"ncprod: {ncprod}")
            #     ncref = [ncin for ncin in ncins if prod not in ncin.name][0]
            #     logger.info(f"ncref: {ncref}")
                
                
                
                
                
                
                
                
                
                
                
                
                
                
                # dsprod = xr.open_dataset(ncprod)
                # dsref = xr.open_dataset(ncref)
                
                # dims_stat = []
                # if "trange_seq" in mparams:
                #     dims_stat.append("time")
                #     tbin = mparams['trange_seq'][0]
                #     tstart = mparams['tbound'][0]
                #     tend = mparams['tbound'][1]
                #     logger.info(f"trange_seq: {tbin}")
                #     dsprod = trange_seq(dsprod, tstart, tend, tbin)
                #     dsref = trange_seq(dsref, tstart, tend, tbin)
    
                # if "vrange" in mparams:
                #     dims_stat.append("z")
                #     vbins = mparams["vrange"][1]
                #     vname = mparams["vrange"][0]
                
                
                
