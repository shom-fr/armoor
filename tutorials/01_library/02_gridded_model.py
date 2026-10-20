"""
A synthetic 4D model field (time, z, y, x)
============================================

The :doc:`01_mooring_dataset` tutorial used a single-point time series.
Regional ocean products are usually gridded instead: a ``(time, z, y, x)``
field with 2-D ``lon(y, x)`` / ``lat(y, x)`` coordinates (curvilinear
grids, as produced by NEMO/CROCO-family models). This tutorial builds one
synthetic field by hand and exercises the accessors that specifically
target gridded data: ``ds.plot.maps``, ``ds.range.vertical``,
``ds.interp.vertical``/``coarsen``/``grid2loc``/``grid2section``.

It requires no external data and no network access.
"""

import numpy as np
import pandas as pd
import xarray as xr

import armoor  # noqa: F401 -- side effect only: registers the accessors

# %%
# Building the grid
# --------------------
#
# A small regional box (20x16 horizontal points, 4 depth levels, 5 daily
# time steps), with a warm, gently stratified upper ocean and a simple
# depth-decaying eddy for the current field.

rng = np.random.default_rng(1)

nx, ny, nz, nt = 20, 16, 4, 5
lon1d = np.linspace(-6.0, -3.0, nx)
lat1d = np.linspace(47.0, 49.0, ny)
lon2d, lat2d = np.meshgrid(lon1d, lat1d)  # dims (y, x)
depth = np.array([0.0, 20.0, 50.0, 100.0])
time = pd.date_range("2021-06-01", periods=nt, freq="1D")

vertical = (18.0 * np.exp(-depth / 80.0) + 8.0).reshape(1, nz, 1, 1)
horizontal = (0.6 * (49.0 - lat2d)).reshape(1, 1, ny, nx)  # warmer south
trend = (0.1 * np.arange(nt)).reshape(nt, 1, 1, 1)
temp = vertical + horizontal + trend + rng.normal(0, 0.05, (nt, nz, ny, nx))
sal = 35.5 - 0.01 * depth.reshape(1, nz, 1, 1) + rng.normal(0, 0.01, (nt, nz, ny, nx))

# A depth-decaying eddy centred on the domain, slowly intensifying over the week.
# Given a "time" dim explicitly (rather than left constant): grid2loc's internal
# _grid2loc_var() only handles the (time, z), (time, no z) and (no time, no z)
# cases -- a (z, no time) variable like a "frozen" current field hits none of
# them and raises a ValueError (see armoor.interp._grid2loc_var).
dxg = lon2d - lon2d.mean()
dyg = lat2d - lat2d.mean()
r = np.hypot(dxg, dyg) + 1e-3
decay = np.exp(-depth / 50.0).reshape(nz, 1, 1)
time_factor = (0.8 + 0.4 * np.arange(nt) / nt).reshape(nt, 1, 1, 1)
u = (-dyg / r) * 0.3 * decay * time_factor
v = (dxg / r) * 0.3 * decay * time_factor

ds = xr.Dataset(
    {
        "temp": (("time", "z", "y", "x"), temp.astype("float32"), {"units": "degC"}),
        "sal": (("time", "z", "y", "x"), sal.astype("float32"), {"units": "1e-3"}),
        "u": (("time", "z", "y", "x"), u.astype("float32"), {"units": "m s-1"}),
        "v": (("time", "z", "y", "x"), v.astype("float32"), {"units": "m s-1"}),
    },
    coords={
        "time": time,
        "depth": ("z", depth),
        "lon": (("y", "x"), lon2d, {"standard_name": "longitude", "units": "degrees_east"}),
        "lat": (("y", "x"), lat2d, {"standard_name": "latitude", "units": "degrees_north"}),
    },
)
print(ds)

# %%
# Maps
# -----
#
# ``ds.plot.maps`` plots one variable of one ``ds[var]`` with
# ``xarray.DataArray.plot`` underneath, so pick a single ``(time, z)``
# slice first, and pass the 2-D ``lon``/``lat`` coordinates explicitly
# since the grid is curvilinear (the ``x``/``y`` dimensions alone are just
# grid indices).

_ = ds.isel(time=0, z=0).plot.maps(var="temp", x="lon", y="lat")

# %%
# Ocean variables on gridded data
# -----------------------------------
#
# ``ds.oceanvars`` works the same way regardless of the dataset's
# dimensions: current speed/direction are derived from ``u``/``v`` exactly
# as in the point-based tutorial.

ds["cspeed"] = ds.oceanvars.sel("cspeed")
ds["cdir"] = ds.oceanvars.sel("cdir")

_ = ds.isel(time=0, z=0).plot.maps(var="cspeed", x="lon", y="lat", cmap="viridis")

# %%
# Vertical operations
# ----------------------
#
# ``ds.range.vertical`` masks 3-D variables outside a depth range (2-D ones
# are untouched); ``ds.interp.vertical`` re-interpolates onto new depth
# levels (via ``xoa.regrid.regrid1d``). Both take the name of the vertical
# *coordinate* (``"depth"``), while the underlying dimension is
# conventionally called ``"z"``.

ds_upper = ds.range.vertical("depth", (0, 60))
print("NaN below 60 m:", bool(ds_upper["temp"].isel(time=0, y=0, x=0, z=-1).isnull()))

ds_zi = ds.interp.vertical("depth", [0, 10, 30, 60])
_ = ds_zi.isel(time=0, y=8, x=10).plot.profiles(var="temp", dim="depth", marker="o")

# %%
# Horizontal operations
# ------------------------
#
# ``ds.interp.coarsen`` block-averages a structured grid;
# ``ds.interp.grid2loc`` samples the grid at scattered points --
# **coordinates are ``(lat, lon)`` tuples, in that order** -- and
# ``ds.interp.grid2section`` interpolates along a broken-line geodesic
# section, adding a ``distance`` coordinate (metres from the first
# waypoint).

ds_coarse = ds.interp.coarsen(2)
print(f"{ds.sizes['x']}x{ds.sizes['y']} -> {ds_coarse.sizes['x']}x{ds_coarse.sizes['y']}")

# (lat, lon) order, not (lon, lat) -- despite what a couple of docstrings
# elsewhere in armoor claim; `armoor.interp.grid2loc` itself does
# `lat, lon = zip(*coords)`.
virtual_moorings = [(47.3, -5.5), (47.9, -4.6), (48.4, -3.8)]
ds_pts = ds.interp.grid2loc(virtual_moorings)
print(ds_pts[["temp", "cspeed"]])

# %%
section = ds.interp.grid2section([(47.2, -5.8), (48.8, -3.2)], dx=10)
_ = section.isel(time=0)["temp"].plot(x="distance", y="depth", yincrease=False)

# %%
# Next steps
# ----------
#
# - :doc:`01_mooring_dataset` -- a single-point time series
# - Full method list: :ref:`accessors`
