import sys
import os
from xoa import cfgm
from armoor.cli.hmi import main
from tests.int.hmi import copy_test_files, change_path

copy_test_files()


class TestForecasterScripts:

    def test_med_1(self):
        test_name = 'hycom3d_med_1'
        out_path, logger = change_path(f'test_{test_name}')
        main(['-o', out_path, '-i', '../../data/', '-c', f'../../config/{test_name}.cfg'])
        assert True

    def test_med_2(self):
        test_name = 'hycom3d_med_2'
        out_path, logger = change_path(f'test_{test_name}')
        main(['-o', out_path, '-i', '../../data/', '-c', f'../../config/{test_name}.cfg'])
        assert True

    def test_med_3(self):
        test_name = 'hycom3d_med_3'
        out_path, logger = change_path(f'test_{test_name}')
        main(['-o', out_path, '-i', '../../data/', '-c', f'../../config/{test_name}.cfg'])
        assert True

    def test_med_4(self):
        test_name = 'hycom3d_med_4'
        out_path, logger = change_path(f'test_{test_name}')
        main(['-o', out_path, '-i', '../../data/', '-c', f'../../config/{test_name}.cfg'])
        assert True

    def test_med_5(self):
        test_name = 'hycom3d_med_5'
        out_path, logger = change_path(f'test_{test_name}')
        main(['-o', out_path, '-i', '../../data/', '-c', f'../../config/{test_name}.cfg'])
        assert True

    def test_med_10(self):
        test_name = 'hycom3d_med_10'
        out_path, logger = change_path(f'test_{test_name}')
        main(['-o', out_path, '-i', '../../data/', '-c', f'../../config/{test_name}.cfg'])
        assert True

    def test_med_11(self):
        test_name = 'hycom3d_med_11'
        out_path, logger = change_path(f'test_{test_name}')
        main(['-o', out_path, '-i', '../../data/', '-c', f'../../config/{test_name}.cfg'])
        assert True

    def test_med_12(self):
        test_name = 'hycom3d_med_12'
        out_path, logger = change_path(f'test_{test_name}')
        main(['-o', out_path, '-i', '../../data/', '-c', f'../../config/{test_name}.cfg'])
        assert True

    #  Please note that the next tests take approximately 1 hour each.
    #
    # def test_med(self):
    #     test_name = 'hycom3d_med_12345101112'
    #     out_path, logger = change_path(f'test_{test_name}')
    #     main(['-o', out_path, '-i', '../../data/', '-c', f'../../config/{test_name}.cfg'])
    #     assert True
    #
    # def test_indien(self):
    #     test_name = 'hycom3d_indien_1234589'
    #     out_path, logger = change_path(f'test_{test_name}')
    #     main(['-o', out_path, '-i', '../../data/', '-c', f'../../config/{test_name}.cfg'])
    #     assert True
    #
    # def test_manga(self):
    #     test_name = 'hycom3d_manga_1234567'
    #     out_path, logger = change_path(f'test_{test_name}')
    #     main(['-o', out_path, '-i', '../../data/', '-c', f'../../config/{test_name}.cfg'])
    #     assert True