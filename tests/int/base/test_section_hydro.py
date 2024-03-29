from armoor.cli.command_line_interface import command_line_interface
from armoor.base.calls_from_dict import dict2call
from armoor.hmi.script_tools import create_folder
from tests.int.base import change_path, copy_test_files

folder_test = 'test_f4'
copy_test_files(folder_test)


class TestBulletins:

    def test_variable_2d(self):
        out_path, logger = change_path(folder_test)
        logger.info('test_variable_2d')
        parser = command_line_interface(
            ['--cfgfile', f"../single_tests/{folder_test}/variable_2d.cfg"])
        parser.update({'output_path': out_path})
        dict2call(parser)
        assert True

    def test_variable_2d_curr_geo(self):
        out_path, logger = change_path(folder_test)
        logger.info('test_variable_2d_curr_geo')
        parser = command_line_interface(
            ['--cfgfile', f"../single_tests/{folder_test}/variable_2d_curr_geo.cfg"])
        parser.update({'output_path': out_path})
        dict2call(parser)
        assert True


    def test_variable_2d_hycom_manga_dens(self):
        out_path, logger = change_path(folder_test)
        logger.info('test_variable_2d_hycom_manga_dens')
        parser = command_line_interface(
            ['--cfgfile', f"../single_tests/{folder_test}/variable_2d_hycom_manga_dens.cfg"])
        parser.update({'output_path': out_path})
        dict2call(parser)
        assert True

    def test_variable_2d_seasor(self):
        out_path, logger = change_path(folder_test)
        logger.info('test_variable_2d_seasor')
        parser = command_line_interface(
            ['--cfgfile', f"../single_tests/{folder_test}/variable_2d_seasor.cfg"])
        parser.update({'output_path': out_path})
        dict2call(parser)
        assert True

    def test_variable_2d_scanfish(self):
        out_path, logger = change_path(folder_test)
        logger.info('test_variable_2d_scanfish')
        parser = command_line_interface(
            ['--cfgfile', f"../single_tests/{folder_test}/variable_2d_scanfish.cfg"])
        parser.update({'output_path': out_path})
        dict2call(parser)
        assert True

    def test_variable_2d_croco(self):
        out_path, logger = change_path(folder_test)
        logger.info('test_variable_2d_croco')
        parser = command_line_interface(
            ['--cfgfile', f"../single_tests/{folder_test}/variable_2d_croco.cfg"])
        parser.update({'output_path': out_path})
        dict2call(parser)
        assert True

    def test_variable_2d_seasor_topaz(self):
        out_path, logger = change_path(folder_test)
        logger.info('test_variable_2d_seasor_topaz')
        parser = command_line_interface(
            ['--cfgfile', f"../single_tests/{folder_test}/variable_2d_seasor_topaz.cfg"])
        parser.update({'output_path': out_path})
        dict2call(parser)
        assert True

    def test_variable_3d(self):
        out_path, logger = change_path(folder_test)
        logger.info('test_variable_3d')
        parser = command_line_interface(
            ['--cfgfile', f"../single_tests/{folder_test}/variable_3d.cfg"])
        parser.update({'output_path': out_path})
        dict2call(parser)
        assert True

    def test_variable_3d_curr_geo(self):
        out_path, logger = change_path(folder_test)
        logger.info('test_variable_3d_curr_geo')
        parser = command_line_interface(
            ['--cfgfile', f"../single_tests/{folder_test}/variable_3d_curr_geo.cfg"])
        parser.update({'output_path': out_path})
        dict2call(parser)
        assert True

    def test_variable_3d_seasor(self):
        out_path, logger = change_path(folder_test)
        logger.info('test_variable_3d_seasor')
        parser = command_line_interface(
            ['--cfgfile', f"../single_tests/{folder_test}/variable_3d_seasor.cfg"])
        parser.update({'output_path': out_path})
        dict2call(parser)
        assert True

    def test_variable_3d_scanfish(self):
        out_path, logger = change_path(folder_test)
        logger.info('test_variable_3d_scanfish')
        parser = command_line_interface(
            ['--cfgfile', f"../single_tests/{folder_test}/variable_3d_scanfish.cfg"])
        parser.update({'output_path': out_path})
        dict2call(parser)
        assert True

    def test_variable_3d_hycom(self):
        out_path, logger = change_path(folder_test)
        logger.info('test_variable_3d_hycom')
        parser = command_line_interface(
            ['--cfgfile', f"../single_tests/{folder_test}/variable_3d_hycom.cfg"])
        parser.update({'output_path': out_path})
        dict2call(parser)
        assert True

    def test_variable_3d_croco(self):
        out_path, logger = change_path(folder_test)
        logger.info('test_variable_3d_croco')
        parser = command_line_interface(
            ['--cfgfile', f"../single_tests/{folder_test}/variable_3d_croco.cfg"])
        parser.update({'output_path': out_path})
        dict2call(parser)
        assert True

    def test_variable_3d_PSY4_SCA(self):
        out_path, logger = change_path(folder_test)

        logger.info("test_variable_3d_PSY4_SCA.cfg")
        parser = command_line_interface(
            ['--cfgfile', f"../single_tests/{folder_test}/variable_3d_PSY4_SCA.cfg"])
        parser.update({'output_path': out_path})
        create_folder(f'tmp')
        dict2call(parser)
        assert True

    def test_variable_2d_SCA(self):
        out_path, logger = change_path(folder_test)

        logger.info("test_variable_2d_SCA.cfg")
        parser = command_line_interface(
            ['--cfgfile', f"../single_tests/{folder_test}/variable_2d_SCA.cfg"])
        parser.update({'output_path': out_path})
        create_folder(f'tmp')
        dict2call(parser)
        assert True