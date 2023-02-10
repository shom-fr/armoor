# from armoor import cli
# from armoor import base
#
# class TestCalls:
#
#     def test_call_cli(self):
#         from armoor import cli
#         from armoor import base
#         parser = cli.command_line_interface(['--func', "1",
#                                              "--observation", "../../shared_data/example/obs_test_ergane.nc",
#                                              "--obs_method", "nearest",
#                                              "--obs_name", "custom obs name",
#                                              "--models", "../../shared_data/example/sst_2D.nc",
#                                                          "../../shared_data/example/sst_2D.nc",
#                                              "--mod_methods", "nearest", "linear",
#                                              "--polygon", "-5.8, 50.", "-4., 48.",
#                                                           "-7.3, 48.", "-5.0, 48.0",
#                                                           "-9., 50.5", "-4., 51.",
#                                              "--quality", "3", "4",
#                                              "--plot", "diag_disp",
#                                              "--format", "pdf", "html"
#                                              ])
#         base.calls_from_dict.dict2call(parser)
#         print("finito")
#         assert True
#
#     def test_call_diag_disp(self):
#         from armoor import cli
#         from armoor import base
#         parser = cli.command_line_interface(['--file', "data/configobj/cli_diag_disp.ini"])
#         base.calls_from_dict.dict2call(parser)
#         print("finito")
#         assert True
#
#     def test_call_diag_disp_TOPAZ(self):
#         parser = cli.command_line_interface(['--file', "data/configobj/cli_diag_disp_TOPAZ.ini"])
#         base.calls_from_dict.dict2call(parser)
#         print("finito")
#         assert True
#
#     def test_call_ts_configObj(self):
#         parser = cli.command_line_interface(['--file', "data/configobj/cli_ts.ini"])
#         base.calls_from_dict.dict2call(parser)
#         print("finito")
#         assert True
#
#     def test_call_ts_interval(self):
#         parser = cli.command_line_interface(['--file', "data/configobj/cli_ts_interval.ini"])
#         base.calls_from_dict.dict2call(parser)
#         print("finito")
#         assert True
#
#     def test_call_map_diff(self):
#         parser = cli.command_line_interface(['--file', "data/configobj/cli_map_diff.ini"])
#         base.calls_from_dict.dict2call(parser)
#         print("finito")
#         assert True
#
#
#     def test_call_map_bias(self):
#         parser = cli.command_line_interface(['--file', "data/configobj/cli_map_bias.ini"])
#         base.calls_from_dict.dict2call(parser)
#         print("finito")
#         assert True
#
#     def test_call_map_RMSEc(self):
#         parser = cli.command_line_interface(['--file', "data/configobj/cli_map_RMSEc.ini"])
#         base.calls_from_dict.dict2call(parser)
#         print("finito")
#         assert True
#
#     def test_call_fun2_map_diff(self):
#         parser = cli.command_line_interface(['--file', "data/configobj/cli_func2.ini"])
#         base.calls_from_dict.dict2call(parser)
#         print("finito")
#         assert True
#
