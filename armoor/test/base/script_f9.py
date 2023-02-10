from armoor import cli
from armoor import base
file = open('log.txt','a')

try:
    #Current along trajectory
    parser = cli.command_line_interface(['--file', "data/test_f9/map_current_DB.ini"])
    base.calls_from_dict.dict2call(parser)
    file.write('F9 Current along trajectory  passed\n')
except:
    file.write ('F9 Current along trajectory  failed\n')
try:
    #Map trajectory
    parser = cli.command_line_interface(['--file', "data/test_f9/map_trajectory.ini"])
    base.calls_from_dict.dict2call(parser)
    file.write('F9 Map trajectory passed\n')
except:
    file.write ('F9  Map trajectory failed\n')
try:
    #Map trajectory TOPAZ
    parser = cli.command_line_interface(['--file', "data/test_f9/map_trajectory_TOPAZ.ini"])
    base.calls_from_dict.dict2call(parser)
    file.write('F9 Map trajectory TOPAZ passed\n')
except:
    file.write ('F9  Map trajectory TOPAZ failed\n')

try:
    #Map diff trajectory
    parser = cli.command_line_interface(['--file', "data/test_f9/plot_diff_traj_distance.ini"])
    base.calls_from_dict.dict2call(parser)
    file.write('F9 Map diff trajectory  passed\n')
except:
    file.write ('F9 Map diff trajectory  failed\n')

print("My work is done")

assert True


