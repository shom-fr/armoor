import xarray as xr
import pandas as pd
import numpy as np
import pytest

import armoor.base.meta_zone
from armoor.hmi.script_tools import create_folder

from armoor.base.open_decode import open_decode


@pytest.mark.parametrize(
    "dsi, polygon", [
        (xr.Dataset(
            coords=dict(
                lon=("time", np.linspace(0.0, 10, 6)),
                lat=("time", np.linspace(30, 36, 6)),
                depth=("z", [0.0, 300.0, 500.0]),
                time=("time", pd.date_range(
                    start='2000-01-01',
                    freq='1H',
                    periods=6
                )),
            ),
        ), [[31.0, 2.0], [35.0, 2.0], [35.0, 9.0], [33.0, 10.0], [31.0, 9.0]]),
        (xr.Dataset(
            coords=dict(
                lon=(
                    ["y", "x"],
                    np.meshgrid(
                        np.arange(0.0, 10, 1),
                        np.arange(30, 36, 1)
                    )[0]
                ),
                lat=(
                    ["y", "x"],
                    np.meshgrid(
                        np.arange(0.0, 10, 1),
                        np.arange(30, 36, 1)
                    )[1]
                ),
                depth=("z", [0.0, 300.0, 500.0]),
                time=("time", pd.date_range(
                    start='2000-01-01',
                    freq='1H',
                    periods=6
                )),
            ),
        ), [[30.0, 0.5], [36.0, 0.5], [36.0, 10.0]]),
    ],
)
def test_horizontal_polygon(dsi, polygon):
    dso = dsi.meta.horizontal_selection_polygon(polygon)
    lat_polygon, lon_polygon = zip(*polygon)
    assert dso.lat.min() >= np.min(lat_polygon)
    assert dso.lon.min() >= np.min(lon_polygon)
    assert dso.lat.max() <= np.max(lat_polygon)
    assert dso.lon.max() <= np.max(lon_polygon)
    
@pytest.mark.parametrize(
    "quality", [
        ("temp", 0, 10),
        ("temp", 1, 4),
        ("sal", 0, 10),
        ("temp", 1, None),
        ("temp", None, 0),
        ("temp", None, None),
    ]
)
def test_horizontal_quality(quality):
    dsi = xr.Dataset(
        data_vars=dict(
            temp=(
                ["time", "z"],
                15 + 8 * np.random.randn(10, 3)
            ),
            temp_qc=(
                ["time", "z"],
                np.random.randint(0, high=7, size=(10, 3))
            )
        ),
    )
    dso = dsi.meta.quality_filter(*quality)
    assert isinstance(dso, xr.Dataset)
    var_qc = quality[0] + "_qc"
    if  var_qc in dsi.data_vars:
        if quality[1]:
            assert dso[var_qc].min() >= quality[1]
        if quality[2]:
            assert dso[var_qc].max() <= quality[2]
    
@pytest.mark.parametrize(
    "dsi, coords", [
        (xr.Dataset(
            data_vars=dict(
                temp=(
                    ["time", "z", "y", "x"],
                    15 + 8 * np.random.randn(6, 3, 5, 10),
                ),
                sst=(
                    ["time", "y", "x"],
                    15 + 1 * np.random.randn(6, 5, 10),
                )
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
                depth=("z", [0.0, 300.0, 500.0]),
                time=("time", pd.date_range(
                    start='2000-01-01',
                    freq='1H',
                    periods=6
                )),
            ),
        ), [[30.0, 0.5], [36.0, 0.5], [36.0, 10.0]],),
        (xr.Dataset(
            data_vars=dict(
                temp=(
                    ["time", "z", "y", "x"],
                    15 + 8 * np.random.randn(6, 3, 5, 10),
                ),
                sst=(
                    ["time", "y", "x"],
                    15 + 1 * np.random.randn(6, 5, 10),
                )
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
                    500 + 200 * np.random.randn(6, 3, 5, 10)
                ),
                time=("time", pd.date_range(
                    start='2000-01-01',
                    freq='1H',
                    periods=6
                )),
            ),
        ), [[31.0, 0.5], [34.0, 0.5], [32.0, 9.0]],
        ),
    ],
)
def test_horizontal_coords(dsi, coords):
    dso = dsi.meta.horizontal_selection_coords(coords)
    assert "npts" in dso.dims
    assert dso.dims["npts"] == len(coords)

@pytest.mark.parametrize(
    "ds, obs", [
        (xr.Dataset(
            coords=dict(
                lon=(
                    ["time", "member"],
                    5 + 2 * np.random.randn(4, 2)
                ),
                lat=(
                    ["time", "member"],
                    30 + 2 * np.random.randn(4, 2)
                ),
                depth=(
                    ["time", "z", "member"],
                    500 + 200 * np.random.randn(4, 3, 2)
                ),
                time=("time", pd.date_range(
                    start='1999-12-31',
                    freq='12h',
                    periods=4
                )),
            ),
        ), xr.Dataset(
            coords=dict(
                lon=(
                    "time",
                    5 + 2 * np.random.randn(4)
                ),
                lat=(
                    "time",
                    30 + 2 * np.random.randn(4)
                ),
                time=("time", pd.date_range(
                    start='1999-12-31',
                    freq='12h',
                    periods=4
                )),
            ),
        )),
        (xr.Dataset(
            coords=dict(
                lon=(
                    "member",
                    5 + 2 * np.random.randn(2)
                ),
                lat=(
                    "member",
                    30 + 2 * np.random.randn(2)
                ),
            ),
        ), xr.Dataset(
            coords=dict(
                lon=5.5,
                lat=31.0
            ),  
        ))
    ],
)
def test_horizontal_closest(ds, obs):
    dso = ds.meta.sel_closest(obs)
    assert isinstance(dso, xr.Dataset)
    assert "member" not in dso.dims

@pytest.mark.parametrize(
    "ds, vrange, var", [
        (xr.Dataset(
            coords=dict(
                lon=(
                    ["y", "x"],
                    5 + 2 * np.random.randn(4, 5)
                ),
                lat=(
                    ["y", "x"],
                    30 + 2 * np.random.randn(4, 5)
                ),
                depth=(
                    ["time", "z", "y", "x"],
                    np.abs(150 + 200 * np.random.randn(2, 3, 4, 5))
                ),
                time=("time", pd.date_range(
                    start='2000-01-01',
                    freq='12h',
                    periods=2
                )),
            ),
        ), [(0.0, 100.0), (150.0, 500.0), (700.0, 1000.0)], "depth"),
        (xr.Dataset(
            coords=dict(
                lon=("time", 5 + 2 * np.random.randn(4)),
                lat=("time", 30 + 2 * np.random.randn(4)),
                depth=(
                    ["time", "z"],
                    np.abs(150 + 200 * np.random.randn(4, 5))
                ),
                time=("time", pd.date_range(
                    start='2000-01-01',
                    freq='12h',
                    periods=4
                )),
            ),
        ), [(0.0, 100.0), (150.0, 500.0), (700.0, 1000.0)], "depth"),
        (xr.Dataset(
            coords=dict(
                lon=("time", 5 + 2 * np.random.randn(4)),
                lat=("time", 30 + 2 * np.random.randn(4)),
                dens=(
                    ["time", "z"],
                    np.abs(1025 + 3 * np.random.randn(4, 5))
                ),
                time=("time", pd.date_range(
                    start='2000-01-01',
                    freq='12h',
                    periods=4
                )),
            ),
        ), [(1025.5, 1026), (1026.5, 1027)], "dens"),
    ],
)
def test_vertical_range(ds, vrange, var):
    dso = ds.meta.vertical_selection_range(var, vrange)
    assert isinstance(dso, xr.Dataset)
    assert dso.sizes["vrange"] == len(vrange)
    assert dso.sizes["vbin"] == 2
    assert set(ds.dims).issubset(dso.dims)

@pytest.mark.parametrize(
    "ds, vlevels, var, method", [
        (xr.Dataset(
            coords=dict(
                lon=(
                    ["y", "x"],
                    5 + 2 * np.random.randn(4, 5)
                ),
                lat=(
                    ["y", "x"],
                    30 + 2 * np.random.randn(4, 5)
                ),
                depth=(
                    ["time", "z", "y", "x"],
                    np.abs(150 + 200 * np.random.randn(2, 3, 4, 5))
                ),
                time=("time", pd.date_range(
                    start='2000-01-01',
                    freq='12h',
                    periods=2
                )),
            ),
            data_vars=dict(
                temp=(
                    ["time", "z", "y", "x"],
                    15 + 5 * np.random.randn(2, 3, 4, 5)
                ),
            )
        ), [0.0, 150.0, 500.0], "depth", "linear"),
        (xr.Dataset(
            coords=dict(
                lon=("time", 5 + 2 * np.random.randn(4)),
                lat=("time", 30 + 2 * np.random.randn(4)),
                depth=(
                    ["time", "z"],
                    np.abs(150 + 200 * np.random.randn(4, 5))
                ),
                time=("time", pd.date_range(
                    start='2000-01-01',
                    freq='12h',
                    periods=4
                )),
            ),
            data_vars=dict(
                temp=(
                    ["time", "z"],
                    15 + 5 * np.random.randn(4, 5)
                ),
            )
        ), [0.0, 150.0, 500.0], "depth", "linear"),
        (xr.Dataset(
            coords=dict(
                lon=("time", 5 + 2 * np.random.randn(4)),
                lat=("time", 30 + 2 * np.random.randn(4)),
                dens=(
                    ["time", "z"],
                    np.abs(1025 + 3 * np.random.randn(4, 5))
                ),
                depth=(
                    ["time", "z"],
                    np.abs(150 + 200 * np.random.randn(4, 5))
                ),
                time=("time", pd.date_range(
                    start='2000-01-01',
                    freq='12h',
                    periods=4
                )),
            ),
        ), [1025.5, 1026, 1026.5, 1027], "dens", "linear"),
    ],
)
def test_vertical_levels(ds, vlevels, var, method):
    dso = ds.meta.vertical_selection_levels(var, vlevels, method=method)
    assert isinstance(dso, xr.Dataset)
    assert dso.sizes["z"] == len(vlevels)
    assert set(ds.dims).issubset(dso.dims)

@pytest.mark.parametrize(
    "ds, start, end, res", [
        (xr.Dataset(
            coords=dict(
                time=("time", pd.date_range(
                    start='2000-01-01',
                    freq='6h',
                    periods=2
                )),
            ),
        ), "2000-01-01", "2000-01-02", 2),
        (xr.Dataset(
            coords=dict(
                time=("time", pd.date_range(
                    start='2000-01-01',
                    freq='1d',
                    periods=3
                )),
            ),
        ), "2000-01-01", "2000-01-02", 2),
        (xr.Dataset(
            coords=dict(
                time=("time", pd.date_range(
                    start='2000-01-01',
                    freq='1d',
                    periods=3
                )),
            ),
        ), "2000-01-01", 1, 2),
    ],
)
def test_time_bounds(ds, start, end, res):
    dso = ds.meta.time_selection_bounds(start, end)
    assert isinstance(dso, xr.Dataset)
    assert dso.sizes["time"] == res
    assert dso.time.min().values >= pd.to_datetime(start)

@pytest.mark.parametrize(
    "ds, start, end, freq, dates, res", [
        (xr.Dataset(
            coords=dict(
                time=("time", pd.date_range(
                    start='2000-01-01',
                    freq='6h',
                    periods=2
                )),
            ),
        ), "2000-01-01", "2000-01-02", "1d", None, 2),
        (xr.Dataset(
            coords=dict(
                time=("time", pd.date_range(
                    start='2000-01-01',
                    freq='6h',
                    periods=2
                )),
            ),
        ), None, None, None, ["2000-01-01", "2000-01-01T12:00", "2000-01-02"], 3),
    ],
)
def test_time_terms(ds, start, end, freq, dates, res):
    dso = ds.meta.time_selection_terms(start, end, freq, dates)
    assert isinstance(dso, xr.Dataset)
    assert dso.sizes["time"] == res
    if start != None:
        assert dso.time.min() == pd.to_datetime(start)
        assert dso.time.max() == pd.to_datetime(end)
    else:
        assert dso.time.min() == pd.to_datetime(dates[0])
        assert dso.time.max() == pd.to_datetime(dates[-1])


@pytest.mark.parametrize(
    "ds, start, end, trange, res", [
        (xr.Dataset(
            coords=dict(
                time=("time", pd.date_range(
                    start='2000-01-01',
                    end='2000-01-02',
                    freq='1h',
                )),
            ),
        ), '2000-01-01', '2000-01-02','6h', 4),
        (xr.Dataset(
            coords=dict(
                time=("time", pd.date_range(
                    start='2000-01-01 01:00:00',
                    end='2000-01-01 23:00:00',
                    freq='1h',
                )),
            ),
        ), '2000-01-01', '2000-01-02','6h', 4),
        (xr.Dataset(
            coords=dict(
                time=("time", pd.date_range(
                    start='2000-01-01',
                    end='2001-01-01',
                    freq='1d',
                )),
            ),
        ), '2000-01-01', '2001-01-01','1MS', 12),
        (xr.Dataset(
            coords=dict(
                time=("time", pd.date_range(
                    start='2000-01-01',
                    end='2001-01-01',
                    freq='1d',
                )),
            ),
        ), '2000-01-01', '2001-01-01','7d', 52),
        (xr.Dataset(
            coords=dict(
                time=("time", pd.date_range(
                    start='2000-01-01',
                    end='2001-01-01',
                    freq='1d',
                )),
            ),
        ), '2000-01-01', '2001-01-01','2MS', 6),
        (xr.Dataset(
            coords=dict(
                time=("time", pd.date_range(
                    start='2000-01-01',
                    end='2004-01-01',
                    freq='1d',
                )),
            ),
        ), '2000-01-01', '2004-01-01', '1YS', 4),
        (xr.Dataset(
            coords=dict(
                time=("time", pd.date_range(
                    start='2000-01-01',
                    end='2003-12-28',
                    freq='1d',
                )),
            ),
        ), '2000-01-01', '2004-01-01', '1YS', 4),
    ],
)
def test_time_range_seq(ds, start, end, trange, res):
    dso = ds.meta.time_selection_range_seq(start, end, trange)
    assert isinstance(dso, xr.core.groupby.DatasetGroupBy)
    assert len(dso.count()["time_bins"]) == res


@pytest.mark.parametrize(
    "ds, trange, res", [
        (xr.Dataset(
            coords=dict(
                time=("time", pd.date_range(
                    start='1999-12-01',
                    end='2004-01-29',
                    freq='1d',
                )),
            ),
        ), 'month', 12),
        (xr.Dataset(
            coords=dict(
                time=("time", pd.date_range(
                    start='1999-12-01',
                    end='2004-01-29',
                    freq='1d',
                )),
            ),
        ), 'week', 52),
        (xr.Dataset(
            coords=dict(
                time=("time", pd.date_range(
                    start='1999-12-01',
                    end='2004-01-29',
                    freq='1d',
                )),
            ),
        ), 'season', 4),
        (xr.Dataset(
            coords=dict(
                time=("time", pd.date_range(
                    start='1999-12-01',
                    end='2004-01-29',
                    freq='1d',
                )),
            ),
        ), {
            "winter_monsoon": [11, 12, 1, 2, 3],
            "spring_intermonsoon": [4, 5],
            "summer_monsoon": [6, 7, 8],
            "fall_intermonsoon": [9, 10],
        }, 4),
    ],
)
def test_time_range_clim(ds, trange, res):
    dso = ds.meta.time_selection_range_clim(trange)
    assert isinstance(dso, xr.core.groupby.DatasetGroupBy)
    if isinstance(trange, dict):
        trange = "season"
    assert len(dso.count()[trange]) == res


@pytest.mark.parametrize(
    "ds, trange, res", [
        (xr.Dataset(
            coords=dict(
                time=("time", pd.date_range(
                    start='2000-01-01',
                    end='2000-01-03',
                    freq='1h',
                )),
            ),
        ), ["hour", 2.0, 4.0], 6),
        (xr.Dataset(
            coords=dict(
                time=("time", pd.date_range(
                    start='2000-01-01',
                    end='2002-01-03',
                    freq='1m',
                )),
            ),
        ), ["month", 2.0, 4.0], 6),
        (xr.Dataset(
            coords=dict(
                time=("time", pd.date_range(
                    start='1999-01-01',
                    end='2002-01-03',
                    freq='1y',
                )),
            ),
        ), ["year", 2000, 2001], 2),
    ],
)
def test_time_cut(ds, trange, res):
    dso = ds.meta.time_selection_cut(*trange)
    assert isinstance(dso, xr.Dataset)
    assert dso.dims["time"] == res
