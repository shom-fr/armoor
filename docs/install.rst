Armoor installation
===================

.. meta::
    :description: Armoor Installation | You can install Armoor from source.

This page describes the installation process for armoor tools

Retrieving sources
------------------

You can retrieve sources from the GitLab repository :

::

    $ git clone https://gitlab.com/GitShom/STM/armoor.git


How to install dependencies
---------------------------


To setup the environment follow the instructions below :

::

    $ conda env create -f armoor/environment.yml
    $ conda activate armoor_env


How to install armoor
---------------------

To install **armoor** follow the instructions below :

::

    $ cd armoor
    $ python -m build
    $ pip install -q ./dist/armoor-0.0.3-py3-none-any.whl