import sys
import os
from xoa import cfgm
from armoor.hmi.run_script import main
from armoor.hmi.script_tools import create_folder

rootdir = os.path.abspath(os.path.dirname(__file__))
cfgm_forecaster = cfgm.ConfigManager(os.path.join(rootdir, "../../../config/tests/tests.ini"))
paths = cfgm_forecaster.load(os.path.join(rootdir, "../../../config/tests.cfg"))

def change_path():
    os.chdir(paths["path_p3"])

class TestForecasterScripts:

    def test_med_1(self):
        change_path()
        out_path = 'out/test_med_1/'
        create_folder(out_path)
        main(['-o', out_path, '-i', 'data/', '-c', 'config/hycom3d_med_1.ini'])
        assert True

    def test_med_2(self):
        change_path()
        out_path = 'out/test_med_2/'
        create_folder(out_path)
        main(['-o', out_path, '-i', 'data/', '-c', 'config/hycom3d_med_2.ini'])
        assert True

    def test_med_3(self):
        change_path()
        out_path = 'out/test_med_3/'
        create_folder(out_path)
        main(['-o', out_path, '-i', 'data/', '-c', 'config/hycom3d_med_3.ini'])
        assert True

    def test_med_4(self):
        change_path()
        out_path = 'out/test_med_4/'
        create_folder(out_path)
        main(['-o', out_path, '-i', 'data/', '-c', 'config/hycom3d_med_4.ini'])
        assert True

    def test_med_5(self):
        change_path()
        out_path = 'out/test_med_5/'
        create_folder(out_path)
        main(['-o', out_path, '-i', 'data/', '-c', 'config/hycom3d_med_5.ini'])
        assert True

    def test_med_10(self):
        change_path()
        out_path = 'out/test_med_10/'
        create_folder(out_path)
        main(['-o', out_path, '-i', 'data/', '-c', 'config/hycom3d_med_10.ini'])
        assert True

    def test_med_11(self):
        change_path()
        out_path = 'out/test_med_11/'
        create_folder(out_path)
        main(['-o', out_path, '-i', 'data/', '-c', 'config/hycom3d_med_11.ini'])
        assert True

    def test_med_12(self):
        change_path()
        out_path = 'out/test_med_12/'
        create_folder(out_path)
        main(['-o', out_path, '-i', 'data/', '-c', 'config/hycom3d_med_12.ini'])
        assert True

    # #TODO uncomment : Caution next tests takes around 1h each
    #
    # def test_med(self):
    #     change_path()
    #     out_path = 'out/test_med/'
    #     create_folder(out_path)
    #     main(['-o', out_path, '-i', 'data/', '-c', 'config/hycom3d_med_12345101112.ini'])
    #     assert True
    #
    # def test_indien(self):
    #     change_path()
    #     out_path = 'out/test_indien/'
    #     create_folder(out_path)
    #     main(['-o', out_path, '-i', 'data/', '-c', 'config/hycom3d_indien_1234589.ini'])
    #     assert True
    #
    # def test_manga(self):
    #     change_path()
    #     out_path = 'out/test_manga/'
    #     create_folder(out_path)
    #     main(['-o', out_path, '-i', 'data/', '-c', 'config/hycom3d_manga_1234567.ini'])
    #     assert True