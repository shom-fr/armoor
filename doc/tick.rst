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

    pytest tests/uni/test_tick.py

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

+------------------+-------------------------------------------------------------------------------------------+
| Field            | Description                                                                               |
+==================+===========================================================================================+
| title            | Ticket title (required field)                                                             |
+------------------+-------------------------------------------------------------------------------------------+
| kind             | Anomaly type (possible options: field_value, nodata and numeric)                          |
+------------------+-------------------------------------------------------------------------------------------+
| production_time  | Production date (required field)                                                          |
+------------------+-------------------------------------------------------------------------------------------+
| comment          | Comment                                                                                   |
+------------------+-------------------------------------------------------------------------------------------+
| reporter         | Name of the person reporting the anomaly                                                  |
+------------------+-------------------------------------------------------------------------------------------+
| reporting_level  | Interest level: Level 0: relevant to everyone, Level 100: expert interest only            |
+------------------+-------------------------------------------------------------------------------------------+
| model            | Model: HYCOM/CROCO/PSY4/TOPAZ                                                             |
+------------------+-------------------------------------------------------------------------------------------+
| version          | Git identifier if a Shom model                                                            |
+------------------+-------------------------------------------------------------------------------------------+
| config           | Configuration name (required field)                                                       |
+------------------+-------------------------------------------------------------------------------------------+
| hpc              | Compute cluster                                                                           |
+------------------+-------------------------------------------------------------------------------------------+
| lon              | Zonal extent                                                                              |
+------------------+-------------------------------------------------------------------------------------------+
| lat              | Meridional extent                                                                         |
+------------------+-------------------------------------------------------------------------------------------+
| depth            | Vertical extent as a numeric value (in m, or layer number) or as a type such as "surf",   |
|                  | "bottom"                                                                                  |
+------------------+-------------------------------------------------------------------------------------------+
| time             | Temporal extent                                                                           |
+------------------+-------------------------------------------------------------------------------------------+
| standard_nam     | Variable name, given as its standard name                                                 |
+------------------+-------------------------------------------------------------------------------------------+
| src_file         | file1#line, file2#line                                                                    |
+------------------+-------------------------------------------------------------------------------------------+
| delta_clim       | Deviation from a climatology                                                              |
+------------------+-------------------------------------------------------------------------------------------+
| clim_value       | Climatological value                                                                      |
+------------------+-------------------------------------------------------------------------------------------+
| clim_name        | Climatology name                                                                          |
+------------------+-------------------------------------------------------------------------------------------+
| blocking         | "True" if the regional configuration's production is rejected. Otherwise, the user may    |
|                  | set the value.                                                                            |
+------------------+-------------------------------------------------------------------------------------------+

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
