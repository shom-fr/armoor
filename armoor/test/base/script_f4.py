from armoor import cli
from armoor import base
file = open('log.txt','a')

try:
    #Variable 3D
    parser = cli.command_line_interface(['--file', "data/test_f4/variable_3d.ini"])
    base.calls_from_dict.dict2call(parser)
    file.write('F4  Variable 3D passed\n')
except:
    file.write ('F4  Variable 3D failed\n')
try:
    #Variable 3D steps
    parser = cli.command_line_interface(['--file', "data/test_f4/variable_3d_steps.ini"])
    base.calls_from_dict.dict2call(parser)
    file.write('F4 Variable 3D steps passed\n')
except:
    file.write ('F4 Variable 3D steps failed\n')
try:
    #Variable 2D
    parser = cli.command_line_interface(['--file', "data/test_f4/variable_2d.ini"])
    base.calls_from_dict.dict2call(parser)
    file.write('F4 Variable 2D passed\n')
except:
    file.write ('F4 Variable 2D failed\n')
try:
    #Variable 3D HYCOM
    parser = cli.command_line_interface(['--file', "data/test_f4/variable_3d_hycom.ini"])
    base.calls_from_dict.dict2call(parser)
    file.write('F4 Variable 3D HYCOM passed\n')
except:
    file.write ('F4 Variable 3D HYCOM failed\n')

print("My work is done")
file.close()
assert True


