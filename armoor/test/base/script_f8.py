from armoor import cli
from armoor import base



file = open('log.txt', 'a')

try:
    # Stick plot data vmadcp shom
    parser = cli.command_line_interface(['--file', "data/test_f8/stick_plot_vmadcp.ini"])
    base.calls_from_dict.dict2call(parser)
    file.write('F8   Stick plot data vmadcp shom  passed\n')
except:
    file.write('F8  Stick plot data vmadcp shom failed\n')

try:
    # Stick plot data vmadcp shom & hycom : 1 depth
    parser = cli.command_line_interface(['--file', "data/test_f8/stick_plot_vmadcp_hycom_1depth.ini"])
    base.calls_from_dict.dict2call(parser)
    file.write('F8 Stick plot data vmadcp shom & hycom : 1 depth    passed\n')
except:
    file.write('F8 Stick plot data vmadcp shom & hycom : 1 depth  failed\n')

try:
    # Stick plot data vmadcp shom & hycom : 3depths
    parser = cli.command_line_interface(['--file', "data/test_f8/stick_plot_vmadcp_hycom_3depths.ini"])
    base.calls_from_dict.dict2call(parser)
    file.write('F8  Stick plot data vmadcp shom & hycom : 3depths   passed\n')
except:
    file.write('F8 Stick plot data vmadcp shom & hycom : 3depths  failed\n')

try:
    # Stick plot data vmadcp shom & hycom : 3depths - fix pb Javier
    parser = cli.command_line_interface(['--file', "data/test_f8/stick_plot_vmadcp_hycom_3depths_pbJP.ini"])
    base.calls_from_dict.dict2call(parser)
    file.write('F8  Stick plot data vmadcp shom & hycom : 3depths - fix pb Javier   passed\n')
except:
    file.write('F8 Stick plot data vmadcp shom & hycom : 3depths - fix pb Javier  failed\n')

try:
    # Graph 2D steps
    parser = cli.command_line_interface(['--file', "data/test_f8/graph2d_steps.ini"])
    base.calls_from_dict.dict2call(parser)
    file.write('F8  Graph 2D steps   passed\n')
except:
    file.write('F8 Graph 2D steps   failed\n')

try:
    # Graph 2D
    parser = cli.command_line_interface(['--file', "data/test_f8/graph2d.ini"])
    base.calls_from_dict.dict2call(parser)
    file.write('F8  Graph 2D   passed\n')
except:
    file.write('F8  Graph 2D failed\n')

print("My work is done")
file.close()
assert True
