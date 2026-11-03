import pytest
import numpy as np
import pandas as pd
import xarray as xr
from unittest.mock import MagicMock, patch

from armoor.data.range import process_time_range, process_vertical_range


def test_process_time_range_daily_split():
    time = pd.date_range("2020-01-01", periods=3, freq="D")
    ds = xr.Dataset({"temp": (["time"], [1, 2, 3])}, coords={"time": time})

    result = process_time_range(ds, "D")

    assert "trange" in result.dims
    assert result.sizes["trange"] == 2
    assert "time_range" in result


def test_process_time_range_check_time_range_format():
    time = pd.date_range("2020-01-01", periods=2, freq="D")
    ds = xr.Dataset({"v": (["time"], [10, 20])}, coords={"time": time})

    result = process_time_range(ds, "D")
    tr = result.time_range.values[0]

    assert "_to_" in tr
    assert tr.startswith("20200101T000000")


def test_process_time_range_includes_non_time_vars():
    """
    xarray >=2024 retains trange dimension even on scalar vars.
    Accept either behavior.
    """
    time = pd.date_range("2020-01-01", periods=2, freq="D")
    ds = xr.Dataset({
        "temp": (["time"], [5., 6.]),
        "meta": ([], 42)
    }, coords={"time": time})

    result = process_time_range(ds, "D")

    assert "meta" in result
    # old xarray => (), newer => ('trange',)
    assert result["meta"].dims in [(), ("trange",)]


def test_process_vertical_range_masks_data():
    ds = xr.Dataset(
        {"temp": (["z", "x"], [[1, 2], [3, 4]]),
         "surface": (["x"], [10, 20])},
        coords={"z": [0, 100]}
    )

    res = process_vertical_range(ds, "z", (0, 50))
    expected = np.array([[1., 2.], [np.nan, np.nan]])

    np.testing.assert_array_equal(res["temp"].values, expected)
    assert np.array_equal(res["surface"].values, [10, 20])
    assert res.vertical_range == "0_to_50"


def test_process_vertical_range_mock_compute():
    """
    Ensure .compute() on mask is called and masking applied.
    """
    ds = xr.Dataset(
        {"temp": (["z", "x"], np.ones((2, 2)))},
        coords={"z": [10, 200]}
    )

    # Expected mask result: keep z==10 discard z==200
    fake_mask_result = xr.DataArray(
        np.array([[True, True], [False, False]]),
        dims=["z", "x"]
    )

    # Patch xarray.DataArray.compute globally during mask operations
    with patch("xarray.core.dataarray.DataArray.compute", return_value=fake_mask_result) as mock_compute:
        res = process_vertical_range(ds, "z", (0, 100))

        # Verify compute was called
        mock_compute.assert_called()

        # Row 0 unmasked, row 1 masked
        assert np.all(~np.isnan(res["temp"].values[0]))
        assert np.all(np.isnan(res["temp"].values[1]))

def test_ranges_tfreq_drops_whole_window_trange():
    """A per-time-step subset must not keep the whole-window trange tagged by
    the time colocation: it would win over "time" in the plot labels and give
    all time steps' figures the same name."""
    from armoor.plot import format_time_label
    from armoor.ranges import tfreq

    time = pd.date_range("2024-01-01", periods=3, freq="D")
    ds = xr.Dataset({"sla": (["time"], [1.0, 2.0, 3.0])}, coords={"time": time})
    ds.attrs["trange"] = "[2024-01-01T00:00:00_2024-01-03T00:00:00["

    subsets = tfreq(ds)

    assert [sub.attrs["time"] for sub in subsets] == [
        "2024-01-01T00:00:00",
        "2024-01-02T00:00:00",
        "2024-01-03T00:00:00",
    ]
    assert all("trange" not in sub.attrs for sub in subsets)
    labels = {format_time_label(sub.attrs)[1] for sub in subsets}
    assert len(labels) == 3
    assert "trange" in ds.attrs  # the input is left untouched
