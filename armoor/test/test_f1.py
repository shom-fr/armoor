from armoor import cli
from armoor import base


class TestFeature1:

    def test_call_L3C_geostat_15(self):
        parser = cli.command_line_interface(['--file', "data/test_f1/cli_L3C_geostat_15.ini"])
        base.calls_from_dict.dict2call(parser)
        assert True

    def test_call_L3C_geostat_19(self):
        from armoor import cli
        from armoor import base
        parser = cli.command_line_interface(['--file', "data/test_f1/cli_L3C_geostat_19.ini"])
        base.calls_from_dict.dict2call(parser)
        assert True

    def test_call_L3C_geostat_28(self):
        parser = cli.command_line_interface(['--file', "data/test_f1/cli_L3C_geostat_28.ini"])
        base.calls_from_dict.dict2call(parser)
        assert True
#
#     def test_call_L3C_geostat_03(self):
#         from armoor import cli
#         from armoor import base
#         parser = cli.command_line_interface(['--file', "data/test_f1/cli_L3C_geostat_03.ini"])
#         base.calls_from_dict.dict2call(parser)
#         print("finito")
#         assert True
#
#     def test_call_L3C_geostat_04(self):
#         from armoor import cli
#         from armoor import base
#         parser = cli.command_line_interface(['--file', "data/test_f1/cli_L3C_geostat_04.ini"])
#         base.calls_from_dict.dict2call(parser)
#         print("finito")
#         assert True
#
#     def test_call_L3C_geostat_05(self):
#         from armoor import cli
#         from armoor import base
#         parser = cli.command_line_interface(['--file', "data/test_f1/cli_L3C_geostat_05.ini"])
#         base.calls_from_dict.dict2call(parser)
#         print("finito")
#         assert True
#
#     def test_call_L3C_geostat_06(self):
#         from armoor import cli
#         from armoor import base
#         parser = cli.command_line_interface(['--file', "data/test_f1/cli_L3C_geostat_06.ini"])
#         base.calls_from_dict.dict2call(parser)
#         print("finito")
#         assert True
#
#     def test_call_L3C_geostat_07(self):
#         from armoor import cli
#         from armoor import base
#         parser = cli.command_line_interface(['--file', "data/test_f1/cli_L3C_geostat_07.ini"])
#         base.calls_from_dict.dict2call(parser)
#         print("finito")
#         assert True
#
#     def test_call_L3C_geostat_08(self):
#         from armoor import cli
#         from armoor import base
#         parser = cli.command_line_interface(['--file', "data/test_f1/cli_L3C_geostat_08.ini"])
#         base.calls_from_dict.dict2call(parser)
#         print("finito")
#         assert True
#
#     def test_call_L3C_geostat_09(self):
#         from armoor import cli
#         from armoor import base
#         parser = cli.command_line_interface(['--file', "data/test_f1/cli_L3C_geostat_09.ini"])
#         base.calls_from_dict.dict2call(parser)
#         print("finito")
#         assert True
#
#     def test_call_L3C_geostat_10(self):
#         from armoor import cli
#         from armoor import base
#         parser = cli.command_line_interface(['--file', "data/test_f1/cli_L3C_geostat_10.ini"])
#         base.calls_from_dict.dict2call(parser)
#         print("finito")
#         assert True
# # def test_call_L3C_polar(self):
# #      parser = cli.command_line_interface(['--file', "data/test_f1/cli_L3C_polar.ini"])
# #      base.calls_from_dict.dict2call(parser)
# #      print("finito")
# #      assert True
# #
# # def test_call_L3S(self):
# #      parser = cli.command_line_interface(['--file', "data/test_f1/cli_L3S.ini"])
# #      base.calls_from_dict.dict2call(parser)
# #      print("finito")
# #      assert True
# #
# # def test_call_L4(self):
# #      parser = cli.command_line_interface(['--file', "data/test_f1/cli_L4.ini"])
# #      base.calls_from_dict.dict2call(parser)
# #      print("finito")
# #      assert True
