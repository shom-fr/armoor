"""
Comparing a model against moorings (``armoor-comp-mooring``)
===================================================================

``armoor-comp-mooring`` compares the model against fixed-point
hydrological mooring time series -- like :doc:`04_comp_config`, it uses
``radius``-based horizontal colocation (a disk of nearby model points),
but the reference is stationary instead of a drifting profile. It
supports a single output type, ``otype=timeseries``.

One thing worth calling out: a ``data.cfg`` source can match *several*
real moorings at once (a glob pattern), and armoor splits the output per
station automatically -- each mooring gets its own ``<ref_name>``
subdirectory in the output tree, named after the station.

This tutorial ships a real ``comp_mooring.cfg`` alongside it and runs the
real ``armoor-comp-mooring`` command on the same CMEMS GLO12 model sample as
before, plus two real mooring station samples (``GL_TS_MO_6200163_*.nc``
and ``NO_TS_MO_6200029_*.nc``) -- all shipped with armoor's own test
suite, no network access or CMEMS credentials needed.
"""

import json
import os
import subprocess
import tempfile

import matplotlib.pyplot as plt

from armoor import ROOTDIR

SAMPLES_DIR = ROOTDIR + "/_samples"


def show_png(path):
    """Display a PNG file armoor wrote to disk as a matplotlib figure, so
    sphinx-gallery captures it (and can use it as the page's thumbnail)."""
    img = plt.imread(path)
    _, ax = plt.subplots(figsize=(9, 9))
    ax.imshow(img)
    ax.axis("off")

# %%
# The configuration files
# ---------------------------
#
# ``data.cfg`` has two sources: ``glo12`` (the model) and ``mooring``
# (``fmt=cmems_insitu``, ``platform=mooring``, ``ref=True``) -- the
# ``*_TS_MO_*.nc`` glob matches both real station samples at once.
#
# .. literalinclude:: 07_comp_mooring_data.cfg
#    :language: ini
#    :caption: comp_mooring.cfg
#    :linenos:
#
# :download:`Download comp_mooring.cfg <07_comp_mooring_data.cfg>`
#
# ``metazones.cfg`` is the same ``[[trange_seq]]`` idiom as the Argo
# tutorial.
#
# .. literalinclude:: 07_comp_mooring_metazones.cfg
#    :language: ini
#    :caption: metazones.cfg
#    :linenos:
#
# :download:`Download metazones.cfg <07_comp_mooring_metazones.cfg>`

workdir = tempfile.mkdtemp()
CONFIG_DIR = os.getcwd()

for src_name, dest_name in [
    ("07_comp_mooring_data.cfg", "comp_mooring.cfg"),
    ("07_comp_mooring_metazones.cfg", "metazones.cfg"),
]:
    text = open(os.path.join(CONFIG_DIR, src_name)).read()
    with open(os.path.join(workdir, dest_name), "w") as f:
        f.write(text.replace("{{SAMPLES_DIR}}", SAMPLES_DIR))

print(sorted(os.listdir(workdir)))

# %%
# Running ``armoor-comp-mooring``
# ------------------------------------
#
# The command line is ``armoor-comp-mooring <metazone(s)> <cfgfile>
# <radius> [--qc ...]``, same shape as ``armoor-comp-argo``.

subprocess.run(
    ["armoor-comp-mooring", "moorzone", "comp_mooring.cfg", "20.0"],
    cwd=workdir,
    check=True,
)

# %%
# Looking at the figures
# ---------------------------
#
# Two stats PNGs come out -- one per station, ``mooring_<station_id>`` --
# listed in ``ncs_comp_mooring.json``.

with open(os.path.join(workdir, "ncs_comp_mooring.json")) as f:
    png_paths = json.load(f)

print(png_paths)

# %%
show_png(png_paths[0])

# %%
show_png(png_paths[1])

# %%
# Next steps
# ----------
#
# - :doc:`08_comp_models` (``armoor-comp-models``) drops the observation
#   entirely -- both sides are models, colocated ``href``-to-grid instead
#   of at point locations.
# - ``armoor-comp-clim``/``-hydrosection`` follow the same
#   ``data.cfg``/``metazones.cfg``/``ref=True`` pattern, each with their
#   own comparison-specific CLI flags -- see ``armoor-comp-* --help`` and
#   :ref:`examples`.
# - Full config schema: ``armoor/cli/comp.ini`` and
#   ``armoor/cli/metazones.ini``
# - :ref:`howtostart` with the command-line executables
