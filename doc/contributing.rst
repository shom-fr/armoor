.. _contributing:

Developer Guide
===============

This page is for contributors and maintainers of **armoor**.  It describes the
architecture, the coding conventions, the testing strategy and the GitLab
workflow that every contributor is expected to follow.

.. contents::
   :local:
   :depth: 2


Architecture overview
---------------------

Armoor is organised as a layered library.  Each layer has a single
responsibility; higher layers may import lower ones but never the reverse.

.. code-block:: text

   ┌─────────────────────────────────────────────────────────────────┐
   │  armoor.cli          Command-line entry points (thin wrappers)  │
   ├─────────────────────────────────────────────────────────────────┤
   │  armoor.accessors    xarray accessor plugins (ds.filters, …)   │
   ├─────────────────────────────────────────────────────────────────┤
   │  armoor.comp         Composite workflows (coloc + stats + plot) │
   │  armoor.data         High-level I/O, interp, range, plot        │
   ├─────────────────────────────────────────────────────────────────┤
   │  armoor.base         Atomic algorithms (no I/O, no Dask)        │
   └─────────────────────────────────────────────────────────────────┘

``armoor.base``
    Pure algorithmic functions.  No I/O, no Dask, no side-effects.
    Everything here must be unit-testable in isolation.  Examples:
    :mod:`armoor.base.stats`, :mod:`armoor.base.interp`,
    :mod:`armoor.base.ranges`, :mod:`armoor.base.plot`.

``armoor.data``
    High-level dataset operations that may read files or launch Dask tasks,
    but still work on a single :class:`xr.Dataset`.  Examples:
    :mod:`armoor.data.interp`, :mod:`armoor.data.range`,
    :mod:`armoor.data.load`.

``armoor.comp``
    Multi-dataset workflows: colocation, statistical comparison, output
    generation.  Orchestrates ``base`` and ``data`` modules.  Examples:
    :mod:`armoor.comp.coloc`, :mod:`armoor.comp.stats`,
    :mod:`armoor.comp.output`.

``armoor.accessors``
    xarray accessor plugins registered on :class:`xr.Dataset`.  They are
    **thin facades only** — no business logic, no duplicated code.  Every
    method must delegate to the appropriate ``base`` or ``data`` function.
    See :ref:`accessor-rules` below.

``armoor.cli``
    Command-line entry points (``argparse`` parsers + ``main_*`` functions).
    They parse arguments, open datasets via :func:`armoor.data.open_decode.open_decode`,
    call the relevant accessor or ``comp`` function, and save the output.
    No computation should live here.


.. _accessor-rules:

Accessor design rules
---------------------

Armoor exposes seven xarray accessor plugins (``ds.filters``,
``ds.oceanvars``, ``ds.coloc``, ``ds.stats``, ``ds.interp``, ``ds.range``,
``ds.plot``).  The following rules are **mandatory** for any new or modified
accessor method.

1. **No business logic in accessors.**
   An accessor method must be a one- or two-line wrapper that calls an
   existing function in ``armoor.base`` or ``armoor.data``.  If there is no
   such function yet, create it there first, then call it from the accessor.

2. **No code duplication.**
   If the logic already exists in ``base`` or ``data``, reuse it.  Copying
   code into the accessor is forbidden.

3. **Register via** ``armoor.accessors.__init__``**.**
   Add a line ``from armoor.accessors import <module>  # noqa: F401`` to
   ``armoor/accessors/__init__.py``.  Importing ``armoor`` must be the only
   action required to activate all accessors.

4. **Preserve xarray built-ins.**
   When overriding a built-in accessor (``ds.interp``, ``ds.plot``),
   restore the original behaviour via ``__call__`` or class inheritance and
   suppress the registration warning with ``warnings.catch_warnings()``.

5. **Return** ``xr.Dataset`` **or** ``list[xr.Dataset]``**.**
   Accessors must not return raw numpy arrays, DataFrames or file paths.
   This keeps chaining (e.g. ``ds.stats.mean().plot.maps()``) possible.

6. **Document every public method** with a NumPy-style docstring including
   at minimum ``Parameters``, ``Returns`` and a one-line ``Delegates to``
   reference.


Code style
----------

All Python code in armoor must comply with the following rules.

Formatter — Black
~~~~~~~~~~~~~~~~~

Armoor uses `Black <https://black.readthedocs.io>`_ as its code formatter
(line length **100**, target Python 3.11).  Run it before every commit:

.. code-block:: bash

   black armoor/

The Black configuration is in ``pyproject.toml`` (``[tool.black]`` section).

Linter — Flake8
~~~~~~~~~~~~~~~

`Flake8 <https://flake8.pycqa.org>`_ is used for linting.  The
configuration is in ``pyproject.toml`` (``[tool.flake8]``):

- Maximum line length: **100**
- Ignored: ``E203``, ``E402``, ``E501``, ``E731``, ``W503``

Run before every commit:

.. code-block:: bash

   flake8 armoor/

PEP 8
~~~~~

All code must follow `PEP 8 <https://peps.python.org/pep-0008/>`_ except
where Black or the Flake8 ignore list overrides it.  Key points:

- Snake\_case for variables, functions and modules.
- CamelCase for classes.
- ``UPPER_SNAKE_CASE`` for module-level constants.
- Two blank lines between top-level definitions; one blank line between
  methods.
- Imports grouped in order: standard library → third-party → armoor internal.
  Each group separated by a blank line.

Docstrings — NumPy style
~~~~~~~~~~~~~~~~~~~~~~~~

Every public module, class and function must have a docstring written in
`NumPy/SciPy docstring format
<https://numpydoc.readthedocs.io/en/latest/format.html>`_.

.. code-block:: python

   def bias(dsprod, dsref, dim):
       """Mean bias (prod − ref) along a dimension.

       Parameters
       ----------
       dsprod : xr.Dataset
           Product dataset.
       dsref : xr.Dataset
           Reference dataset.
       dim : str or list of str
           Dimension(s) to reduce over.

       Returns
       -------
       xr.Dataset
           Dataset with the same variables as *dsprod*, reduced along *dim*.

       Examples
       --------
       >>> bias = ds_prod.stats.bias(ds_ref, dim="time")
       """

Rules:

- First line: short imperative summary (no trailing period).
- Blank line, then extended description if needed.
- Standard sections: ``Parameters``, ``Returns``, ``Raises``, ``Notes``,
  ``Examples`` (in that order, only include sections that apply).
- All parameter/return types must be actual Python types or xarray types.
- Examples must be runnable (use ``>>>`` prefix).

Language
~~~~~~~~

All code, docstrings, comments, commit messages, issue titles and merge
request descriptions must be written in **English**.


Testing
-------

Framework
~~~~~~~~~

Armoor uses `pytest <https://docs.pytest.org>`_.  Tests live under
``armoor/tests/uni/`` (unit tests) and ``armoor/tests/int/`` (integration
tests, if any).

.. code-block:: bash

   # Run the full unit test suite
   python -m pytest armoor/tests/uni/ -v

   # Run a single test file
   python -m pytest armoor/tests/uni/test_accessors.py -v

   # Run tests matching a pattern
   python -m pytest armoor/tests/uni/ -k "stats" -v

Rules
~~~~~

- Every new **public function** in ``armoor.base`` or ``armoor.data`` must
  have at least one unit test.
- Every new **accessor method** must have at least one unit test that checks
  the return type and a known numerical value (or structural property).
- Tests must be **self-contained**: use ``pytest.fixture`` for shared
  datasets; never rely on files from disk or network access.
- Tests must **not mock** ``armoor.base`` functions — they must be tested
  against real (small) data.
- Tests must pass without warnings related to deprecation in armoor code
  itself (third-party warnings can be filtered).

Naming conventions
~~~~~~~~~~~~~~~~~~

.. code-block:: text

   armoor/tests/uni/test_<module>.py      e.g. test_accessors_interp.py
   class Test<Feature>:                   e.g. TestInterpTime
       def test_<behaviour>(self, ...):   e.g. test_output_times_match_targets

Each test class groups related tests for a single feature or method.  Test
functions describe the expected behaviour, not the implementation detail.

Coverage
~~~~~~~~

The target line coverage for ``armoor.base`` and ``armoor.accessors`` is
**≥ 80 %**.  Run coverage locally with:

.. code-block:: bash

   python -m pytest armoor/tests/uni/ --cov=armoor --cov-report=term-missing


GitLab workflow
---------------

Repository
~~~~~~~~~~

Source code is hosted at
`<https://gitlab.com/GitShom/STM/armoor>`_.
Documentation is published at
`<https://gitshom.gitlab.io/STM/armoor/>`_.

Branches
~~~~~~~~

.. list-table::
   :header-rows: 1
   :widths: 20 80

   * - Branch
     - Purpose
   * - ``main``
     - Stable, always passing CI.  Direct pushes are forbidden.
   * - ``develop``
     - Integration branch.  Features are merged here first.
   * - ``feature/<slug>``
     - One branch per feature or bug fix.  Branched from ``develop``.
   * - ``hotfix/<slug>``
     - Critical fixes branched from ``main``, merged into both ``main``
       and ``develop``.

Branch names must be lowercase, use hyphens (not underscores), and be short
but descriptive.  Examples: ``feature/range-accessor``,
``hotfix/tfreq-nan-edge-case``.

Issues
~~~~~~

All work must be tracked in the
`issue tracker <https://gitlab.com/GitShom/STM/armoor/-/issues>`_ before
a branch is created.

When opening an issue:

- **Title**: short, in English, describes the problem or feature in the
  imperative (e.g. *Add ds.range accessor*, *Fix bias sign convention*).
- **Label**: assign at least one label (``bug``, ``enhancement``,
  ``documentation``, ``refactor``, ``test``).
- **Description**: include context, expected behaviour and, for bugs, a
  minimal reproducible example.
- **Assignee**: assign yourself if you intend to work on it immediately.

Merge requests
~~~~~~~~~~~~~~

Merge requests (MR) must be opened against ``develop`` (or ``main`` for
hotfixes).

Checklist before opening an MR:

.. code-block:: text

   [ ] Branch is up to date with the target branch
   [ ] black armoor/ passes with no changes
   [ ] flake8 armoor/ reports no errors
   [ ] python -m pytest armoor/tests/uni/ passes
   [ ] New code has docstrings (NumPy style, English)
   [ ] New public API has at least one unit test
   [ ] CHANGES.rst updated with a one-line entry
   [ ] MR title references the issue number (e.g. "Fix #42 — …")

MR description template:

.. code-block:: text

   ## What this MR does
   Short description of the change.

   ## Related issue
   Closes #<issue-number>

   ## Type of change
   - [ ] Bug fix
   - [ ] New feature
   - [ ] Refactoring
   - [ ] Documentation
   - [ ] Tests

   ## Checklist
   - [ ] Tests pass
   - [ ] Docstrings updated
   - [ ] CHANGES.rst updated

Review rules:

- At least **one approval** from a maintainer is required before merging.
- The CI pipeline (lint + tests) must be **green**.
- Squash commits when merging feature branches to keep ``develop`` history
  clean.
- Delete the feature branch after the MR is merged.

CI/CD variables
~~~~~~~~~~~~~~~

The GitLab CI pipeline installs ``woom``, a private dependency hosted on
GitHub, via its git URL.  Two CI/CD variables must be defined in the GitLab
project settings (**Settings → CI/CD → Variables**) before any pipeline can
run successfully:

.. list-table::
   :header-rows: 1
   :widths: 35 65

   * - Variable
     - Description
   * - ``GIT_SHOM_FR_USERNAME``
     - GitHub username with read access to ``shom-fr/woom``.
   * - ``GIT_SHOM_FR_TOKEN``
     - GitHub personal access token (PAT) for that account, with at least
       ``repo`` (read) scope.  Mark it **Masked** and **Protected** in GitLab.

These variables are injected at runtime into the global ``before_script``,
which rewrites all ``https://github.com`` URLs to embed the credentials:

.. code-block:: bash

   git config --global \
     url."https://${GIT_SHOM_FR_USERNAME}:${GIT_SHOM_FR_TOKEN}@github.com".insteadOf \
     "https://github.com"

.. warning::

   Never hard-code credentials in ``.gitlab-ci.yml`` or any tracked file.
   Always use GitLab CI/CD masked variables.

Summary of rules
----------------

.. list-table::
   :header-rows: 1
   :widths: 35 65

   * - Rule
     - Requirement
   * - Language
     - English for all code, docs, commits and issues
   * - Formatter
     - Black (line length 100, Python 3.11)
   * - Linter
     - Flake8 (no errors before commit)
   * - Docstrings
     - NumPy style, every public function/class/method
   * - Typing
     - Type hints on all new public functions
   * - Tests
     - pytest, one test class per feature, ≥ 80 % coverage on base/accessors
   * - No logic in accessors
     - Delegate to ``base`` or ``data``; no duplicated code
   * - No logic in CLI
     - Delegate to accessors or ``comp``; no direct ``base``/``data`` calls
   * - Imports
     - stdlib → third-party → armoor; one blank line between groups
   * - Branches
     - ``feature/<slug>`` off ``develop``; ``hotfix/<slug>`` off ``main``
   * - MR
     - Green CI + one approval + CHANGES.rst entry required
