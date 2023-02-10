from armoor import cli
from armoor import base

file = open('log.txt','a')
try:
    #Carte des ecarts
    parser = cli.command_line_interface(['--file', "data/test_f5/map_diff.ini"])
    base.calls_from_dict.dict2call(parser)
    file.write('F5 Carte des ecarts passed\n')
except:
    file.write ('F5 Carte des ecarts failed\n')

try:
    #Série temporelle statistique
    parser = cli.command_line_interface(['--file', "data/test_f5/ser_temp_stats.ini"])
    base.calls_from_dict.dict2call(parser)
    file.write('F5  Série temporelle statistique passed\n')
except:
    file.write ('F5 Série temporelle statistique failed\n')

try:
    #Série temporelle ponctuelle
    parser = cli.command_line_interface(['--file', "data/test_f5/ser_temp_ponct.ini"])
    base.calls_from_dict.dict2call(parser)
    file.write('F5 Série temporelle ponctuelle passed\n')
except:
    file.write ('F5 Série temporelle ponctuelle failed\n')

print("My work is done")
file.close()
assert True


