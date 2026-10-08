"""
Comparing a model against a climatology (``armoor-comp-clim``)
=====================================================================

``armoor-comp-clim`` compares a model against an observed hydrological
climatology (e.g. WOA18) instead of individual observations -- both sides
get matched on **calendar month** rather than real dates: the model is
grouped by ``time.month`` and averaged, then aligned with the
climatology's own month index (1-12). This "tmonth" time strategy is
always on for ``comp_clim`` (there is no ``[[trange_seq]]``/``tfreq`` to
configure), the same way ``armoor-comp-mooring``/``-drifter`` force their
own vertical/horizontal strategies -- see :ref:`examples` for the full
list of what's user-configurable per comparison type.

Horizontal colocation uses ``href`` (regrid the model onto the
climatology's grid) like :doc:`05_comp_sst`, so ``otype=maps`` renders a
proper ``pcolormesh`` rather than scattered points. ``armoor-comp-clim``
supports 2 output types: ``timeseries`` and ``maps``.

This tutorial ships a real ``comp_clim.cfg`` alongside it and runs the real
``armoor-comp-clim`` command against the real WOA18 ``decav`` climatology
samples (``woa18_decav_[t,s]0[5,6,7]_01.nc`` -- May/June/July, temperature
and salinity) and the same CMEMS GLO12 model sample as the other
tutorials, which covers June 15 to July 8: 2 of the 3 available
climatology months overlap.
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
# The configuration files
# ---------------------------
#
# ``data.cfg`` has two sources: ``woa18`` (``fmt=woa18``, ``ref=True``, a
# glob matching all three ``decav`` files at once) and ``glo12`` (the
# model).
#
# .. literalinclude:: 09_comp_clim_data.cfg
#    :language: ini
#    :caption: comp_clim.cfg
#    :linenos:
#
# :download:`Download comp_clim.cfg <09_comp_clim_data.cfg>`
#
# ``metazones.cfg`` sets ``href=reference`` and a single ``[[vlevel]]`` --
# same idiom as the :doc:`08_comp_models` ``modelzone_href`` metazone, no
# ``[[trange_seq]]`` needed here since time colocation is forced.
#
# .. literalinclude:: 09_comp_clim_metazones.cfg
#    :language: ini
#    :caption: metazones.cfg
#    :linenos:
#
# :download:`Download metazones.cfg <09_comp_clim_metazones.cfg>`

workdir = tempfile.mkdtemp()
CONFIG_DIR = os.getcwd()

for src_name, dest_name in [
    ("09_comp_clim_data.cfg", "comp_clim.cfg"),
    ("09_comp_clim_metazones.cfg", "metazones.cfg"),
]:
    text = open(os.path.join(CONFIG_DIR, src_name)).read()
    with open(os.path.join(workdir, dest_name), "w") as f:
        f.write(text.replace("{{SAMPLES_DIR}}", SAMPLES_DIR))

print(sorted(os.listdir(workdir)))

# %%
# Running ``armoor-comp-clim``
# ----------------------------------
#
# The command line is just ``armoor-comp-clim <metazone(s)> <cfgfile>
# [--tbound ...]`` -- no ``radius``/``period`` positional, same shape as
# ``armoor-comp-sst``/``-models``.

subprocess.run(
    ["armoor-comp-clim", "climzone", "comp_clim.cfg", "--jsonfile", "ncs.json"],
    cwd=workdir,
    check=True,
)

# %%
# Looking at the scores
# -------------------------
#
# ``CompClim`` scores both ``ptemp`` and ``sal``. The ``time`` coordinate
# here is the calendar month index (6, 7), not a real date -- the two
# overlapping months between the GLO12 sample and the WOA18 climatology.

dt = xr.open_datatree(
    os.path.join(workdir, "comp_clim/output/climzone/woa18clim/timeseries/10.0/all.zarr")
)
print(dt["glo12"]["ref"]["data"].to_dataset()["time"])

# %%
print(dt["glo12"]["comp"]["bias"].to_dataset())

# %%
# The figures
# ---------------

with open(os.path.join(workdir, "ncs.json")) as f:
    png_paths = json.load(f)

print(png_paths)

# %%
# Timeseries
# ~~~~~~~~~~~~~
#
# One stats PNG per variable (``ptemp``, ``sal``), month 6 to month 7 on
# the x-axis instead of a real date range.

stats_png = next(p for p in png_paths if "timeseries_stats_ptemp_" in p)
show_png(stats_png)

# %%
# Maps
# ~~~~~~
#
# One bias/rmse/rmsec map per variable, averaged over the two overlapping
# months -- WOA18 reads noticeably colder than GLO12 here, which is
# expected: it's a multi-decadal, heavily smoothed average, not a
# same-year snapshot.

map_png = next(p for p in png_paths if "map_ptemp_bias_" in p)
show_png(map_png)

# %%
map_png = next(p for p in png_paths if "map_sal_bias_" in p)
show_png(map_png)

# %%
# Next steps
# ----------
#
# - :doc:`10_comp_hydrosection` (``armoor-comp-hydrosection``) matches a
#   glider mission's own irregular (time, lon, lat, depth) path instead of
#   a fixed grid or point.
# - Full config schema: ``armoor/cli/comp.ini`` and
#   ``armoor/cli/metazones.ini``
# - :ref:`howtostart` with the command-line executables
