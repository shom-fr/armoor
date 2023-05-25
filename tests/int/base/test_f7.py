from armoor.cli.command_line_interface import command_line_interface
from armoor.base.calls_from_dict import dict2call
from tests.int.base import change_path, copy_test_files

folder_test = 'test_f7'
copy_test_files(folder_test)


class TestBulletins:

    def test_ellipses(self):  # OK
        out_path, logger = change_path(folder_test)
        logger.info('test_ellipses')
        parser = command_line_interface(['--cfgfile', f"../single_tests/{folder_test}/ellipses.ini"])
        parser.update({'output_path': out_path})
        dict2call(parser)
        assert True
    #
    def test_ellipses_tranche(self):  # OK
        out_path, logger = change_path(folder_test)
        logger.info('test_ellipses_tranche')
        parser = command_line_interface(['--cfgfile', f"../single_tests/{folder_test}/ellipses_tranche.ini"])
        parser.update({'output_path': out_path})
        dict2call(parser)
        assert True

    def test_harmonic_table(self):  # OK
        out_path, logger = change_path(folder_test)
        logger.info('test_harmonic_table')
        parser = command_line_interface(['--cfgfile', f"../single_tests/{folder_test}/harmonic_table.ini"])
        parser.update({'output_path': out_path})
        dict2call(parser)
        assert True

    # def test_harmonic_table_tranche(self):  # OK
    #     out_path, logger = change_path(folder_test)
    #     logger.info('test_harmonic_table_tranche')
    #     parser = command_line_interface(['--cfgfile', f"../single_tests/{folder_test}/harmonic_table_tranche.ini"])
    #     parser.update({'output_path': out_path})
    #     dict2call(parser)
    #     assert True
    #
    # def test_hovmoller_datashom(self):  # OK
    #     out_path, logger = change_path(folder_test)
    #     logger.info('test_hovmoller_datashom')
    #     parser = command_line_interface(['--cfgfile', f"../single_tests/{folder_test}/hovmoller_datashom.ini"])
    #     parser.update({'output_path': out_path})
    #     dict2call(parser)
    #     assert True
    #
    # def test_hovmoller_ladcp(self):  # OK
    #     out_path, logger = change_path(folder_test)
    #     logger.info('test_hovmoller_LADCP')
    #     parser = command_line_interface(['--cfgfile', f"../single_tests/{folder_test}/hovmoller_LADCP.ini"])
    #     parser.update({'output_path': out_path})
    #     dict2call(parser)
    #     assert True
    #
    # def test_hovmoller_datashom_bathyradius(self):  # OK
    #     out_path, logger = change_path(folder_test)
    #     logger.info('test_hovmoller_datashom_bathyradius')
    #     parser = command_line_interface(
    #         ['--cfgfile', f"../single_tests/{folder_test}/hovmoller_datashom_bathyradius.ini"])
    #     parser.update({'output_path': out_path})
    #     dict2call(parser)
    #     assert True
