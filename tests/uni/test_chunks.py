"""Unit tests for armoor.chunks and its use by armoor.data.load."""

import dask.array as dsa
import numpy as np
import pytest
import xarray as xr

from armoor.chunks import DEFAULT, MAP, POINT, ChunkType, read_chunks, select_chunk_type
from armoor.comp.comparison import get_comparison
from armoor.data.datatype import get_data_type
from armoor.data.load import _chunk_output, save_result


def _lazy(**sizes):
    data = dsa.zeros(tuple(sizes.values()), dtype="f4", chunks=-1)
    return xr.Dataset({"temp": (tuple(sizes), data)})


def _mib(ds, chunks):
    return np.prod([chunks[d] for d in ds.temp.dims]) * 4 / 1024**2


class TestResolve:
    @pytest.mark.parametrize("chunk_type", [DEFAULT, POINT, MAP])
    def test_below_target_and_close_to_it(self, chunk_type):
        ds = _lazy(time=121, z=80, y=700, x=1200)
        chunks = chunk_type.resolve(ds)
        assert chunk_type.target_mb * 0.5 < _mib(ds, chunks) <= chunk_type.target_mb
        for dim in chunk_type.full:
            assert chunks[dim] == ds.sizes[dim]

    def test_point_is_longer_in_time(self):
        ds = _lazy(time=1000, z=80, y=700, x=1200)
        chunks = POINT.resolve(ds)
        assert chunks["time"] > 3 * chunks["x"]

    def test_small_dataset_is_a_single_chunk(self):
        ds = _lazy(time=10, z=5, y=20, x=20)
        assert DEFAULT.resolve(ds) == dict(ds.sizes)

    def test_short_dimension_leaves_room_to_the_others(self):
        wide = POINT.resolve(_lazy(time=2, z=80, y=700, x=1200))
        assert wide["time"] == 2
        assert wide["x"] > POINT.resolve(_lazy(time=1000, z=80, y=700, x=1200))["x"]

    def test_full_dimensions_larger_than_target(self):
        ds = _lazy(time=10, y=200, x=200)
        chunks = ChunkType("tiny", full=("y", "x"), target_mb=0.01).resolve(ds)
        assert chunks == {"time": 1, "y": 200, "x": 200}

    def test_no_sliver_at_the_end(self):
        ds = _lazy(time=121, z=80, y=296, x=292)
        chunks = ChunkType("p", full=("z",), weights={"time": 4}, target_mb=32).resolve(ds)
        for dim, size in ds.sizes.items():
            assert (size % chunks[dim] or chunks[dim]) > chunks[dim] / 2

    def test_unknown_dims_and_empty(self):
        assert DEFAULT.resolve(_lazy(obs=50)) == {"obs": 50}
        assert DEFAULT.resolve(xr.Dataset()) == {}
        assert DEFAULT.resolve(_lazy(time=0, z=3)) == {"time": 0, "z": 3}


class TestSelect:
    def test_priority(self):
        sst, argo = get_data_type("cmems_sst_l4"), get_comparison("comp_argo")
        assert select_chunk_type(argo, sst) is POINT
        assert select_chunk_type(get_comparison("comp_models"), sst) is MAP
        assert select_chunk_type(None, sst) is MAP
        assert select_chunk_type(None, get_data_type("croco")) is DEFAULT
        assert select_chunk_type() is DEFAULT


@pytest.mark.parametrize("func_comp", ["comp_argo", "comp_sst", "data", None])
def test_written_store(tmp_path, monkeypatch, func_comp):
    """The store has the resolved chunks, whatever the input ones, and the same values."""
    monkeypatch.chdir(tmp_path)
    values = np.random.default_rng(0).random((30, 40, 100, 120)).astype("f4")
    ds = xr.Dataset(
        {"temp": (("time", "z", "y", "x"), dsa.from_array(values, chunks=(7, 33, 64, 50)))},
        coords={"lon": (("y", "x"), np.zeros((100, 120), "f4"))},
        attrs={"data_name": "m", "data_ref": "False", "data_type": "ocean_model"},
    )
    out = _chunk_output(ds, func_comp)
    path = save_result(out, "MZ", func_comp)
    res = xr.open_zarr(path)
    chunk_type = {"comp_argo": POINT, "comp_sst": MAP}.get(func_comp, DEFAULT)
    expected = chunk_type.resolve(ds)
    assert res.temp.encoding["chunks"] == tuple(expected[d] for d in res.temp.dims)
    np.testing.assert_array_equal(res.temp.values, values)


def _nc(path, shape, stored, unlimited=True, zlib=False):
    import netCDF4

    with netCDF4.Dataset(path, "w") as nc:
        names = ("time", "s_rho", "eta_rho", "xi_rho")
        for name, size in zip(names, shape):
            nc.createDimension(name, None if unlimited and name == "time" else size)
        kw = {"contiguous": True} if stored is None else {"chunksizes": stored}
        var = nc.createVariable("temp", "f4", names, zlib=zlib, **kw)
        var[:] = np.zeros(shape, "f4")
        nc.createVariable("h", "f4", names[2:])[:] = np.zeros(shape[2:], "f4")
    return str(path)


class TestReadChunks:
    def test_whole_time_step_when_small(self, tmp_path):
        path = _nc(tmp_path / "a.nc", (2, 8, 70, 120), (1, 4, 35, 24))
        assert read_chunks(path) == {"time": 1, "s_rho": 8, "eta_rho": 70, "xi_rho": 120}

    def test_split_along_stored_chunks_above_the_cap(self, tmp_path):
        path = _nc(tmp_path / "b.nc", (1, 8, 70, 120), (1, 4, 35, 24), zlib=True)
        chunks = read_chunks(path, max_mb=8 * 70 * 120 * 4 / 1024**2 / 3)
        assert chunks["time"] == 1
        for dim, stored in (("s_rho", 4), ("eta_rho", 35), ("xi_rho", 24)):
            assert chunks[dim] % stored == 0
        assert np.prod([chunks[d] for d in ("s_rho", "eta_rho", "xi_rho")]) * 4 <= (
            8 * 70 * 120 * 4 / 3
        )
        # The largest dimension is split first.
        assert chunks["xi_rho"] < 120 and chunks["s_rho"] == 8

    def test_stored_time_chunk_is_kept(self, tmp_path):
        path = _nc(tmp_path / "c.nc", (6, 4, 10, 10), (3, 4, 10, 10))
        assert read_chunks(path)["time"] == 3

    def test_contiguous(self, tmp_path):
        path = _nc(tmp_path / "d.nc", (2, 4, 10, 10), None, unlimited=False)
        assert read_chunks(path) == {"time": 1, "s_rho": 4, "eta_rho": 10, "xi_rho": 10}

    def test_no_time_variable(self, tmp_path):
        import netCDF4

        with netCDF4.Dataset(tmp_path / "e.nc", "w") as nc:
            nc.createDimension("y", 3)
            nc.createVariable("h", "f4", ("y",))[:] = 0
        assert read_chunks(str(tmp_path / "e.nc")) == {}
