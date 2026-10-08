"""
Getting started with the accessors
===================================

Importing ``armoor`` registers a handful of `xarray accessors
<https://docs.xarray.dev/en/stable/internals/extending-xarray.html>`_ on
every ``xr.Dataset``: ``ds.filters``, ``ds.oceanvars``, ``ds.coloc``,
``ds.stats``, ``ds.range``, ``ds.interp`` and ``ds.plot`` (which extends
xarray's own). None of them require the dataset to originate from armoor
itself -- they work on any `CF-ish <http://cfconventions.org/>`_
``xr.Dataset`` with ``time``/``lon``/``lat``/``depth``.

This tutorial builds a small synthetic mooring-like dataset by hand (no
network access, no sample data files needed) and chains the accessors on it.
See ``armoor.accessors`` in the API reference and the :ref:`accessors` page
for the full method list.
"""

import numpy as np
import pandas as pd
import xarray as xr

import armoor  # noqa: F401 -- side effect only: registers the accessors above

# %%
# A synthetic mooring dataset
# ----------------------------
#
# Two weeks of hourly temperature and salinity at a fixed point (15 m
# depth), with a mild warming trend, a diurnal cycle, and a handful of
# bad-quality spikes flagged in ``temp_qc`` (Argo-style 1=good ... 4=bad
# convention used throughout armoor).

rng = np.random.default_rng(0)

time = pd.date_range("2021-06-01", periods=24 * 14, freq="1h")
n = time.size
hours = np.arange(n)

temp = (
    14.0
    + 0.05 * hours / 24            # slow warming trend
    + 0.3 * np.sin(2 * np.pi * hours / 24)  # diurnal cycle
    + rng.normal(0, 0.05, n)
)
sal = 35.2 + 0.02 * np.sin(2 * np.pi * hours / (24 * 12.42)) + rng.normal(0, 0.01, n)

temp_qc = np.ones(n, dtype="int8")
bad = rng.choice(n, size=10, replace=False)
temp[bad] += rng.normal(0, 3, bad.size)
temp_qc[bad] = 4

ds = xr.Dataset(
    {
        "temp": ("time", temp.astype("float32"), {"units": "degC"}),
        "sal": ("time", sal.astype("float32"), {"units": "1e-3"}),
        "temp_qc": ("time", temp_qc),
    },
    coords={"time": time, "depth": 15.0, "lon": -4.5, "lat": 48.3},
)
print(ds)

# %%
_ = ds.plot.timeseries(var="temp")

# %%
# The spikes flagged by ``temp_qc == 4`` are clearly visible. We will
# filter them out below with ``ds.filters``.
#
# Deriving ocean variables with ``ds.oceanvars``
# ------------------------------------------------
#
# ``ds.oceanvars`` selects a variable if it is already present, or derives
# it from whatever *is* present using the `GSW
# <https://teos-10.github.io/GSW-Python/>`_ Thermodynamic Equation of
# Seawater library -- here, potential temperature and potential density are
# computed from ``temp`` + ``sal`` (+ ``depth``/``lat`` for pressure).

ds["ptemp"] = ds.oceanvars.sel("ptemp")

# sel_pdens() is called directly (rather than through sel()) to pick the
# reference pressure explicitly -- sigma0, referenced to the surface.
ds["pdens"] = ds.oceanvars.sel_pdens(ref_dens=0)

print(ds[["temp", "ptemp", "pdens"]])

# %%
_ = ds.plot.timeseries(var="pdens")

# %%
# Filtering with ``ds.filters``
# --------------------------------
#
# ``ds.filters.combined(...)`` builds a single boolean mask from any number
# of filter keys (quality, time range, polygon, ...) and applies it in one
# pass. Here we drop everything flagged worse than QC 2:

ds_qc = ds.filters.combined({"quality": {"qname": "temp", "qmin": 1, "qmax": 2}})

print(f"{ds.sizes['time']} points -> {ds_qc.sizes['time']} points after quality filtering")

# %%
# Filter keys combine into a single mask, so a time window and a quality
# threshold can be applied together in one call:

ds_week2 = ds.filters.combined(
    {
        "time_selection": {"minimum": "2021-06-08", "maximum": "2021-06-11"},
        "quality": {"qname": "temp", "qmin": 1, "qmax": 2},
    }
)
print(f"-> {ds_week2.sizes['time']} points between 2021-06-08 and 2021-06-11, QC 1-2 only")

# %%
# A minimal model-vs-observation comparison with ``ds.stats``
# ---------------------------------------------------------------
#
# Armoor exists to compare regional model output against observations. To
# illustrate the pattern on a single point, treat the quality-checked
# mooring as the *reference* and build a synthetic *product* with a small
# warm bias and extra noise -- the situation ``ds.stats.bias``/
# ``ds.stats.rmse`` are meant for.

ds_ref = ds_qc[["temp"]]
ds_prod = ds_ref + 0.4 + xr.DataArray(
    rng.normal(0, 0.15, ds_ref.sizes["time"]), dims="time", coords={"time": ds_ref.time}
)

bias = ds_prod.stats.bias(ds_ref, dim="time")
rmse = ds_prod.stats.rmse(ds_ref, dim="time")
print(f"temp bias: {float(bias['temp']):.2f} degC, RMSE: {float(rmse['temp']):.2f} degC")

# %%
ds_diag = xr.Dataset({"ref_temp": ds_ref["temp"], "prod_temp": ds_prod["temp"]})
_ = ds_diag.plot.diagdisp("ref_temp", "prod_temp")

# %%
# Next steps
# ----------
#
# - Full method list: :ref:`accessors`
# - Ready-to-run configuration files for the ``armoor-comp-*`` /
#   ``armoor-data`` / ``armoor-bull`` command-line executables:
#   :ref:`examples`
# - :ref:`howtostart` with the command-line executables
