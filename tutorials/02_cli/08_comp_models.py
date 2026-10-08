"""
Comparing two models against each other (``armoor-comp-models``)
=======================================================================

``armoor-comp-models`` compares one *reference* model against another
*product* model -- no real-world observations involved. armoor's own
sample data doesn't ship two real model sources covering the same
domain/period (the real HYCOM sample is a 3x3 extract near the equator, in
2024 -- nowhere near the GLO12 sample's Bay-of-Biscay domain in 2026), so
this tutorial builds a synthetic *second* model by perturbing a copy of
the real GLO12 sample (same grid, same dates, a deterministic offset) --
the same trick armoor's own ``test_comp_sst.py`` uses for exactly this
situation.

``armoor-comp-models`` has the same 8 output types as
:doc:`04_comp_config`, split the same way: ``maps``/``timeseries``/
``diagdisp_glob``/``diagdisp_sel``/``mdiagts`` need a single fixed depth
(``[[vlevel]]``); ``mvprofiles``/``uvprofiles``/``udiagts`` need a
depth-binned profile (``[[vrange]]``) at a specific point (``cloud``)
rather than a full grid (``href``). Two metazones, two CLI calls, same
idiom as the Argo tutorial.
"""

import json
import os
import subprocess
import tempfile

import matplotlib.pyplot as plt
import numpy as np
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
# Building the second "model"
# --------------------------------
#
# ``model2`` is ``glo12``'s own ``thetao``/``so`` fields, scaled and offset
# by a small deterministic amount (plus a little noise) -- same grid, same
# dates, same CF attributes, so it decodes with ``fmt=cmems_model`` exactly
# like the original.

workdir = tempfile.mkdtemp()

ds_temp = xr.open_dataset(f"{SAMPLES_DIR}/cmems_glo12_temp.nc")
ds_sal = xr.open_dataset(f"{SAMPLES_DIR}/cmems_glo12_sal.nc")

rng = np.random.default_rng(7)
thetao2 = ds_temp["thetao"] * 1.02 + 0.4 - 0.0005 * ds_temp["depth"]
thetao2 = thetao2 + rng.normal(0, 0.05, size=thetao2.shape).astype("float32")
thetao2.attrs = ds_temp["thetao"].attrs
so2 = ds_sal["so"] * 0.995 + 0.1
so2.attrs = ds_sal["so"].attrs

ds_temp2 = ds_temp.copy()
ds_temp2["thetao"] = thetao2
ds_sal2 = ds_sal.copy()
ds_sal2["so"] = so2

ds_temp2.to_netcdf(os.path.join(workdir, "model2_temp.nc"))
ds_sal2.to_netcdf(os.path.join(workdir, "model2_sal.nc"))
print(sorted(os.listdir(workdir)))

# %%
# The configuration files
# ---------------------------
#
# Same ``[data]`` section for both cfg files -- ``glo12`` (``ref=True``)
# and ``model2`` -- only ``[outputs]`` differs.
#
# .. literalinclude:: 08_comp_models_href.cfg
#    :language: ini
#    :caption: comp_models_href.cfg
#    :linenos:
#
# :download:`Download comp_models_href.cfg <08_comp_models_href.cfg>`
#
# .. literalinclude:: 08_comp_models_cloud.cfg
#    :language: ini
#    :caption: comp_models_cloud.cfg
#    :linenos:
#
# :download:`Download comp_models_cloud.cfg <08_comp_models_cloud.cfg>`
#
# ``metazones.cfg`` defines both metazones: ``modelzone_href``
# (``href=reference``, ``[[vlevel]]``) and ``modelzone_cloud`` (a single
# ``cloud`` point, ``[[vrange]]``). ``armoor-comp-models``'s ``maps``
# specifically needs ``[[trange_seq]]`` (not a bare ``tfreq=``) -- it
# flags the bare form as conflicting.
#
# .. literalinclude:: 08_comp_models_metazones.cfg
#    :language: ini
#    :caption: metazones.cfg
#    :linenos:
#
# :download:`Download metazones.cfg <08_comp_models_metazones.cfg>`

CONFIG_DIR = os.getcwd()

for src_name, dest_name in [
    ("08_comp_models_href.cfg", "comp_models_href.cfg"),
    ("08_comp_models_cloud.cfg", "comp_models_cloud.cfg"),
    ("08_comp_models_metazones.cfg", "metazones.cfg"),
]:
    text = open(os.path.join(CONFIG_DIR, src_name)).read()
    text = text.replace("{{SAMPLES_DIR}}", SAMPLES_DIR).replace("{{WORKDIR}}", workdir)
    with open(os.path.join(workdir, dest_name), "w") as f:
        f.write(text)

print(sorted(os.listdir(workdir)))

# %%
# Running ``armoor-comp-models``
# ------------------------------------
#
# The command line is just ``armoor-comp-models <metazone(s)> <cfgfile>
# [--tbound ...]`` -- no radius/period positional (unlike Argo/drifter).

subprocess.run(
    ["armoor-comp-models", "modelzone_href", "comp_models_href.cfg",
     "--jsonfile", "ncs_href.json"],
    cwd=workdir,
    check=True,
)
subprocess.run(
    ["armoor-comp-models", "modelzone_cloud", "comp_models_cloud.cfg",
     "--jsonfile", "ncs_cloud.json"],
    cwd=workdir,
    check=True,
)

# %%
# Looking at the scores
# -------------------------
#
# Same ``xarray.DataTree`` shape as the other ``armoor-comp-*`` tutorials.

dt = xr.open_datatree(
    os.path.join(workdir, "comp_models/output/modelzone_href/glo12/timeseries/10.0/all.zarr")
)
print(dt["model2"]["comp"]["bias"].to_dataset())

# %%
# The ``href``/``vlevel`` figures
# -------------------------------------

with open(os.path.join(workdir, "ncs_href.json")) as f:
    png_paths_href = json.load(f)

stats_png = next(p for p in png_paths_href if "timeseries_stats_ptemp_" in p)
show_png(stats_png)

# %%
# Maps
# ~~~~~~
#
# Since ``model2`` is a scaled/offset copy of ``glo12``, the bias map is
# close to uniform -- a good sanity check that the comparison pipeline is
# measuring exactly the deterministic offset we injected.

map_png = next(p for p in png_paths_href if "map_ptemp_bias_" in p)
show_png(map_png)

# %%
# Global dispersion (``diagdisp_glob``)
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

diagdisp_glob_png = next(p for p in png_paths_href if "diagdisp_glob_ptemp_" in p)
show_png(diagdisp_glob_png)

# %%
# Per-interval dispersion (``diagdisp_sel``)
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

diagdisp_sel_png = next(p for p in png_paths_href if "diagdisp_sel_ptemp_" in p)
show_png(diagdisp_sel_png)

# %%
# Theta-S diagram (``mdiagts``)
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

mdiagts_png = next(p for p in png_paths_href if "mdiagts_" in p)
show_png(mdiagts_png)

# %%
# The ``cloud``/``vrange`` figures
# --------------------------------------
#
# From ``modelzone_cloud`` -- a single point (46.5N, 11W), 3 depth bins.

with open(os.path.join(workdir, "ncs_cloud.json")) as f:
    png_paths_cloud = json.load(f)

# %%
# Multiple vertical profiles (``mvprofiles``)
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

mvprofiles_png = next(
    p for p in png_paths_cloud if "mvprofiles_model2_ptemp_" in p and "0.0-50.0" in p
)
show_png(mvprofiles_png)

# %%
# Single-profile vertical profile (``uvprofiles``) and theta-S diagram (``udiagts``)
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
#
# Both need ``"concat": ["time"], "output": "merge"`` for
# ``armoor-comp-models`` -- unlike Argo's version, they merge *all 3 depth
# bins and all 3 weeks* into one figure here, so with GLO12's own coarse
# 9-level sample resolution this comes out busier (and the legend repeats
# once per merged slice) than the clean, single-bin Argo equivalent. Still
# real data, just a less polished view -- a genuine gap in how this
# otype's legend/labeling handles a multi-bin merge, not something this
# tutorial works around.

uvprofiles_png = next(p for p in png_paths_cloud if "uvprofiles_ptemp_" in p)
show_png(uvprofiles_png)

# %%
udiagts_png = next(p for p in png_paths_cloud if "udiagts_" in p)
show_png(udiagts_png)

# %%
# Next steps
# ----------
#
# - :doc:`09_comp_clim` (``armoor-comp-clim``) is ``href``-based like the
#   ``modelzone_href`` metazone above, but time colocation is forced to
#   calendar-month matching instead of ``[[trange_seq]]``.
# - ``armoor-comp-hydrosection`` follows the same
#   ``data.cfg``/``metazones.cfg``/``ref=True`` pattern, with its own
#   comparison-specific CLI flags -- see ``armoor-comp-* --help`` and
#   :ref:`examples`.
# - Full config schema: ``armoor/cli/comp.ini`` and
#   ``armoor/cli/metazones.ini``
# - :ref:`howtostart` with the command-line executables
