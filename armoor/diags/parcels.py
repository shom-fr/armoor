import os, shutil

from datetime import timedelta
import numpy as np
import pandas as pd
import xarray as xr
import parcels
from xoa.regrid import grid2loc


TMP_OFILE = "ptc_tmp.zarr"


class MyParticle(parcels.JITParticle):
    start_time = parcels.Variable('start_time', dtype=np.float64)
    end_time = parcels.Variable('end_time', dtype=np.float64)
    active = parcels.Variable('active', dtype=np.int32, initial=1)


def check_runtime(particle, fieldset, time):
        """OceanParcels kernel: activate/deactivate a particle based on its own
        start_time/end_time window, deleting it once past end_time."""
        if time < particle.start_time:
            particle.active = 0  # Not active yet
        elif time >= particle.end_time:
            particle.active = 0  # Done
            particle.delete()
        else:
            particle.active = 1  # Active

def outofbounds(particle, fieldset, time):
    """OceanParcels kernel: delete a particle once it drifts out of the fieldset's domain."""
    if particle.state == parcels.StatusCode.ErrorOutOfBounds:
        particle.delete()

class  Parcels(object):

    def __init__(self, ncin, ptc_coords_start, runtime, outputdt=None):
        self.ncin = ncin
        self.ptc_coords_start = ptc_coords_start
        self.runtime = runtime
        self.outputdt = outputdt if outputdt else "3600s"
        self.vars = {
            "U": "u",
            "V": "v"
            }
        self.dims = {
            "lon": "lon",
            "lat": "lat",
            "time": "time"
            }

    def _fieldset_(self):
        return parcels.FieldSet.from_a_grid_dataset(
            self.ncin, self.vars, self.dims,
            chunksize="auto",
            allow_time_extrapolation=True,
            )

    def _particleset_(self):
        return parcels.ParticleSet(
            fieldset=self._fieldset_(),
            pclass=MyParticle,#parcels.JITParticle,
            **self.ptc_coords_start,
            )

    def _particlefile_(self, pset):
        outputdt = pd.to_timedelta(self.outputdt)
        outputdt = outputdt.to_pytimedelta()
        return pset.ParticleFile(
            name=TMP_OFILE,
            outputdt=pd.to_timedelta(outputdt)
            )

    def _post_(self):
        ds_parcels = xr.open_dataset(TMP_OFILE)
        if "z" in ds_parcels.data_vars:
            ds_parcels = ds_parcels.drop_vars("z")
        ds_parcels = ds_parcels.set_coords(["lon", "lat"])
        ds_field = xr.open_dataset(self.ncin)
        n = len(self.ptc_coords_start["time"])
        time = [pd.to_datetime(ds_field.time.min().values) + pd.to_timedelta(t, "s") for t in self.ptc_coords_start["time"]]
        self.ptc_coords_start["time"] = time
        da = xr.DataArray(
            np.zeros(n),
            coords={
                coord: (
                    "npt", self.ptc_coords_start[coord]
                    ) for coord in ["time", "lon", "lat"]
                },
            dims=["npt"]
            )
        u_parcels = grid2loc(
            ds_field["u"],
            da
            )
        u_parcels = u_parcels.to_dataset(name="u_drifter")
        v_parcels = grid2loc(
            ds_field["v"],
            da
            )
        del da
        v_parcels = v_parcels.to_dataset(name="v_drifter")
        ds_drifter = xr.merge([u_parcels, v_parcels])
        del u_parcels
        del v_parcels
        ds_drifter = ds_drifter.rename({
            "time": "time_drifter",
            "lon": "lon_drifter",
            "lat": "lat_drifter",
            })
        ds_parcels = ds_parcels.swap_dims({
            "obs": "obs_parcels",
            "trajectory": "trajectory_parcels"
            }).rename_vars({
            "lon": "lon_parcels",
            "lat": "lat_parcels",
            "time": "time_parcels",
            "obs": "obs_parcels",
            "trajectory": "obj_trajectory"
            })
        ds = xr.merge([ds_parcels, ds_field, ds_drifter])
        ds = ds.assign_attrs({**ds_field.attrs})
        os.remove(self.ncin)
        ds.to_netcdf(self.ncin)
        ds.close()
        ds_parcels.close()
        ds_drifter.close()
        del ds_drifter
        del ds_parcels
        shutil.rmtree(TMP_OFILE)

    def execute(self):
        """Run the particle-tracking simulation and post-process its output.

        Builds the particle set, gives each particle its own start/end time
        window (from `ptc_coords_start["time"]` and `self.runtime`), then
        advects every particle (`parcels.AdvectionRK4`, gated by
        `check_runtime`/`outofbounds`) over the full time span, and merges
        the result back with the drifter's own coordinates via `_post_`.
        """
        pset = self._particleset_()
        for i, particle in enumerate(pset):
            particle.start_time = self.ptc_coords_start["time"][i]
            particle.end_time = self.ptc_coords_start["time"][i] + self.runtime
        dt = pd.to_timedelta("3600s")
        dt = dt.to_pytimedelta()
        runtime = pd.to_timedelta(
            self.ptc_coords_start["time"][-1] - self.ptc_coords_start["time"][0]
            , "s")
        pset.execute(
            [parcels.AdvectionRK4, check_runtime, outofbounds],
            runtime=runtime,
            dt=dt,
            output_file=self._particlefile_(pset),
            )
        self._post_()

