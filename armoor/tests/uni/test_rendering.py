"""Unit tests for armoor.viewer.rendering (colormap + raster)."""

import io

import numpy as np
import pandas as pd
import pytest
import xarray as xr
from PIL import Image

from armoor.viewer.rendering.colormap import apply_colormap, colormap_strip, resolve_colormap
from armoor.viewer.rendering.raster import _extract_bbox, slice_to_png


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_2d_ds(ny=8, nx=10):
    lons = np.linspace(-10.0, 10.0, nx)
    lats = np.linspace(40.0, 50.0, ny)
    rng = np.random.default_rng(0)
    data = rng.random((ny, nx))
    return xr.Dataset(
        {"sst": (("lat", "lon"), data)},
        coords={"lat": lats, "lon": lons},
    )


def _make_4d_ds(nt=3, nz=3, ny=8, nx=10):
    lons = np.linspace(-10.0, 10.0, nx)
    lats = np.linspace(40.0, 50.0, ny)
    times = pd.date_range("2020-01-01", periods=nt, freq="D")
    depths = [0.0, 10.0, 50.0]
    rng = np.random.default_rng(1)
    data = rng.random((nt, nz, ny, nx))
    return xr.Dataset(
        {"temp": (("time", "depth", "lat", "lon"), data)},
        coords={"time": times, "depth": depths, "lat": lats, "lon": lons},
    )


# ---------------------------------------------------------------------------
# apply_colormap
# ---------------------------------------------------------------------------


def test_apply_colormap_shape():
    data = np.linspace(0.0, 1.0, 20).reshape(4, 5)
    rgba = apply_colormap(data, "viridis", 0.0, 1.0)
    assert rgba.shape == (4, 5, 4)
    assert rgba.dtype == np.uint8


def test_apply_colormap_nan_is_transparent():
    data = np.array([[1.0, np.nan], [0.5, 0.0]])
    rgba = apply_colormap(data, "viridis", 0.0, 1.0)
    assert rgba[0, 1, 3] == 0   # NaN → alpha=0
    assert rgba[0, 0, 3] > 0   # finite → opaque


def test_apply_colormap_cmo_fallback_to_viridis():
    """Unknown cmo name should not raise — falls back to viridis."""
    data = np.ones((3, 3))
    rgba = apply_colormap(data, "cmo.this_does_not_exist", 0.0, 1.0)
    assert rgba.shape == (3, 3, 4)


# ---------------------------------------------------------------------------
# colormap_strip
# ---------------------------------------------------------------------------


def test_colormap_strip_shape():
    strip = colormap_strip("viridis", n=128)
    assert strip.shape == (1, 128, 4)
    assert strip.dtype == np.uint8


# ---------------------------------------------------------------------------
# _extract_bbox
# ---------------------------------------------------------------------------


def test_extract_bbox_with_coords():
    ds = _make_2d_ds()
    da = ds["sst"]
    bbox = _extract_bbox(ds, da)
    assert bbox["west"] == pytest.approx(-10.0)
    assert bbox["east"] == pytest.approx(10.0)
    assert bbox["south"] == pytest.approx(40.0)
    assert bbox["north"] == pytest.approx(50.0)


def test_extract_bbox_fallback_when_no_coords():
    ds = xr.Dataset({"sst": (("y", "x"), np.zeros((4, 5)))})
    da = ds["sst"]
    bbox = _extract_bbox(ds, da)
    assert bbox == {"west": -180.0, "east": 180.0, "south": -90.0, "north": 90.0}


# ---------------------------------------------------------------------------
# slice_to_png
# ---------------------------------------------------------------------------


def _assert_image(data: bytes) -> Image.Image:
    """Assert *data* is a valid PNG or JPEG and return the PIL Image."""
    is_png  = data[:8] == b"\x89PNG\r\n\x1a\n"
    is_jpeg = data[:3] == b"\xff\xd8\xff"
    assert is_png or is_jpeg, "Expected PNG or JPEG magic bytes"
    buf = io.BytesIO(data)
    return Image.open(buf)


def test_slice_to_png_2d_returns_image():
    # No NaN in data → JPEG (RGB); with NaN → PNG (RGBA). Either is valid.
    ds = _make_2d_ds()
    img_bytes, vmin, vmax, bbox = slice_to_png(ds, "sst")
    img = _assert_image(img_bytes)
    assert img.mode in ("RGB", "RGBA")


def test_slice_to_png_output_size():
    ds = _make_2d_ds()
    img_bytes, _, _, _ = slice_to_png(ds, "sst", width=64, height=32)
    img = _assert_image(img_bytes)
    assert img.size == (64, 32)


def test_slice_to_png_vmin_vmax_returned():
    ds = _make_2d_ds()
    _, vmin, vmax, _ = slice_to_png(ds, "sst", vmin=0.1, vmax=0.9)
    assert vmin == pytest.approx(0.1)
    assert vmax == pytest.approx(0.9)


def test_slice_to_png_auto_vmin_vmax():
    data = np.array([[0.2, 0.8], [0.4, 0.6]])
    ds = xr.Dataset({"v": (("lat", "lon"), data)})
    _, vmin, vmax, _ = slice_to_png(ds, "v")
    assert vmin == pytest.approx(0.2)
    assert vmax == pytest.approx(0.8)


def test_slice_to_png_vmin_equals_vmax_gets_bumped():
    """Constant field: vmax should be vmin+1 to avoid division by zero."""
    ds = xr.Dataset({"v": (("lat", "lon"), np.ones((3, 4)))})
    _, vmin, vmax, _ = slice_to_png(ds, "v")
    assert vmax == pytest.approx(vmin + 1.0)


def test_slice_to_png_4d_with_time_and_depth():
    ds = _make_4d_ds()
    img_bytes, _, _, _ = slice_to_png(ds, "temp", time_idx=1, depth_idx=2, width=32, height=16)
    _assert_image(img_bytes)


def test_slice_to_png_bbox_keys():
    ds = _make_2d_ds()
    _, _, _, bbox = slice_to_png(ds, "sst")
    for key in ("west", "east", "south", "north"):
        assert key in bbox


def test_slice_to_png_wrong_dims_raises():
    """Variable with 3 unrecognised dims cannot be reduced to 2-D."""
    ds = xr.Dataset({"v": (("a", "b", "c"), np.ones((2, 3, 4)))})
    with pytest.raises(ValueError, match="expected 2"):
        slice_to_png(ds, "v")
