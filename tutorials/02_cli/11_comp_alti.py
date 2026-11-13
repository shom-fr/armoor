"""
Comparing a model against altimetry (``armoor-comp-alti``)
=================================================================

``armoor-comp-alti`` compares the model sea surface height (and the
kinetic energies derived from it) with a gridded L4 altimetry product
(``fmt=cmems_alti_duacs``). Like :doc:`05_comp_sst`, the reference is
gridded, so horizontal colocation uses ``href`` (the model is regridded
onto the DUACS grid) rather than a ``radius``.

The compared variables are ``ssh`` (model ``zos`` vs. DUACS ``adt``),
``sla`` (anomaly of ``ssh`` over the colocated window), ``ke_geos`` and
``eke`` (from geostrophic currents) and ``mke_geos`` (mean kinetic energy
of the time-averaged geostrophic current). Geostrophic currents are
recomputed the same way on both sides with ``shoot.dyn.get_geos``:
DUACS ``sla``/``ugos``/``vgos`` are ignored, and ``ke``/``mke`` (total
current) are dropped since altimetry has no total current.

To keep this tutorial light, it runs on the tiny DUACS extract shipped with
armoor's test suite (``cmems_duacs_l4.nc``, 3 days) against a
small synthetic model product generated on the fly -- a few seconds of
run, no network access or CMEMS credentials needed.
"""

import json
import os
import subprocess
import tempfile

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
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
# A small synthetic model
# ---------------------------
#
# The DUACS sample covers lon 48.38/49.12E, lat 12.12/12.88N, from
# 2024-01-01 to 2024-01-03. We write a 12x13 surface model product slightly
# larger than that, every 6 hours, with the CMEMS model variable names
# (``zos``, ``uo``, ``vo``) so that ``fmt=cmems_model`` decodes it. Its sea
# level mimics the DUACS ``adt`` (about 0.62 to 0.80 m, rising eastward),
# with a slightly weaker gradient, a small daily drift and some noise.

workdir = tempfile.mkdtemp()

lon = np.linspace(48.2, 49.3, 12).astype("float32")
lat = np.linspace(11.9, 13.1, 13).astype("float32")
time = pd.date_range("2024-01-01", "2024-01-03", freq="6h")
shape = (len(time), len(lat), len(lon))

rng = np.random.default_rng(0)
xx, yy = np.meshgrid(lon, lat)
days = np.arange(len(time))[:, None, None] / 4.0
zos = (
    0.63
    + 0.18 * (xx - 48.38)[None]
    + 0.01 * days
    + rng.normal(0, 0.01, shape)
)

dims = ("time", "latitude", "longitude")
model = xr.Dataset(
    {
        "zos": (dims, zos.astype("float32"), {"units": "m"}),
        "uo": (dims, rng.normal(0.1, 0.05, shape).astype("float32"), {"units": "m/s"}),
        "vo": (dims, rng.normal(0.0, 0.05, shape).astype("float32"), {"units": "m/s"}),
    },
    coords={"time": time, "latitude": lat, "longitude": lon},
)
model.to_netcdf(os.path.join(workdir, "synth_model_ssh.nc"))
print(model)

# %%
# The two configuration files
# -------------------------------
#
# ``data.cfg`` has two sources: ``duacs`` (``fmt=cmems_alti_duacs``,
# ``ref=True``) and the synthetic ``model``. The four output types
# supported by ``armoor-comp-alti`` are requested.
#
# .. literalinclude:: 11_comp_alti_data.cfg
#    :language: ini
#    :caption: comp_alti.cfg
#    :linenos:
#
# :download:`Download comp_alti.cfg <11_comp_alti_data.cfg>`
#
# ``metazones.cfg`` sets ``href=reference`` (regrid the model onto the
# DUACS grid) and ``tfreq=1d`` (one colocation per day); the polygon is
# tightened to the DUACS sample footprint.
#
# .. literalinclude:: 11_comp_alti_metazones.cfg
#    :language: ini
#    :caption: metazones.cfg
#    :linenos:
#
# :download:`Download metazones.cfg <11_comp_alti_metazones.cfg>`

CONFIG_DIR = os.getcwd()

for src_name, dest_name in [
    ("11_comp_alti_data.cfg", "comp_alti.cfg"),
    ("11_comp_alti_metazones.cfg", "metazones.cfg"),
]:
    text = open(os.path.join(CONFIG_DIR, src_name)).read()
    text = text.replace("{{SAMPLES_DIR}}", SAMPLES_DIR).replace("{{WORKDIR}}", workdir)
    with open(os.path.join(workdir, dest_name), "w") as f:
        f.write(text)

print(sorted(os.listdir(workdir)))

# %%
# Running ``armoor-comp-alti``
# --------------------------------
#
# The command line is ``armoor-comp-alti <metazone(s)> <cfgfile>
# [--tbound START END]``. ``--tbound`` overrides the metazone ``tbound``
# for this run only; it is not needed here.

subprocess.run(["armoor-comp-alti", "altizone", "comp_alti.cfg"], cwd=workdir, check=True)

# %%
# Daily and whole-window colocations
# --------------------------------------
#
# Colocation writes one file per day for each side, plus one *period* file
# per side holding ``mke_geos``: it is computed from the current averaged
# over the whole window, so it carries a size-1 ``period`` dimension
# instead of ``time``.

coloc_dir = os.path.join(workdir, "comp_alti/coloc/altizone/duacs/synthmodel")
print(sorted(os.listdir(coloc_dir)))

# %%
# Looking at the scores
# -------------------------
#
# The ``timeseries`` output holds the daily bias/RMSE of the
# time-dependent variables (``ssh``, ``sla``, ``ke_geos``, ``eke``).

dt = xr.open_datatree(
    os.path.join(workdir, "comp_alti/output/altizone/duacs/timeseries/None/all.zarr")
)
print(dt["synthmodel"]["comp"]["bias"].to_dataset())

# %%
# All the rendered PNGs are listed in ``ncs_comp_alti.json``: one stats
# figure per variable, one map and one dispersion scatter per day and
# variable, the ``mke_geos`` period map, and one global dispersion scatter
# per variable (``mke_geos`` included).

with open(os.path.join(workdir, "ncs_comp_alti.json")) as f:
    png_paths = json.load(f)

for path in sorted(png_paths):
    print(os.path.basename(path))

# %%
show_png(next(p for p in png_paths if p.endswith("timeseries_stats_sla.png")))

# %%
# Maps
# --------
#
# ``otype=maps`` renders the model, the reference and their difference on
# the DUACS grid -- here the first day's ``ssh``, then the whole-window
# ``mke_geos``.

show_png(sorted(p for p in png_paths if "map_ssh_" in p)[0])

# %%
show_png(next(p for p in png_paths if "map_mke_geos_" in p))

# %%
# Global dispersion (``diagdisp_glob``)
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
#
# A single model vs. altimetry scatter pooling every colocated pixel of the
# period, with a linear fit -- one PNG per variable.

show_png(next(p for p in png_paths if "diagdisp_glob_ssh_" in p))

# %%
# Next steps
# ----------
#
# - :doc:`/cli.meta.comp.alti` for the full reference of
#   ``armoor-comp-alti`` (scope, pipeline control, HPC options).
# - On real data, point ``data.cfg`` to a DUACS L4 file and to your model
#   ``ssh`` outputs (see the altimetry card in :ref:`examples`), and widen
#   ``tbound``: ``sla`` and ``mke_geos`` are only meaningful over a window
#   much longer than the three days used here.
# - Full config schema: ``armoor/cli/comp.ini`` and
#   ``armoor/cli/metazones.ini``
