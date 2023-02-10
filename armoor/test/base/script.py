from armoor import cli
from armoor import base

parser = cli.command_line_interface(['--file', "data/test_f1/cli_L3C_geostat_1.ini"])
base.calls_from_dict.dict2call(parser)
print("My work is done")

assert True


