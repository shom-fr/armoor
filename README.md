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


Utilisation d'armoor pour l'interface previsioniste :
-----------------------------------------------------

Suivre les instructions d'installation précedentes, avec env_forecaster.yml

Placer les fichiers de configuration **forecaster.cfg** et **auth.cfg** dans le répertoire courant d'exécution de l'api.

**forecaster.cfg** :

    approval_path = '/path_to_front/assets/data'
    origins = 'http://localhost', 'https://shom_url.fr'
    ldap_server_url = 'ldap://shom_ldap_url'
    domain = 'SHOM_DOMAIN'
    search_base = 'OU=ShomUsers,DC=shom,DC=shom_loc'
    authorized_user_group = 'shom_users'

**auth.cfg** :

    [gitlab]
        token = TOKEN
        url = GITLAB_URL_SERVER
        project = ID_PROJECT


Lancer l'api via uvicorn comme suit :

    $ uvicorn armoor-api --timeout-keep-alive 60 --workers 4 --host 0.0.0.0 --port 1234 >/home/www/shom-demo/api/logs/uvicorn-armoor.log 2>&1 
