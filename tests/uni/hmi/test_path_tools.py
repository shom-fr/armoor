import sys
import os
from xoa import cfgm
from armoor.hmi.path_tools import get_config_reg_path, get_obs_path, get_forcing_model_path, sort_by_start_name
from tests.uni.hmi import copy_test_files, change_path, test_day, get_input_folder_path, model, config

copy_test_files()


class TestPathTools:

    def test_get_config_reg_path(self):
        test_name = 'get_config_reg_path'
        _, logger = change_path(f'test_{test_name}')

        config_reg = f'{model}_{config}'
        input_folder_path = get_input_folder_path()
        config_reg_day = f"{config_reg}_{test_day}"

        assert get_config_reg_path(input_folder_path, config_reg_day, "sst") == \
               [os.path.join('..', 'empty_data', config_reg_day, 'model', f'sst_2D_{config}.nc')]
        assert get_config_reg_path(input_folder_path, config_reg_day, "sss") == \
               [os.path.join('..', 'empty_data', config_reg_day, 'model', f'sss_2D_{config}.nc')]
        assert get_config_reg_path(input_folder_path, config_reg_day, "suv") == \
               [os.path.join('..', 'empty_data', config_reg_day, 'model', f'u_2D_{config}.nc'),
                os.path.join('..', 'empty_data', config_reg_day, 'model', f'v_2D_{config}.nc')]

        assert get_config_reg_path(input_folder_path, config_reg_day, "temp") == \
               [os.path.join('..', 'empty_data', config_reg_day, 'model', f'h_3D_{config}.nc'),
                os.path.join('..', 'empty_data', config_reg_day, 'model', f'temp_3D_{config}.nc')]
        assert get_config_reg_path(input_folder_path, config_reg_day, "sal") == \
               [os.path.join('..', 'empty_data', config_reg_day, 'model', f'h_3D_{config}.nc'),
                os.path.join('..', 'empty_data', config_reg_day, 'model', f'saln_3D_{config}.nc')]
        assert get_config_reg_path(input_folder_path, config_reg_day, "uv") == \
               [os.path.join('..', 'empty_data', config_reg_day, 'model', f'h_3D_{config}.nc'),
                os.path.join('..', 'empty_data', config_reg_day, 'model', f'u_3D_{config}.nc'),
                os.path.join('..', 'empty_data', config_reg_day, 'model', f'v_3D_{config}.nc')]

    def test_get_obs_path(self):
        test_name = 'get_obs_path'
        _, logger = change_path(f'test_{test_name}')

        config_reg = f'{model}_{config}'
        input_folder_path = get_input_folder_path()
        config_reg_day = f"{config_reg}_{test_day}"

        assert get_obs_path(input_folder_path, config_reg_day, 'sstl4', 'sst') == \
               [os.path.join('..', 'empty_data', config_reg_day, 'sstl4',
                             '20220309120000-UKMO-L4_GHRSST-SSTfnd-OSTIAanom-GLOB-v02.0-fv02.0.nc')]

        assert get_obs_path(input_folder_path, config_reg_day, 'woa18', 'sss') == \
               [os.path.join('..', 'empty_data', config_reg_day, 'woa18', 'woa18_decav_s03_04.nc')]
        assert get_obs_path(input_folder_path, config_reg_day, 'woa18', 'sst') == \
               [os.path.join('..', 'empty_data', config_reg_day, 'woa18', 'woa18_decav_t03_04.nc')]
        assert get_obs_path(input_folder_path, config_reg_day, 'woa18', 'sal') == \
               [os.path.join('..', 'empty_data', config_reg_day, 'woa18', 'woa18_decav_s03_04.nc')]
        assert get_obs_path(input_folder_path, config_reg_day, 'woa18', 'temp') == \
               [os.path.join('..', 'empty_data', config_reg_day, 'woa18', 'woa18_decav_t03_04.nc')]

    def test_get_forcing_model_path(self):
        test_name = 'get_forcing_model_path'
        _, logger = change_path(f'test_{test_name}')

        config_reg = f'{model}_{config}'
        input_folder_path = get_input_folder_path()
        config_reg_day = f"{config_reg}_{test_day}"

        def get_timestamp_from_path(path, delimiter):
            filename = os.path.basename(path)
            parts = filename.split(delimiter)
            timestamp_str = parts[1]
            return timestamp_str

        def sort_river_dict(my_dict):
            for key in my_dict:
                my_dict[key] = sorted(my_dict[key], key=lambda x: get_timestamp_from_path(x, 'GL_TS'))
            return my_dict


        assert sorted(get_forcing_model_path(input_folder_path, config_reg_day, "atmfrc/insta", 'uv'),
                      key=lambda x: get_timestamp_from_path(x, 'arpege')) == \
               [os.path.join('..', 'empty_data', config_reg_day, 'atmfrc', 'insta', 'arpege_202203090000_0000_ana_insta.grib'),
                os.path.join('..', 'empty_data', config_reg_day, 'atmfrc', 'insta', 'arpege_202203090000_0001_ana_insta.grib'),
                os.path.join('..', 'empty_data', config_reg_day, 'atmfrc', 'insta', 'arpege_202203090000_0002_ana_insta.grib'),
                os.path.join('..', 'empty_data', config_reg_day, 'atmfrc', 'insta', 'arpege_202203090000_0003_ana_insta.grib'),
                os.path.join('..', 'empty_data', config_reg_day, 'atmfrc', 'insta', 'arpege_202203090000_0004_ana_insta.grib'),
                os.path.join('..', 'empty_data', config_reg_day, 'atmfrc', 'insta', 'arpege_202203090000_0005_ana_insta.grib'),
                os.path.join('..', 'empty_data', config_reg_day, 'atmfrc', 'insta', 'arpege_202203090600_0000_ana_insta.grib'),
                os.path.join('..', 'empty_data', config_reg_day, 'atmfrc', 'insta', 'arpege_202203090600_0001_ana_insta.grib'),
                os.path.join('..', 'empty_data', config_reg_day, 'atmfrc', 'insta', 'arpege_202203090600_0002_ana_insta.grib'),
                os.path.join('..', 'empty_data', config_reg_day, 'atmfrc', 'insta', 'arpege_202203090600_0003_ana_insta.grib'),
                os.path.join('..', 'empty_data', config_reg_day, 'atmfrc', 'insta', 'arpege_202203090600_0004_ana_insta.grib'),
                os.path.join('..', 'empty_data', config_reg_day, 'atmfrc', 'insta', 'arpege_202203090600_0005_ana_insta.grib'),
                os.path.join('..', 'empty_data', config_reg_day, 'atmfrc', 'insta', 'arpege_202203091200_0000_ana_insta.grib'),
                os.path.join('..', 'empty_data', config_reg_day, 'atmfrc', 'insta', 'arpege_202203091200_0001_ana_insta.grib'),
                os.path.join('..', 'empty_data', config_reg_day, 'atmfrc', 'insta', 'arpege_202203091200_0002_ana_insta.grib'),
                os.path.join('..', 'empty_data', config_reg_day, 'atmfrc', 'insta', 'arpege_202203091200_0003_ana_insta.grib'),
                os.path.join('..', 'empty_data', config_reg_day, 'atmfrc', 'insta', 'arpege_202203091200_0004_ana_insta.grib'),
                os.path.join('..', 'empty_data', config_reg_day, 'atmfrc', 'insta', 'arpege_202203091200_0005_ana_insta.grib'),
                os.path.join('..', 'empty_data', config_reg_day, 'atmfrc', 'insta', 'arpege_202203091800_0000_ana_insta.grib'),
                os.path.join('..', 'empty_data', config_reg_day, 'atmfrc', 'insta', 'arpege_202203091800_0001_ana_insta.grib'),
                os.path.join('..', 'empty_data', config_reg_day, 'atmfrc', 'insta', 'arpege_202203091800_0002_ana_insta.grib'),
                os.path.join('..', 'empty_data', config_reg_day, 'atmfrc', 'insta', 'arpege_202203091800_0003_ana_insta.grib'),
                os.path.join('..', 'empty_data', config_reg_day, 'atmfrc', 'insta', 'arpege_202203091800_0004_ana_insta.grib'),
                os.path.join('..', 'empty_data', config_reg_day, 'atmfrc', 'insta', 'arpege_202203091800_0005_ana_insta.grib'),
                os.path.join('..', 'empty_data', config_reg_day, 'atmfrc', 'insta', 'arpege_202203100000_0000_fcst_insta.grib'),
                os.path.join('..', 'empty_data', config_reg_day, 'atmfrc', 'insta', 'arpege_202203100000_0001_fcst_insta.grib'),
                os.path.join('..', 'empty_data', config_reg_day, 'atmfrc', 'insta', 'arpege_202203100000_0002_fcst_insta.grib'),
                os.path.join('..', 'empty_data', config_reg_day, 'atmfrc', 'insta', 'arpege_202203100000_0003_fcst_insta.grib'),
                os.path.join('..', 'empty_data', config_reg_day, 'atmfrc', 'insta', 'arpege_202203100000_0004_fcst_insta.grib'),
                os.path.join('..', 'empty_data', config_reg_day, 'atmfrc', 'insta', 'arpege_202203100000_0005_fcst_insta.grib'),
                os.path.join('..', 'empty_data', config_reg_day, 'atmfrc', 'insta', 'arpege_202203100000_0006_fcst_insta.grib'),
                os.path.join('..', 'empty_data', config_reg_day, 'atmfrc', 'insta', 'arpege_202203100000_0007_fcst_insta.grib'),
                os.path.join('..', 'empty_data', config_reg_day, 'atmfrc', 'insta', 'arpege_202203100000_0008_fcst_insta.grib'),
                os.path.join('..', 'empty_data', config_reg_day, 'atmfrc', 'insta', 'arpege_202203100000_0009_fcst_insta.grib'),
                os.path.join('..', 'empty_data', config_reg_day, 'atmfrc', 'insta', 'arpege_202203100000_0010_fcst_insta.grib'),
                os.path.join('..', 'empty_data', config_reg_day, 'atmfrc', 'insta', 'arpege_202203100000_0011_fcst_insta.grib'),
                os.path.join('..', 'empty_data', config_reg_day, 'atmfrc', 'insta', 'arpege_202203100000_0012_fcst_insta.grib'),
                os.path.join('..', 'empty_data', config_reg_day, 'atmfrc', 'insta', 'arpege_202203100000_0013_fcst_insta.grib'),
                os.path.join('..', 'empty_data', config_reg_day, 'atmfrc', 'insta', 'arpege_202203100000_0014_fcst_insta.grib'),
                os.path.join('..', 'empty_data', config_reg_day, 'atmfrc', 'insta', 'arpege_202203100000_0015_fcst_insta.grib'),
                os.path.join('..', 'empty_data', config_reg_day, 'atmfrc', 'insta', 'arpege_202203100000_0016_fcst_insta.grib'),
                os.path.join('..', 'empty_data', config_reg_day, 'atmfrc', 'insta', 'arpege_202203100000_0017_fcst_insta.grib'),
                os.path.join('..', 'empty_data', config_reg_day, 'atmfrc', 'insta', 'arpege_202203100000_0018_fcst_insta.grib'),
                os.path.join('..', 'empty_data', config_reg_day, 'atmfrc', 'insta', 'arpege_202203100000_0019_fcst_insta.grib'),
                os.path.join('..', 'empty_data', config_reg_day, 'atmfrc', 'insta', 'arpege_202203100000_0020_fcst_insta.grib'),
                os.path.join('..', 'empty_data', config_reg_day, 'atmfrc', 'insta', 'arpege_202203100000_0021_fcst_insta.grib'),
                os.path.join('..', 'empty_data', config_reg_day, 'atmfrc', 'insta', 'arpege_202203100000_0022_fcst_insta.grib'),
                os.path.join('..', 'empty_data', config_reg_day, 'atmfrc', 'insta', 'arpege_202203100000_0023_fcst_insta.grib'),
                os.path.join('..', 'empty_data', config_reg_day, 'atmfrc', 'insta', 'arpege_202203100000_0024_fcst_insta.grib'),
                os.path.join('..', 'empty_data', config_reg_day, 'atmfrc', 'insta', 'arpege_202203100000_0025_fcst_insta.grib'),
                os.path.join('..', 'empty_data', config_reg_day, 'atmfrc', 'insta', 'arpege_202203100000_0026_fcst_insta.grib'),
                os.path.join('..', 'empty_data', config_reg_day, 'atmfrc', 'insta', 'arpege_202203100000_0027_fcst_insta.grib'),
                os.path.join('..', 'empty_data', config_reg_day, 'atmfrc', 'insta', 'arpege_202203100000_0028_fcst_insta.grib'),
                os.path.join('..', 'empty_data', config_reg_day, 'atmfrc', 'insta', 'arpege_202203100000_0029_fcst_insta.grib'),
                os.path.join('..', 'empty_data', config_reg_day, 'atmfrc', 'insta', 'arpege_202203100000_0030_fcst_insta.grib'),
                os.path.join('..', 'empty_data', config_reg_day, 'atmfrc', 'insta', 'arpege_202203100000_0031_fcst_insta.grib'),
                os.path.join('..', 'empty_data', config_reg_day, 'atmfrc', 'insta', 'arpege_202203100000_0032_fcst_insta.grib'),
                os.path.join('..', 'empty_data', config_reg_day, 'atmfrc', 'insta', 'arpege_202203100000_0033_fcst_insta.grib'),
                os.path.join('..', 'empty_data', config_reg_day, 'atmfrc', 'insta', 'arpege_202203100000_0034_fcst_insta.grib'),
                os.path.join('..', 'empty_data', config_reg_day, 'atmfrc', 'insta', 'arpege_202203100000_0035_fcst_insta.grib'),
                os.path.join('..', 'empty_data', config_reg_day, 'atmfrc', 'insta', 'arpege_202203100000_0036_fcst_insta.grib'),
                os.path.join('..', 'empty_data', config_reg_day, 'atmfrc', 'insta', 'arpege_202203100000_0037_fcst_insta.grib'),
                os.path.join('..', 'empty_data', config_reg_day, 'atmfrc', 'insta', 'arpege_202203100000_0038_fcst_insta.grib'),
                os.path.join('..', 'empty_data', config_reg_day, 'atmfrc', 'insta', 'arpege_202203100000_0039_fcst_insta.grib'),
                os.path.join('..', 'empty_data', config_reg_day, 'atmfrc', 'insta', 'arpege_202203100000_0040_fcst_insta.grib'),
                os.path.join('..', 'empty_data', config_reg_day, 'atmfrc', 'insta', 'arpege_202203100000_0041_fcst_insta.grib'),
                os.path.join('..', 'empty_data', config_reg_day, 'atmfrc', 'insta', 'arpege_202203100000_0042_fcst_insta.grib'),
                os.path.join('..', 'empty_data', config_reg_day, 'atmfrc', 'insta', 'arpege_202203100000_0043_fcst_insta.grib'),
                os.path.join('..', 'empty_data', config_reg_day, 'atmfrc', 'insta', 'arpege_202203100000_0044_fcst_insta.grib'),
                os.path.join('..', 'empty_data', config_reg_day, 'atmfrc', 'insta', 'arpege_202203100000_0045_fcst_insta.grib'),
                os.path.join('..', 'empty_data', config_reg_day, 'atmfrc', 'insta', 'arpege_202203100000_0046_fcst_insta.grib'),
                os.path.join('..', 'empty_data', config_reg_day, 'atmfrc', 'insta', 'arpege_202203100000_0047_fcst_insta.grib'),
                os.path.join('..', 'empty_data', config_reg_day, 'atmfrc', 'insta', 'arpege_202203100000_0048_fcst_insta.grib'),
                os.path.join('..', 'empty_data', config_reg_day, 'atmfrc', 'insta', 'arpege_202203100000_0049_fcst_insta.grib'),
                os.path.join('..', 'empty_data', config_reg_day, 'atmfrc', 'insta', 'arpege_202203100000_0050_fcst_insta.grib'),
                os.path.join('..', 'empty_data', config_reg_day, 'atmfrc', 'insta', 'arpege_202203100000_0051_fcst_insta.grib'),
                os.path.join('..', 'empty_data', config_reg_day, 'atmfrc', 'insta', 'arpege_202203100000_0052_fcst_insta.grib'),
                os.path.join('..', 'empty_data', config_reg_day, 'atmfrc', 'insta', 'arpege_202203100000_0053_fcst_insta.grib'),
                os.path.join('..', 'empty_data', config_reg_day, 'atmfrc', 'insta', 'arpege_202203100000_0054_fcst_insta.grib'),
                os.path.join('..', 'empty_data', config_reg_day, 'atmfrc', 'insta', 'arpege_202203100000_0055_fcst_insta.grib'),
                os.path.join('..', 'empty_data', config_reg_day, 'atmfrc', 'insta', 'arpege_202203100000_0056_fcst_insta.grib'),
                os.path.join('..', 'empty_data', config_reg_day, 'atmfrc', 'insta', 'arpege_202203100000_0057_fcst_insta.grib'),
                os.path.join('..', 'empty_data', config_reg_day, 'atmfrc', 'insta', 'arpege_202203100000_0058_fcst_insta.grib'),
                os.path.join('..', 'empty_data', config_reg_day, 'atmfrc', 'insta', 'arpege_202203100000_0059_fcst_insta.grib'),
                os.path.join('..', 'empty_data', config_reg_day, 'atmfrc', 'insta', 'arpege_202203100000_0060_fcst_insta.grib'),
                os.path.join('..', 'empty_data', config_reg_day, 'atmfrc', 'insta', 'arpege_202203100000_0061_fcst_insta.grib'),
                os.path.join('..', 'empty_data', config_reg_day, 'atmfrc', 'insta', 'arpege_202203100000_0062_fcst_insta.grib'),
                os.path.join('..', 'empty_data', config_reg_day, 'atmfrc', 'insta', 'arpege_202203100000_0063_fcst_insta.grib'),
                os.path.join('..', 'empty_data', config_reg_day, 'atmfrc', 'insta', 'arpege_202203100000_0064_fcst_insta.grib'),
                os.path.join('..', 'empty_data', config_reg_day, 'atmfrc', 'insta', 'arpege_202203100000_0065_fcst_insta.grib'),
                os.path.join('..', 'empty_data', config_reg_day, 'atmfrc', 'insta', 'arpege_202203100000_0066_fcst_insta.grib'),
                os.path.join('..', 'empty_data', config_reg_day, 'atmfrc', 'insta', 'arpege_202203100000_0067_fcst_insta.grib'),
                os.path.join('..', 'empty_data', config_reg_day, 'atmfrc', 'insta', 'arpege_202203100000_0068_fcst_insta.grib'),
                os.path.join('..', 'empty_data', config_reg_day, 'atmfrc', 'insta', 'arpege_202203100000_0069_fcst_insta.grib'),
                os.path.join('..', 'empty_data', config_reg_day, 'atmfrc', 'insta', 'arpege_202203100000_0070_fcst_insta.grib'),
                os.path.join('..', 'empty_data', config_reg_day, 'atmfrc', 'insta', 'arpege_202203100000_0071_fcst_insta.grib'),
                os.path.join('..', 'empty_data', config_reg_day, 'atmfrc', 'insta', 'arpege_202203100000_0072_fcst_insta.grib'),
                os.path.join('..', 'empty_data', config_reg_day, 'atmfrc', 'insta', 'arpege_202203100000_0073_fcst_insta.grib'),
                os.path.join('..', 'empty_data', config_reg_day, 'atmfrc', 'insta', 'arpege_202203100000_0074_fcst_insta.grib'),
                os.path.join('..', 'empty_data', config_reg_day, 'atmfrc', 'insta', 'arpege_202203100000_0075_fcst_insta.grib'),
                os.path.join('..', 'empty_data', config_reg_day, 'atmfrc', 'insta', 'arpege_202203100000_0076_fcst_insta.grib'),
                os.path.join('..', 'empty_data', config_reg_day, 'atmfrc', 'insta', 'arpege_202203100000_0077_fcst_insta.grib'),
                os.path.join('..', 'empty_data', config_reg_day, 'atmfrc', 'insta', 'arpege_202203100000_0078_fcst_insta.grib'),
                os.path.join('..', 'empty_data', config_reg_day, 'atmfrc', 'insta', 'arpege_202203100000_0079_fcst_insta.grib'),
                os.path.join('..', 'empty_data', config_reg_day, 'atmfrc', 'insta', 'arpege_202203100000_0080_fcst_insta.grib'),
                os.path.join('..', 'empty_data', config_reg_day, 'atmfrc', 'insta', 'arpege_202203100000_0081_fcst_insta.grib'),
                os.path.join('..', 'empty_data', config_reg_day, 'atmfrc', 'insta', 'arpege_202203100000_0082_fcst_insta.grib'),
                os.path.join('..', 'empty_data', config_reg_day, 'atmfrc', 'insta', 'arpege_202203100000_0083_fcst_insta.grib'),
                os.path.join('..', 'empty_data', config_reg_day, 'atmfrc', 'insta', 'arpege_202203100000_0084_fcst_insta.grib'),
                os.path.join('..', 'empty_data', config_reg_day, 'atmfrc', 'insta', 'arpege_202203100000_0085_fcst_insta.grib'),
                os.path.join('..', 'empty_data', config_reg_day, 'atmfrc', 'insta', 'arpege_202203100000_0086_fcst_insta.grib'),
                os.path.join('..', 'empty_data', config_reg_day, 'atmfrc', 'insta', 'arpege_202203100000_0087_fcst_insta.grib'),
                os.path.join('..', 'empty_data', config_reg_day, 'atmfrc', 'insta', 'arpege_202203100000_0088_fcst_insta.grib'),
                os.path.join('..', 'empty_data', config_reg_day, 'atmfrc', 'insta', 'arpege_202203100000_0089_fcst_insta.grib'),
                os.path.join('..', 'empty_data', config_reg_day, 'atmfrc', 'insta', 'arpege_202203100000_0090_fcst_insta.grib'),
                os.path.join('..', 'empty_data', config_reg_day, 'atmfrc', 'insta', 'arpege_202203100000_0091_fcst_insta.grib'),
                os.path.join('..', 'empty_data', config_reg_day, 'atmfrc', 'insta', 'arpege_202203100000_0092_fcst_insta.grib'),
                os.path.join('..', 'empty_data', config_reg_day, 'atmfrc', 'insta', 'arpege_202203100000_0093_fcst_insta.grib'),
                os.path.join('..', 'empty_data', config_reg_day, 'atmfrc', 'insta', 'arpege_202203100000_0094_fcst_insta.grib'),
                os.path.join('..', 'empty_data', config_reg_day, 'atmfrc', 'insta', 'arpege_202203100000_0095_fcst_insta.grib'),
                os.path.join('..', 'empty_data', config_reg_day, 'atmfrc', 'insta', 'arpege_202203100000_0096_fcst_insta.grib'),
                os.path.join('..', 'empty_data', config_reg_day, 'atmfrc', 'insta', 'arpege_202203100000_0097_fcst_insta.grib'),
                os.path.join('..', 'empty_data', config_reg_day, 'atmfrc', 'insta', 'arpege_202203100000_0098_fcst_insta.grib'),
                os.path.join('..', 'empty_data', config_reg_day, 'atmfrc', 'insta', 'arpege_202203100000_0099_fcst_insta.grib'),
                os.path.join('..', 'empty_data', config_reg_day, 'atmfrc', 'insta', 'arpege_202203100000_0100_fcst_insta.grib'),
                os.path.join('..', 'empty_data', config_reg_day, 'atmfrc', 'insta', 'arpege_202203100000_0101_fcst_insta.grib'),
                os.path.join('..', 'empty_data', config_reg_day, 'atmfrc', 'insta', 'arpege_202203100000_0102_fcst_insta.grib')]

        assert sorted(get_forcing_model_path(input_folder_path, config_reg_day, "atmfrc/cumul", 'tp'),
                      key=lambda x: get_timestamp_from_path(x, 'arpege')) == \
               sorted(get_forcing_model_path(input_folder_path, config_reg_day, "atmfrc/cumul", 'hfsen'),
                      key=lambda x: get_timestamp_from_path(x, 'arpege')) == \
               [os.path.join('..', 'empty_data', config_reg_day, 'atmfrc', 'cumul', 'arpege_202203090000_0001_ana_cumul.grib'),
                os.path.join('..', 'empty_data', config_reg_day, 'atmfrc', 'cumul', 'arpege_202203090000_0002_ana_cumul.grib'),
                os.path.join('..', 'empty_data', config_reg_day, 'atmfrc', 'cumul', 'arpege_202203090000_0003_ana_cumul.grib'),
                os.path.join('..', 'empty_data', config_reg_day, 'atmfrc', 'cumul', 'arpege_202203090000_0004_ana_cumul.grib'),
                os.path.join('..', 'empty_data', config_reg_day, 'atmfrc', 'cumul', 'arpege_202203090000_0005_ana_cumul.grib'),
                os.path.join('..', 'empty_data', config_reg_day, 'atmfrc', 'cumul', 'arpege_202203090000_0006_ana_cumul.grib'),
                os.path.join('..', 'empty_data', config_reg_day, 'atmfrc', 'cumul', 'arpege_202203090600_0001_ana_cumul.grib'),
                os.path.join('..', 'empty_data', config_reg_day, 'atmfrc', 'cumul', 'arpege_202203090600_0002_ana_cumul.grib'),
                os.path.join('..', 'empty_data', config_reg_day, 'atmfrc', 'cumul', 'arpege_202203090600_0003_ana_cumul.grib'),
                os.path.join('..', 'empty_data', config_reg_day, 'atmfrc', 'cumul', 'arpege_202203090600_0004_ana_cumul.grib'),
                os.path.join('..', 'empty_data', config_reg_day, 'atmfrc', 'cumul', 'arpege_202203090600_0005_ana_cumul.grib'),
                os.path.join('..', 'empty_data', config_reg_day, 'atmfrc', 'cumul', 'arpege_202203090600_0006_ana_cumul.grib'),
                os.path.join('..', 'empty_data', config_reg_day, 'atmfrc', 'cumul', 'arpege_202203091200_0001_ana_cumul.grib'),
                os.path.join('..', 'empty_data', config_reg_day, 'atmfrc', 'cumul', 'arpege_202203091200_0002_ana_cumul.grib'),
                os.path.join('..', 'empty_data', config_reg_day, 'atmfrc', 'cumul', 'arpege_202203091200_0003_ana_cumul.grib'),
                os.path.join('..', 'empty_data', config_reg_day, 'atmfrc', 'cumul', 'arpege_202203091200_0004_ana_cumul.grib'),
                os.path.join('..', 'empty_data', config_reg_day, 'atmfrc', 'cumul', 'arpege_202203091200_0005_ana_cumul.grib'),
                os.path.join('..', 'empty_data', config_reg_day, 'atmfrc', 'cumul', 'arpege_202203091200_0006_ana_cumul.grib'),
                os.path.join('..', 'empty_data', config_reg_day, 'atmfrc', 'cumul', 'arpege_202203091800_0001_ana_cumul.grib'),
                os.path.join('..', 'empty_data', config_reg_day, 'atmfrc', 'cumul', 'arpege_202203091800_0002_ana_cumul.grib'),
                os.path.join('..', 'empty_data', config_reg_day, 'atmfrc', 'cumul', 'arpege_202203091800_0003_ana_cumul.grib'),
                os.path.join('..', 'empty_data', config_reg_day, 'atmfrc', 'cumul', 'arpege_202203091800_0004_ana_cumul.grib'),
                os.path.join('..', 'empty_data', config_reg_day, 'atmfrc', 'cumul', 'arpege_202203091800_0005_ana_cumul.grib'),
                os.path.join('..', 'empty_data', config_reg_day, 'atmfrc', 'cumul', 'arpege_202203091800_0006_ana_cumul.grib'),
                os.path.join('..', 'empty_data', config_reg_day, 'atmfrc', 'cumul', 'arpege_202203100000_0001_fcst_cumul.grib'),
                os.path.join('..', 'empty_data', config_reg_day, 'atmfrc', 'cumul', 'arpege_202203100000_0002_fcst_cumul.grib'),
                os.path.join('..', 'empty_data', config_reg_day, 'atmfrc', 'cumul', 'arpege_202203100000_0003_fcst_cumul.grib'),
                os.path.join('..', 'empty_data', config_reg_day, 'atmfrc', 'cumul', 'arpege_202203100000_0004_fcst_cumul.grib'),
                os.path.join('..', 'empty_data', config_reg_day, 'atmfrc', 'cumul', 'arpege_202203100000_0005_fcst_cumul.grib'),
                os.path.join('..', 'empty_data', config_reg_day, 'atmfrc', 'cumul', 'arpege_202203100000_0006_fcst_cumul.grib'),
                os.path.join('..', 'empty_data', config_reg_day, 'atmfrc', 'cumul', 'arpege_202203100000_0007_fcst_cumul.grib'),
                os.path.join('..', 'empty_data', config_reg_day, 'atmfrc', 'cumul', 'arpege_202203100000_0008_fcst_cumul.grib'),
                os.path.join('..', 'empty_data', config_reg_day, 'atmfrc', 'cumul', 'arpege_202203100000_0009_fcst_cumul.grib'),
                os.path.join('..', 'empty_data', config_reg_day, 'atmfrc', 'cumul', 'arpege_202203100000_0010_fcst_cumul.grib'),
                os.path.join('..', 'empty_data', config_reg_day, 'atmfrc', 'cumul', 'arpege_202203100000_0011_fcst_cumul.grib'),
                os.path.join('..', 'empty_data', config_reg_day, 'atmfrc', 'cumul', 'arpege_202203100000_0012_fcst_cumul.grib'),
                os.path.join('..', 'empty_data', config_reg_day, 'atmfrc', 'cumul', 'arpege_202203100000_0015_fcst_cumul.grib'),
                os.path.join('..', 'empty_data', config_reg_day, 'atmfrc', 'cumul', 'arpege_202203100000_0018_fcst_cumul.grib'),
                os.path.join('..', 'empty_data', config_reg_day, 'atmfrc', 'cumul', 'arpege_202203100000_0021_fcst_cumul.grib'),
                os.path.join('..', 'empty_data', config_reg_day, 'atmfrc', 'cumul', 'arpege_202203100000_0024_fcst_cumul.grib'),
                os.path.join('..', 'empty_data', config_reg_day, 'atmfrc', 'cumul', 'arpege_202203100000_0027_fcst_cumul.grib'),
                os.path.join('..', 'empty_data', config_reg_day, 'atmfrc', 'cumul', 'arpege_202203100000_0030_fcst_cumul.grib'),
                os.path.join('..', 'empty_data', config_reg_day, 'atmfrc', 'cumul', 'arpege_202203100000_0033_fcst_cumul.grib'),
                os.path.join('..', 'empty_data', config_reg_day, 'atmfrc', 'cumul', 'arpege_202203100000_0036_fcst_cumul.grib'),
                os.path.join('..', 'empty_data', config_reg_day, 'atmfrc', 'cumul', 'arpege_202203100000_0039_fcst_cumul.grib'),
                os.path.join('..', 'empty_data', config_reg_day, 'atmfrc', 'cumul', 'arpege_202203100000_0042_fcst_cumul.grib'),
                os.path.join('..', 'empty_data', config_reg_day, 'atmfrc', 'cumul', 'arpege_202203100000_0045_fcst_cumul.grib'),
                os.path.join('..', 'empty_data', config_reg_day, 'atmfrc', 'cumul', 'arpege_202203100000_0048_fcst_cumul.grib'),
                os.path.join('..', 'empty_data', config_reg_day, 'atmfrc', 'cumul', 'arpege_202203100000_0051_fcst_cumul.grib'),
                os.path.join('..', 'empty_data', config_reg_day, 'atmfrc', 'cumul', 'arpege_202203100000_0054_fcst_cumul.grib'),
                os.path.join('..', 'empty_data', config_reg_day, 'atmfrc', 'cumul', 'arpege_202203100000_0057_fcst_cumul.grib'),
                os.path.join('..', 'empty_data', config_reg_day, 'atmfrc', 'cumul', 'arpege_202203100000_0060_fcst_cumul.grib'),
                os.path.join('..', 'empty_data', config_reg_day, 'atmfrc', 'cumul', 'arpege_202203100000_0063_fcst_cumul.grib'),
                os.path.join('..', 'empty_data', config_reg_day, 'atmfrc', 'cumul', 'arpege_202203100000_0066_fcst_cumul.grib'),
                os.path.join('..', 'empty_data', config_reg_day, 'atmfrc', 'cumul', 'arpege_202203100000_0069_fcst_cumul.grib'),
                os.path.join('..', 'empty_data', config_reg_day, 'atmfrc', 'cumul', 'arpege_202203100000_0072_fcst_cumul.grib'),
                os.path.join('..', 'empty_data', config_reg_day, 'atmfrc', 'cumul', 'arpege_202203100000_0075_fcst_cumul.grib'),
                os.path.join('..', 'empty_data', config_reg_day, 'atmfrc', 'cumul', 'arpege_202203100000_0078_fcst_cumul.grib'),
                os.path.join('..', 'empty_data', config_reg_day, 'atmfrc', 'cumul', 'arpege_202203100000_0081_fcst_cumul.grib'),
                os.path.join('..', 'empty_data', config_reg_day, 'atmfrc', 'cumul', 'arpege_202203100000_0084_fcst_cumul.grib'),
                os.path.join('..', 'empty_data', config_reg_day, 'atmfrc', 'cumul', 'arpege_202203100000_0087_fcst_cumul.grib'),
                os.path.join('..', 'empty_data', config_reg_day, 'atmfrc', 'cumul', 'arpege_202203100000_0090_fcst_cumul.grib'),
                os.path.join('..', 'empty_data', config_reg_day, 'atmfrc', 'cumul', 'arpege_202203100000_0093_fcst_cumul.grib'),
                os.path.join('..', 'empty_data', config_reg_day, 'atmfrc', 'cumul', 'arpege_202203100000_0096_fcst_cumul.grib'),
                os.path.join('..', 'empty_data', config_reg_day, 'atmfrc', 'cumul', 'arpege_202203100000_0099_fcst_cumul.grib'),
                os.path.join('..', 'empty_data', config_reg_day, 'atmfrc', 'cumul', 'arpege_202203100000_0102_fcst_cumul.grib')]

        assert sort_river_dict(get_forcing_model_path(input_folder_path, config_reg_day, "rivers", 'RVFL')) == \
               {'GL_TS_RF_EXSC0001':
                    [os.path.join('..', 'empty_data', config_reg_day, 'rivers', 'GL_TS_RF_EXSC0001_20220226.nc'),
                     os.path.join('..', 'empty_data', config_reg_day, 'rivers', 'GL_TS_RF_EXSC0001_20220227.nc'),
                     os.path.join('..', 'empty_data', config_reg_day, 'rivers', 'GL_TS_RF_EXSC0001_20220228.nc'),
                     os.path.join('..', 'empty_data', config_reg_day, 'rivers', 'GL_TS_RF_EXSC0001_20220301.nc'),
                     os.path.join('..', 'empty_data', config_reg_day, 'rivers', 'GL_TS_RF_EXSC0001_20220302.nc'),
                     os.path.join('..', 'empty_data', config_reg_day, 'rivers', 'GL_TS_RF_EXSC0001_20220303.nc'),
                     os.path.join('..', 'empty_data', config_reg_day, 'rivers', 'GL_TS_RF_EXSC0001_20220304.nc'),
                     os.path.join('..', 'empty_data', config_reg_day, 'rivers', 'GL_TS_RF_EXSC0001_20220305.nc'),
                     os.path.join('..', 'empty_data', config_reg_day, 'rivers', 'GL_TS_RF_EXSC0001_20220306.nc'),
                     os.path.join('..', 'empty_data', config_reg_day, 'rivers', 'GL_TS_RF_EXSC0001_20220307.nc'),
                     os.path.join('..', 'empty_data', config_reg_day, 'rivers', 'GL_TS_RF_EXSC0001_20220308.nc'),
                     os.path.join('..', 'empty_data', config_reg_day, 'rivers', 'GL_TS_RF_EXSC0001_20220309.nc'),
                     os.path.join('..', 'empty_data', config_reg_day, 'rivers', 'GL_TS_RF_EXSC0001_20220310.nc')],
                'GL_TS_RF_EXSC0002':
                    [os.path.join('..', 'empty_data', config_reg_day, 'rivers', 'GL_TS_RF_EXSC0002_20220226.nc'),
                     os.path.join('..', 'empty_data', config_reg_day, 'rivers', 'GL_TS_RF_EXSC0002_20220227.nc'),
                     os.path.join('..', 'empty_data', config_reg_day, 'rivers', 'GL_TS_RF_EXSC0002_20220228.nc'),
                     os.path.join('..', 'empty_data', config_reg_day, 'rivers', 'GL_TS_RF_EXSC0002_20220301.nc'),
                     os.path.join('..', 'empty_data', config_reg_day, 'rivers', 'GL_TS_RF_EXSC0002_20220302.nc'),
                     os.path.join('..', 'empty_data', config_reg_day, 'rivers', 'GL_TS_RF_EXSC0002_20220303.nc'),
                     os.path.join('..', 'empty_data', config_reg_day, 'rivers', 'GL_TS_RF_EXSC0002_20220304.nc'),
                     os.path.join('..', 'empty_data', config_reg_day, 'rivers', 'GL_TS_RF_EXSC0002_20220305.nc'),
                     os.path.join('..', 'empty_data', config_reg_day, 'rivers', 'GL_TS_RF_EXSC0002_20220306.nc'),
                     os.path.join('..', 'empty_data', config_reg_day, 'rivers', 'GL_TS_RF_EXSC0002_20220307.nc'),
                     os.path.join('..', 'empty_data', config_reg_day, 'rivers', 'GL_TS_RF_EXSC0002_20220308.nc'),
                     os.path.join('..', 'empty_data', config_reg_day, 'rivers', 'GL_TS_RF_EXSC0002_20220309.nc'),
                     os.path.join('..', 'empty_data', config_reg_day, 'rivers', 'GL_TS_RF_EXSC0002_20220310.nc')],
                'GL_TS_RF_EXSC0003':
                    [os.path.join('..', 'empty_data', config_reg_day, 'rivers', 'GL_TS_RF_EXSC0003_20220226.nc'),
                     os.path.join('..', 'empty_data', config_reg_day, 'rivers', 'GL_TS_RF_EXSC0003_20220227.nc'),
                     os.path.join('..', 'empty_data', config_reg_day, 'rivers', 'GL_TS_RF_EXSC0003_20220228.nc'),
                     os.path.join('..', 'empty_data', config_reg_day, 'rivers', 'GL_TS_RF_EXSC0003_20220301.nc'),
                     os.path.join('..', 'empty_data', config_reg_day, 'rivers', 'GL_TS_RF_EXSC0003_20220302.nc'),
                     os.path.join('..', 'empty_data', config_reg_day, 'rivers', 'GL_TS_RF_EXSC0003_20220303.nc'),
                     os.path.join('..', 'empty_data', config_reg_day, 'rivers', 'GL_TS_RF_EXSC0003_20220304.nc'),
                     os.path.join('..', 'empty_data', config_reg_day, 'rivers', 'GL_TS_RF_EXSC0003_20220305.nc'),
                     os.path.join('..', 'empty_data', config_reg_day, 'rivers', 'GL_TS_RF_EXSC0003_20220306.nc'),
                     os.path.join('..', 'empty_data', config_reg_day, 'rivers', 'GL_TS_RF_EXSC0003_20220307.nc'),
                     os.path.join('..', 'empty_data', config_reg_day, 'rivers', 'GL_TS_RF_EXSC0003_20220308.nc'),
                     os.path.join('..', 'empty_data', config_reg_day, 'rivers', 'GL_TS_RF_EXSC0003_20220309.nc'),
                     os.path.join('..', 'empty_data', config_reg_day, 'rivers', 'GL_TS_RF_EXSC0003_20220310.nc')],
                'GL_TS_RF_EXSC0006':
                    [os.path.join('..', 'empty_data', config_reg_day, 'rivers', 'GL_TS_RF_EXSC0006_20220226.nc'),
                     os.path.join('..', 'empty_data', config_reg_day, 'rivers', 'GL_TS_RF_EXSC0006_20220227.nc'),
                     os.path.join('..', 'empty_data', config_reg_day, 'rivers', 'GL_TS_RF_EXSC0006_20220228.nc'),
                     os.path.join('..', 'empty_data', config_reg_day, 'rivers', 'GL_TS_RF_EXSC0006_20220301.nc'),
                     os.path.join('..', 'empty_data', config_reg_day, 'rivers', 'GL_TS_RF_EXSC0006_20220302.nc'),
                     os.path.join('..', 'empty_data', config_reg_day, 'rivers', 'GL_TS_RF_EXSC0006_20220303.nc'),
                     os.path.join('..', 'empty_data', config_reg_day, 'rivers', 'GL_TS_RF_EXSC0006_20220304.nc'),
                     os.path.join('..', 'empty_data', config_reg_day, 'rivers', 'GL_TS_RF_EXSC0006_20220305.nc'),
                     os.path.join('..', 'empty_data', config_reg_day, 'rivers', 'GL_TS_RF_EXSC0006_20220306.nc'),
                     os.path.join('..', 'empty_data', config_reg_day, 'rivers', 'GL_TS_RF_EXSC0006_20220307.nc'),
                     os.path.join('..', 'empty_data', config_reg_day, 'rivers', 'GL_TS_RF_EXSC0006_20220308.nc'),
                     os.path.join('..', 'empty_data', config_reg_day, 'rivers', 'GL_TS_RF_EXSC0006_20220309.nc'),
                     os.path.join('..', 'empty_data', config_reg_day, 'rivers', 'GL_TS_RF_EXSC0006_20220310.nc')],
                'GL_TS_RF_EXSC0020':
                    [os.path.join('..', 'empty_data', config_reg_day, 'rivers', 'GL_TS_RF_EXSC0020_20220226.nc'),
                     os.path.join('..', 'empty_data', config_reg_day, 'rivers', 'GL_TS_RF_EXSC0020_20220227.nc'),
                     os.path.join('..', 'empty_data', config_reg_day, 'rivers', 'GL_TS_RF_EXSC0020_20220228.nc'),
                     os.path.join('..', 'empty_data', config_reg_day, 'rivers', 'GL_TS_RF_EXSC0020_20220301.nc'),
                     os.path.join('..', 'empty_data', config_reg_day, 'rivers', 'GL_TS_RF_EXSC0020_20220302.nc'),
                     os.path.join('..', 'empty_data', config_reg_day, 'rivers', 'GL_TS_RF_EXSC0020_20220303.nc'),
                     os.path.join('..', 'empty_data', config_reg_day, 'rivers', 'GL_TS_RF_EXSC0020_20220304.nc'),
                     os.path.join('..', 'empty_data', config_reg_day, 'rivers', 'GL_TS_RF_EXSC0020_20220305.nc'),
                     os.path.join('..', 'empty_data', config_reg_day, 'rivers', 'GL_TS_RF_EXSC0020_20220306.nc'),
                     os.path.join('..', 'empty_data', config_reg_day, 'rivers', 'GL_TS_RF_EXSC0020_20220307.nc'),
                     os.path.join('..', 'empty_data', config_reg_day, 'rivers', 'GL_TS_RF_EXSC0020_20220308.nc'),
                     os.path.join('..', 'empty_data', config_reg_day, 'rivers', 'GL_TS_RF_EXSC0020_20220309.nc'),
                     os.path.join('..', 'empty_data', config_reg_day, 'rivers', 'GL_TS_RF_EXSC0020_20220310.nc')],
                'GL_TS_RF_EXSC0048':
                    [os.path.join('..', 'empty_data', config_reg_day, 'rivers', 'GL_TS_RF_EXSC0048_20220226.nc'),
                     os.path.join('..', 'empty_data', config_reg_day, 'rivers', 'GL_TS_RF_EXSC0048_20220227.nc'),
                     os.path.join('..', 'empty_data', config_reg_day, 'rivers', 'GL_TS_RF_EXSC0048_20220228.nc'),
                     os.path.join('..', 'empty_data', config_reg_day, 'rivers', 'GL_TS_RF_EXSC0048_20220301.nc'),
                     os.path.join('..', 'empty_data', config_reg_day, 'rivers', 'GL_TS_RF_EXSC0048_20220302.nc'),
                     os.path.join('..', 'empty_data', config_reg_day, 'rivers', 'GL_TS_RF_EXSC0048_20220303.nc'),
                     os.path.join('..', 'empty_data', config_reg_day, 'rivers', 'GL_TS_RF_EXSC0048_20220304.nc'),
                     os.path.join('..', 'empty_data', config_reg_day, 'rivers', 'GL_TS_RF_EXSC0048_20220305.nc'),
                     os.path.join('..', 'empty_data', config_reg_day, 'rivers', 'GL_TS_RF_EXSC0048_20220306.nc'),
                     os.path.join('..', 'empty_data', config_reg_day, 'rivers', 'GL_TS_RF_EXSC0048_20220307.nc'),
                     os.path.join('..', 'empty_data', config_reg_day, 'rivers', 'GL_TS_RF_EXSC0048_20220308.nc'),
                     os.path.join('..', 'empty_data', config_reg_day, 'rivers', 'GL_TS_RF_EXSC0048_20220309.nc'),
                     os.path.join('..', 'empty_data', config_reg_day, 'rivers', 'GL_TS_RF_EXSC0048_20220310.nc')]
                }

        assert get_forcing_model_path(input_folder_path, config_reg_day, "woa18", 'temp') == \
               [os.path.join('..', 'empty_data', config_reg_day, 'woa18', 'woa18_decav_t03_04.nc')]
        assert get_forcing_model_path(input_folder_path, config_reg_day, "woa18", 'sal') == \
               [os.path.join('..', 'empty_data', config_reg_day, 'woa18', 'woa18_decav_s03_04.nc')]
