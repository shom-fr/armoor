import xarray as xr
import pandas as pd
import numpy as np
import pytest

import armoor.base.colocation as coloc
from armoor.hmi.script_tools import create_folder


    
@pytest.mark.parametrize(
    "ds_model, ds_obs", [
        (xr.Dataset(
            data_vars=dict(
                temp=(
                    ["time", "z", "y", "x"],
                    15 + 8 * np.random.randn(15, 3, 5, 10),
                ),
            ),
            coords=dict(
                lon=(
                    ["y", "x"],
                    np.meshgrid(
                        np.arange(0.0, 10, 1),
                        np.arange(30, 35, 1)
                    )[0]
                ),
                lat=(
                    ["y", "x"],
                    np.meshgrid(
                        np.arange(0.0, 10, 1),
                        np.arange(30, 35, 1)
                    )[1]
                ),
                depth=(
                    ["time", "z", "y", "x"],
                    500 + 200 * np.random.randn(15, 3, 5, 10)
                ),
                time=("time", pd.date_range(
                    start='1999-12-31',
                    freq='12h',
                    periods=15
                )),
            ),
        ),
        xr.Dataset(
            data_vars=dict(
                temp=(
                    ["time", "z"],
                    15 + 8 * np.random.randn(4, 3),
                ),
            ),
            coords=dict(
                lon=(
                    ["time"], np.linspace(5, 8, 4)
                ),
                lat=(
                    ["time"], np.linspace(32, 34, 4)
                ),
                depth=(
                    ["time", "z"],
                    500 + 200 * np.random.randn(4, 3)
                ),
                time=("time", pd.date_range(
                    start='2000-01-01',
                    freq='1D',
                    periods=4
                )),
            ),
        )),
        (xr.Dataset(
            data_vars=dict(
                temp=(
                    ["time", "z", "y", "x"],
                    15 + 8 * np.random.randn(15, 3, 5, 10),
                ),
            ),
            coords=dict(
                lon=(
                    ["y", "x"],
                    np.meshgrid(
                        np.arange(0.0, 10, 1),
                        np.arange(30, 35, 1)
                    )[0]
                ),
                lat=(
                    ["y", "x"],
                    np.meshgrid(
                        np.arange(0.0, 10, 1),
                        np.arange(30, 35, 1)
                    )[1]
                ),
                depth=(
                    ["time", "z", "y", "x"],
                    500 + 200 * np.random.randn(15, 3, 5, 10)
                ),
                time=("time", pd.date_range(
                    start='1999-12-31',
                    freq='12h',
                    periods=15
                )),
            ),
        ),
        xr.Dataset(
            data_vars=dict(
                temp=(
                    ["time", "z"],
                    15 + 8 * np.random.randn(4, 3),
                ),
            ),
            coords=dict(
                lon=6.0,
                lat=33.0,
                depth=(
                    ["time", "z"],
                    500 + 200 * np.random.randn(4, 3)
                ),
                time=("time", pd.date_range(
                    start='2000-01-01',
                    freq='1D',
                    periods=4
                )),
            ),
        )),
    ],
)
def test_horizontal_radius(ds_model, ds_obs):
    radius = 100 #km
    dso, dsm = coloc.obs_coords_radius(ds_obs, ds_model, radius)
    assert isinstance(dsm, xr.Dataset)
    assert set(["time", "z", "member"]).issubset(dsm.dims)

@pytest.mark.parametrize(
    "dsi, dso", [
        (xr.Dataset(
            data_vars=dict(
                temp=(
                    ["time", "z", "y", "x"],
                    15 + 8 * np.random.randn(15, 3, 5, 10),
                ),
            ),
            coords=dict(
                lon=(
                    ["y", "x"],
                    np.meshgrid(
                        np.arange(0.0, 10, 1),
                        np.arange(30, 35, 1)
                    )[0]
                ),
                lat=(
                    ["y", "x"],
                    np.meshgrid(
                        np.arange(0.0, 10, 1),
                        np.arange(30, 35, 1)
                    )[1]
                ),
                depth=(
                    ["time", "z", "y", "x"],
                    500 + 200 * np.random.randn(15, 3, 5, 10)
                ),
                time=("time", pd.date_range(
                    start='1999-12-31',
                    freq='12h',
                    periods=15
                )),
            ),
        ),
        xr.Dataset(
            data_vars=dict(
                temp=(
                    ["time", "z", "y", "x"],
                    15 + 8 * np.random.randn(15, 3, 9, 10),
                ),
            ),
            coords=dict(
                lon=(
                    ["y", "x"],
                    np.meshgrid(
                        np.linspace(0.0, 10, 10),
                        np.linspace(28, 35, 9)
                    )[0]
                ),
                lat=(
                    ["y", "x"],
                    np.meshgrid(
                        np.linspace(0.0, 10, 10),
                        np.linspace(28, 35, 9)
                    )[1]
                ),
                depth=(
                    ["time", "z", "y", "x"],
                    500 + 200 * np.random.randn(15, 3, 9, 10)
                ),
                time=("time", pd.date_range(
                    start='1999-12-31',
                    freq='12h',
                    periods=15
                )),
            ),
        ))
    ],
)
def test_horizontal_regrid(dsi, dso):
    dsi, dso = coloc.horizontal_regrid(dsi, dso)
    assert isinstance(dso, xr.Dataset)
    assert dso.sizes == dsi.sizes
