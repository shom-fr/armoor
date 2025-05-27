import logging
import numpy as np
import xarray as xr

from armoor.__init__ import ArmoorError
from armoor.base.ranges import trange_seq, vrange

logger = logging.getLogger(__name__)


class StatsComp:
    """Class for plot comparison."""
    
    def __init__(self, mparams, dsref, dsprod, extra_dims=None):
        """Initialize the AbstractPlotComp instance with an empty dictionary to store methods."""
        self.mparams = mparams
        self.dsref = dsref
        self.dsprod = dsprod
        self.extra_dims = extra_dims
        
    def compute(self):
        """Compute statistics over dimensions."""
        if "trange_seq" in self.mparams:
            return self.trange()
        elif "vrange" in self.mparams:
            return self.vrange()
        elif ("vrange" in self.mparams) and ("trange_seq" in self.mparams):
            return self.trange_vrange()
        else:
            return self.norange()

    def dims(self, dims_stat: list):
        """Get dims over which statictics will be computed."""
        if self.extra_dims:
            for dim in self.extra_dims:
                if dim in self.dsref.dims:
                    dims_stat.append(dim)        
        return dims_stat

    def get_stats(self, data_ref, data_prod, diff, diff2, diff2c):
        """Get statistics."""
        stats = {}
        stats["data"] = {
            "ref": [ref0 for ref0 in data_ref][0][1] if isinstance(data_ref, xr.core.groupby.DatasetGroupBy) else data_ref,
            }
        stats["mean"] = {
            "ref": data_ref.mean(dim=self.dims_stat),
            "prod": data_prod.mean(dim=self.dims_stat)
            }
        stats["std"] = {
            "ref": data_ref.std(dim=self.dims_stat),
            "prod": data_prod.std(dim=self.dims_stat)
            }
        stats["bias"] = diff.mean(dim=self.dims_stat)
        stats["rmse"] = np.sqrt(diff2.mean(dim=self.dims_stat))
        stats["rmsec"] = np.sqrt(diff2c.mean(dim=self.dims_stat))
 
        return stats
    
    def get_diffs(self, data_ref, data_prod):
        diff = {}
        diff["prod"] = data_prod
        diff["ref"] = data_ref
        diff["diff"] = data_prod - data_ref
        return diff
 
    def centered_diff(self, data_ref, data_prod, dims_stat):
        center_data = lambda x, dim: x - x.mean(dim=dim)
        return (data_prod.map(
            center_data, args=(dims_stat,)
            ) - data_ref.map(
            center_data, args=(dims_stat,)
            )) ** 2

    def norange(self):
        self.dims_stat = self.dims(dims_stat=[])
        if len(self.dims_stat) == 0:
            return self.get_diffs(self.dsref, self.dsprod)
        else:
            diff = self.dsprod - self.dsref
            diff2 = diff.copy() ** 2
            diff2c = self.centered_diff(self.dsprod, self.dsref, self.dims_stat)
            return self.get_stats(
                self.dsref,
                self.dsprod,
                diff,
                diff2,
                diff2c
                )
                
    def trange(self):
        """Compute statistics over trange."""
        tbin = self.mparams['trange_seq'][0]
        tstart = self.mparams['tbound'][0]
        tend = self.mparams['tbound'][1]
        gprod = trange_seq(self.dsprod, tstart, tend, tbin)
        gref = trange_seq(self.dsref, tstart, tend, tbin)
        gdiff = trange_seq(self.dsprod - self.dsref, tstart, tend, tbin)
        gdiff2 = trange_seq((self.dsprod - self.dsref) ** 2, tstart, tend, tbin)
        self.dims_stat = self.dims(["time"])
        gdiff2c = trange_seq(self.centered_diff(
            gref, gprod, self.dims_stat
            ), tstart, tend, tbin)
        return self.get_stats(gref, gprod, gdiff,gdiff2,  gdiff2c)
    
    def vrange(self):
        return self.dsref, self.dsprod
    
    def trange_vrange(self):
        return self.dsref, self.dsprod
        
        
        
        
