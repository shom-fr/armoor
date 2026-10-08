"""
Comparing a model against drifters (``armoor-comp-drifter``)
===================================================================

``armoor-comp-drifter`` doesn't score the model against the observation
point-for-point like ``armoor-comp-argo``/``-sst`` do. Instead it releases
a *virtual particle* at the real drifter's starting position/time and
integrates its trajectory forward through the model's current field
(``u``/``v``) using `OceanParcels <https://oceanparcels.org/>`_ -- then
compares the simulated trajectory against the real drifter track. The CLI
reflects this: ``armoor-comp-drifter METAZONES CFGFILE PERIOD FREQ
[OPTIONS]`` takes two extra positional arguments the other
``armoor-comp-*`` commands don't -- ``PERIOD`` (how far each
particle-tracking integration runs) and ``FREQ`` (how often the simulated
and real tracks are compared).

There are 3 output types, and armoor remaps the generic names you write in
``[outputs]`` to drifter-specific ones internally
(``CompDrifter.otype_remap``): ``otype=timeseries`` becomes
``timeseries_drifter``, ``otype=maps_trajectory`` becomes
``maps_trajectory_drifter``, ``otype=maps_current`` becomes
``maps_current_drifter``.

This tutorial ships a real ``comp_drifter.cfg`` alongside it and runs the
real ``armoor-comp-drifter`` command on the same CMEMS GLO12 model sample as
before (now including its current components, ``cmems_glo12_curr.nc``),
plus a real drifting-buoy sample
(``GL_TS_DB_1301782_20260703_20260708.nc``) -- both shipped with armoor's
own test suite, no network access or CMEMS credentials needed.
"""

import json
import os
import subprocess
import tempfile

import matplotlib.pyplot as plt

from armoor import ROOTDIR

SAMPLES_DIR = ROOTDIR + "/_samples"
DRIFTER_SAMPLE = SAMPLES_DIR + "/GL_TS_DB_1301782_20260703_20260708.nc"


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
# ``data.cfg`` has two sources: ``glo12`` (``fmt=cmems_model``, now with
# both ``temp`` and ``curr`` files -- the currents drive the virtual
# particle) and ``drifter`` (``fmt=cmems_insitu``, ``platform=drifter``,
# ``ref=True``).
#
# .. literalinclude:: 06_comp_drifter_data.cfg
#    :language: ini
#    :caption: comp_drifter.cfg
#    :linenos:
#
# :download:`Download comp_drifter.cfg <06_comp_drifter_data.cfg>`
#
# ``metazones.cfg`` needs no colocation parameters at all here --
# ``CompDrifter`` has no user-configurable ``colocation_params_user``,
# since the comparison isn't a point-match but a particle-tracking
# simulation.
#
# .. literalinclude:: 06_comp_drifter_metazones.cfg
#    :language: ini
#    :caption: metazones.cfg
#    :linenos:
#
# :download:`Download metazones.cfg <06_comp_drifter_metazones.cfg>`

workdir = tempfile.mkdtemp()
CONFIG_DIR = os.getcwd()

for src_name, dest_name in [
    ("06_comp_drifter_data.cfg", "comp_drifter.cfg"),
    ("06_comp_drifter_metazones.cfg", "metazones.cfg"),
]:
    text = open(os.path.join(CONFIG_DIR, src_name)).read()
    text = text.replace("{{SAMPLES_DIR}}", SAMPLES_DIR).replace("{{DRIFTER_SAMPLE}}", DRIFTER_SAMPLE)
    with open(os.path.join(workdir, dest_name), "w") as f:
        f.write(text)

print(sorted(os.listdir(workdir)))

# %%
# Running ``armoor-comp-drifter``
# ------------------------------------
#
# ``PERIOD=5d`` integrates a virtual particle for up to 5 days (the length
# of the drifter sample); ``FREQ=1h`` compares the simulated and real
# positions every hour.

subprocess.run(
    ["armoor-comp-drifter", "driftzone", "comp_drifter.cfg", "5d", "1h"],
    cwd=workdir,
    check=True,
)

# %%
# Looking at the figures
# ---------------------------
#
# All three output types (after remapping) are listed in
# ``ncs_comp_drifter.json``.

with open(os.path.join(workdir, "ncs_comp_drifter.json")) as f:
    png_paths = json.load(f)

print(png_paths)

# %%
# Distance and direction (``timeseries_drifter``)
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
#
# How far the simulated particle has drifted from the real drifter (top),
# and the direction difference between their instantaneous velocities
# (bottom), over the integration period.

timeseries_png = next(p for p in png_paths if "timeseries_drifter" in p)
show_png(timeseries_png)

# %%
# Trajectories (``maps_trajectory``)
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
#
# The real drifter track (black) against a fan of virtual particle
# trajectories (purple), one launched at each ``FREQ`` step along the real
# track -- the spread between them shows how quickly the model's currents
# diverge from reality.

trajectories_png = next(p for p in png_paths if "trajector" in p)
show_png(trajectories_png)

# %%
# Currents (``maps_current``)
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
#
# The real drifter's own velocity (black arrows) against the model's
# current at the same positions (purple arrows), along the track.

current_png = next(p for p in png_paths if "current" in p)
show_png(current_png)

# %%
# Next steps
# ----------
#
# - :doc:`07_comp_mooring` (``armoor-comp-mooring``) is back to
#   ``radius``-based point-matching, like Argo but stationary.
# - ``armoor-comp-models``/``-clim``/``-hydrosection`` follow the same
#   ``data.cfg``/``metazones.cfg``/``ref=True`` pattern, each with their
#   own comparison-specific CLI flags -- see ``armoor-comp-* --help`` and
#   :ref:`examples`.
# - Full config schema: ``armoor/cli/comp.ini`` and
#   ``armoor/cli/metazones.ini``
# - :ref:`howtostart` with the command-line executables
