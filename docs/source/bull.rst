Reports
=======

.. meta::
    :description: Reports | You can generate reports based on armoor functionalities.


How to generate reports
-----------------------

You will learn here how to use ``armoor-bull`` to create reports based on the 9 functionalities of armoor.
To generate a report, run the command ``armoor-bull`` with two options:

    * ``-o``: This option specifies the output folder where the report will be saved. Please create the output folder before running the command.
    * ``-c``: This option specifies the configuration file that defines the report generation parameters.

We can distinguish 3 sections in the configuration file:

    #. Report : common part of the execution.
    #. Functionalities : configurations.
    #. Meta-zones : filters applied to the configurations.


1. Report
---------

In the report's section, 2 attributes must be provided after ``[report]``:

    * ``title`` : the title of the report.
    * ``format`` : the output format, that is either **html**, **pdf** or **all** (both).


2. Functionalities
------------------

We can provide as many Functionalities as needed after ``[functionalities]``.

For each functionality, you must provide a functionality name in double brackets ``[[functionality_name]]`` followed by 2 attributes:

    * ``path_to_config`` : path to a configuration file as it is described in :doc:`base` chapter, but without a **meta-zone** (they are described in the configuration file of the report).
    * ``meta_zones`` : a list of **meta-zone** names.

.. Note::
    In this list, the name of the **meta-zone**, must match the name in double brackets ``[[meta_zone_name]]`` defined in the section below.


.. IMPORTANT::
    Each functionality name ``[[functionality_name]]`` must be unique.


3. Meta-zones
-------------

We can provide as many meta-zones as needed after ``[meta_zones]``.

For each **meta-zone**, you must provide a meta-zone name in double brackets ``[[meta_zone_name]]`` followed by 2 attributes, plus the **filters to apply**:

    * ``name`` : *meta-zone* name appearing in the title plots.
    * ``description`` : *description* text appearing in the report.
    * **filters to apply** : use the same attributes names as described in section **4. Meta-zone** of the :doc:`base` chapter.

.. IMPORTANT::
    Each **meta-zone** name ``[[meta_zone_name]]`` must be unique.


Example
-------

Example of configuration file::

    [report]
        title = Bulletin de validation
        format = pdf

    [functionalities]
        [[f1_map_sst_biais]]
            path_to_config = test_f1/map_sst_biais.ini
            meta_zones = meta_zone_polygon_1, meta_zone_polygon_2
        [[f1_map_sst_diff]]
            path_to_config = test_f1/map_sst_diff.ini
            meta_zones = meta_zone_simple_polygon_1

    [meta_zones]

        [[meta_zone_polygon_1]]
            name = "Polygon, interval, start and end time. => 2020"
            description = Description de la meta_zone_polygon_1
            polygon = [-6,49], [-6, 47],[-4, 47], [-4, 49]
            start = 2020-06-01T00:00:00
            end = 2020-06-04T03:00:00
            interval = 12h

        [[meta_zone_polygon_2]]
            name = "Polygon, interval, start and end time. => 2022"
            description = Description de la meta_zone_polygon_2
            polygon = [-6,49], [-6, 47],[-4, 47], [-4, 49]
            start = 2022-06-01T00:00:00
            end = 2022-06-04T03:00:00
            interval = 12h

        [[meta_zone_simple_polygon_1]]
            name = "Polygon 1"
            description = Description de la meta_zone_simple_polygon_1
            polygon = [-3.5,46], [-3.5, 48],[-2, 48], [-2, 46]


Run test
--------

To run the report's test, use the following command::

    pytest your_path_to/tests/int/bull/test_bull.py


In the folder where you will run ``pytest`` please create a file named **tests.cfg**
and add the following line by replacing ``/path/to/output/tests/P1/`` with your information::

    path_p1 = '/path/to/output/tests/P1/'

In the ``path_p1`` folder, you must have the ``data`` folder from the delivered archive ``archive_data_for_tests.tar.gz``.
