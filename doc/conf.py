# Configuration file for the Sphinx documentation builder.
#
# This file only contains a selection of the most common options. For a full
# list see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html

# %% Path setup --------------------------------------------------------------

# If extensions (or modules to document with autodoc) are in another directory,
# add these directories to sys.path here. If the directory is relative to the
# documentation root, use os.path.abspath to make it absolute, like shown here.
#
import os
import sys
# sys.path.insert(0, os.path.abspath('.'))

# %% Project information -----------------------------------------------------

project = 'Armoor'
copyright = '2025, Shom'
author = 'Shom'

# The full version, including alpha/beta/rc tags
release = '0.1.0'


# %% General configuration ---------------------------------------------------

# Add any Sphinx extension module names here, as strings. They can be
# extensions coming with Sphinx (named 'sphinx.ext.*') or your custom
# ones.
extensions = [
    'sphinx.ext.autodoc',
    'sphinx.ext.autosummary',
    'sphinx.ext.intersphinx',
    'sphinx.ext.napoleon',
    'sphinx.ext.viewcode',
    "sphinx.ext.extlinks",
    "sphinx.ext.mathjax",
    'sphinx_gallery.gen_gallery',
    'sphinxarg.ext',
    'sphinxcontrib.programoutput',
    'sphinx_rtd_theme',
    'sphinx_design'
]

# autodoc_type_aliases = {
#     'Delayed': 'dask.delayed.Delayed',
# }
autodoc_typehints_format = 'short'
# Add any paths that contain templates here, relative to this directory.
templates_path = ['_templates']

# List of patterns, relative to source directory, that match files and
# directories to ignore when looking for source files.
# This pattern also affects html_static_path and html_extra_path.
exclude_patterns = ['_build', 'Thumbs.db', '.DS_Store', '**.ipynb_checkpoints']


# %% Options for HTML output -------------------------------------------------

# The theme to use for HTML and HTML Help pages.  See the documentation for
# a list of builtin themes.
#
html_theme = 'sphinx_book_theme'

# Add any paths that contain custom static files (such as style sheets) here,
# relative to this directory. They are copied after the builtin static files,
# so a file named "default.css" will overwrite the builtin "default.css".
html_static_path = ['_static']

# The logo is drawn with matplotlib by _logo/armoor_logo.py (see logo.rst).
# Its images are written to _static/logo/ (not versioned) at each build,
# and only redrawn when the script or its font has changed.
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '_logo'))
import armoor_logo  # noqa: E402

armoor_logo.build_doc_assets(os.path.join(os.path.dirname(os.path.abspath(__file__)), '_static', 'logo'))

html_favicon = '_static/logo/armoor-favicon.png'

html_theme_options = {
    "logo": {
        "image_light": "_static/logo/armoor-logo.png",
        "image_dark": "_static/logo/armoor-logo-dark.png",
    },
    "repository_url": "https://github.com/shom-fr/armoor",
    "repository_branch": "develop",
    "use_repository_button": True,
    "use_issues_button": True,
    "use_source_button": True,
    "path_to_docs": "doc/",
    # The left sidebar is re-rendered for every page; with ~1000 autosummary
    # pages, a fully expanded 4-level tree made HTML writing take minutes
    # (Read the Docs build timeout). Only render the current page's branch.
    "collapse_navbar": True,
    "max_navbar_depth": 2,
}

# %% Autosumarry
autosummary_generate = True

# The master toctree document.
master_doc ='index'

# %% sphinx-gallery (tutorials/*.py) ------------------------------------------

# Tutorials live as plain Python scripts at the repository root (../tutorials,
# sibling to armoor/, doc/, tests/), not under doc/ -- so they can be run
# directly with `python tutorials/01_....py`, no Jupyter/nbsphinx required.
# sphinx-gallery executes each one at doc-build time, capturing every
# matplotlib figure and stdout print, and builds three artifacts per script:
# the rendered HTML page, a downloadable .py, and a downloadable .ipynb --
# with the gallery thumbnail taken from one of the actual generated figures
# (by default, the first one; see `sphinx_gallery_thumbnail_number` in a
# script to pick a different one).
sphinx_gallery_conf = {
    'examples_dirs': '../tutorials',
    'gallery_dirs': 'tutorials',
    # Matches "01_mooring_dataset.py", "02_gridded_model.py", etc. -- the
    # default pattern (r'/plot') is scikit-learn/matplotlib's own convention
    # and wouldn't match our numbered filenames.
    'filename_pattern': r'/\d+_.*\.py$',
    'download_all_examples': False,
    'remove_config_comments': True,
    # The CLI tutorials ship their own real data.cfg/metazones.cfg next to
    # the script (displayed inline with `.. literalinclude::`, same as
    # doc/examples/) -- copy them into the built gallery page's own
    # directory too, so the :download: links there work.
    'copyfile_regex': r'.*\.cfg$',
}

# %% Options for LATEXPDF output---------------------------------------------

latex_toplevel_sectioning = 'section'

latex_engine = 'pdflatex'
#latex_elements = {
#  'preamble': r'''\usepackage{lscape}'''
#}
latex_elements = {
    'preamble': r'''
\counterwithout{section}{chapter}
\usepackage{lscape}
\usepackage[titles]{tocloft}
\setcounter{tocdepth}{3}
\cftsetpnumwidth {1.25cm}\cftsetrmarg{1.5cm}
\setlength{\cftchapnumwidth}{0.75cm}
\setlength{\cftsecindent}{\cftchapnumwidth}
\setlength{\cftsecnumwidth}{1.25cm}
''',
    'fncychap': r'\usepackage[Bjornstrup]{fncychap}',
    'printindex': r'\footnotesize\raggedright\printindex',
}
latex_show_urls = 'footnote'
# %% Intersphinx
intersphinx_mapping = {
    'matplotlib': ('https://matplotlib.org/stable/', None),
    'pandas': ('https://pandas.pydata.org/docs/', None),
    }
# 'xarray': ('https://xarray.pydata.org', None),
# 'xoa': ('https://xoa.readthedocs.io/', None),
# 'cmocean': ('https://matplotlib.org/cmocean/', None),
# 'configobj': ('https://configobj.readthedocs.io', None)


# %% Napoleon
napoleon_use_admonition_for_examples = True
napoleon_use_admonition_for_notes = True
napoleon_use_admonition_for_references = True
napoleon_use_rtype = True

def setup(app):
    app.add_css_file('custom.css')

