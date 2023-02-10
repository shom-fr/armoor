from armoor import cli
from armoor import base
file = open('log.txt','a')


try:
    #Carte composantes harmoniques courant
    parser = cli.command_line_interface(['--file', "data/test_f6/map_harm_courant.ini"])
    base.calls_from_dict.dict2call(parser)
    file.write('F6 Carte composantes harmoniques courant  passed\n')
except:
    file.write ('F6 Carte composantes harmoniques courant  failed\n')
try:
    # Ellipses composantes harmoniques courant
    parser = cli.command_line_interface(['--file', "data/test_f6/ellipse_courant.ini"])
    base.calls_from_dict.dict2call(parser)
    file.write('F6 Ellipses composantes harmoniques courant  passed\n')
except:
    file.write ('F6  Ellipses composantes harmoniques courant failed\n')
try:
    # Ellipses composantes harmoniques courant sur une même période
    parser = cli.command_line_interface(['--file', "data/test_f6/ellipse_courant_periode.ini"])
    base.calls_from_dict.dict2call(parser)
    file.write('F6  Ellipses composantes harmoniques courant sur une même période passed\n')
except:
    file.write ('F6 Ellipses composantes harmoniques courant sur une même période  failed\n')
try:
    # Serie temporelle ponctuelle
    parser = cli.command_line_interface(['--file', "data/test_f6/ser_temp_uv_ponct.ini"])
    base.calls_from_dict.dict2call(parser)
    file.write('F6  Serie temporelle ponctuelle  passed\n')
except:
    file.write ('F6 Serie temporelle ponctuelle   failed\n')
try:
    # Serie temporelle ponctuelle avec intervalles
    parser = cli.command_line_interface(['--file', "data/test_f6/ser_temp_uv_ponct_intervalles.ini"])
    base.calls_from_dict.dict2call(parser)
    file.write('F6  Serie temporelle ponctuelle avec intervalles  passed\n')
except:
    file.write ('F6   Serie temporelle ponctuelle avec intervalles failed\n')
try:
    # Serie temporelle statistique avec intervalles
    parser = cli.command_line_interface(['--file', "data/test_f6/ser_temp_uv_stat_intervalles.ini"])
    base.calls_from_dict.dict2call(parser)
    file.write('F6 Serie temporelle statistique avec intervalles  passed\n')
except:
    file.write ('F6   Serie temporelle statistique avec intervalles failed\n')
try:
    # Carte courants différence HYCOM
    parser = cli.command_line_interface(['--file', "data/test_f6/map_current_hycom.ini"])
    base.calls_from_dict.dict2call(parser)
    file.write('F6  Carte courants différence HYCOM passed\n')
except:
    file.write ('F6  Carte courants différence HYCOM failed\n')
try:
    # Carte courants différence HYCOM 2D
    parser = cli.command_line_interface(['--file', "data/test_f6/map_current_hycom2D.ini"])
    base.calls_from_dict.dict2call(parser)
    file.write('F6 Carte courants différence HYCOM 2D  passed\n')
except:
    file.write ('F6 Carte courants différence HYCOM 2D  failed\n')
try:
    # Carte courants différence CROCO
    parser = cli.command_line_interface(['--file', "data/test_f6/map_current_croco.ini"])
    base.calls_from_dict.dict2call(parser)
    file.write('F6 Carte courants différence CROCO  passed\n')
except:
    file.write ('F6  Carte courants différence CROCO failed\n')
try:
    # Carte courants différence
    parser = cli.command_line_interface(['--file', "data/test_f6/map_current.ini"])
    base.calls_from_dict.dict2call(parser)
    file.write('F6 arte courants différence   passed\n')
except:
    file.write ('F6  arte courants différence failed\n')
try:
    # Carte courants biais
    parser = cli.command_line_interface(['--file', "data/test_f6/map_current_biais.ini"])
    base.calls_from_dict.dict2call(parser)
    file.write('F6  Carte courants biais passed\n')
except:
    file.write ('F6 Carte courants biais  failed\n')
try:
    # Carte courants RMSE
    parser = cli.command_line_interface(['--file', "data/test_f6/map_current_RMSE.ini"])
    base.calls_from_dict.dict2call(parser)
    file.write('F6Carte courants RMSE  passed\n')
except:
    file.write ('F6 Carte courants RMSE  failed\n')
print("My work is done")
file.close()
assert True


