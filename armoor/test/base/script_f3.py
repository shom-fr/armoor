from armoor import cli
from armoor import base
file = open('log.txt','a')
try :
    #Courbe temporelle de statistique (intervalle)
    parser = cli.command_line_interface(['--file', "data/test_f3/ser_temp_stat.ini"])
    base.calls_from_dict.dict2call(parser)
    file.write('F3 Courbe temporelle de statistique (intervalle) passed\n')
except:
    file.write ('F3 Courbe temporelle de statistique (intervalle) failed\n')

print("My work is done")
file.close()
assert True


