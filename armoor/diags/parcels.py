import os, shutil

import pandas as pd
import xarray as xr
import parcels


TMP_OFILE = "ptc_tmp.zarr"

class Parcels(object):
    
    def __init__(self, ncin, ptc_coords_start, runtime, outputdt=None):
        self.ncin = ncin
        self.ptc_coords_start = ptc_coords_start
        self.runtime = runtime
        self.outputdt = outputdt if outputdt else "1h"
        self.vars = {
            "U": "u",
            "V": "v"
            }
        self.dims = {
            "U": {"lat": "y", "lon": "x", "time": "time"},
            "V": {"lat": "y", "lon": "x", "time": "time"},
            }
        self.fieldset = None

    def _fieldset_(self):
        return parcels.FieldSet.from_netcdf(
            self.ncin, self.vars, self.dims,
            allow_time_extrapolation=True,
            )
        
    def _particleset_(self):
        return parcels.ParticleSet(
            fieldset=self._fieldset_(),
            pclass=parcels.JITParticle,
            **self.ptc_coords_start,
            )
    def _particlefile_(self, pset):
        return pset.ParticleFile(
            name=TMP_OFILE,
            outputdt=pd.to_timedelta(self.outputdt)
            )
    
    def _post_(self):
        ds_parcels = xr.open_dataset(TMP_OFILE)
        if "z" in ds_parcels.data_vars:
            ds_parcels = ds_parcels.drop_vars("z")
        ds_parcels = ds_parcels.swap_dims({
            "obs": "obs_parcels",
            "trajectory": "trajectory_parcels"
            })
        ds_parcels = ds_parcels.rename_vars({
            "lon": "lon_parcels",
            "lat": "lat_parcels",
            "time": "time_parcels",
            "obs": "obs_parcels",
            "trajectory": "obj_trajectory"
            })
        ds_field = xr.open_dataset(self.ncin)
        ds = xr.merge([ds_parcels, ds_field])
        os.remove(self.ncin)
        ds.to_netcdf(self.ncin)
        shutil.rmtree(TMP_OFILE)
        
    def execute(self):
        pset = self._particleset_()
        pset.execute(
            parcels.AdvectionRK4,
            runtime=pd.to_timedelta(self.runtime),
            dt=pd.to_timedelta("1h"),
            output_file=self._particlefile_(pset),
            )
        self._post_()
    