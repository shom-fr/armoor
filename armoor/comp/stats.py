import logging
import numpy as np
import xarray as xr
import pandas as pd

from armoor.__init__ import ArmoorError
from armoor.base.ranges import trange_seq, vrange

logger = logging.getLogger(__name__)


class StatsComp:
    """Class for plot comparison."""
    
    def __init__(self, mparams, dsref, dsprod, extra_dims=None, exclude_dims=None):
        """Initialize the AbstractPlotComp instance with an empty dictionary to store methods."""
        self.mparams = mparams
        self.dsref = dsref
        self.dsprod = dsprod
        self.extra_dims = extra_dims
        self.exclude_dims = exclude_dims
        
    def compute(self):
        """Compute statistics over dimensions."""
        if ("trange_seq" in self.mparams) and ("vrange" not in self.mparams):
            dims = ["time"]
            if self.extra_dims:
                dims += self.extra_dims
            if self.exclude_dims:
                [dims.remove(dim) for dim in self.exclude_dims]
            return self.get_stats(dims)
        elif ("vrange" in self.mparams) and ("trange_seq" not in self.mparams):
            dims = ["z"]
            if self.extra_dims:
                dims += self.extra_dims
            if self.exclude_dims:
                [dims.remove(dim) for dim in self.exclude_dims]
            return self.get_stats(dims)
        elif ("vrange" in self.mparams) and ("trange_seq" in self.mparams):
            dims = ["time", "z"]
            if self.extra_dims:
                dims += self.extra_dims
            if self.exclude_dims:
                [dims.remove(dim) for dim in self.exclude_dims]
            return self.get_stats(dims)
        else:
            return self.get_diff()

    def get_stats(self, dim):
        """Get statistics."""
        stats = {}
        stats["data"] = self.dsref
        stats["mean_ref"] = self.dsref.mean(dim=dim)
        stats["mean_prod"] = self.dsprod.mean(dim=dim)
        stats["std_ref"] = self.dsref.std(dim=dim)
        stats["std_prod"] = self.dsprod.std(dim=dim)
        diff = self.dsprod - self.dsref
        diffc = (
            self.dsprod - self.dsprod.mean(dim=dim)
            ) - (
            self.dsref - self.dsref.mean(dim=dim)
            )
        stats["bias"] = diff.mean(dim=dim)
        stats["rmse"] = np.sqrt((diff ** 2).mean(dim=dim))
        stats["rmsec"] = np.sqrt((diffc ** 2).mean(dim=dim))
        xdim = {}
        if "trange_seq" in self.mparams:
            xdim.update({"time": self.dsprod.attrs["trange"]})
        for k, v in xdim.items():
            for stat, ds in stats.items():
                if stat != "data":
                    if "time" not in ds.dims:
                        ds = ds.expand_dims(dim="time")
                        ds["time"] = xr.DataArray(data=[pd.to_datetime(v)], dims="time")
                        ds = ds.set_coords("time")
                    stats[stat].update(ds)
        return stats
    
    def get_diff(self):
        diff = {}
        diff["prod"] = self.dsprod
        diff["ref"] = self.dsref
        diff["diff"] = self.dsprod - self.dsref
        return diff
 
    # def centered_diff(self, data_ref, data_prod, dims_stat):
    #     center_data = lambda x, dim: x - x.mean(dim=dim)
    #     return (data_prod.map(
    #         center_data, args=(dims_stat,)
    #         ) - data_ref.map(
    #         center_data, args=(dims_stat,)
    #         )) ** 2

    # def norange(self):
    #     self.dims_stat = self.dims(dims_stat=[])
    #     if len(self.dims_stat) == 0:
    #         return self.get_diffs(self.dsref, self.dsprod)
    #     else:
    #         diff = self.dsprod - self.dsref
    #         diff2 = diff.copy() ** 2
    #         diff2c = self.centered_diff(self.dsprod, self.dsref, self.dims_stat)
    #         return self.get_stats(
    #             self.dsref,
    #             self.dsprod,
    #             diff,
    #             diff2,
    #             diff2c
                                
    # def trange(self):
        # """Compute statistics over trange."""
        # tbin = self.mparams['trange_seq'][0]
        # tstart = self.mparams['tbound'][0]
        # tend = self.mparams['tbound'][1]
        # gprod = trange_seq(self.dsprod, tstart, tend, tbin)
        # gref = trange_seq(self.dsref, tstart, tend, tbin)
        # gdiff = trange_seq(self.dsprod - self.dsref, tstart, tend, tbin)
        # gdiff2 = trange_seq((self.dsprod - self.dsref) ** 2, tstart, tend, tbin)
        # self.dims_stat = self.dims(["time"])
        # gdiff2c = trange_seq(self.centered_diff(
        #     gref, gprod, self.dims_stat
        #     ), tstart, tend, tbin)
        # return self.get_stats(gref, gprod, gdiff,gdiff2,  gdiff2c)
    
    # def vrange(self):
    #     return self.dsref, self.dsprod
    
    # def trange_vrange(self):
    #     return self.dsref, self.dsprod
        # )
#
        
        
        
