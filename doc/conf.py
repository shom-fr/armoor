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
# import os
# import sys
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
    "IPython.sphinxext.ipython_directive",
    "IPython.sphinxext.ipython_console_highlighting",
    'nbsphinx',
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
exclude_patterns = ['_build', 'Thumbs.db', '.DS_Store']


# %% Options for HTML output -------------------------------------------------

# The theme to use for HTML and HTML Help pages.  See the documentation for
# a list of builtin themes.
#
html_theme = 'sphinx_book_theme'

# Add any paths that contain custom static files (such as style sheets) here,
# relative to this directory. They are copied after the builtin static files,
# so a file named "default.css" will overwrite the builtin "default.css".
html_static_path = ['_static']

html_theme_options = {
    "logo": {
        "image_light": "images/armoor.png",
        "image_dark": "images/armoor.png",
    },
    "repository_url": "https://gitlab.com/GitShom/STM/armoor",
    "repository_branch": "develop",
    "use_repository_button": True,
    "use_issues_button": True,
    "use_source_button": True,
    "path_to_docs": "doc/",
}

# %% Autosumarry
autosummary_generate = True

# The master toctree document.
master_doc ='index'

sphinx_gallery_conf = {
    'examples_dirs': '../examples/configs',
    'gallery_dirs': 'auto_examples/configs',
    'filename_pattern': '/*.cfg',
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
# intersphinx_mapping = {
#     'xarray': ('https://xarray.pydata.org', None),
#     'xoa': ('https://xoa.readthedocs.io/', None),
#     'cmocean': ('https://matplotlib.org/cmocean/', None),
#     'configobj': ('https://configobj.readthedocs.io', None)
#     }


# %% Napoleon
napoleon_use_admonition_for_examples = True
napoleon_use_admonition_for_notes = True
napoleon_use_admonition_for_references = True
napoleon_use_rtype = True

def setup(app):
    app.add_css_file('custom.css')

