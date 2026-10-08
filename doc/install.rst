.. _install:

How to install
==============

.. highlight:: bash

Dependencies
------------

armoor requires ``python>3.11`` and depends on the following packages:

.. list-table::
   :widths: 10 90

   * - `cartopy <https://cartopy.readthedocs.io/stable/>`_
     - Cartopy is a Python package designed for geospatial data processing 
       in order to produce maps and other geospatial data analyses.
   * - `cmocean <https://matplotlib.org/cmocean>`_
     - Beautiful colormaps for oceanography.
   * - `configobj <https://configobj.readthedocs.io/en/latest/configobj.html>`_
     - ConfigObj is a simple but powerful config file reader and writer:
       an ini file round-tripper.
   * - `gsw <https://teos-10.github.io/GSW-Python/>`_
     - gsw is the python implementation of the Thermodynamic Equation of
       Seawater 2010 (TEOS-10).
   * - `matplotlib <https://matplotlib.org/>`_
     - Matplotlib is a comprehensive library for creating static, animated,
       and interactive visualisations in Python.
   * - `numba <https://numba.pydata.org/>`_
     - A high performance python compiler.
   * - `pandas <https://pandas.pydata.org/>`_
     - pandas is a fast, powerful, flexible and easy-to-use open source
       data analysis and manipulation tool, built on top of the
       Python programming language.
   * - `platformdirs <https://github.com/tox-dev/platformdirs>`_
     - A small Python module for determining appropriate platform-specific dirs, e.g. a "user data dir".
   * - `scipy <https://www.scipy.org/scipylib/index.html>`_
     - Scipy provides many user-friendly and efficient numerical routines,
       such as routines for numerical integration, interpolation,
       optimization, linear algebra, and statistics.
   * - `xarray <http://xarray.pydata.org/en/stable/>`_
     - xarray is an open source project and Python package that makes working
       with labelled multi-dimensional arrays simple, efficient, and fun!
   * - `xesmf <https://xesmf.readthedocs.io/en/stable/>`_
     - xESMF is a Python package for regridding.



A complete list of dependencies is given in ``requirements.txt``:

    .. literalinclude:: ../requirements.txt
           :language: text

GitHub access prerequisite
--------------------------

armoor depends on two packages hosted on GitHub (``shom-fr/woom`` and
``shom-fr/xoa``).  Before installing armoor, git must be able to authenticate
against GitHub.

Configure the URL rewrite once on your machine:

.. code-block:: bash

   git config --global \
     url."https://<USERNAME>:<TOKEN>@github.com".insteadOf \
     "https://github.com"

Replace ``<USERNAME>`` with your GitHub username and ``<TOKEN>`` with a
`Personal Access Token (PAT) <https://github.com/settings/tokens>`_ with at
least the ``repo`` (read) scope.

To create a token: **GitHub → Settings → Developer settings →
Personal access tokens → Generate new token**, check the ``repo`` scope.

.. note::

   This configuration is persistent (stored in ``~/.gitconfig``) and only
   needs to be done once per machine.

From sources
------------

\1. Clone the repository::

    $ git clone https://github.com/shom-fr/armoor.git

\2. Run the installation command::

    $ cd armoor
    $ mamba install -n base -c conda-forge -y --file requirements.txt
    $ pip install .

Alternatively, use ``environment.yml``::

    $ cd armoor
    $ mamba env create -f environment.yml

\3. Then, run tests::

    $ export PYTHONPATH=$PWD
    $ cd tests/uni
    $ pytest

