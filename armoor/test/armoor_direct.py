# import armoor <-once installed
from armoor import base
import xarray as xr

model = 'N:\\1144-FE_Shom_Outils_validation_et_bulletins\\REALISATION\\Technique\\shared_data\\example\\model_pour_test.nc'
observation = 'N:\\1144-FE_Shom_Outils_validation_et_bulletins\\REALISATION\\Technique\\shared_data\\example\\obs_test_ergane.nc'

start = '2020-06-02T00:00:00'
end = '2020-06-03T00:00:00'
polygon = [(-6, 47.5), (-6, 49.0), (-4, 49.0), (-4, 47.5)]
colocate = 'observation'

obs = xr.open_dataset(observation)
obs = obs.read.decode()
obs = obs.meta.time_selection_start(start)
obs = obs.meta.time_selection_end(end)
obs = obs.meta.horizontal_selection_polygon(polygon)

mod = xr.open_dataset(model)
mod = mod.read.decode()
mod = mod.meta.time_selection_start(start)
mod = mod.meta.time_selection_end(end)
mod = mod.meta.horizontal_selection_polygon(polygon)

obs_coloc_l, mod_coloc_l = base.colocate(obs=obs,
                                         mod=mod,
                                         obs_method=None,
                                         mod_method='linear',
                                         opt_grid=colocate)

obs_coloc_n, mod_coloc_n = base.colocate(obs=obs,
                                         mod=mod,
                                         obs_method=None,
                                         mod_method='nearest',
                                         opt_grid=colocate)

mod = mod.read_sst.sel_sst()
mod_coloc_l = mod_coloc_l.read_sst.sel_sst()
mod_coloc_n = mod_coloc_n.read_sst.sel_sst()

obs = obs.read_sst.sel_sst()
obs_coloc_l = obs_coloc_l.read_sst.sel_sst()
obs_coloc_n = obs_coloc_n.read_sst.sel_sst()


base.plot_features.plot_map_metr(mod,
                                 mod_coloc_n,
                                 obs,
                                 obs_coloc_n,
                                  'RMSEc')

base.plot_features.plot_map_metr(mod,
                                 mod_coloc_l,
                                 obs,
                                 obs_coloc_l,
                                  'RMSEc')

"""'example/croco.south-africa.meridional.nc'
example/SST_L3MONOSENSOR.nc
example/nemo.nc"""
