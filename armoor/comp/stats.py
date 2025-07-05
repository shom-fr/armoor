import logging
import numpy as np
import xarray as xr
import pandas as pd

from armoor.__init__ import ArmoorError
from armoor.base.ranges import trange_seq, vrange

logger = logging.getLogger(__name__)


class StatsComp:
    """Class for plot comparison."""
    
    def __init__(self, mparams, dsprod, dsref, dims, extra_dims=None, exclude_dims=None):
        """Initialize the AbstractPlotComp instance with an empty dictionary to store methods."""
        self.mparams = mparams
        self.dsref = dsref
        self.dsprod = dsprod.reset_coords(
            ["lon", "lat"]
            ).mean(dim="member").set_coords(
            ["lon", "lat"]
            ) if "member" in dsprod.dims else dsprod
        self.dims = dims if dims else []
        self.extra_dims = extra_dims
        self.exclude_dims = exclude_dims
        self.dtref = xr.DataTree(name="ref")
        self.dtprod = xr.DataTree(name="prod")
        self.dtcomps = xr.DataTree(name="comps")
        self.dtref.update(xr.DataTree.from_dict({
            "data": dsref
            })) 
        self.dtprod.update(xr.DataTree.from_dict({
            "data": dsprod
            }))
        
    def compute(self):
        """Compute statistics over dimensions."""
        
        if len(self.dims) == 0:
            return self.dtprod, self.dtref, None
        dims = self.dims
        if ("time" in self.dims) and ("trange_seq" not in self.mparams):
            dims.remove("time")
        if ("z" in self.dims) and ("vrange" not in self.mparams):
            dims.remove("z")
        if ("x" in self.dims) and ("x" not in self.dsref.dims):
            dims.remove("x")
            dims.remove("y")
            
        if len(dims) > 0:
            return self.get_stats(dims)
        else:
            return self.get_diff()

    def prepare_coords(self, dim):
        # for d in ["time", "z", "y", "x"]:
        #     if d in dim:
        #         for coord in ["depth", "lon", "lat"]:
        #             if (coord in self.dsprod.coord) and (d in self.dsprod.dim):
        #                 self.dsprod = self.dsprod.reset_coords(coord)
        #             if (coord in self.dsref.coord) and (d in self.dsref.dim):
        #                 self.dsref = self.dsref.reset_coords(coord)
        coords_to_check = {"depth", "lon", "lat"}
        dims_to_check = {"time", "z", "y", "x"}
        
        # Check if we need to do anything at all
        if dims_to_check & set(dim):
            # For each dataset, check if any target dimension exists
            for ds_name, ds in [("dsprod", self.dsprod), ("dsref", self.dsref)]:
                if dims_to_check & set(ds.dims):
                    # Find coordinates that exist in this dataset
                    coords_to_reset = list(coords_to_check & set(ds.coords))
                    if coords_to_reset:
                        if ds_name == "dsprod":
                            self.dsprod = ds.reset_coords(coords_to_reset)
                        else:
                            self.dsref = ds.reset_coords(coords_to_reset)

    def get_stats(self, dim):
        """Get statistics."""
                
        # self.prepare_coords(dim)
        diff = self.dsprod - self.dsref
        diffc = (
            self.dsprod - self.dsprod.mean(dim=dim)
            ) - (
            self.dsref - self.dsref.mean(dim=dim)
            )
        self.dtref.update(xr.DataTree.from_dict({
            "mean": self.dsref.mean(dim=dim)
            }))
        self.dtprod.update(xr.DataTree.from_dict({
            "mean": self.dsprod.mean(dim=dim)
            }))
        self.dtref.update(xr.DataTree.from_dict({
            "std": self.dsref.std(dim=dim)
            }))
        self.dtprod.update(xr.DataTree.from_dict({
            "std": self.dsprod.std(dim=dim)
            }))
        self.dtcomps.update(xr.DataTree.from_dict({
            "bias": diff.mean(dim=dim)
            }))
        self.dtcomps.update(xr.DataTree.from_dict({
            "rmse": np.sqrt((diff ** 2).mean(dim=dim))
            }))
        self.dtcomps.update(xr.DataTree.from_dict({
            "rmsec": np.sqrt((diffc ** 2).mean(dim=dim))
            }))
        
        xdim = {}
        if "trange_seq" in self.mparams:
            xdim.update({"time": self.dsprod.attrs["trange"]})
            
        for k, v in xdim.items():
            for comp, dt in self.dtref.items():
                ds = dt.to_dataset()
                if comp != "data":
                    if ("time" in dim) and (k == "time"):
                        ds = self.set_time_range(ds, v)
                    self.dtref.update(xr.DataTree.from_dict({
                        comp: ds
                        }))
            
            for comp, dt in self.dtprod.items():
                ds = dt.to_dataset()
                if comp != "data":
                    if ("time" in dim) and (k == "time"):
                        ds = self.set_time_range(ds, v)
                    self.dtprod.update(xr.DataTree.from_dict({
                        comp: ds
                        }))
            
            for comp, dt in self.dtcomps.items():
                ds = dt.to_dataset()
                if ("time" in dim) and (k == "time"):
                    ds = self.set_time_range(ds, v)
                self.dtcomps.update(xr.DataTree.from_dict({
                    comp: ds
                    }))
        return self.dtprod, self.dtref, self.dtcomps
    
    def set_time_range(self, ds, time):
        if "time" in ds.dims:
            ds = ds.drop_dims("time")
        if "time" in ds.coords:
            ds = ds.drop_vars("time")
        ds = ds.expand_dims(dim="time")
        ds["time"] = xr.DataArray(
            data=[pd.to_datetime(time)],
            dims="time"
            )
        ds = ds.set_coords("time")
        return ds
        
    def get_diff(self):
        self.dtcomps.update(xr.DataTree.from_dict({
            "diff": self.dsprod - self.dsref
            }))
        return self.dtprod, self.dtref, self.dtcomps
 

