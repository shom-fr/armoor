"""
Comparing a model against satellite SST (``armoor-comp-sst``)
====================================================================

``armoor-comp-sst`` follows the same ``data.cfg``/``metazones.cfg`` idiom
as :doc:`04_comp_config`, but the reference is a *gridded* satellite
product (``fmt=cmems_sst_l3``/``cmems_sst_l4``/``cersat_sst_l3``) instead
of scattered profiles -- so horizontal colocation uses ``href`` (regrid
one side onto the other's grid) rather than ``radius`` (disk of nearby
points): no ``member``/cloud dimension, and the model side is compared
point-for-point against the satellite grid.

This tutorial ships a real ``comp_sst.cfg`` alongside it and runs the real
``armoor-comp-sst`` command on the same CMEMS GLO12 model sample as the
other tutorials, plus a real Odyssea/OSI-SAF-style L3 SST extract
(``cmems_sst_l3.nc``) -- both shipped with armoor's own test suite, no
network access or CMEMS credentials needed.
"""

import json
import os
import subprocess
import tempfile

import matplotlib.pyplot as plt
import xarray as xr

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
# The two configuration files
# -------------------------------
#
# ``data.cfg`` has two sources: ``glo12`` (the model, same sample as
# before) and ``sstobs`` (``fmt=cmems_sst_l3``, ``ref=True``) -- the GLO12
# extract's domain (45-49N, 14-7W, 2026-06-15/07-08) fully covers the SST
# sample's own domain (45.05-45.95N, 13.95-13.05W, 2026-07-03/08), so no
# synthetic data is needed here, unlike the :doc:`/tutorials/01_library/02_gridded_model`
# tutorial.
#
# .. literalinclude:: 05_comp_sst_data.cfg
#    :language: ini
#    :caption: comp_sst.cfg
#    :linenos:
#
# :download:`Download comp_sst.cfg <05_comp_sst_data.cfg>`
#
# ``metazones.cfg`` sets ``href=reference`` (regrid the model onto the
# satellite's grid) and ``tfreq=1d`` (one colocation per day); the polygon
# is tightened to the SST sample's own footprint so the comparison stays
# on the region both sources actually cover.
#
# .. literalinclude:: 05_comp_sst_metazones.cfg
#    :language: ini
#    :caption: metazones.cfg
#    :linenos:
#
# :download:`Download metazones.cfg <05_comp_sst_metazones.cfg>`

workdir = tempfile.mkdtemp()
CONFIG_DIR = os.getcwd()

for src_name, dest_name in [
    ("05_comp_sst_data.cfg", "comp_sst.cfg"),
    ("05_comp_sst_metazones.cfg", "metazones.cfg"),
]:
    text = open(os.path.join(CONFIG_DIR, src_name)).read()
    with open(os.path.join(workdir, dest_name), "w") as f:
        f.write(text.replace("{{SAMPLES_DIR}}", SAMPLES_DIR))

print(sorted(os.listdir(workdir)))

# %%
# Running ``armoor-comp-sst``
# --------------------------------
#
# The command line is just ``armoor-comp-sst <metazone(s)> <cfgfile>
# [--qc ...] [--tbound ...]`` -- no ``radius`` positional (that's
# argo-specific): with ``href`` colocation there's no cloud of nearby
# points to pick a radius for. ``--qc`` filters satellite pixels by
# quality flag (not used here, to keep the sample's own points).

subprocess.run(["armoor-comp-sst", "sstzone", "comp_sst.cfg"], cwd=workdir, check=True)

# %%
# Looking at the scores
# -------------------------
#
# ``CompSst`` only scores ``ptemp`` (SST is a single surface variable, no
# vertical dimension) -- ``ref``/``data`` holds the satellite values
# regridded onto the comparison grid, ``comp``/``bias`` the model's bias
# against them.

dt = xr.open_datatree(
    os.path.join(workdir, "comp_sst/output/sstzone/sstobs/timeseries/None/all.zarr")
)
print(dt["glo12"]["ref"]["data"].to_dataset())

# %%
print(dt["glo12"]["comp"]["bias"].to_dataset())

# %%
# ``armoor-comp-sst`` also rendered a stats PNG
# (``timeseries_stats_ptemp.png``), a map per day
# (``map_ptemp_diff_<prod>_<day>.png``), and global/per-day dispersion
# scatters (``diagdisp_glob_ptemp_<prod>.png``,
# ``diagdisp_sel_ptemp_<prod>_<day>.png``) -- all listed in
# ``ncs_comp_sst.json``. Unlike Argo's single-profile-per-interval issue,
# SST is a gridded product with many pixels per day, so ``diagdisp_sel``
# already has enough points per day for a meaningful regression, no
# ``tfreq`` adjustment needed.

with open(os.path.join(workdir, "ncs_comp_sst.json")) as f:
    png_paths = json.load(f)

stats_png = next(p for p in png_paths if "timeseries_stats" in p)
show_png(stats_png)

# %%
# Looking at the maps
# -----------------------
#
# Unlike the :doc:`04_comp_config` tutorial's scattered profile locations,
# ``href`` colocation puts the model on the satellite's own regular grid,
# so ``otype=maps`` renders a proper ``pcolormesh`` for each side and their
# difference -- one map per day here (``tfreq=1d``).

map_pngs = sorted(p for p in png_paths if "map_ptemp_diff_" in p)
print(f"{len(map_pngs)} map(s) rendered (one per day)")
show_png(map_pngs[0])

# %%
# Global dispersion (``diagdisp_glob``)
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
#
# A single scatter of every colocated pixel over the whole period, model
# vs. satellite, with a linear fit and R\\ :sup:`2` -- one PNG per
# variable, pooling all days together.

diagdisp_glob_png = next(p for p in png_paths if "diagdisp_glob_ptemp_" in p)
show_png(diagdisp_glob_png)

# %%
# Per-day dispersion (``diagdisp_sel``)
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
#
# The same scatter/regression as ``diagdisp_glob``, but one PNG per day
# instead of pooling them.

diagdisp_sel_pngs = sorted(p for p in png_paths if "diagdisp_sel_ptemp_" in p)
show_png(diagdisp_sel_pngs[0])

# %%
# Next steps
# ----------
#
# - :doc:`06_comp_drifter` (``armoor-comp-drifter``) uses OceanParcels
#   particle-tracking instead of point-matching.
# - ``armoor-comp-mooring``/``-models``/``-clim``/``-hydrosection`` follow
#   the same ``data.cfg``/``metazones.cfg``/``ref=True`` pattern, each with
#   their own comparison-specific CLI flags -- see ``armoor-comp-* --help``
#   and :ref:`examples`.
# - Full config schema: ``armoor/cli/comp.ini`` and
#   ``armoor/cli/metazones.ini``
# - :ref:`howtostart` with the command-line executables
