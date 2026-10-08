.. _howtostart:

How to get started
==================

Armoor Python library comes with command-line executables of two types : 

- the elementary command-lines, to execute distinct elementary tasks ;

- the metazone-based command-lines, to execute a chain of tasks.

More details about Armoor command-lines can be found in the dedicated sections : 

- :ref:`cliunit` :

   .. hlist::
      :columns: 3
   
      * armoor-coloc-horizontal
      * armoor-coloc-time
      * armoor-coloc-vertical
      * armoor-comp
      * armoor-decode
      * armoor-filters-horizontal
      * armoor-filters-oceanvars
      * armoor-filters-quality
      * armoor-filters-time
      * armoor-interp-horizontal
      * armoor-interp-time
      * armoor-interp-vertical
      * armoor-range-time
      * armoor-range-vertical

- :ref:`climeta` :

   .. hlist::
      :columns: 3
   
      * armoor-bull
      * armoor-comp-argo
      * armoor-comp-clim
      * armoor-comp-drifter
      * armoor-comp-models
      * armoor-comp-mooring
      * armoor-comp-sst
      * armoor-data
      * armoor-filters

Armoor executables are shown below and can be found in the ``bin/`` folder or with ``armoor-[Tab key]`` command. Metazone-based executables are shown in bold.

To get a better understanding of how Armoor processes incoming data, see the :ref:`opendecode` section.

.. tip:: Armoor saves the outputs in the folder of execution. Run your commands accordingly.

.. note::
   * For the metazone-based executables, you should probably start with the :ref:`examples` section. This collection of examples will gradually be completed to cover almost all features of the library.
   * For the elementary executables, you can find more details in the corresponding armoor.cli API sections.

.. tip:: Once you are comfortable with the basics, the :ref:`guides` section
   explains metazones, colocation, configuration files and the CLI
   architecture in more depth than the reference pages above.
