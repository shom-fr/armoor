from armoor import base
import xarray as xr

vertical_colocation_flag = False
class TestColoc:

    model = 'N:\\1144-FE_Shom_Outils_validation_et_bulletins\\REALISATION\\Technique\\shared_data\\example\\model_pour_test.nc'
    observation = 'N:\\1144-FE_Shom_Outils_validation_et_bulletins\\REALISATION\\Technique\\shared_data\\example\\obs_test_ergane.nc'

    start = '2020-06-02T00:00:00.000000000'
    end = '2020-06-03T00:00:00.000000000'
    polygon = [(-6, 47.5), (-6, 49.0), (-4, 49.0), (-4, 47.5)]

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


    def test_coloc_auto(self):
        base.colocation.colocate(vertical_colocation_flag, self.obs, self.mod, obs_method='linear', mod_method='linear', opt_grid='auto')
        assert True

    def test_coloc_obs(self):
        base.colocation.colocate(vertical_colocation_flag, self.obs, self.mod, obs_method='nearest', mod_method='nearest', opt_grid='observation')
        assert True

    def test_coloc_mod(self):
        base.colocation.colocate(vertical_colocation_flag, self.obs, self.mod, obs_method='linear', mod_method='nearest', opt_grid='model')
        assert True
