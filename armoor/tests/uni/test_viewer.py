"""Unit tests for armoor.viewer Flask application."""

import numpy as np
import pandas as pd
import pytest
import xarray as xr
from flask import Flask

from armoor.viewer import app as viewer_app
from armoor.viewer.app import create_app
from armoor.viewer.store import _build_entry, store


# ---------------------------------------------------------------------------
# Dataset factory
# ---------------------------------------------------------------------------


def _make_ds(nt=3, nz=3, ny=8, nx=10):
    """4-D dataset (time, depth, lat, lon) with a single 'temp' variable."""
    lons = np.linspace(-10.0, 10.0, nx)
    lats = np.linspace(40.0, 50.0, ny)
    times = pd.date_range("2020-01-01", periods=nt, freq="D")
    depths = [0.0, 10.0, 50.0]
    rng = np.random.default_rng(0)
    data = rng.random((nt, nz, ny, nx))
    return xr.Dataset(
        {"temp": (("time", "depth", "lat", "lon"), data)},
        coords={"time": times, "depth": depths, "lat": lats, "lon": lons},
    )


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def app():
    """Create a Flask test application with testing config."""
    application = create_app(
        test_config={
            "TESTING": True,
            "SECRET_KEY": "test-secret",
        }
    )
    yield application


@pytest.fixture()
def client(app):
    """Return a test client for the Flask application."""
    return app.test_client()


@pytest.fixture(autouse=True)
def clean_store():
    """Wipe the global dataset store before and after every test."""
    for ds_id in store.list_ids():
        store.close(ds_id)
    yield
    for ds_id in store.list_ids():
        store.close(ds_id)


@pytest.fixture()
def loaded_entry():
    """Inject a synthetic DatasetEntry into the global store (no file I/O)."""
    entry = _build_entry("/fake/test.zarr", "zarr", _make_ds())
    with store._lock:
        store._store[entry.id] = entry
    return entry


# ---------------------------------------------------------------------------
# App bootstrap
# ---------------------------------------------------------------------------


def test_create_app_returns_flask_instance(app):
    assert isinstance(app, Flask)
    assert app.config["TESTING"] is True


def test_index_returns_200(client):
    response = client.get("/")
    assert response.status_code == 200


def test_basemap_tile_returns_jpeg(client):
    """Basemap falls back to a solid dark tile when no Blue Marble image is present."""
    response = client.get("/basemap/geo/1/0/0.png")
    assert response.status_code == 200
    assert response.content_type == "image/jpeg"
    assert response.data[:2] == b"\xff\xd8"


# ---------------------------------------------------------------------------
# GET /api/config
# ---------------------------------------------------------------------------


def test_config_defaults_to_auto_render_mode(client):
    response = client.get("/api/config")
    assert response.status_code == 200
    assert response.get_json() == {"render_mode": "auto"}


def test_create_app_render_mode_override(monkeypatch):
    monkeypatch.delenv("ARMOOR_VIEWER_RENDER_MODE", raising=False)
    application = create_app(
        test_config={"TESTING": True}, render_mode="2d",
    )
    client = application.test_client()
    response = client.get("/api/config")
    assert response.get_json() == {"render_mode": "2d"}


# ---------------------------------------------------------------------------
# CLI: --render-mode
# ---------------------------------------------------------------------------


def test_cli_parses_render_mode(monkeypatch):
    captured = {}

    def fake_serve(**kwargs):
        captured.update(kwargs)

    monkeypatch.setattr(viewer_app, "serve", fake_serve)
    monkeypatch.setattr("sys.argv", ["armoor-viewer", "--render-mode", "2d"])
    viewer_app.main()
    assert captured["render_mode"] == "2d"


def test_cli_render_mode_defaults_to_none(monkeypatch):
    """No --render-mode flag → serve() receives None, config.py's env-based default applies."""
    captured = {}

    def fake_serve(**kwargs):
        captured.update(kwargs)

    monkeypatch.setattr(viewer_app, "serve", fake_serve)
    monkeypatch.setattr("sys.argv", ["armoor-viewer"])
    viewer_app.main()
    assert captured["render_mode"] is None


# ---------------------------------------------------------------------------
# POST /api/datasets  – validation
# ---------------------------------------------------------------------------


def test_post_datasets_missing_path_returns_400(client):
    response = client.post("/api/datasets", json={"fmt": "zarr"})
    assert response.status_code == 400
    data = response.get_json()
    assert "error" in data
    assert "path" in data["error"].lower()


# ---------------------------------------------------------------------------
# GET /api/datasets
# ---------------------------------------------------------------------------


def test_list_datasets_empty(client):
    response = client.get("/api/datasets")
    assert response.status_code == 200
    assert response.get_json() == []


def test_list_datasets_returns_loaded_entries(client, loaded_entry):
    response = client.get("/api/datasets")
    assert response.status_code == 200
    items = response.get_json()
    assert len(items) == 1
    assert items[0]["id"] == loaded_entry.id
    assert items[0]["variables"] == ["temp"]


# ---------------------------------------------------------------------------
# DELETE /api/datasets/<id>
# ---------------------------------------------------------------------------


def test_delete_dataset(client, loaded_entry):
    response = client.delete(f"/api/datasets/{loaded_entry.id}")
    assert response.status_code == 200
    data = response.get_json()
    assert data["id"] == loaded_entry.id
    assert loaded_entry.id not in store._store


def test_delete_dataset_not_found(client):
    response = client.delete("/api/datasets/does-not-exist")
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# GET /api/datasets/<id>/metadata
# ---------------------------------------------------------------------------


def test_get_metadata(client, loaded_entry):
    response = client.get(f"/api/datasets/{loaded_entry.id}/metadata")
    assert response.status_code == 200
    data = response.get_json()
    assert data["id"] == loaded_entry.id
    assert "temp" in data["variables"]
    assert "var_info" in data
    assert "dims" in data["var_info"]["temp"]


def test_get_metadata_not_found(client):
    response = client.get("/api/datasets/bad-id/metadata")
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# GET /api/datasets/<id>/tile
# ---------------------------------------------------------------------------


def test_get_tile_missing_variable(client, loaded_entry):
    response = client.get(f"/api/datasets/{loaded_entry.id}/tile")
    assert response.status_code == 400
    assert "variable" in response.get_json()["error"].lower()


def test_get_tile_unknown_variable(client, loaded_entry):
    response = client.get(f"/api/datasets/{loaded_entry.id}/tile?variable=no_such_var")
    assert response.status_code == 400


def test_get_tile_not_found(client):
    response = client.get("/api/datasets/bad-id/tile?variable=temp")
    assert response.status_code == 404


def test_get_tile_renders_image(client, loaded_entry):
    response = client.get(
        f"/api/datasets/{loaded_entry.id}/tile"
        "?variable=temp&time_idx=0&depth_idx=0&width=32&height=16"
    )
    assert response.status_code == 200
    # PNG when NaN/land-mask present, JPEG otherwise — both are valid.
    assert response.content_type in ("image/png", "image/jpeg")


def test_get_tile_exposes_bbox_headers(client, loaded_entry):
    response = client.get(
        f"/api/datasets/{loaded_entry.id}/tile?variable=temp&width=16&height=8"
    )
    assert response.status_code == 200
    for header in ("X-Bbox-West", "X-Bbox-East", "X-Bbox-South", "X-Bbox-North"):
        assert header in response.headers


def test_get_tile_exposes_vmin_vmax_headers(client, loaded_entry):
    response = client.get(
        f"/api/datasets/{loaded_entry.id}/tile?variable=temp&width=16&height=8"
    )
    assert "X-Vmin" in response.headers
    assert "X-Vmax" in response.headers


# ---------------------------------------------------------------------------
# GET /api/datasets/<id>/timeseries
# ---------------------------------------------------------------------------


def test_get_timeseries(client, loaded_entry):
    response = client.get(
        f"/api/datasets/{loaded_entry.id}/timeseries"
        "?variable=temp&lon=0.0&lat=45.0&depth_idx=0"
    )
    assert response.status_code == 200
    data = response.get_json()
    assert data["variable"] == "temp"
    assert len(data["values"]) == 3   # 3 time steps
    assert len(data["times"]) == 3


def test_get_timeseries_missing_lon_lat(client, loaded_entry):
    response = client.get(
        f"/api/datasets/{loaded_entry.id}/timeseries?variable=temp"
    )
    assert response.status_code == 400


def test_get_timeseries_missing_variable(client, loaded_entry):
    response = client.get(
        f"/api/datasets/{loaded_entry.id}/timeseries?lon=0&lat=45"
    )
    assert response.status_code == 400


def test_get_timeseries_not_found(client):
    response = client.get("/api/datasets/bad-id/timeseries?variable=temp&lon=0&lat=45")
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# GET /api/datasets/<id>/point
# ---------------------------------------------------------------------------


def test_get_point(client, loaded_entry):
    response = client.get(
        f"/api/datasets/{loaded_entry.id}/point"
        "?variable=temp&lon=0.0&lat=45.0&time_idx=0&depth_idx=0"
    )
    assert response.status_code == 200
    data = response.get_json()
    assert data["variable"] == "temp"
    assert "value" in data
    assert "lon" in data and "lat" in data


def test_get_point_missing_variable(client, loaded_entry):
    response = client.get(
        f"/api/datasets/{loaded_entry.id}/point?lon=0&lat=45"
    )
    assert response.status_code == 400


def test_get_point_not_found(client):
    response = client.get("/api/datasets/bad-id/point?variable=temp&lon=0&lat=45")
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# GET /api/datasets/<id>/section
# ---------------------------------------------------------------------------


def test_get_section(client, loaded_entry):
    response = client.get(
        f"/api/datasets/{loaded_entry.id}/section"
        "?variable=temp&lon1=-5&lat1=42&lon2=5&lat2=48&time_idx=0&n_points=10"
    )
    assert response.status_code == 200
    data = response.get_json()
    assert data["variable"] == "temp"
    assert len(data["values"]) == 3     # 3 depth levels
    assert len(data["values"][0]) == 10  # 10 section points


def test_get_section_missing_variable(client, loaded_entry):
    response = client.get(
        f"/api/datasets/{loaded_entry.id}/section"
        "?lon1=-5&lat1=42&lon2=5&lat2=48"
    )
    assert response.status_code == 400


def test_get_section_not_found(client):
    response = client.get(
        "/api/datasets/bad-id/section?variable=temp&lon1=0&lat1=40&lon2=5&lat2=45"
    )
    assert response.status_code == 404
