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

You can verify that the API is responding correctly by accessing host:port_api/ping/ and
``curl --noproxy '*' -x GET host:port_api/ping/`` and expecting a "pong" response.


Forecasters Interface
---------------------

Here are the instructions to launch the front-end of the forecasters interface:

* Unzip the shom-ui.zip file on an environment that has access to the API (it can be on the same server or not).
* Prepare the ``shom-ui/assets/endpoints.json`` configuration file by specifying the API URL.

**endpoints.json**::

    {
        "api": "https://shom_url.fr/api"
    }

* Open port ``port_api`` for the front-end.

Apache Configuration:

* Define the website's URL (internally at Shom).
* Redirect all requests ``/api`` to the API (back-end server).
* Redirect all requests ``/*`` to the index.html file (on the front-end server).

Here is an example of Apache Configuration::

    <VirtualHost *:80>
        ServerName sl-noveltis-int.shom.fr

        DocumentRoot /opt/prevops/fish/

        RewriteEngine On

        # Redirect /api to your API server
        RewriteRule ^/api/(.*)$ http://sl-noveltis-int.shom.fr:3000/$1 [P,L]

        # Redirect / to index.html
        RewriteCond %{DOCUMENT_ROOT}%{REQUEST_URI} -f [OR]
        RewriteCond %{DOCUMENT_ROOT}%{REQUEST_URI} -d
        RewriteRule ^ - [L]
        RewriteRule ^ /index.html

        <Directory /opt/prevops/fish>
            Options Indexes FollowSymLinks
            AllowOverride All
            Require all granted
        </Directory>

    </VirtualHost>


You can verify that the API is responding correctly through the Apache configuration with
``curl --noproxy '*' -x GET shom_url/api/ping/`` and expecting a "pong" response.

Hosting the API and Website
---------------------------

All tests have been conducted with 8 GB of RAM and 6 vCPUs.
At least 90 GB of disk space is required for 10 days of history and
3 regional configurations (3 GB x 10 days x 3 configurations).


Update Website labels
---------------------

To add or update labels of a regional configuration and parameters,
you will find two json files : ``config_reg.json`` and ``parameters.json`` in the folder ``shom-ui/assets/data``.


*config_reg*
~~~~~~~~~~~~

To add a regional configuration, add a line to the ``config_reg.json`` file in the format of a Python dictionary as follow::

    {
        "hycom3d_med": "HYCOM Mediterrannée",
        "hycom3d_indien": "HYCOM Indien",
        "hycom3d_manga": "HYCOM Manche/Gascogne"
    }

In the above example, the key ``hycom3d_med`` follows the naming of ``model_config`` from :doc:`hmi` ``config_reg section`` and
``HYCOM Mediterrannée`` is the label displayed in the website within the ``Configurations régionales`` component.


*parameters*
~~~~~~~~~~~~

By default, the parameter labels are taken from the configuration file
``[[parameter_name]]`` and are displayed as ``parameter_name`` (c.f. :doc:`hmi` ``Section parameters``)
in the website within the ``Paramètres`` component.

To customise a label, you can add a line to the ``parameters.json`` file: the key shall be the ``parameter_name`` and the value is the customized label. Here's an example::

    {
        "SEA_SURFACE_TEMPERATURE": "1- température de surface",
        "SEA_SURFACE_SALINITY": "2- salinité de surface",
        "MIXED_LAYER": "3- couche de mélange",
        "CURRENT": "4- courant",
        "TEMPERATURE": "5- température",
        "OUTFLOW_MED_TEMP": "6- outflow mediterranéen - température",
        "OUTFLOW_MED_SAL": "7- outflow mediterranéen - salinité",
        "OUTFLOW_PERS_TEMP": "8- outflow persique et mer Rouge - température",
        "OUTFLOW_PERS_SAL": "9- outflow persique et mer Rouge - salinité",
        "GIBRALTAR_TEMP": "10- Gibraltar - température",
        "GIBRALTAR_SAL": "11- Gibraltar - salinité",
        "GIBRALTAR_CURRENT": "12- Gibraltar - courant"
    }


Where to place :doc:`hmi` data
------------------------------

All the data from :doc:`hmi` must be decompressed and placed in the folder ``shom-ui/assets/data``.

Here's an example of a tree inside the ``shom-ui/assets/data`` folder where `YYYYMMDD` are the production dates::

    ├── assets
    │   ├── data
        │   ├── hycom3d_med_YYYYMMDD
            ├── ...
            ├── hycom3d_manga_YYYYMMDD
            ├── ...
            ├── hycom3d_indien_YYYYMMDD
            ├── ...
            ├── config_reg.json
            └── parameters.json


.. NOTE::
    Data in folders `config_reg_YYYYMMDD` older than 10 days are ignored.
