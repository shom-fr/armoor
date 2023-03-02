import sys
import os
from xoa import cfgm
from armoor.bull.run_script import main
from armoor.hmi.script_tools import create_folder

rootdir = os.path.abspath(os.path.dirname(__file__))
cfgm_forecaster = cfgm.ConfigManager(os.path.join(rootdir, "../../tests.ini"))
paths = cfgm_forecaster.load(os.path.join(rootdir, "../../../config/tests.cfg"))

def change_path():
    os.chdir(paths["path_p1"])

    out_path = 'output_test_bull/'
    create_folder(out_path)

    return out_path

class TestBulletins:

    def test_f1(self):
        out_path = change_path()
        bull_path = f'{out_path}f1/'
        create_folder(bull_path)
        main(['-o', bull_path, '-c', 'Bulletin_f1.ini'])
        assert True

    def test_f2(self):
        out_path = change_path()
        bull_path = f'{out_path}f2/'
        create_folder(bull_path)
        main(['-o', bull_path, '-c', 'Bulletin_f2.ini'])
        assert True

    def test_f3(self):
        out_path = change_path()
        bull_path = f'{out_path}f3/'
        create_folder(bull_path)
        main(['-o', bull_path, '-c', 'Bulletin_f3.ini'])
        assert True

    def test_f4(self):
        out_path = change_path()
        bull_path = f'{out_path}f4/'
        create_folder(bull_path)
        main(['-o', bull_path, '-c', 'Bulletin_f4.ini'])
        assert True

    def test_f5(self):
        out_path = change_path()
        bull_path = f'{out_path}f5/'
        create_folder(bull_path)
        main(['-o', bull_path, '-c', 'Bulletin_f5.ini'])
        assert True

    def test_f6(self):
        out_path = change_path()
        bull_path = f'{out_path}f6/'
        create_folder(bull_path)
        main(['-o', bull_path, '-c', 'Bulletin_f6.ini'])
        assert True

    def test_f7(self):
        out_path = change_path()
        bull_path = f'{out_path}f7/'
        create_folder(bull_path)
        main(['-o', bull_path, '-c', 'Bulletin_f7.ini'])
        assert True

    def test_f8(self):
        out_path = change_path()
        bull_path = f'{out_path}f8/'
        create_folder(bull_path)
        main(['-o', bull_path, '-c', 'Bulletin_f8.ini'])
        assert True

    def test_f9(self):
        out_path = change_path()
        bull_path = f'{out_path}f9/'
        create_folder(bull_path)
        main(['-o', bull_path, '-c', 'Bulletin_f9.ini'])
        assert True