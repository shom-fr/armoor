"""Unit tests for armoor.diags.eddies."""
import numpy as np
import xarray as xr

from armoor.diags.eddies import area2radius, compute_vars


# ---------------------------------------------------------------------------
# Eddies
# ---------------------------------------------------------------------------

def test_area2radius():
    ds = xr.Dataset({"vmax_area": ("obs", [np.pi, 4 * np.pi])})
    ds = area2radius(ds)

    np.testing.assert_allclose(ds["vmax_radius"], [1.0, 2.0])
    assert ds["vmax_radius"].attrs["units"] == "km"


class TestComputeVars:

    def test_compute_vars_adds_radius(self):
        ds = xr.Dataset(
            {
                "vmax_area": ("obs", [np.pi]),
            }
        )
        ds = compute_vars(ds)

        assert "vmax_radius" in ds
        np.testing.assert_allclose(ds["vmax_radius"], [1.0])

    def test_compute_vars_keeps_existing_radius(self):
        ds = xr.Dataset(
            {
                "vmax_area": ("obs", [np.pi]),
                "vmax_radius": ("obs", [42.0]),
            }
        )
        ds = compute_vars(ds)

        np.testing.assert_allclose(ds["vmax_radius"], [42.0])
