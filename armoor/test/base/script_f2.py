from armoor import cli
from armoor import base

file = open('log.txt','a')

try :
    #Carte de différence de sst pour une immersion choisie, entre 2 dates
    parser = cli.command_line_interface(['--file', "data/test_f2/map_diff.ini"])
    base.calls_from_dict.dict2call(parser)
    file.write('F2 Carte de différence de sst pour une immersion choisie, entre 2 dates passed\n')
except:
    file.write ('F2 Carte de différence de sst pour une immersion choisie, entre 2 dates failed\n')
try:
    #Carte de différence de sst pour une immersion choisie, entre 2 dates, avec intervalles
    parser = cli.command_line_interface(['--file', "data/test_f2/map_diff_intervalles.ini"])
    base.calls_from_dict.dict2call(parser)
    file.write('F2 Carte de différence de sst pour une immersion choisie, entre 2 dates, avec intervalles passed\n')
except:
    file.write ('F2 Carte de différence de sst pour une immersion choisie, entre 2 dates, avec intervalles failed\n')
try:
    #Carte de biais de sst, entre 2 dates, avec intervalles et tranches
    parser = cli.command_line_interface(['--file', "data/test_f2/map_biais_intervalles_tranches.ini"])
    base.calls_from_dict.dict2call(parser)
    file.write('F2 Carte de biais de sst, entre 2 dates, avec intervalles et tranches passed\n')
except:
    file.write ('F2 Carte de biais de sst, entre 2 dates, avec intervalles et tranches failed\n')
try:
    #Carte de rmse de sst, entre 2 dates, avec intervalles et tranches
    parser = cli.command_line_interface(['--file', "data/test_f2/map_RMSE_intervalles_tranches.ini"])
    base.calls_from_dict.dict2call(parser)
    file.write('F2 Carte de rmse de sst, entre 2 dates, avec intervalles et tranches passed\n')
except:
    file.write ('F2 Carte de rmse de sst, entre 2 dates, avec intervalles et tranches failed\n')
try:
    #Carte de rmse centrée de sst, entre 2 dates, avec intervalles et tranches
    parser = cli.command_line_interface(['--file', "data/test_f2/map_RMSEc_intervalles_tranches.ini"])
    base.calls_from_dict.dict2call(parser)
    file.write('F2 Carte de rmse centrée de sst, entre 2 dates, avec intervalles et tranches passed\n')
except:
    file.write ('F2 Carte de rmse centrée de sst, entre 2 dates, avec intervalles et tranches failed\n')
try:
    #Profil unique
    parser = cli.command_line_interface(['--file', "data/test_f2/profil_unique_temp.ini"])
    base.calls_from_dict.dict2call(parser)
    file.write('F2 Profil unique passed\n')
except:
    file.write ('F2 Profil unique failed\n')
try:
    #Profil multi
    parser = cli.command_line_interface(['--file', "data/test_f2/profil_multi_temp.ini"])
    base.calls_from_dict.dict2call(parser)
    file.write('F2 Profil multi passed\n')
except:
    file.write ('F2 Profil multi failed\n')
try:
    #Diagramme de dispersion
    parser = cli.command_line_interface(['--file', "data/test_f2/diag_disp.ini"])
    base.calls_from_dict.dict2call(parser)
    file.write('F2 Diagramme de dispersion passed\n')
except:
    file.write ('F2 Diagramme de dispersion failed\n')
try:
    #Diagramme de dispersion avec tranche et intervalle
    parser = cli.command_line_interface(['--file', "data/test_f2/diag_disp_tranche_intervalle.ini"])
    base.calls_from_dict.dict2call(parser)
    file.write('F2 Diagramme de dispersion avec tranche et intervalle passed\n')
except:
    file.write ('F2 Diagramme de dispersion avec tranche et intervalle failed\n')
try:
    #Série temporelle statistique avec intervalle sans profondeur
    parser = cli.command_line_interface(['--file', "data/test_f2/ser_temp_intervalles.ini"])
    base.calls_from_dict.dict2call(parser)
    file.write('F2 érie temporelle statistique avec intervalle sans profondeur passed\n')
except:
    file.write ('F2 érie temporelle statistique avec intervalle sans profondeur failed\n')
try:
    #Série temporelle statistique sans intervalle avec tranches
    parser = cli.command_line_interface(['--file', "data/test_f2/ser_temp_tranches.ini"])
    base.calls_from_dict.dict2call(parser)
    file.write('F2 Série temporelle statistique sans intervalle avec tranches passed\n')
except:
    file.write ('F2 Série temporelle statistique sans intervalle avec tranches failed\n')
try:
    #Diagramme theta s "profil unique"
    parser = cli.command_line_interface(['--file', "data/test_f2/diag_theta_s_unique.ini"])
    base.calls_from_dict.dict2call(parser)
    file.write('F2 Diagramme theta s "profil unique" passed\n')
except:
    file.write ('F2 Diagramme theta s "profil unique" failed\n')

try:
    #Diagramme theta-s multi-profils
    parser = cli.command_line_interface(['--file', "data/test_f2/diag_theta_s_multi.ini"])
    base.calls_from_dict.dict2call(parser)
    file.write('F2 Diagramme theta-s multi-profils passed\n')
except:
    file.write ('F2 Diagramme theta-s multi-profils failed\n')

print("My work is done")
file.close()
assert True


