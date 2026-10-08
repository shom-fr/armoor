"""Unit tests for armoor.viewer.store (DatasetStore + _build_entry)."""

import re
import threading

import numpy as np
import pandas as pd
import pytest
import xarray as xr

from armoor.viewer.store import DatasetStore, _build_entry


# ---------------------------------------------------------------------------
# Dataset factory
# ---------------------------------------------------------------------------


def _make_ds():
    """Minimal 4-D dataset with time / depth / lat / lon coords."""
    lons = np.linspace(-10.0, 10.0, 5)
    lats = np.linspace(40.0, 50.0, 4)
    times = pd.date_range("2020-01-01", periods=3, freq="D")
    depths = [0.0, 10.0, 20.0]
    rng = np.random.default_rng(42)
    data = rng.random((3, 3, 4, 5))
    return xr.Dataset(
        {"temp": (("time", "depth", "lat", "lon"), data)},
        coords={"time": times, "depth": depths, "lat": lats, "lon": lons},
    )


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def fresh_store():
    """Return a new DatasetStore independent of the module singleton."""
    return DatasetStore()


# ---------------------------------------------------------------------------
# _build_entry – metadata extraction
# ---------------------------------------------------------------------------


def test_build_entry_assigns_uuid():
    entry = _build_entry("/fake.zarr", "zarr", _make_ds())
    assert re.match(
        r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", entry.id
    )


def test_build_entry_existing_id_preserved():
    entry = _build_entry("/fake.zarr", "zarr", _make_ds(), existing_id="my-fixed-id")
    assert entry.id == "my-fixed-id"


def test_build_entry_variables():
    entry = _build_entry("/fake.zarr", "zarr", _make_ds())
    assert entry.variables == ["temp"]


def test_build_entry_time_values():
    entry = _build_entry("/fake.zarr", "zarr", _make_ds())
    assert len(entry.time_values) == 3
    assert entry.time_values[0].startswith("2020-01-01")


def test_build_entry_depth_values():
    entry = _build_entry("/fake.zarr", "zarr", _make_ds())
    assert entry.depth_values == pytest.approx([0.0, 10.0, 20.0])


def test_build_entry_lon_lat_range():
    entry = _build_entry("/fake.zarr", "zarr", _make_ds())
    assert entry.lon_range == pytest.approx([-10.0, 10.0])
    assert entry.lat_range == pytest.approx([40.0, 50.0])


def test_build_entry_dims():
    entry = _build_entry("/fake.zarr", "zarr", _make_ds())
    assert entry.dims == {"time": 3, "depth": 3, "lat": 4, "lon": 5}


def test_build_entry_no_coords():
    """Dataset with no named coordinates: ranges are None, lists empty."""
    ds = xr.Dataset({"temp": (("y", "x"), np.ones((3, 4)))})
    entry = _build_entry("/fake.zarr", "zarr", ds)
    assert entry.lon_range is None
    assert entry.lat_range is None
    assert entry.time_values == []
    assert entry.depth_values == []


def test_build_entry_path_and_fmt():
    entry = _build_entry("/data/model.zarr", "zarr", _make_ds())
    assert entry.path == "/data/model.zarr"
    assert entry.fmt == "zarr"


# ---------------------------------------------------------------------------
# DatasetStore – basic operations
# ---------------------------------------------------------------------------


def test_store_starts_empty(fresh_store):
    assert fresh_store.list_ids() == []
    assert fresh_store.list_entries() == []


def test_store_get_missing_raises(fresh_store):
    with pytest.raises(KeyError, match="Dataset not found"):
        fresh_store.get("nonexistent-id")


def test_store_get_returns_entry(fresh_store):
    ds = _make_ds()
    entry = _build_entry("/fake.zarr", "zarr", ds)
    fresh_store._store[entry.id] = entry
    assert fresh_store.get(entry.id) is entry


def test_store_list_ids_and_entries(fresh_store):
    ds = _make_ds()
    e1 = _build_entry("/a.zarr", "zarr", ds)
    e2 = _build_entry("/b.zarr", "zarr", ds)
    fresh_store._store[e1.id] = e1
    fresh_store._store[e2.id] = e2

    assert set(fresh_store.list_ids()) == {e1.id, e2.id}
    assert len(fresh_store.list_entries()) == 2


def test_store_close_removes_entry(fresh_store):
    ds = _make_ds()
    entry = _build_entry("/fake.zarr", "zarr", ds)
    fresh_store._store[entry.id] = entry

    fresh_store.close(entry.id)
    assert entry.id not in fresh_store._store


def test_store_close_unknown_is_noop(fresh_store):
    fresh_store.close("does-not-exist")


def test_store_update_replaces_dataset(fresh_store):
    ds = _make_ds()
    entry = _build_entry("/fake.zarr", "zarr", ds)
    fresh_store._store[entry.id] = entry

    ds2 = xr.Dataset({"sal": (("lat", "lon"), np.zeros((4, 5)))})
    updated = fresh_store.update(entry.id, ds2)

    assert updated.id == entry.id
    assert fresh_store.get(entry.id).ds is ds2
    assert fresh_store.get(entry.id).variables == ["sal"]


def test_store_update_missing_raises(fresh_store):
    ds = _make_ds()
    with pytest.raises(KeyError):
        fresh_store.update("nonexistent", ds)


# ---------------------------------------------------------------------------
# Thread safety
# ---------------------------------------------------------------------------


def test_store_concurrent_writes_are_safe(fresh_store):
    """Concurrent registrations must not corrupt the store count."""
    ds = _make_ds()
    errors = []

    def _add(n):
        try:
            entry = _build_entry(f"/{n}.zarr", "zarr", ds)
            with fresh_store._lock:
                fresh_store._store[entry.id] = entry
        except Exception as exc:  # pragma: no cover
            errors.append(exc)

    threads = [threading.Thread(target=_add, args=(i,)) for i in range(20)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert not errors
    assert len(fresh_store.list_ids()) == 20
