"""
Comparing a model against a hydrological section (``armoor-comp-hydrosection``)
======================================================================================

``armoor-comp-hydrosection`` compares a 3D model against a towed/glider
hydrological section -- a single mission file holding several profiles at
their own ``(time, lon, lat)``, tracing an irregular path rather than a
fixed grid or point. Unlike every other ``armoor-comp-*`` type, nothing
about the colocation strategy is user-configurable: the model is always
matched nearest-in-time to each reference profile, tracks the reference's
own ``(lon, lat)`` path (``horizontal=track``), and is vertically
interpolated onto the reference's own per-profile depth levels -- the
same rationale as ``armoor-comp-mooring``/``-drifter`` forcing their own
strategies. ``armoor-comp-hydrosection`` supports a single output type,
``otype=sections``.

This tutorial ships a real ``comp_hydrosection.cfg`` alongside it and runs
the real ``armoor-comp-hydrosection`` command against a real glider mission sample
(``GL_PR_GL_8901067_20240816.nc``, 6 profiles off the UK coast) and a
small synthetic gridded model built to share its domain/time window -- the
same fixture armoor's own ``test_comp_hydrosection.py`` uses, with one
change: a proper thermocline (rather than a flat, noisy profile) so the
model's own mixed-layer depth is well-defined and comparable to the
glider's.
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
GLIDER_SAMPLE = SAMPLES_DIR + "/GL_PR_GL_8901067_20240816.nc"


def show_png(path):
    """Display a PNG file armoor wrote to disk as a matplotlib figure, so
    sphinx-gallery captures it (and can use it as the page's thumbnail)."""
    img = plt.imread(path)
    _, ax = plt.subplots(figsize=(9, 9))
    ax.imshow(img)
    ax.axis("off")

# %%
# Building the synthetic model
# --------------------------------
#
# armoor's own sample data doesn't ship a real gridded model covering this
# glider's own domain (56.4-56.8N, 1.3-0.9W, 2024-08-15/17), so this
# tutorial builds a small synthetic ``(time, depth, lat, lon)`` product
# instead -- a logistic thermocline (~16.5C at the surface, ~11C below
# ~20m) plus a little noise, so ``otype=sections``' mixed-layer-depth
# panel has real structure to show, not a flat/undefined profile.

workdir = tempfile.mkdtemp()

lon = np.linspace(-1.3, -0.9, 6).astype("float32")
lat = np.linspace(56.4, 56.8, 6).astype("float32")
depth = np.array([0.5, 5., 10., 20., 40., 60., 100.], dtype="float32")
time = pd.date_range("2024-08-15", "2024-08-17", freq="6h")

rng = np.random.default_rng(1)
surface_temp, deep_temp, mld_center, thickness = 16.5, 11.0, 18.0, 4.0
profile = deep_temp + (surface_temp - deep_temp) / (1 + np.exp((depth - mld_center) / thickness))
thetao = (
    profile[None, :, None, None]
    + rng.normal(0, 0.15, size=(len(time), len(depth), len(lat), len(lon)))
).astype("float32")
so = (35 + rng.normal(0, 0.2, size=(len(time), len(depth), len(lat), len(lon)))).astype("float32")


def make(varname, data):
    return xr.Dataset(
        {varname: (("time", "depth", "latitude", "longitude"), data)},
        coords={"time": time, "depth": depth, "latitude": lat, "longitude": lon},
    )


make("thetao", thetao).to_netcdf(os.path.join(workdir, "synth_model_temp.nc"))
make("so", so).to_netcdf(os.path.join(workdir, "synth_model_sal.nc"))
print(sorted(os.listdir(workdir)))

# %%
# The configuration files
# ---------------------------
#
# ``data.cfg`` has two sources: ``model`` (the synthetic gridded product)
# and ``glider`` (``fmt=cmems_insitu``, ``platform=glider``, ``ref=True``).
#
# .. literalinclude:: 10_comp_hydrosection_data.cfg
#    :language: ini
#    :caption: comp_hydrosection.cfg
#    :linenos:
#
# :download:`Download comp_hydrosection.cfg <10_comp_hydrosection_data.cfg>`
#
# ``metazones.cfg`` needs no ``[[trange_seq]]``/``[[vlevel]]``/
# ``[[vrange]]`` blocks at all -- the polygon and ``tbound`` are the only
# real settings, since time/horizontal/vertical colocation are all forced.
#
# .. literalinclude:: 10_comp_hydrosection_metazones.cfg
#    :language: ini
#    :caption: metazones.cfg
#    :linenos:
#
# :download:`Download metazones.cfg <10_comp_hydrosection_metazones.cfg>`

CONFIG_DIR = os.getcwd()

for src_name, dest_name in [
    ("10_comp_hydrosection_data.cfg", "comp_hydrosection.cfg"),
    ("10_comp_hydrosection_metazones.cfg", "metazones.cfg"),
]:
    text = open(os.path.join(CONFIG_DIR, src_name)).read()
    text = text.replace("{{WORKDIR}}", workdir).replace("{{GLIDER_SAMPLE}}", GLIDER_SAMPLE)
    with open(os.path.join(workdir, dest_name), "w") as f:
        f.write(text)

print(sorted(os.listdir(workdir)))

# %%
# Running ``armoor-comp-hydrosection``
# ------------------------------------------
#
# The command line is just ``armoor-comp-hydrosection <metazone(s)>
# <cfgfile> [--cgeo-ref ...]`` -- ``--cgeo-ref`` sets the reference
# pressure (in dbar) for the geostrophic-velocity diagnostic (``cgeo``,
# one of the comparison variables below); left at its default here.

subprocess.run(
    ["armoor-comp-hydrosection", "hydro", "comp_hydrosection.cfg",
     "--jsonfile", "ncs.json"],
    cwd=workdir,
    check=True,
)

# %%
# Looking at the scores
# -------------------------
#
# ``CompHydrosection`` scores 7 variables, split into 3 non-colliding
# groups by their own dimension signature: the depth-resolved group
# (``ptemp``/``sal``/``pdens``/``temp``/``sndspeed``, dims ``time, z``),
# the depth-less ``mld`` (dims ``time`` only), and ``cgeo`` (geostrophic
# velocity, dims ``pair, z`` -- one value per pair of consecutive
# profiles, not per profile).

dt = xr.open_datatree(
    os.path.join(workdir, "comp_hydrosection/output/hydro/glider mission/sections/None/all.zarr")
)
ref_data = dt["synthmodel"]["ref"]["data"]
print({c: sorted(ref_data[c].to_dataset().data_vars) for c in ref_data.children})

# %%
# The figures
# ---------------
#
# One PNG per variable, listed in ``ncs.json``: a ``pcolormesh`` section
# (model / reference / difference) for the depth-resolved variables, and a
# line plot for ``mld``/``cgeo``.

with open(os.path.join(workdir, "ncs.json")) as f:
    png_paths = json.load(f)

print(png_paths)

# %%
# Depth-resolved section (``ptemp``)
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

ptemp_png = next(p for p in png_paths if "sections_ptemp_" in p)
show_png(ptemp_png)

# %%
# Mixed layer depth (``mld``)
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

mld_png = next(p for p in png_paths if "sections_mld_" in p)
show_png(mld_png)

# %%
# Geostrophic velocity (``cgeo``)
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
#
# One value per pair of consecutive profiles (5 pairs from the glider's 6
# profiles), not per profile.

cgeo_png = next(p for p in png_paths if "sections_cgeo_" in p)
show_png(cgeo_png)

# %%
# Next steps
# ----------
#
# - This was the last comparison type in this series -- see :ref:`examples`
#   for more ready-to-run configuration files, and ``armoor-comp-*
#   --help`` for the full CLI reference of each.
# - Full config schema: ``armoor/cli/comp.ini`` and
#   ``armoor/cli/metazones.ini``
# - :ref:`howtostart` with the command-line executables
