from armoor.cli.command_line_interface import command_line_interface
from armoor.base.calls_from_dict import dict2call
from tests.int.base import change_path, copy_test_files
from pytest import raises
folder_test = 'test_f7'
copy_test_files(folder_test)


class TestBulletins:

    def test_ellipse_courant_ttide(self):  # OK
        out_path, logger = change_path(folder_test)
        logger.info('test_ellipse_courant_ttide')
        parser = command_line_interface(
            ['--cfgfile', f"../single_tests/{folder_test}/ellipse_courant_ttide.cfg"])
        parser.update({'output_path': out_path})
        dict2call(parser)
        assert True

    def test_ellipse_courant_utide(self):  # OK
        out_path, logger = change_path(folder_test)
        logger.info('test_ellipse_courant_utide')
        parser = command_line_interface(
            ['--cfgfile', f"../single_tests/{folder_test}/ellipse_courant_utide.cfg"])
        parser.update({'output_path': out_path})
        dict2call(parser)
        assert True

    def test_harmonic_table(self):  # OK
        out_path, logger = change_path(folder_test)
        logger.info('test_harmonic_table')
        parser = command_line_interface(
            ['--cfgfile', f"../single_tests/{folder_test}/harmonic_table.cfg"])
        parser.update({'output_path': out_path})
        dict2call(parser)
        assert True

    def test_harmonic_table_slice(self):  # OK
        out_path, logger = change_path(folder_test)
        logger.info('test_harmonic_table_slice')
        parser = command_line_interface(
            ['--cfgfile', f"../single_tests/{folder_test}/harmonic_table_slice.cfg"])
        parser.update({'output_path': out_path})
        dict2call(parser)
        assert True

    def test_harmonic_table_depth(self):  # OK
        out_path, logger = change_path(folder_test)
        logger.info('test_harmonic_table_depth')
        parser = command_line_interface(
            ['--cfgfile', f"../single_tests/{folder_test}/harmonic_table_depth.cfg"])
        parser.update({'output_path': out_path})
        dict2call(parser)
        assert True

    def test_harmonic_table_tranches(self):  # OK
        out_path, logger = change_path(folder_test)
        logger.info('test_harmonic_table_tranches')
        parser = command_line_interface(
            ['--cfgfile', f"../single_tests/{folder_test}/harmonic_table_tranches.cfg"])
        parser.update({'output_path': out_path})
        dict2call(parser)
        assert True

    def test_harmonic_table_raise_error(self):  # OK
        out_path, logger = change_path(folder_test)
        logger.info('test_harmonic_table')
        parser = command_line_interface(
            ['--cfgfile', f"../single_tests/{folder_test}/harmonic_table_raise_error.cfg"])
        parser.update({'output_path': out_path})
        with raises(ValueError):
            dict2call(parser)

    def test_hovmoller_LADCP_bc(self):  # OK
        out_path, logger = change_path(folder_test)
        logger.info('test_hovmoller_LADCP_bc')
        parser = command_line_interface(
            ['--cfgfile', f"../single_tests/{folder_test}/hovmoller_LADCP_bc.cfg"])
        parser.update({'output_path': out_path})
        dict2call(parser)
        assert True

    def test_hovmoller_LADCP_bathyradius(self):  # OK
        out_path, logger = change_path(folder_test)
        logger.info('test_hovmoller_LADCP_bathyradius')
        parser = command_line_interface(
            ['--cfgfile', f"../single_tests/{folder_test}/hovmoller_LADCP_bathyradius.cfg"])
        parser.update({'output_path': out_path})
        dict2call(parser)
        assert True

    def test_hovmoller_ADCP_res(self):  # OK
        out_path, logger = change_path(folder_test)
        logger.info('test_hovmoller_ADCP_res')
        parser = command_line_interface(
            ['--cfgfile', f"../single_tests/{folder_test}/hovmoller_ADCP_res.cfg"])
        parser.update({'output_path': out_path})
        dict2call(parser)
        assert True

    def test_hovmoller_ADCP_bathyradius(self):  # OK
        out_path, logger = change_path(folder_test)
        logger.info('test_hovmoller_ADCP_bathyradius')
        parser = command_line_interface(
            ['--cfgfile', f"../single_tests/{folder_test}/hovmoller_ADCP_bathyradius.cfg"])
        parser.update({'output_path': out_path})
        dict2call(parser)
        assert True

    def test_hovmoller_ADCP_bathyradius_res(self):
        out_path, logger = change_path(folder_test)
        logger.info('test_hovmoller_ADCP_bathyradius_res')
        parser = command_line_interface(
            ['--cfgfile', f"../single_tests/{folder_test}/hovmoller_ADCP_bathyradius_res.cfg"])
        parser.update({'output_path': out_path})
        dict2call(parser)
        assert True

    def test_ellipses_ADCP_CROCO(self):
        out_path, logger = change_path(folder_test)
        logger.info("test_ellipses_ADCP_CROCO")
        parser = command_line_interface(
            ['--cfgfile', f"../single_tests/{folder_test}/ellipses_ADCP_CROCO.cfg"])
        parser.update({'output_path': out_path})
        dict2call(parser)
        assert True