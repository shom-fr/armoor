import itertools
import logging
import re
import pandas as pd
import xarray as xr

from armoor import ArmoorError
from armoor.comp import OUTPUTS_PARAMS, COMP_VARS
from armoor.comp.plot import PlotComp

logger = logging.getLogger(__name__)

def check_output(func_name, outputs):
    for output in outputs.values():
        if output.get('otype') not in OUTPUTS_PARAMS[func_name]:
            raise ArmoorError(
                f"Not implemented output for {func_name}: {output}"
                )

def process_output(ocfg, func_comp):
    
    metazone = ''.join(ocfg[0].keys())
    output = ''.join(ocfg[1].keys())
    mparams, oparams = ocfg[0][metazone], ocfg[1][output]
    ax_minimap = [0.7, 0.9, 0.19]
    
    logger.info(f"{metazone} -- {output}")
    plot = PlotComp(mparams, oparams, func_comp, metazone, ax_minimap)
    plot.__post_init__()
    plot.call(oparams.get("otype"))    

def main_output(ncs, metazones, output_ins, func_comp):
    
    check_output(func_comp, output_ins)
    
    for metazone in metazones:
        metazones[metazone].update({
            "ncins": ncs.get(metazone),
            "vars": COMP_VARS[func_comp]
            })
    metazones = [{key: value} for key, value in metazones.items()]
    output_ins = [{key: value} for key, value in output_ins.items()]
    outputs = list(itertools.product(metazones, output_ins))
    
    for output in outputs:
        process_output(output, func_comp)        
