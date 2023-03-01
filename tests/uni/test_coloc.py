from armoor import base
from armoor.base.colocation import colocate_all
from armoor.base.open_data import open_file
from tests.int.base import change_path

folder_test = 'uni_test_coloc'

class TestColoc:

    out_path, logger = change_path(folder_test)

    horizontal_colocation_flag = True
    vertical_colocation_flag = False
    temporal_colocation_flag = True

    model = '../data/uni_tests/model_pour_test.nc'
    observation = '../data/uni_tests/obs_pour_test.nc'

    start = '2020-06-02T00:00:00'
    end = '2020-06-03T00:00:00'
    polygon = [(-6, 47.5), (-6, 49.0), (-4, 49.0), (-4, 47.5)]

    obs = open_file(observation)
    obs = obs.read.decode()
    obs = obs.meta.time_selection_start(start)
    obs = obs.meta.time_selection_end(end)
    obs = obs.meta.horizontal_selection_polygon(polygon)

    mod = open_file(model)
    mod = mod.read.decode()
    mod = mod.meta.time_selection_start(start)
    mod = mod.meta.time_selection_end(end)
    mod = mod.meta.horizontal_selection_polygon(polygon)

    def test_coloc_auto(self):
        self.logger.info('test_coloc_auto')
        colocate_all(self.obs,
                     self.mod,
                     self.horizontal_colocation_flag,
                     self.vertical_colocation_flag,
                     self.temporal_colocation_flag,
                     opt_grid='auto')
        assert True

    def test_coloc_obs(self):
        self.logger.info('test_coloc_obs')
        colocate_all(self.obs,
                     self.mod,
                     self.horizontal_colocation_flag,
                     self.vertical_colocation_flag,
                     self.temporal_colocation_flag,
                     opt_grid='observation')
        assert True

    def test_coloc_mod(self):
        self.logger.info('test_coloc_mod')
        colocate_all(self.obs,
                     self.mod,
                     self.horizontal_colocation_flag,
                     self.vertical_colocation_flag,
                     self.temporal_colocation_flag,
                     opt_grid='model')
        assert True