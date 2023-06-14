Forecasters Interface installation
==================================

Armoor API
----------

Here are the instructions to launch the Armoor API used by the forecasters interface.

First follow the instructions from :doc:`install` section.

Place the configuration files forecaster.cfg and auth.cfg in the current execution directory of the API (e.g., ~/api_directory).

**forecaster.cfg**::

    approval_path = '/path_to_front/shom-ui/assets/data'
    origins = 'http://localhost', 'https://shom_url.fr'
    ldap_server_url = 'ldap://shom_ldap_url'
    domain = 'SHOM_DOMAIN'
    search_base = 'OU=ShomUsers,DC=shom,DC=shom_loc'
    authorized_user_group = 'shom_users'

* approval_path : Path where the images from the script are copied
* origins : List of URLs from which requests to the API originate, e.g., 'http://localhost', 'https://shom_url.fr'
* ldap_server_url : Shom's LDAP server addres
* domain : Domain name to use in the LDAP
* search_base : LDAP mask used to create a distinguished name (DN) when the user logs in
* authorized_user_group : Definition of LDAP groups allowed to connect to the web application

**auth.cfg**::

    [gitlab]
        token = TOKEN
        url = GITLAB_URL_SERVER
        project = ID_PROJECT


* token : Token used for authentication (e.g., glpat-uy8upta6xMoTh5yUTrfH).
* url : GitLab server address (e.g., https://gitlab.com/).
* project : Project identifier (e.g., 9549702).

You can launch the API with Uvicorn using the following script::

    #!/bin/bash
    cd ~/api_directory
    source activate armoor_env
    uvicorn armoor.tick.forecaster_api:app --workers 4 --host 0.0.0.0 --port port_api

You can verify that the API is responding correctly by accessing host:port_api/ping/ and expecting a "pong" response.


Forecasters Interface
---------------------

Here are the instructions to launch the front-end of the forecasters interface:

* Unzip the shom-ui.zip file on an environment that has access to the API (it can be on the same server or not).
* Prepare the shom-ui/assets/endpoints.json configuration file by specifying the API URL.

**endpoints.json**::

    {
        "api": "https://shom_url.fr/api"
    }

* Open port ``port_api`` for the front-end.

Apache Configuration:

* Define the website's URL (internally at Shom).
* Redirect all requests ``/*`` to the index.html file (on the front-end server).
* Redirect all requests ``/api`` to the API (back-end server).


Hosting the API and Website
---------------------------

All tests have been conducted with 8 GB of RAM and 6 vCPUs.
At least 90 GB of disk space is required for 10 days of history and
3 regional configurations (3 GB x 10 days x 3 configurations).