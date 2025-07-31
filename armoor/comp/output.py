import gc
import itertools
import logging
import re
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Optional

import dask
import numpy as np
import pandas as pd
import xarray as xr

from armoor import ArmoorError
from armoor.base.io import (
    get_zarr_encoding,
    setup_dask_client,
    sort_ncs_by_suffix
    )
from armoor.comp import COMP_VARS, OUTPUTS_PARAMS
from armoor.comp.plot import PlotComp
from armoor.comp.stats import StatsComp

logger = logging.getLogger(__name__)


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
                ncout = dirout_sort / "all.zarr"
                encoding = get_zarr_encoding(dt)
                dt.to_zarr(ncout, mode="w", encoding=encoding)
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
                    ncout = dirout_sort / f"{prod}.zarr"
                    encoding = get_zarr_encoding(dt)
                    dt.to_zarr(ncout, mode="w", encoding=encoding)
                    ncouts[output][metazone].append(str(ncout))
            del dt
        del dss
        gc.collect()
    return ncouts

@dask.delayed
def process_and_extract(output, func_comp):
    """Process output and extract non-empty results"""
    ncs = process_output(output, func_comp)
    
    # Extract only non-empty results
    filtered_results = {}
    for o, ms in ncs.items():
        for m, ns in ms.items():
            if len(ns) > 0:
                if o not in filtered_results:
                    filtered_results[o] = {}
                filtered_results[o][m] = ns
    
    return filtered_results

def main_output(ncs, metazones_in, outputs, func_comp):
    
    output_ins = outputs.copy()
    output_ins.pop("fmt")
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

    delayed_tasks = [
        process_and_extract(output, func_comp)
        for output in outputs
    ]

    results = dask.compute(*delayed_tasks)
    
    # Merge all filtered results
    ncouts = {}
    for result in results:
        for o, ms in result.items():
            if o not in ncouts:
                ncouts[o] = {}
            ncouts[o].update(ms) 

    return ncouts

