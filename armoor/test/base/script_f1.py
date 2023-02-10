from armoor import cli
from armoor import base

file = open('log.txt','a')

try:
    #Carte SST : différence CROCO
    parser = cli.command_line_interface(['--file', "data/test_f1/map_sst_diff.ini"])
    base.calls_from_dict.dict2call(parser)
    file.write('F1 Carte SST : différence CROCO passed\n')
except:
    file.write ('F1 Carte SST : différence CROCO failed\n')
try:
    #Carte SST : différence TOPAZ
    parser = cli.command_line_interface(['--file', "data/test_f1/map_sst_diff_TOPAZ.ini"])
    base.calls_from_dict.dict2call(parser)
    file.write('F1 Carte SST : différence TOPAZ passed\n')
except:
    file.write ('F1 Carte SST : différence TOPAZ failed\n')
try:
    #Carte SST : biais (avec intervalle)
    parser = cli.command_line_interface(['--file', "data/test_f1/map_sst_biais.ini"])
    base.calls_from_dict.dict2call(parser)
    file.write('F1 Carte SST : biais (avec intervalle) passed\n')
except:
    file.write ('F1 Carte SST : biais (avec intervalle) failed\n')
try:
    #Carte SST : RMSE (avec intervalle)
    parser = cli.command_line_interface(['--file', "data/test_f1/map_sst_rmse.ini"])
    base.calls_from_dict.dict2call(parser)
    file.write('F1 Carte SST : RMSE (avec intervalle) passed\n')
except:
    file.write ('F1 Carte SST : RMSE (avec intervalle) failed\n')
try:
    #Carte SST : RMSE centree(avec intervalle)
    parser = cli.command_line_interface(['--file', "data/test_f1/map_sst_rmse_centree.ini"])
    base.calls_from_dict.dict2call(parser)
    file.write('F1 Carte SST : RMSE centree(avec intervalle) passed\n')
except:
    file.write ('F1 Carte SST : RMSE centree(avec intervalle) failed\n')
try:
    #Diagramme de dispersion SST
    parser = cli.command_line_interface(['--file', "data/test_f1/diag_disp_sst.ini"])
    base.calls_from_dict.dict2call(parser)
    file.write('F1 Diagramme de dispersion SST passed\n')
except:
    file.write ('F1 Diagramme de dispersion SST failed\n')
try:
    #Série temporelle SST métriques stats avec intervalles
    parser = cli.command_line_interface(['--file', "data/test_f1/ser_temp_sst.ini"])
    base.calls_from_dict.dict2call(parser)
    file.write('F1 Série temporelle SST métriques stats avec intervalles passed\n')
except:
    file.write ('F1 Série temporelle SST métriques stats avec intervalles failed\n')
try:
    #Série temporelle SST métriques ponctuelles avec intervalles
    parser = cli.command_line_interface(['--file', "data/test_f1/ser_temp_sst_ponct_intervalles.ini"])
    base.calls_from_dict.dict2call(parser)
    file.write('F1 Série temporelle SST métriques ponctuelles avec intervalles passed\n')
except:
    file.write ('F1 Série temporelle SST métriques ponctuelles avec intervalles failed\n')
try:
    #Série temporelle SST métriques ponctuelles sans intervalles
    parser = cli.command_line_interface(['--file', "data/test_f1/ser_temp_sst_ponct_diff.ini"])
    base.calls_from_dict.dict2call(parser)
    file.write('F1 Série temporelle SST métriques ponctuelles sans intervalles passed\n')
except:
    file.write ('F1 Série temporelle SST métriques ponctuelles sans intervalles failed\n')

print("My work is done")
file.close()
assert True


