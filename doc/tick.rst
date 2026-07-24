.. _tick:

Issues management (armoor-tick)
################################

.. meta::
    :description: Anomaly management | You can create, search and read issues from Gitlab.

You can create, search and read issues from Gitlab.
Use **armoor-tick + TAB** to visualize all the commands available, and get some help with the **-h** option.

How to setup
------------

In the folder where you will run the commands to create, read or search issues, please create a file named **auth.cfg**
and paste the following code by replacing ``TOKEN``, ``GITLAB_URL_SERVER`` and ``ID_PROJECT`` with your information :

::

    [gitlab]
        token = TOKEN
        url = GITLAB_URL_SERVER
        project = ID_PROJECT

.. IMPORTANT::

   ``TOKEN`` must have an api scope for the project ``ID_PROJECT``

You can read your credentials information with : ``armoor-tick-authentication-info``

You can update your credential with : ``armoor-tick-authentication``.

Here is an example to update your token :

::

    armoor-tick-authentication --gitlab-token your_token_with_read_write_api_scope

Run unit tests
--------------

To run issues management unit tests, use the following command::

    pytest armoor/tests/uni/test_tick.py

How to use
----------

In this section you will learn how to search, read and create issues from Gitlab in a command line with armoor.

Search for issues
~~~~~~~~~~~~~~~~~

The command to search for issues is ``armoor-tick-search`` which comes with three options : *request*, *config* and *state*.

* *request* : Any text which should be in the issue
* *config* : Regional configuration name.
* *state* : Filter by issues that are in a certain state, that is either *opened* (default), *closed* or *all*.

Here is an example :

::

    armoor-tick-search --config med

.. program-output:: armoor-tick-search -h
   :shell:
   :returncode: 0

Read an existing issue
~~~~~~~~~~~~~~~~~~~~~~

To retrieve the description of an issue you need the ``issue_id`` that is provided
with any search or after the creation of an issue.

Here is an example :

::

    armoor-tick-description 1

.. program-output:: armoor-tick-description -h
   :shell:
   :returncode: 0

Create an issue
~~~~~~~~~~~~~~~

The command to create an issue is ``armoor-tick-create``. All the options can be found in the following table :

+-------------------+---------------------------------------------------------------------------------------+
| Field             | Description                                                                           |
+===================+=======================================================================================+
| title             | Titre du ticket (champ obligatoire)                                                   |
+-------------------+---------------------------------------------------------------------------------------+
| kind              | Type d’anomalie (options possibles : field_value, nodata et numeric)                  |
+-------------------+---------------------------------------------------------------------------------------+
| production_time   | Date de production (champ obligatoire)                                                |
+-------------------+---------------------------------------------------------------------------------------+
| comment           | Commentaire                                                                           |
+-------------------+---------------------------------------------------------------------------------------+
| reporter          | Nom de la personne qui rapporte l’anomalie                                            |
+-------------------+---------------------------------------------------------------------------------------+
| reporting_level   | Niveau d’intérêt: Niveau 0: intérêt pour tous, Niveau 100: intérêt expert seulement   |
+-------------------+---------------------------------------------------------------------------------------+
| model             | Modèle : HYCOM/CROCO/PSY4/TOPAZ                                                       |
+-------------------+---------------------------------------------------------------------------------------+
| version           | Identifiant git si modèle Shom                                                        |
+-------------------+---------------------------------------------------------------------------------------+
| config            | Nom de la configuration (champ obligatoire)                                           |
+-------------------+---------------------------------------------------------------------------------------+
| hpc               | Calculateur                                                                           |
+-------------------+---------------------------------------------------------------------------------------+
| lon               | Extension zonale                                                                      |
+-------------------+---------------------------------------------------------------------------------------+
| lat               | Extension méridienne                                                                  |
+-------------------+---------------------------------------------------------------------------------------+
| depth             | Extension verticale en valeur numérique (en m, en numéro de couche) ou                |
|                   | de type « surf », « bottom »                                                          |
+-------------------+---------------------------------------------------------------------------------------+
| time              | Extension temporelle                                                                  |
+-------------------+---------------------------------------------------------------------------------------+
| standard_nam      | Nom de la variable par son nom standard                                               |
+-------------------+---------------------------------------------------------------------------------------+
| src_file          | Fichier1#ligne, fichier2#ligne                                                        |
+-------------------+---------------------------------------------------------------------------------------+
| delta_clim        | Ecart à une climatologie                                                              |
+-------------------+---------------------------------------------------------------------------------------+
| clim_value        | Valeur climatologique                                                                 |
+-------------------+---------------------------------------------------------------------------------------+
| clim_name         | Nom de la climatologie                                                                |
+-------------------+---------------------------------------------------------------------------------------+
| blocking          | « True » si la production de la configuration régionale est refusée.                  |
|                   | Sinon, l’utilisateur peut renseigner la valeur.                                       |
+-------------------+---------------------------------------------------------------------------------------+

All the options can be given in a command line, in a file, or a combination of both.
Here is an example :

::

    armoor-tick-create --title "my title" --production-time "06/03/2023" --cfgfile ticket_hycom_manga.cfg

The content of the *ticket_hycom_manga.cfg* file could be :

::

    kind = nodata
    reporting_level = 100
    model = hycom3d
    config = manga
    depth = 500
    blocking = False

.. program-output:: armoor-tick-create -h
   :shell:
   :returncode: 0
