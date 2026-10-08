"""
Comparing a model against observations with a config file (``armoor-comp-*``)
==================================================================================

``armoor-comp-*`` (``armoor-comp-argo``, ``-drifter``, ``-mooring``,
``-sst``, ``-models``, ``-clim``, ``-hydrosection``) builds on the exact
same ``data.cfg``/``metazones.cfg`` idiom as :doc:`03_data_config`, with
two additions: one ``[data]`` source is marked ``ref=True`` (the
observations to score the model against), and the metazone adds
colocation parameters -- ``[[trange_seq]]``'s ``tref`` (which side's time
axis to interpolate onto), ``[[vlevel]]``/``[[vrange]]``'s ``vref``,
``href`` -- controlling how model and observations are matched up in
time/space/depth before scoring.

``armoor-comp-argo`` supports 8 output types (``otype``), each a different
way of looking at the same colocated data: ``timeseries``/``maps``/
``diagdisp_glob``/``diagdisp_sel``/``mdiagts`` need a single fixed depth
(``[[vlevel]]``); ``mvprofiles``/``uvprofiles``/``udiagts`` need a
depth-binned profile instead (``[[vrange]]``). armoor refuses a metazone
that defines both, so this tutorial writes two metazones --
``argozone_vlevel`` and ``argozone_vrange`` -- and runs ``armoor-comp-argo``
once per metazone, to show all 8.

This tutorial ships real ``comp_argo_*.cfg`` files alongside it and runs
the real ``armoor-comp-argo`` command on the same CMEMS GLO12 model sample as
before, plus real Argo profile samples (two floats,
``GL_PR_PF_1902796_*.nc`` and ``GL_PR_PF_2901943_*.nc``) -- all shipped
with armoor's own test suite, no network access or CMEMS credentials
needed.
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
# ``data.cfg`` has two sources: ``glo12`` (the model) and ``argoprofiles``
# (``fmt=cmems_insitu``, ``platform=argo``, ``ref=True``) -- the same for
# both metazones, only ``[outputs]`` differs (one otype list per
# vertical-colocation family).
#
# .. literalinclude:: 04_comp_config_vlevel.cfg
#    :language: ini
#    :caption: comp_argo_vlevel.cfg
#    :linenos:
#
# :download:`Download comp_argo_vlevel.cfg <04_comp_config_vlevel.cfg>`
#
# .. literalinclude:: 04_comp_config_vrange.cfg
#    :language: ini
#    :caption: comp_argo_vrange.cfg
#    :linenos:
#
# :download:`Download comp_argo_vrange.cfg <04_comp_config_vrange.cfg>`
#
# ``metazones.cfg`` defines both metazones: ``[[trange_seq]]``
# (``tfreq=7d``, ``tref=reference``) is shared -- one week per Argo float
# pass gives enough colocated points per interval for ``diagdisp_sel``'s
# regression to be meaningful, unlike a daily split where most days only
# have a single profile.
#
# .. literalinclude:: 04_comp_config_metazones.cfg
#    :language: ini
#    :caption: metazones.cfg
#    :linenos:
#
# :download:`Download metazones.cfg <04_comp_config_metazones.cfg>`

workdir = tempfile.mkdtemp()
CONFIG_DIR = os.getcwd()

for src_name, dest_name in [
    ("04_comp_config_vlevel.cfg", "comp_argo_vlevel.cfg"),
    ("04_comp_config_vrange.cfg", "comp_argo_vrange.cfg"),
    ("04_comp_config_metazones.cfg", "metazones.cfg"),
]:
    text = open(os.path.join(CONFIG_DIR, src_name)).read()
    with open(os.path.join(workdir, dest_name), "w") as f:
        f.write(text.replace("{{SAMPLES_DIR}}", SAMPLES_DIR))

print(sorted(os.listdir(workdir)))

# %%
# Running ``armoor-comp-argo``
# --------------------------------
#
# The command line is ``armoor-comp-argo <metazone(s)> <cfgfile> <radius>
# [--qc ...]`` -- ``radius`` (km) is argo-specific: the disk around each
# profile's location within which model grid points are matched to it. Run
# once per metazone/cfg pair below; each writes its own
# ``ncs_comp_argo*.json`` (``--jsonfile``).

subprocess.run(
    ["armoor-comp-argo", "argozone_vlevel", "comp_argo_vlevel.cfg", "20.0",
     "--jsonfile", "ncs_vlevel.json"],
    cwd=workdir,
    check=True,
)
subprocess.run(
    ["armoor-comp-argo", "argozone_vrange", "comp_argo_vrange.cfg", "20.0",
     "--jsonfile", "ncs_vrange.json"],
    cwd=workdir,
    check=True,
)

# %%
# Looking at the scores
# -------------------------
#
# Comparison outputs are written as ``xarray.DataTree``\\ s, one per
# output/metazone/reference-source/vertical-level:
# ``<func_comp>/output/<metazone>/<ref source>/<otype>/<vlevel>/all.zarr``.
# Under the model's group (``glo12``), ``ref``/``data`` holds the
# colocated Argo values and ``comp``/``bias`` the model's bias against
# them, for every derived variable (``ptemp``, ``sal``, ``pdens``,
# ``temp``, ``sndspeed``) -- ``temp`` and the others are the same
# GSW-derived variables as in the :doc:`/tutorials/01_library/01_mooring_dataset` and
# :doc:`03_data_config` tutorials, now scored against real Argo floats
# instead of built or read from a file directly.

dt = xr.open_datatree(
    os.path.join(workdir, "comp_argo/output/argozone_vlevel/argoprofiles/timeseries/10.0/all.zarr")
)
print(dt["glo12"]["ref"]["data"].to_dataset())

# %%
print(dt["glo12"]["comp"]["bias"].to_dataset())

# %%
# The ``vlevel`` figures
# --------------------------
#
# ``armoor-comp-argo`` also rendered a stats PNG per variable
# (``timeseries_stats_<var>_10.0.png``), listed in ``ncs_vlevel.json``.
# Picking ``temp``'s below -- ``png_paths`` also includes
# ``timeseries_stats_mld.png``, but this toy example doesn't have enough
# profiles for a meaningful mixed-layer-depth comparison, so that one
# plots empty panels.

with open(os.path.join(workdir, "ncs_vlevel.json")) as f:
    png_paths_vlevel = json.load(f)

temp_png = next(p for p in png_paths_vlevel if "timeseries_stats_temp_" in p)
show_png(temp_png)

# %%
# Maps
# ~~~~~~
#
# ``otype=maps`` renders one PNG per variable *and* per colocation
# interval (here, one per week -- ``tfreq=7d``):
# ``map_<var>_diff_<prod>_<start>_<end>[_<vlevel>].png``. Each shows the
# model, the Argo observations, and their difference side by side, for
# that week.

map_pngs = sorted(p for p in png_paths_vlevel if "map_temp_diff_" in p)
print(f"{len(map_pngs)} temp map(s) rendered (one per week)")
show_png(map_pngs[0])

# %%
# Global dispersion (``diagdisp_glob``)
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
#
# A single scatter of every colocated point over the whole period, model
# vs. Argo, with a linear fit and R\\ :sup:`2` -- one PNG per variable,
# pooling all weeks together.

diagdisp_glob_png = next(p for p in png_paths_vlevel if "diagdisp_glob_temp_" in p)
show_png(diagdisp_glob_png)

# %%
# Per-interval dispersion (``diagdisp_sel``)
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
#
# The same scatter/regression as ``diagdisp_glob``, but one PNG per
# colocation interval instead of pooling them. The regression needs at
# least two colocated points to be defined -- the first week here only has
# one Argo profile, so its fit would be ``y = nanx + nan``; picking the
# second week instead, which has three.

diagdisp_sel_pngs = sorted(p for p in png_paths_vlevel if "diagdisp_sel_temp_" in p)
show_png(diagdisp_sel_pngs[1])

# %%
# Theta-S diagram (``mdiagts``)
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
#
# One temperature-salinity diagram per week, model vs. Argo, with density
# isopycnal contours -- a classic hydrological diagnostic, unaffected by
# the single-profile-per-week issue above since it doesn't fit a
# regression.

mdiagts_pngs = sorted(p for p in png_paths_vlevel if "mdiagts_" in p)
show_png(mdiagts_pngs[1])  # skip the first week (still just 1 profile)

# %%
# The ``vrange`` figures
# --------------------------
#
# The remaining three otypes come from the ``argozone_vrange`` run
# (``ncs_vrange.json``) and its three depth bins (0-50m, 50-150m,
# 150-500m) instead of a single fixed depth -- they show the profile shape
# itself, not a single-depth score.

with open(os.path.join(workdir, "ncs_vrange.json")) as f:
    png_paths_vrange = json.load(f)

# %%
# Multiple vertical profiles (``mvprofiles``)
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
#
# One line per Argo profile (black) and one line *per matched model grid
# point* (purple) within the colocation radius -- showing the local spread
# of the model around each observation, not just its mean.

mvprofiles_pngs = sorted(
    p for p in png_paths_vrange if "mvprofiles_glo12_temp_" in p and "0.0-50.0" in p
)
show_png(mvprofiles_pngs[0])

# %%
# Single-profile vertical profile (``uvprofiles``)
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
#
# One PNG per individual Argo profile: the profile itself (black), the
# single closest model grid point (blue), and the model's mean ± std
# across the matched cloud (shaded band).

uvprofiles_pngs = sorted(
    p for p in png_paths_vrange if "uvprofiles_temp_" in p and "0.0-50.0" in p
)
show_png(uvprofiles_pngs[0])

# %%
# Single-profile theta-S diagram (``udiagts``)
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
#
# Like ``mdiagts``, but per individual profile instead of per week --
# model members (blue) scattered against the single Argo profile (black).

udiagts_pngs = sorted(p for p in png_paths_vrange if "udiagts_" in p and "0.0-50.0" in p)
show_png(udiagts_pngs[0])

# %%
# Next steps
# ----------
#
# - :doc:`05_comp_sst` (``armoor-comp-sst``) uses the same idiom with a
#   gridded reference and ``href`` colocation instead of ``radius``.
# - ``armoor-comp-drifter``/``-mooring``/``-models``/``-clim``/
#   ``-hydrosection`` follow the same ``data.cfg``/``metazones.cfg``/
#   ``ref=True`` pattern, each with their own comparison-specific CLI flags
#   (``--qc``, ``--cgeo-ref``, ...) -- see ``armoor-comp-* --help`` and
#   :ref:`examples`.
# - Full config schema: ``armoor/cli/comp.ini`` and
#   ``armoor/cli/metazones.ini``
# - :ref:`howtostart` with the command-line executables
