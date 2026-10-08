"""
Processing data with a config file (``armoor-data``)
=========================================================

``armoor-data`` is one of the metazone-based executables (see
:ref:`howtostart`): it is driven by two configuration files instead of
command-line flags --

- **``data.cfg``** -- which source(s) to read (path + format) and what to
  output;
- **``metazones.cfg``** -- the region/period/filters to apply (a polygon, a
  time bound, a vertical level or range, ...), shared with
  ``armoor-comp-*``/``armoor-bull`` (see :ref:`examples`).

Both are shipped as real files alongside this script, and this tutorial
runs the real ``armoor-data`` command
on two small CMEMS GLO12 extracts already shipped with armoor for its own
test suite (``armoor/_samples/cmems_glo12_{temp,sal}.nc``) -- no network
access or CMEMS credentials needed.
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
# ``data.cfg`` declares one source (``fmt=cmems_model``, matching the
# sample files) and asks for a ``timeseries`` output as PNG.
#
# .. literalinclude:: 03_data_config_data.cfg
#    :language: ini
#    :caption: data.cfg
#    :linenos:
#
# :download:`Download data.cfg <03_data_config_data.cfg>`
#
# ``metazones.cfg`` defines one metazone (``datazone``): a bounding
# polygon, a time bound matching the sample files' own date range, a daily
# frequency and a single depth level -- the same schema ``armoor-comp-*``
# and ``armoor-bull`` metazones use (see ``armoor/cli/metazones.ini`` for
# the full set of keys: ``polygon``, ``tbound``, ``tfreq``, ``tide``,
# ``href``, and the ``[[vlevel]]``/``[[vrange]]``/``[[trange_seq]]``
# sub-sections).
#
# .. literalinclude:: 03_data_config_metazones.cfg
#    :language: ini
#    :caption: metazones.cfg
#    :linenos:
#
# :download:`Download metazones.cfg <03_data_config_metazones.cfg>`
#
# Both files are shipped for real next to this script (see the download
# links above) -- copy them into a scratch directory, substituting the
# actual sample-data location for the ``{{SAMPLES_DIR}}`` placeholder in
# ``data.cfg``, then run ``armoor-data`` from there.

workdir = tempfile.mkdtemp()
CONFIG_DIR = os.getcwd()

for src_name, dest_name in [
    ("03_data_config_data.cfg", "data.cfg"),
    ("03_data_config_metazones.cfg", "metazones.cfg"),
]:
    text = open(os.path.join(CONFIG_DIR, src_name)).read()
    with open(os.path.join(workdir, dest_name), "w") as f:
        f.write(text.replace("{{SAMPLES_DIR}}", SAMPLES_DIR))

print(sorted(os.listdir(workdir)))

# %%
# Running ``armoor-data``
# ---------------------------
#
# ``armoor-data`` writes its outputs relative to the current directory, so
# it's run with ``cwd=workdir``. The command line itself is just
# ``armoor-data <metazone(s)> <data.cfg>`` -- ``metazones.cfg`` is picked up
# automatically since it uses the default name.
#
# Run once here, all the way through to the PNG ``armoor-data`` renders for
# this config (paths recorded in ``ncs_png.json`` via ``--jsonfile``).
# Passing ``--filters-only`` instead stops right after the load/filter
# stage -- useful on its own when only the intermediate data is needed --
# but since it's a strict subset of the full run, this tutorial runs the
# full pipeline once and inspects the intermediate Zarr it leaves behind as
# a byproduct (see below).

subprocess.run(
    ["armoor-data", "datazone", "data.cfg", "--jsonfile", "ncs_png.json"],
    cwd=workdir,
    check=True,
)

# %%
# Looking at the result
# -------------------------
#
# Besides the final PNG (listed in ``ncs_png.json``, see below),
# ``armoor-data`` also writes each source's filtered/loaded data as an
# intermediate Zarr store, at a path derived from the metazone and source
# names: ``data/metazones/<metazone>/<source>/prod_<source>.zarr``. Handy
# to inspect directly with ``xarray``, without a separate
# ``--filters-only`` run.

ds = xr.open_zarr(os.path.join(workdir, "data/metazones/datazone/glo12/prod_glo12.zarr"))
print(ds)

# %%
# ``fmt=cmems_model`` renames CMEMS' own variable names to armoor's (see
# ``armoor/data/cf_cmems_model.cfg``): ``thetao`` -> ``ptemp`` (potential
# temperature), ``so`` -> ``sal``. In-situ ``temp`` isn't one of the source
# variables, but ``ds.oceanvars`` (see :doc:`/tutorials/01_library/01_mooring_dataset`) derives
# it from ``ptemp``+``sal``+``depth`` via GSW, exactly as it derived
# ``ptemp`` from ``temp`` there -- the same accessor, either direction.

ds["temp"] = ds.oceanvars.sel("temp")
print(ds[["ptemp", "sal", "temp"]])

# %%
# Reduce whatever non-spatial dimensions the metazone pipeline produced
# (time/trange/z/vlevel, ...) so this plots regardless of their exact names.
extra_dims = [d for d in ds["temp"].dims if d not in ("y", "x")]
_ = ds["temp"].mean(extra_dims, keep_attrs=True).plot(x="lon", y="lat")

# %%
# The actual rendered output
# ------------------------------
#
# ``armoor-data`` also produced the real ``timeseries`` PNG for this
# metazone in the run above, with its path recorded in ``ncs_png.json``.

with open(os.path.join(workdir, "ncs_png.json")) as f:
    png_paths = json.load(f)

show_png(png_paths[0])

# %%
# Next steps
# ----------
#
# ``armoor-comp-*`` (e.g. ``armoor-comp-argo``, see
# :doc:`04_comp_config` and ``comp_argo.cfg`` in :ref:`examples`) uses the
# exact same ``[data]``/metazone idiom, with two differences: one source is
# marked ``ref=True`` (the observations to compare against), and the
# metazone adds colocation parameters (``[[vrange]]``'s ``vref``,
# ``[[trange_seq]]``'s ``tref``, ``href``) controlling how the model is
# matched up with it in time/space/depth before scoring.
#
# - Full config schema: ``armoor/cli/data.ini`` and
#   ``armoor/cli/metazones.ini``
# - :ref:`howtostart` with the command-line executables
# - Full method list: :ref:`accessors`
