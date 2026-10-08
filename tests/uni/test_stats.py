import numpy as np
import pandas as pd
import xarray as xr
import pytest
from scipy.stats import gaussian_kde

from armoor.stats import diff, cdiff, mean, std, bias, rms, crms, pdf


def _make_test_data():
    time = pd.date_range("2020-01-01", periods=4, freq="D")
    dsref = xr.Dataset(
        {"a": (["time"], np.array([1., 2., 3., 4.]))},
        coords={"time": time}
    )
    dsprod = xr.Dataset(
        {"a": (["time"], np.array([0.5, 2., 2.5, 5.]))},
        coords={"time": time}
    )
    return dsref, dsprod


def test_diff_basic():
    dsref, dsprod = _make_test_data()
    out = diff(dsref, dsprod)

    expected = np.array([0.5, 0.0, 0.5, -1.0])
    np.testing.assert_array_almost_equal(out["a"].values, expected)


def test_cdiff_centered():
    dsref, dsprod = _make_test_data()

    # manual centered computation
    ref_center = (np.array([1., 2., 3., 4.]) - 2.5)
    prod_center = (np.array([0.5, 2., 2.5, 5.]) - 2.5)
    expected = ref_center - prod_center

    out = cdiff(dsref, dsprod, dim="time")
    np.testing.assert_array_almost_equal(out["a"].values, expected)


def test_mean():
    dsref, _ = _make_test_data()
    out = mean(dsref, dim="time")

    assert np.isclose(out["a"].item(), 2.5)


def test_std():
    dsref, _ = _make_test_data()
    out = std(dsref, dim="time")

    # std of [1,2,3,4] (population)
    expected = np.std([1., 2., 3., 4.])
    assert np.isclose(out["a"].item(), expected)


def test_bias():
    dsref, dsprod = _make_test_data()
    # (0.5, 0, 0.5, -1) mean = 0
    out = bias(dsref, dsprod, dim="time")

    assert np.isclose(out["a"].item(), 0.0)


def test_rms():
    dsref, dsprod = _make_test_data()

    diffs = np.array([0.5, 0.0, 0.5, -1.0])
    expected = np.sqrt(np.mean(diffs**2))

    out = rms(dsref, dsprod, dim="time")
    assert np.isclose(out["a"].item(), expected)


def test_crms():
    dsref, dsprod = _make_test_data()

    ref_center = np.array([1., 2., 3., 4.]) - 2.5
    prod_center = np.array([0.5, 2., 2.5, 5.]) - 2.5
    cdiffs = ref_center - prod_center
    expected = np.sqrt(np.mean(cdiffs**2))

    out = crms(dsref, dsprod, dim="time")
    assert np.isclose(out["a"].item(), expected)


def test_pdf():
    ds, _ = _make_test_data()
    out = pdf(ds, "a")["a_pdf"]

    arr = np.array([1., 2., 3., 4.])
    bins = np.linspace(0, max(arr), 100)
    kde = gaussian_kde(arr)
    expected = kde.pdf(bins)

    np.testing.assert_array_almost_equal(out, expected)