from armoor import cli
from armoor import base
file = open('log.txt','a')
try:
    #Ellipses courant marée
    parser = cli.command_line_interface(['--file', "data/test_f7/ellipses.ini"])
    base.calls_from_dict.dict2call(parser)
    file.write('F7  Ellipses courant marée  passed\n')
except:
    file.write ('F7 Ellipses courant marée   failed\n')
try:
    #Diagramme hovmoller mouillage txt shom
    parser = cli.command_line_interface(['--file', "data/test_f7/hovmoller_datashom.ini"])
    base.calls_from_dict.dict2call(parser)
    file.write('F7  Diagramme hovmoller mouillage txt shom  passed\n')
except:
    file.write ('F7  Diagramme hovmoller mouillage txt shom  failed\n')
try:
    #Diagramme hovmoller mouillage txt shom bathy/rayon
    parser = cli.command_line_interface(['--file', "data/test_f7/hovmoller_datashom_bathyradius.ini"])
    base.calls_from_dict.dict2call(parser)
    file.write('F7  Diagramme hovmoller mouillage txt shom bathy/rayon  passed\n')
except:
    file.write ('F7  Diagramme hovmoller mouillage txt shom bathy/rayon  failed\n')
try:
    #Diagramme hovmoller LADCP txt shom
    parser = cli.command_line_interface(['--file', "data/test_f7/hovmoller_LADCP.ini"])
    base.calls_from_dict.dict2call(parser)
    file.write('F7 Diagramme hovmoller LADCP txt shom   passed\n')
except:
    file.write ('F7  Diagramme hovmoller LADCP txt shom  failed\n')
try:
    #Tableau harmoniques courant
    parser = cli.command_line_interface(['--file', "data/test_f7/harmonic_table.ini"])
    base.calls_from_dict.dict2call(parser)
    file.write('F7 Tableau harmoniques courant   passed\n')
except:
    file.write ('F7   Tableau harmoniques courant failed\n')
try:
    #Tableau harmoniques courant tranches
    parser = cli.command_line_interface(['--file', "data/test_f7/harmonic_table_tranche.ini"])
    base.calls_from_dict.dict2call(parser)
    file.write('F7  Tableau harmoniques courant tranches  passed\n')
except:
    file.write ('F7  Tableau harmoniques courant tranches  failed\n')
try:
    #Ellipses courant marée avec tranches
    parser = cli.command_line_interface(['--file', "data/test_f7/ellipses_tranche.ini"])
    base.calls_from_dict.dict2call(parser)
    file.write('F7  Ellipses courant marée avec tranches  passed\n')
except:
    file.write ('F7  Ellipses courant marée avec tranches  failed\n')
print("My work is done")
file.close()
assert True


