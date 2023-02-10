Création de docs pour le projet SHOM

Pour récupérer l’environnement avec tous les modules utilisés par le projet : 
conda create --name <env> --file env-shom.txt 

Si vous avez déjà un environnement, voici les deux packages à rajouter : 
Sphinx : conda install -c conda-forge sphinx 
Sphinx-rtd-theme : conda install -c conda-forge sphinx_rtd_theme 

Utilisation de Sphinx Je me suis appuyé sur cet article 
(https://betterprogramming.pub/auto-documenting-a-python-project-using-sphinx-8878f9ddc6e9) 
pour construire la doc. Voici les quelques commandes utiles pour la générer, en ce mettant 
à la base du projet : 

Ajouter un module : 
sphinx-apidoc -f -o <OUTPUT_PATH> <MODULE_PATH> 
Ici <OUTPUT_PATH> est docs/source et <MODULE_PATH> cli par exemple. 

Compiler la doc : 
sphinx-build -b html docs/source/ ../../shared_output_data/Doc 

Il suffit ensuite d’ouvrir le fichier ../../shared_output_data/Doc/index.html