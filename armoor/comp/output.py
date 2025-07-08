import itertools
from pathlib import Path
import logging
import re, gc
import numpy as np
import dask
import pandas as pd
import xarray as xr
from typing import List, Dict, Optional
from collections import defaultdict

from armoor import ArmoorError
from armoor.comp import OUTPUTS_PARAMS, COMP_VARS
from armoor.comp.plot import PlotComp
from armoor.comp.stats import StatsComp

logger = logging.getLogger(__name__)


def check_output(func_name, outputs):
    for output in outputs.values():
        if output.get('otype') not in OUTPUTS_PARAMS[func_name].keys():
            raise ArmoorError(
                f"Not implemented output for {func_name}: {output}"
                )

def extract_suffix_from_filename(filename):
    """
    Extracts 'time' and 'z' values from a filename in the format ref_[time]_[z].nc
    
    Args:
        filename (str): Filename to analyze
        
    Returns:
        dict: Dictionary with 'time' and 'z' keys (values None if not found)
    """
    result = {'time': None, 'z': None}
    
    # Main pattern: ref_[time]_[z].nc
    pattern_full = r'([^/]+)_(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})_([0-9.-]+)\.nc'
    match_full = re.search(pattern_full, filename)
    if match_full:
        result['time'] = match_full.group(2)
        result['z'] = match_full.group(3)
        return result
    
    # Partial pattern: ref_[time]_*.nc (time without z)
    pattern_time_only = r'([^/]+)_(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})\.nc'
    match_time = re.search(pattern_time_only, filename)
    
    if match_time:
        result['time'] = match_time.group(2)
    
    # Partial pattern: ref_*_[z].nc (z without valid time)
    pattern_z_only = r'([^/]+)_([0-9.-]+)\.nc'
    match_z = re.search(pattern_z_only, filename)
    
    if match_z and not result['time']:  # Only if time not already found
        result['z'] = match_z.group(2)
    return result

def sort_ncs_by_suffix(ncs: List[str], sort_dim=["time", "z"]) -> Dict[str, List[str]]:
    """Sort a list of NetCDF files by their suffix.
    """
    ncouts = {}
    for nc in ncs:
        if not isinstance(nc, str):
            nc = str(nc)
        res = extract_suffix_from_filename(nc)
        if sort_dim == ["time", "z"]:
            if res.get("time") and res.get("z"):
                suff = f"{res['time']}_{res['z']}"
            elif not res.get("time") and res.get("z"):
                suff =  f"{res['z']}"
            elif res.get("time") and not res.get("z"):
                suff =  f"{res['time']}"
            else:
                suff = "None"
        elif sort_dim == ["z"]:
            if res.get("z"):
                suff = f"{res['z']}"
            else:
                suff = "None"
        elif sort_dim == ["time"]:
            if res.get("time"):
                suff = f"{res['time']}"
            else:
                suff = "None"
        else:
            suff = "None"
        if not ncouts.get(suff):
            ncouts[suff] = []
        
        ncouts[suff].append(nc)

    return ncouts


def process_output(ocfg, func_comp):
    
    metazone = ''.join(ocfg[0].keys())
    output = ''.join(ocfg[1].keys())
    mparams, oparams = ocfg[0][metazone], ocfg[1][output]
    output = oparams.get("otype")
    
    logger.info(f"{metazone} -- {output}")
    oparams = OUTPUTS_PARAMS[func_comp][output]
    ref_ncins = mparams.get("ncins")
    concat_dim = oparams.get("concat")
    ncouts =  {output: {metazone: []}}
    
    if oparams.get("mparams_pro"):
        for dim, param in oparams.get("mparams_pro").items():
            if not bool(set(param) & set(mparams.keys())):
                logger.info(f"{output} cannot be processed for {metazone} caused by missing {param}")
                return ncouts
    if oparams.get("mparams_con"):
        for dim, param in oparams.get("mparams_con").items():
            if bool(set(param) & set(mparams.keys())):
                logger.info(f"{output} cannot be processed for {metazone} caused by {param}")
                return ncouts
    for ref_name, prods in ref_ncins.items():
        logger.info(f"Process {output} for {ref_name}")
        sorted_prods = {}
        logger.info("Sorting")
        for prod, ncins in prods.items():
            logger.info(f"{prod}")
            sorted_prods[prod] = {}
            for prefix in ["prod", "ref"]:
                ncs = [nc for nc in ncins if prefix in str(nc)]
                ncs = sort_ncs_by_suffix(
                    ncs,
                    sort_dim=oparams.get("sort")
                    )
                sorted_prods[prod].update({f"{prefix}": ncs})

        logger.info("Stats & concat")
        dts = {}
        dss = {}
        for prod in sorted_prods.keys():
            logger.info(f"{prod}")
            dss[prod] = {
                "prod": {},
                "ref": {},
                "comp": {}
                }
            dts.update({
                "prod": {},
                "ref": {},
                "comp": {}
                })
            sorts = sorted_prods[prod]["prod"].keys()
            for sort in sorts:
                nncs = len(sorted_prods[prod]["prod"][sort])
                dts["prod"].update({sort: []})
                dts["ref"].update({sort: []})
                dts["comp"].update({sort: []})
                for inc in range(nncs):
                    ds_prod = xr.open_dataset(
                        sorted_prods[prod]["prod"][sort][inc]
                        )
                    ds_ref = xr.open_dataset(
                        sorted_prods[prod]["ref"][sort][inc]
                        )
                    if oparams.get("stat"):
                        stats =  oparams.get("stat").copy()
                    else:
                        stats =  None
                    dt_prod, dt_ref, dt_comps = StatsComp(
                        mparams, ds_prod, ds_ref, stats
                        ).compute()
                    dts["prod"][sort].append(dt_prod)
                    dts["ref"][sort].append(dt_ref)
                    dts["comp"][sort].append(dt_comps)
                    del dt_prod
                    del dt_ref
                    del dt_comps
                for data in ["prod", "ref", "comp"]:
                    dts0 = dts[data][sort]
                    dts_data = {}
                    if len(dts0) > 0:
                        if dts0[0]:
                            for ds_name in dts0[0].keys():
                                dss0 = []
                                for dt in dts0:
                                    dss0.append(dt[ds_name].to_dataset())
                                if concat_dim == ["time"]:
                                    if dss0[0].sizes["time"] > 1:
                                        dss1 = []
                                        for ids, ds0 in enumerate(dss0):
                                            dss1 += [
                                                ds0.isel(time=itime) 
                                                for itime in range(
                                                    ds0.sizes["time"]
                                                    )
                                                ]
                                        dss0 = dss1
                                        del dss1
                                    ds = xr.concat(dss0, "time")
                                    if dss0[0].attrs.get("vrange"):
                                        xattrs = [
                                            ds0.attrs.get("vrange") for ds0 in dss0
                                            ]
                                        ds.attrs["vrange"] = xattrs
                                elif len(dss0) == 1:
                                    ds = dss0[0]
                                else:
                                    raise ArmoorError(
                                        "Not implemented."
                                        )
                                del dss0
                                dts_data.update({ds_name: ds})
                                del ds
                    dss[prod][data].update({sort: dts_data})
                    del dts_data

        dirout = Path(
            f"{func_comp}/output/{metazone}/"
            f"{ref_name}/{output}"
            )
        
        for sort in sorts:
            dirout_sort = dirout / sort
            dirout_sort.mkdir(parents=True, exist_ok=True)
            if oparams.get("output"):
                dt = xr.DataTree()
                for prod in sorted_prods.keys():
                    dt.update(xr.DataTree.from_dict({
                        prod: xr.DataTree()
                        }))
                    for data in ["prod", "ref", "comp"]:
                        dss0 = dss[prod][data][sort]
                        dss0 = xr.DataTree.from_dict(dss0)
                        dt[prod].update(xr.DataTree.from_dict({
                            data: dss0
                            }))
                ncout = dirout_sort / "all.nc"
                dt.to_netcdf(ncout)
                ncouts[output][metazone].append(str(ncout))
            else:
                for prod in sorted_prods.keys():
                    dt = xr.DataTree()
                    dt.update(xr.DataTree.from_dict({
                        prod: xr.DataTree()
                        }))
                    for data in ["prod", "ref", "comp"]:
                        dss0 = dss[prod][data][sort]
                        dss0 = xr.DataTree.from_dict(dss0)
                        dt[prod].update(xr.DataTree.from_dict({
                            data: dss0
                            }))
                    ncout = dirout_sort / f"{prod}.nc"
                    dt.to_netcdf(ncout)
                    ncouts[output][metazone].append(str(ncout))
            del dt
        del dss
        gc.collect()
    return ncouts

def main_output(ncs, metazones_in, output_ins, func_comp):
    
    check_output(func_comp, output_ins)
    metazones = {}
    for metazone in metazones_in.keys():
        if metazones_in.get(metazone):
            metazones.update({metazone: {
                "ncins": ncs.get(metazone),
                "vars": COMP_VARS[func_comp],
                **metazones_in[metazone].copy()
                }})
    metazones = [{key: value} for key, value in metazones.items()]
    output_ins = [{key: value} for key, value in output_ins.items()]
    outputs = list(itertools.product(metazones, output_ins))
    ncouts = {}
    for output in outputs:
        dask.config.set({
            'distributed.worker.daemon': False,
            'distributed.comm.timeouts.connect': '120s',
            'distributed.comm.timeouts.tcp': '120s',
            'distributed.worker.memory.target': 0.9,
            'distributed.worker.memory.spill': 0.8,
            'distributed.worker.memory.pause': 0.9,
            'distributed.worker.memory.terminate': 0.95,
            'distributed.worker.memory.monitor-interval': '100ms',
            'distributed.scheduler.allowed-failures': 2,
            'distributed.scheduler.work-stealing': True,
        })
        
        with dask.distributed.Client(
            n_workers=4,  # Réduire le nombre de workers
            threads_per_worker=4,
            memory_limit='10GB',
            silence_logs=True,
            dashboard_address='localhost:8787'
            ) as client:
            print(client.dashboard_link)
            ncs = process_output(output, func_comp)
        for o, ms in ncs.items():
            if o not in ncouts:
                ncouts[o] = {}
            for m, ns in ms.items():
                if len(ns) > 0:
                    ncouts[o][m] = ns
    logger.info(ncouts)
    return ncouts
