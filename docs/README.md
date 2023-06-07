Interface prévisionnistes
=========================

Api armoor
----------

Voici les instructions pour lancer l'api armoor utilisée par l'interface prévisionnistes.

Suivre les instructions d'installation du README.md à la racine du projet.

Placer les fichiers de configuration **forecaster.cfg** et **auth.cfg** dans le répertoire courant d'exécution de l'api (ex: ~/api_directory).

**forecaster.cfg** :

    approval_path = '/path_to_front/shom-ui/assets/data'
    origins = 'http://localhost', 'https://shom_url.fr'
    ldap_server_url = 'ldap://shom_ldap_url'
    domain = 'SHOM_DOMAIN'
    search_base = 'OU=ShomUsers,DC=shom,DC=shom_loc'
    authorized_user_group = 'shom_users'

- approval_path : Path où sont copiées les images provenant du script
- origins : liste d'URLs d'où proviennent les requêtes vers l'API 'http://localhost', 'https://shom_url.fr'
- ldap_server_url : Adresse du serveur LDAP du Shom
- domain : Nom de domaine à utiliser dans le LDAP
- search_base : Masque LDAP utilisé pour créer un nom distinctif (DN) lorsque l'utilisateur se connecte
- authorized_user_group : Définition des groupes LDAP autorisés à se connecter sur l'application Web

**auth.cfg** :

    [gitlab]
        token = TOKEN
        url = GITLAB_URL_SERVER
        project = ID_PROJECT

- token : le token afin de pouvoir s’authentifier (ex: glpat-uy8upta6xMoTh5yUTrfH). 
- url : l’adresse du serveur Gitlab (ex: https://gitlab.com/).
- project : l’identifiant du projet (ex: 24837828).

Vous pouvez lancer l'api avec uvicorn avec le script suivant :

    #!/bin/bash
    cd ~/api_directory
    source activate armoor_env
    uvicorn armoor.tick.forecaster_api:app --workers 4 --host 0.0.0.0 --port port_api

Vous pouvez vérifier que l'api répond correctement avec host:port_api/ping/ si vous avez comme réponse "pong".


Interface prévisionnistes
-------------------------

Voici les instructions pour lancer front-end de l'interface prévisionnistes.
- Dézipper le fichier shom-ui.zip sur un environnement ayant accès à l’API (ça peut être sur le même serveur ou pas)
- Préparer le fichier de configuration shom-ui/assets/endpoints.json en renseignant l’URL de l’API.

    ```
    {
        "api": "https://shom_url.fr/api"
    }
  ```

- Ouvrir le port `port_api` pour le front

Configuration Apache : 
-	Définir l’URL du site web (en interne Shom)
-	Faire pointer toutes les requêtes /* vers le fichier index.html (sur le serveur Front End)
-	Faire pointer toutes les requêtes /api vers l’API (serveur Back End)


Hébergement de l'API et du site web
-----------------------------------

Tous les tests ont été effectués avec 8 Go de RAM et 6 vCPU. 
Il faut prévoir au moins 90 Go d'espace disque pour 10 jours d'historique et 
3 configurations régionales (3 Go x 10 j x 3 conf).