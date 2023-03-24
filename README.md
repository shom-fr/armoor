Armoor installation
===================

Retrieving sources
------------------

You can retrieve sources from the GitLab repository:

    $ git clone https://gitlab.com/GitShom/STM/armoor.git

How to install dependencies
---------------------------

To setup the environment follow the instructions below:

    $ conda env create -f armoor/environment.yml
    $ conda activate armoor_env

How to install armoor
---------------------

To install **armoor** follow the instructions below:

    $ cd armoor
    $ python -m build
    $ pip install -q ./dist/armoor-0.0.3-py3-none-any.whl

Build documentation
-------------------

To build sphinx documentation as html files:

    $ cd docs
    $ make html

Then open docs/build/html/index.html file.


Interface prévisionnistes
=========================

Api armoor
----------

Voici les instructions pour lancer l'api armoor utilisé par l'interface prévisionnistes.

Suivre les instructions d'installation précédentes.

Placer les fichiers de configuration **forecaster.cfg** et **auth.cfg** dans le répertoire courant d'exécution de l'api.

**forecaster.cfg** :

    approval_path = '/path_to_front/shom-ui/assets/data'
    origins = 'http://localhost', 'https://shom_url.fr'
    ldap_server_url = 'ldap://shom_ldap_url'
    domain = 'SHOM_DOMAIN'
    search_base = 'OU=ShomUsers,DC=shom,DC=shom_loc'
    authorized_user_group = 'shom_users'

- approval_path : '/path_to_front/shom-ui/assets/data'
- origins : 'http://localhost', 'https://shom_url.fr'
- ldap_server_url : 'ldap://shom_ldap_url'
- domain : 'SHOM_DOMAIN'
- search_base : 'OU=ShomUsers,DC=shom,DC=shom_loc'
- authorized_user_group : 'shom_users'

**auth.cfg** :

    [gitlab]
        token = TOKEN
        url = GITLAB_URL_SERVER
        project = ID_PROJECT

- token : l’adresse du serveur Gitlab (ex: https://gitlab.com/).
- url : le token afin de pouvoir s’authentifier (ex: glpat-uy8upta6xMoTh5yUTrfH).
- project : l’identifiant du projet (ex: 24837828).

Lancer l'api via uvicorn comme suit :

    $ uvicorn armoor.tick.forecaster_api:app --workers 4 --host 0.0.0.0 --port 1234

Vous pouvez vérifier que l'api répond correctement avec host:port/ping/ si vous avez comme réponse "pong".


Interface prévisionnistes
-------------------------

Voici les instructions pour lancer front-end de l'interface prévisionnistes.

TODO @MATHIS @LAURENT

TODO Compléter à la manière de auth.cfg les 6 points pour forecaster.cfg un peu plus haut
