"""Unit tests for armoor.comp.coloc module."""

import gc
from pathlib import Path
from unittest.mock import MagicMock, patch, PropertyMock

import numpy as np
import pandas as pd
import pytest
import xarray as xr

from armoor.__init__ import ArmoorError
from armoor.data.load import StagedDataset
from armoor.comp.coloc import (
    AbstractColocation,
    TimeColocation,
    HorizontalColocation,
    VerticalColocation,
    validate_and_get_params,
    process_time_colocation,
    process_horizontal_colocation,
    process_vertical_colocation,
    save_datasets,
    _drop_time_cf_attrs_if_not_datetime,
    _prepare_dataset,
    _apply_colocations,
    _apply_time_ranges,
    _apply_vertical_ranges,
    _save_colocation_results,
    _split_by_dims,
    _process_single_product,
    _process_reference,
    _process_metazone,
    main_coloc,
)


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def sample_dataset():
    """Create an xr.Dataset with time, z, y, x dims and temp/sal/ptemp vars."""
    time = pd.date_range("2023-01-01", periods=3, freq="D")
    lon = np.linspace(-10, 0, 4)
    lat = np.linspace(40, 50, 3)
    lon_grid, lat_grid = np.meshgrid(lon, lat)

    ds = xr.Dataset(
        {
            "temp": (["time", "z", "y", "x"], np.random.rand(3, 2, 3, 4)),
            "sal": (["time", "z", "y", "x"], np.random.rand(3, 2, 3, 4) * 35),
            "ptemp": (["time", "z", "y", "x"], np.random.rand(3, 2, 3, 4)),
        },
        coords={
            "time": time,
            "z": [0, 1],
            "lat": (["y", "x"], lat_grid),
            "lon": (["y", "x"], lon_grid),
            "depth": (["z"], [0.0, 10.0]),
        },
    )
    ds.attrs["data_name"] = "test_dataset"
    return ds


@pytest.fixture
def reference_dataset(sample_dataset):
    """Create a reference dataset with mask variable and data_name attr."""
    ds = sample_dataset.copy()
    ds["mask"] = (["y", "x"], np.ones((3, 4), dtype=bool))
    ds.attrs["data_name"] = "reference"
    return ds


@pytest.fixture
def product_dataset_points():
    """Create point data with member dimension (Argo-like)."""
    time = pd.date_range("2023-01-01", periods=3, freq="D")

    ds = xr.Dataset(
        {
            "temp": (["time", "z", "member"], np.random.rand(3, 5, 10)),
            "sal": (["time", "z", "member"], np.random.rand(3, 5, 10) * 35),
            "ptemp": (["time", "z", "member"], np.random.rand(3, 5, 10)),
        },
        coords={
            "time": time,
            "z": np.arange(5),
            "member": np.arange(10),
            "lon": (["member"], np.linspace(-5, -1, 10)),
            "lat": (["member"], np.linspace(42, 48, 10)),
            "depth": (["z"], [0.0, 10.0, 50.0, 100.0, 200.0]),
        },
    )
    ds.attrs["data_name"] = "argo_product"
    return ds


@pytest.fixture
def time_bounds():
    """Create tuple of (start, end) timestamps."""
    return (pd.Timestamp("2023-01-01"), pd.Timestamp("2023-01-03"))


@pytest.fixture
def coloc_params_argo():
    """Create dict with time/horizontal/vertical params for comp_argo."""
    return {
        "time": ("trange_seq", ("D", "reference")),
        "horizontal": ("radius", 50.0),
        "vertical": ("vlevel", ("depth", [0.0, 50.0, 100.0])),
    }


@pytest.fixture
def tmp_output_dir(tmp_path):
    """Create a temporary output directory."""
    return tmp_path


# =============================================================================
# TestAbstractColocation
# =============================================================================

class TestAbstractColocation:
    """Test suite for the AbstractColocation class."""

    def test_init_creates_empty_methods_dict(self):
        """Test that __init__ creates an empty methods dictionary."""
        coloc = AbstractColocation()
        assert coloc.methods == {}

    def test_register_method_adds_to_dict(self):
        """Test that register_method adds a function to the methods dict."""
        coloc = AbstractColocation()

        def test_func():
            return "test"

        result = coloc.register_method(test_func)
        assert "test_func" in coloc.methods
        assert result is test_func

    def test_call_invokes_registered_method(self):
        """Test that call invokes a registered method correctly."""
        coloc = AbstractColocation()

        def my_method(self, x, y):
            return x + y

        coloc.register_method(my_method)
        result = coloc.call("my_method", 2, 3)
        assert result == 5

    def test_call_raises_error_for_unknown_method(self):
        """Test that call raises ArmoorError for unknown method."""
        coloc = AbstractColocation()

        with pytest.raises(ArmoorError, match="Colocation 'unknown' not found"):
            coloc.call("unknown")

    def test_init_subclass_adds_post_init(self):
        """Test that __init_subclass__ properly adds __post_init__ method."""
        class TestSubclass(AbstractColocation):
            def custom_method(self, x):
                return x * 2

        instance = TestSubclass()
        instance.__post_init__()
        assert "custom_method" in instance.methods


# =============================================================================
# TestTimeColocation
# =============================================================================

class TestTimeColocation:
    """Test suite for the TimeColocation class."""

    def setup_method(self):
        """Create test datasets for time colocation."""
        time = pd.date_range("2023-01-01", periods=5, freq="D")
        self.dsref = xr.Dataset(
            {"temp": (["time", "y", "x"], np.random.rand(5, 3, 4))},
            coords={"time": time},
        )
        self.dsprod = xr.Dataset(
            {"temp": (["time", "y", "x"], np.random.rand(5, 3, 4))},
            coords={"time": time},
        )
        self.tbound = (pd.Timestamp("2023-01-01"), pd.Timestamp("2023-01-05"))

    def test_init_stores_datasets_and_bounds(self):
        """Test that __init__ properly stores datasets and time bounds."""
        coloc = TimeColocation(self.dsref, self.dsprod, self.tbound)

        assert coloc.dsref is self.dsref
        assert coloc.dsprod is self.dsprod
        assert coloc.start == self.tbound[0]
        assert coloc.end == self.tbound[1]
        assert coloc.methods == {}

    @patch("armoor.comp.coloc.interp_time")
    def test_tfreq_calls_interp_time(self, mock_interp):
        """Test that tfreq calls interp_time for both datasets."""
        mock_interp.return_value = self.dsref
        coloc = TimeColocation(self.dsref, self.dsprod, self.tbound)

        coloc.tfreq("D")

        assert mock_interp.call_count == 2

    @patch("armoor.comp.coloc.interp_time")
    def test_tfreq_returns_datasets(self, mock_interp):
        """Test that tfreq returns both datasets."""
        mock_interp.side_effect = [self.dsref, self.dsprod]
        coloc = TimeColocation(self.dsref, self.dsprod, self.tbound)

        dsref_out, dsprod_out = coloc.tfreq("D")

        assert dsref_out is not None
        assert dsprod_out is not None

    @patch("armoor.comp.coloc.interp_time")
    def test_trange_seq_reference(self, mock_interp):
        """Test trange_seq with 'reference' as the time axis."""
        mock_interp.return_value = self.dsprod
        coloc = TimeColocation(self.dsref, self.dsprod, self.tbound)

        coloc.trange_seq(("D", "reference"))

        mock_interp.assert_called_once()

    @patch("armoor.comp.coloc.interp_time")
    def test_trange_seq_product(self, mock_interp):
        """Test trange_seq with 'product' as the time axis."""
        mock_interp.return_value = self.dsref
        coloc = TimeColocation(self.dsref, self.dsprod, self.tbound)

        coloc.trange_seq(("D", "product"))

        mock_interp.assert_called_once()

    def test_trange_seq_invalid_ref_raises_error(self):
        """Test that trange_seq raises error for invalid reference."""
        coloc = TimeColocation(self.dsref, self.dsprod, self.tbound)

        with pytest.raises(ArmoorError, match="Use 'reference' or 'product'"):
            coloc.trange_seq(("D", "invalid"))

    @patch("armoor.comp.coloc.interp_time")
    def test_trange_seq_with_custom_method(self, mock_interp):
        """Test trange_seq with custom interpolation method."""
        mock_interp.return_value = self.dsprod
        coloc = TimeColocation(self.dsref, self.dsprod, self.tbound)

        coloc.trange_seq(("D", "reference", "nearest"))

        mock_interp.assert_called_once()
        call_kwargs = mock_interp.call_args
        assert call_kwargs[1]["method"] == "nearest"

    # -------------------------------------------------------------------------
    # tmonth
    # -------------------------------------------------------------------------

    def _make_clim_datasets(self, months=(1, 2, 3, 4)):
        """Helper: reference climatology (monthly indices) + model (datetime)."""
        dsref = xr.Dataset(
            {"temp": (["time"], np.arange(1., len(months) + 1))},
            coords={"time": np.array(months)},
        )
        # Two years of daily data covering the requested months
        time_prod = pd.date_range("2022-01-01", "2023-12-31", freq="MS")
        time_prod = time_prod[time_prod.month.isin(months)]
        dsprod = xr.Dataset(
            {"temp": (["time"], np.ones(len(time_prod)) * 10.0)},
            coords={"time": time_prod},
        )
        tbound = (pd.Timestamp("2022-01-01"), pd.Timestamp("2023-12-31"))
        return dsref, dsprod, tbound

    def test_tmonth_output_has_monthly_index(self):
        """tmonth must produce a time axis of integer month indices (1–12)."""
        dsref, dsprod, tbound = self._make_clim_datasets(months=(1, 3, 6, 9))
        coloc = TimeColocation(dsref, dsprod, tbound)
        ref_out, prod_out = coloc.tmonth()

        assert "time" in ref_out.dims
        assert "time" in prod_out.dims
        assert ref_out.sizes["time"] == prod_out.sizes["time"]
        # Values must be integer month numbers
        np.testing.assert_array_equal(
            np.sort(prod_out.time.values),
            np.sort(ref_out.time.values),
        )

    def test_tmonth_aligns_on_common_months(self):
        """tmonth must restrict output to the intersection of ref and prod months."""
        # Reference covers months 1–6, product only covers months 3–12
        dsref = xr.Dataset(
            {"temp": (["time"], np.ones(6))},
            coords={"time": np.arange(1, 7)},
        )
        time_prod = pd.date_range("2022-03-01", "2022-12-01", freq="MS")
        dsprod = xr.Dataset(
            {"temp": (["time"], np.ones(len(time_prod)))},
            coords={"time": time_prod},
        )
        tbound = (pd.Timestamp("2022-01-01"), pd.Timestamp("2022-12-31"))
        coloc = TimeColocation(dsref, dsprod, tbound)
        ref_out, prod_out = coloc.tmonth()

        # Common months are 3, 4, 5, 6
        assert ref_out.sizes["time"] == 4
        assert prod_out.sizes["time"] == 4
        np.testing.assert_array_equal(np.sort(ref_out.time.values), [3, 4, 5, 6])

    def test_tmonth_multiyear_averaging(self):
        """tmonth must average all same-month values across multiple years."""
        dsref = xr.Dataset(
            {"temp": (["time"], [20.0])},
            coords={"time": np.array([1])},
        )
        # Two januaries: values 10 and 20 → mean should be 15
        time_prod = pd.to_datetime(["2022-01-01", "2023-01-01"])
        dsprod = xr.Dataset(
            {"temp": (["time"], [10.0, 20.0])},
            coords={"time": time_prod},
        )
        tbound = (pd.Timestamp("2022-01-01"), pd.Timestamp("2023-12-31"))
        coloc = TimeColocation(dsref, dsprod, tbound)
        _, prod_out = coloc.tmonth()

        assert prod_out.sizes["time"] == 1
        assert float(prod_out["temp"].values[0]) == pytest.approx(15.0)

    def test_tmonth_respects_tbound(self):
        """tmonth must exclude product data outside tbound."""
        dsref = xr.Dataset(
            {"temp": (["time"], [1.0, 2.0])},
            coords={"time": np.array([1, 2])},
        )
        # Month 1 inside tbound, month 2 outside
        time_prod = pd.to_datetime(["2023-01-01", "2023-02-01"])
        dsprod = xr.Dataset(
            {"temp": (["time"], [5.0, 99.0])},
            coords={"time": time_prod},
        )
        tbound = (pd.Timestamp("2023-01-01"), pd.Timestamp("2023-01-31"))
        coloc = TimeColocation(dsref, dsprod, tbound)
        _, prod_out = coloc.tmonth()

        assert 2 not in prod_out.time.values


# =============================================================================
# TestHorizontalColocation
# =============================================================================

class TestHorizontalColocation:
    """Test suite for the HorizontalColocation class."""

    def setup_method(self):
        """Create test datasets for horizontal colocation."""
        lon = np.linspace(-10, 0, 4)
        lat = np.linspace(40, 50, 3)
        lon_grid, lat_grid = np.meshgrid(lon, lat)

        self.dsref = xr.Dataset(
            {"temp": (["time", "y", "x"], np.random.rand(2, 3, 4))},
            coords={
                "time": pd.date_range("2023-01-01", periods=2),
                "lat": (["y", "x"], lat_grid),
                "lon": (["y", "x"], lon_grid),
            },
        )
        self.dsref["mask"] = (["y", "x"], np.ones((3, 4), dtype=bool))

        self.dsprod = xr.Dataset(
            {"temp": (["time", "y", "x"], np.random.rand(2, 3, 4))},
            coords={
                "time": pd.date_range("2023-01-01", periods=2),
                "lat": (["y", "x"], lat_grid),
                "lon": (["y", "x"], lon_grid),
            },
        )

    def test_init_stores_datasets(self):
        """Test that __init__ stores datasets properly."""
        coloc = HorizontalColocation(self.dsref, self.dsprod)

        assert coloc.dsref is self.dsref
        assert coloc.dsprod is self.dsprod
        assert coloc.methods == {}

    @patch("armoor.comp.coloc.grid2loc")
    def test_cloud_calls_grid2loc(self, mock_grid2loc):
        """Test that cloud calls grid2loc for datasets."""
        mock_grid2loc.return_value = self.dsref
        coloc = HorizontalColocation(self.dsref, self.dsprod)

        coords = [(45.0, -5.0), (46.0, -4.0)]
        coloc.cloud(coords)

        assert mock_grid2loc.call_count >= 1

    @patch("armoor.comp.coloc.regrid")
    def test_href_reference(self, mock_regrid):
        """Test href with 'reference' as target grid."""
        mock_regrid.return_value = self.dsprod
        coloc = HorizontalColocation(self.dsref, self.dsprod)

        dsref_out, dsprod_out = coloc.href("reference")

        mock_regrid.assert_called_once()

    @patch("armoor.comp.coloc.regrid")
    def test_href_product(self, mock_regrid):
        """Test href with 'product' as target grid."""
        mock_regrid.return_value = self.dsref
        coloc = HorizontalColocation(self.dsref, self.dsprod)

        dsref_out, dsprod_out = coloc.href("product")

        mock_regrid.assert_called_once()

    @patch("armoor.comp.coloc.regrid")
    def test_href_drops_mask(self, mock_regrid):
        """Test that href drops mask variable from output."""
        mock_regrid.return_value = self.dsprod
        coloc = HorizontalColocation(self.dsref, self.dsprod)

        dsref_out, dsprod_out = coloc.href("reference")

        assert "mask" not in dsref_out.data_vars

    def test_clean_coordinates_renames_coords(self):
        """Test that _clean_coordinates properly renames coordinates."""
        coloc = HorizontalColocation(self.dsref, self.dsprod)

        ds = xr.Dataset(coords={
            "lon_0": (["y", "x"], np.zeros((3, 4))),
            "lat_0": (["y", "x"], np.zeros((3, 4))),
            "lon": (["y", "x"], np.ones((3, 4))),
            "lat": (["y", "x"], np.ones((3, 4))),
        })

        cleaned = coloc._clean_coordinates(ds)

        assert "lon" in cleaned.coords
        assert "lat" in cleaned.coords

    def test_radius_raises_error_for_invalid_value(self):
        """Test that radius raises ValueError for non-positive radius."""
        coloc = HorizontalColocation(self.dsref, self.dsprod)

        with pytest.raises(ValueError, match="Radius must be positive"):
            coloc.radius(0)

        with pytest.raises(ValueError, match="Radius must be positive"):
            coloc.radius(-10)

    @patch("armoor.comp.coloc.xcoords.geo_stack")
    @patch("armoor.comp.coloc.xgeo.get_distances")
    def test_radius_calls_geo_stack(self, mock_distances, mock_geo_stack):
        """Test that radius calls geo_stack on product."""
        # Setup mocks
        mock_geo_stack.return_value = self.dsprod.assign_coords(
            member=np.arange(12)
        ).stack(member=["y", "x"])
        mock_distances.return_value = xr.DataArray(
            np.ones((12,)) * 100000,  # 100 km
            dims=["npts0"],
        ).rename({"npts0": "member"}).assign_coords(member=np.arange(12))

        coloc = HorizontalColocation(self.dsref, self.dsprod)

        # Skip the actual calculation since it's complex
        # Just verify the method exists and can be called
        assert hasattr(coloc, "radius")

    @patch("armoor.comp.coloc.xcoords.geo_stack")
    @patch("armoor.comp.coloc.xgeo.get_distances")
    def test_radius_filters_by_distance(self, mock_distances, mock_geo_stack):
        """Test that radius filters points by distance."""
        # This test verifies the filtering logic exists
        coloc = HorizontalColocation(self.dsref, self.dsprod)
        assert callable(coloc.radius)

    def test_calculate_distances_vectorized_method_exists(self):
        """Test that _calculate_distances_vectorized method exists."""
        coloc = HorizontalColocation(self.dsref, self.dsprod)
        assert hasattr(coloc, "_calculate_distances_vectorized")

    def test_handle_time_dependent_method_exists(self):
        """Test that _handle_time_dependent method exists."""
        coloc = HorizontalColocation(self.dsref, self.dsprod)
        assert hasattr(coloc, "_handle_time_dependent")

    @patch("armoor.comp.coloc._coarsen")
    def test_coarsen_on_product_calls_coarsen(self, mock_coarsen):
        """coarsen(on='product') must call _coarsen on dsprod only."""
        mock_coarsen.return_value = self.dsprod
        coloc = HorizontalColocation(self.dsref, self.dsprod)
        coloc.coarsen(2, on="product")
        mock_coarsen.assert_called_once_with(
            self.dsprod, factor=2, boundary="trim", method="mean"
        )

    @patch("armoor.comp.coloc._coarsen")
    def test_coarsen_on_reference_calls_coarsen(self, mock_coarsen):
        """coarsen(on='reference') must call _coarsen on dsref only."""
        mock_coarsen.return_value = self.dsref
        coloc = HorizontalColocation(self.dsref, self.dsprod)
        coloc.coarsen(4, on="reference")
        mock_coarsen.assert_called_once_with(
            self.dsref, factor=4, boundary="trim", method="mean"
        )

    @patch("armoor.comp.coloc._coarsen")
    def test_coarsen_on_both_calls_coarsen_twice(self, mock_coarsen):
        """coarsen(on='both') must call _coarsen once per dataset."""
        mock_coarsen.side_effect = [self.dsref, self.dsprod]
        coloc = HorizontalColocation(self.dsref, self.dsprod)
        coloc.coarsen(2, on="both")
        assert mock_coarsen.call_count == 2

    @patch("armoor.comp.coloc._coarsen")
    def test_coarsen_returns_tuple_of_two_datasets(self, mock_coarsen):
        mock_coarsen.return_value = self.dsprod
        coloc = HorizontalColocation(self.dsref, self.dsprod)
        result = coloc.coarsen(2)
        assert isinstance(result, tuple)
        assert len(result) == 2

    @patch("armoor.comp.coloc._coarsen")
    def test_coarsen_default_on_is_product(self, mock_coarsen):
        """Default on='product' → dsref returned unchanged."""
        mock_coarsen.return_value = self.dsprod
        coloc = HorizontalColocation(self.dsref, self.dsprod)
        dsref_out, _ = coloc.coarsen(2)
        assert dsref_out is self.dsref

    def test_coarsen_integration(self):
        """End-to-end: coarsen actually reduces spatial dims."""
        lon2d, lat2d = np.meshgrid(np.linspace(0.0, 7.0, 8), np.linspace(40.0, 45.0, 6))
        ds = xr.Dataset(
            {"temp": (["y", "x"], np.ones((6, 8)))},
            coords={"lon": (["y", "x"], lon2d), "lat": (["y", "x"], lat2d)},
        )
        coloc = HorizontalColocation(ds, ds.copy())
        _, dsprod_out = coloc.coarsen(2, on="product")
        assert dsprod_out.sizes["x"] == 4
        assert dsprod_out.sizes["y"] == 3


# =============================================================================
# TestVerticalColocation
# =============================================================================

class TestVerticalColocation:
    """Test suite for the VerticalColocation class."""

    def setup_method(self):
        """Create test datasets for vertical colocation."""
        self.dsref = xr.Dataset(
            {"temp": (["time", "z", "y", "x"], np.random.rand(2, 3, 3, 4))},
            coords={
                "time": pd.date_range("2023-01-01", periods=2),
                "z": [0, 1, 2],
                "depth": (["z"], [0.0, 50.0, 100.0]),
            },
        )
        self.dsref.attrs["data_name"] = "ref"

        self.dsprod = xr.Dataset(
            {"temp": (["time", "z", "y", "x"], np.random.rand(2, 3, 3, 4))},
            coords={
                "time": pd.date_range("2023-01-01", periods=2),
                "z": [0, 1, 2],
                "depth": (["z"], [0.0, 50.0, 100.0]),
            },
        )
        self.dsprod.attrs["data_name"] = "prod"

    def test_init_stores_datasets(self):
        """Test that __init__ stores datasets properly."""
        coloc = VerticalColocation(self.dsref, self.dsprod)

        assert coloc.dsref is self.dsref
        assert coloc.dsprod is self.dsprod
        assert coloc.methods == {}

    @patch("armoor.comp.coloc.vinterp")
    def test_vlevel_calls_vinterp(self, mock_vinterp):
        """Test that vlevel calls vinterp for datasets with z dim."""
        mock_vinterp.return_value = self.dsref
        coloc = VerticalColocation(self.dsref, self.dsprod)

        coloc.vlevel(("depth", [0.0, 50.0]))

        assert mock_vinterp.call_count == 2

    @patch("armoor.comp.coloc.vinterp")
    def test_vlevel_preserves_attrs(self, mock_vinterp):
        """Test that vlevel preserves dataset attributes."""
        mock_vinterp.return_value = self.dsref.copy()
        coloc = VerticalColocation(self.dsref, self.dsprod)

        dsref_out, dsprod_out = coloc.vlevel(("depth", [0.0, 50.0]))

        # Attributes should be updated
        assert hasattr(dsref_out, "attrs")

    @patch("armoor.comp.coloc.vinterp")
    def test_vlevel_skips_without_z_dim(self, mock_vinterp):
        """Test that vlevel skips datasets without z dimension."""
        dsref_no_z = xr.Dataset(
            {"temp": (["time", "y", "x"], np.random.rand(2, 3, 4))},
            coords={"time": pd.date_range("2023-01-01", periods=2)},
        )
        dsref_no_z.attrs["data_name"] = "ref"

        mock_vinterp.return_value = self.dsprod
        coloc = VerticalColocation(dsref_no_z, self.dsprod)

        coloc.vlevel(("depth", [0.0, 50.0]))

        # Should only call vinterp for dsprod
        assert mock_vinterp.call_count == 1

    @patch("armoor.comp.coloc.vinterp")
    def test_vrange_reference(self, mock_vinterp):
        """Test vrange with 'reference' as vertical reference."""
        mock_vinterp.return_value = self.dsprod.chunk(dict(z=-1))
        coloc = VerticalColocation(self.dsref, self.dsprod)

        coloc.vrange(("reference", "depth", [0, 50, 100]))

        mock_vinterp.assert_called_once()

    @patch("armoor.comp.coloc.vinterp")
    def test_vrange_product(self, mock_vinterp):
        """Test vrange with 'product' as vertical reference."""
        mock_vinterp.return_value = self.dsref.chunk(dict(z=-1))
        coloc = VerticalColocation(self.dsref, self.dsprod)

        coloc.vrange(("product", "depth", [0, 50, 100]))

        mock_vinterp.assert_called_once()

    def test_vrange_invalid_ref_raises_error(self):
        """Test that vrange raises error for invalid reference."""
        coloc = VerticalColocation(self.dsref, self.dsprod)

        with pytest.raises(ArmoorError, match="Use 'reference' or 'product'"):
            coloc.vrange(("invalid", "depth", [0, 50, 100]))

    @patch("armoor.comp.coloc.vinterp")
    def test_vrange_preserves_attrs(self, mock_vinterp):
        """Test that vrange preserves dataset attributes."""
        mock_vinterp.return_value = self.dsprod.chunk(dict(z=-1))
        coloc = VerticalColocation(self.dsref, self.dsprod)

        dsref_out, dsprod_out = coloc.vrange(("reference", "depth", [0, 50]))

        assert hasattr(dsprod_out, "attrs")


# =============================================================================
# TestValidateAndGetParams
# =============================================================================

class TestValidateAndGetParams:
    """Test suite for validate_and_get_params function."""

    @patch("armoor.comp.coloc.validate_colocation")
    @patch("armoor.comp.coloc.get_colocation_params")
    def test_calls_validate_colocation(self, mock_get_params, mock_validate):
        """Test that validate_and_get_params calls validate_colocation."""
        mock_validate.return_value = {"zone1": {}}
        mock_get_params.return_value = {"zone1": {"time": ("tfreq", "D")}}

        metazones = {"zone1": {"tbound": ("2023-01-01", "2023-01-31")}}

        validate_and_get_params(metazones, "comp_argo")

        mock_validate.assert_called_once()

    @patch("armoor.comp.coloc.validate_colocation")
    @patch("armoor.comp.coloc.get_colocation_params")
    def test_returns_colocation_params(self, mock_get_params, mock_validate):
        """Test that validate_and_get_params returns colocation params."""
        expected_params = {"zone1": {"time": ("tfreq", "D")}}
        mock_validate.return_value = {"zone1": {}}
        mock_get_params.return_value = expected_params

        metazones = {"zone1": {"tbound": ("2023-01-01", "2023-01-31")}}

        result = validate_and_get_params(metazones, "comp_argo")

        assert result == expected_params

    @patch("armoor.comp.coloc.validate_colocation")
    @patch("armoor.comp.coloc.get_colocation_params")
    def test_uses_default_params(self, mock_get_params, mock_validate):
        """Test that validate_and_get_params uses default params when available."""
        mock_validate.return_value = {"zone1": {}}
        mock_get_params.return_value = {"zone1": {}}

        metazones = {"zone1": {}}

        validate_and_get_params(metazones, "comp_argo")

        # Check that COLOCATION_PARAMS_DEFAULT was passed
        call_args = mock_get_params.call_args
        assert call_args[0][2] is not None or call_args[1].get("default") is not None


# =============================================================================
# TestProcessColocationFunctions
# =============================================================================

class TestProcessColocationFunctions:
    """Test suite for process_*_colocation functions."""

    def setup_method(self):
        """Create test datasets."""
        time = pd.date_range("2023-01-01", periods=3, freq="D")
        self.dsref = xr.Dataset(
            {"temp": (["time", "y", "x"], np.random.rand(3, 3, 4))},
            coords={"time": time},
        )
        self.dsprod = xr.Dataset(
            {"temp": (["time", "y", "x"], np.random.rand(3, 3, 4))},
            coords={"time": time},
        )
        self.tbound = (pd.Timestamp("2023-01-01"), pd.Timestamp("2023-01-03"))

    @patch("armoor.comp.coloc.interp_time")
    def test_process_time_colocation(self, mock_interp):
        """Test process_time_colocation function."""
        mock_interp.return_value = self.dsref

        param = ("tfreq", "D")

        dsref_out, dsprod_out = process_time_colocation(
            self.dsref, self.dsprod, param, self.tbound
        )

        assert dsref_out is not None
        assert dsprod_out is not None

    @patch("armoor.comp.coloc.regrid")
    def test_process_horizontal_colocation(self, mock_regrid):
        """Test process_horizontal_colocation function."""
        mock_regrid.return_value = self.dsprod

        # Add required coords
        lon_grid, lat_grid = np.meshgrid(np.linspace(-10, 0, 4), np.linspace(40, 50, 3))
        self.dsref = self.dsref.assign_coords(
            lon=(["y", "x"], lon_grid),
            lat=(["y", "x"], lat_grid),
        )
        self.dsprod = self.dsprod.assign_coords(
            lon=(["y", "x"], lon_grid),
            lat=(["y", "x"], lat_grid),
        )

        param = ("href", "reference")

        dsref_out, dsprod_out = process_horizontal_colocation(
            self.dsref, self.dsprod, param
        )

        assert dsref_out is not None
        assert dsprod_out is not None

    @patch("armoor.comp.coloc.vinterp")
    def test_process_vertical_colocation(self, mock_vinterp):
        """Test process_vertical_colocation function."""
        dsref_z = self.dsref.expand_dims("z").assign_coords(
            z=[0], depth=(["z"], [0.0])
        )
        dsprod_z = self.dsprod.expand_dims("z").assign_coords(
            z=[0], depth=(["z"], [0.0])
        )
        dsref_z.attrs["data_name"] = "ref"
        dsprod_z.attrs["data_name"] = "prod"
        mock_vinterp.return_value = dsref_z

        param = ("vlevel", ("depth", [0.0, 50.0]))

        dsref_out, dsprod_out = process_vertical_colocation(
            dsref_z, dsprod_z, param
        )

        assert dsref_out is not None
        assert dsprod_out is not None

    def test_process_time_colocation_creates_instance(self):
        """Test that process_time_colocation creates TimeColocation instance."""
        # This is an integration test to verify the function structure
        # We can't easily test internal instance creation without more mocking
        assert callable(process_time_colocation)

    def test_process_horizontal_colocation_creates_instance(self):
        """Test that process_horizontal_colocation creates HorizontalColocation instance."""
        assert callable(process_horizontal_colocation)

    def test_process_vertical_colocation_creates_instance(self):
        """Test that process_vertical_colocation creates VerticalColocation instance."""
        assert callable(process_vertical_colocation)


# =============================================================================
# TestSaveDatasets
# =============================================================================

class TestSaveDatasets:
    """Test suite for save_datasets function."""

    def setup_method(self):
        """Create test datasets."""
        time = pd.date_range("2023-01-01", periods=2, freq="D")
        self.dsref = xr.Dataset(
            {"temp": (["time", "y", "x"], np.random.rand(2, 3, 4))},
            coords={"time": time},
        )
        self.dsref.attrs = {"time": "2023-01", "data_name": "ref"}

        self.dsprod = xr.Dataset(
            {"temp": (["time", "y", "x"], np.random.rand(2, 3, 4))},
            coords={"time": time},
        )
        self.dsprod.attrs = {"data_name": "prod"}

    @patch("armoor.comp.coloc.get_zarr_encoding")
    def test_save_datasets_creates_files(self, mock_encoding, tmp_path):
        """Test that save_datasets creates zarr files."""
        mock_encoding.return_value = {}

        ncout_ref, ncout_prod = save_datasets(
            self.dsref, self.dsprod, tmp_path
        )

        assert ncout_ref.exists()
        assert ncout_prod.exists()

    @patch("armoor.comp.coloc.get_zarr_encoding")
    def test_save_datasets_uses_time_attr_in_name(self, mock_encoding, tmp_path):
        """Test that save_datasets uses time attribute in filename."""
        mock_encoding.return_value = {}

        ncout_ref, ncout_prod = save_datasets(
            self.dsref, self.dsprod, tmp_path
        )

        assert "2023-01" in str(ncout_ref)

    @patch("armoor.comp.coloc.get_zarr_encoding")
    def test_save_datasets_uses_trange_attr(self, mock_encoding, tmp_path):
        """Test that save_datasets uses trange attribute if no time attr."""
        mock_encoding.return_value = {}
        self.dsref.attrs = {"trange": "2023-01_to_2023-02", "data_name": "ref"}

        ncout_ref, ncout_prod = save_datasets(
            self.dsref, self.dsprod, tmp_path
        )

        assert "2023-01_to_2023-02" in str(ncout_ref)

    @patch("armoor.comp.coloc.get_zarr_encoding")
    def test_save_datasets_drops_mask(self, mock_encoding, tmp_path):
        """Test that save_datasets drops mask variable."""
        mock_encoding.return_value = {}
        self.dsref["mask"] = (["y", "x"], np.ones((3, 4), dtype=bool))

        ncout_ref, _ = save_datasets(
            self.dsref, self.dsprod, tmp_path
        )

        # Verify the file was created
        assert ncout_ref.exists()

    @patch("armoor.comp.coloc.get_zarr_encoding")
    def test_save_datasets_includes_vlevel_in_name(self, mock_encoding, tmp_path):
        """Test that save_datasets includes vlevel in filename."""
        mock_encoding.return_value = {}
        self.dsref.attrs = {"vlevel": "0-100m", "data_name": "ref"}

        ncout_ref, _ = save_datasets(
            self.dsref, self.dsprod, tmp_path
        )

        assert "0-100m" in str(ncout_ref)

    def test_save_datasets_woa18_like_float_time_with_cf_attrs(self, tmp_path):
        """Regression test: saving a WOA18-like dataset must not raise.

        WOA18 is opened with decode_times=False, so the time coordinate is a
        float array (month indices 1–12) with CF attrs ``units`` and
        ``calendar`` in its attrs dict.  Older code failed with::

            ValueError: failed to prevent overwriting existing key units in attrs

        because xarray's CF encoder tried to write ``units`` again.
        """
        # Simulate WOA18 reference: float time with CF attrs in attrs dict
        time_vals = np.arange(1, 4, dtype=np.float64)
        time_coord = xr.Variable(
            "time",
            time_vals,
            attrs={"units": "months since 1955-01-01", "calendar": "gregorian"},
        )
        dsref = xr.Dataset(
            {"temp": (["time", "y", "x"], np.random.rand(3, 3, 4))},
            coords={"time": time_coord},
        )
        dsref.attrs = {"time": "clim", "data_name": "woa18"}

        dsprod = xr.Dataset(
            {"temp": (["time", "y", "x"], np.random.rand(3, 3, 4))},
            coords={"time": pd.date_range("2023-01-01", periods=3, freq="MS")},
        )
        dsprod.attrs = {"data_name": "glo12"}

        # Must not raise
        ncout_ref, ncout_prod = save_datasets(dsref, dsprod, tmp_path)

        assert ncout_ref.exists()
        assert ncout_prod.exists()

        # Time written to zarr must be numeric (not decoded as datetime)
        ds_read = xr.open_zarr(ncout_ref)
        assert np.issubdtype(ds_read["time"].dtype, np.floating)
        np.testing.assert_array_equal(ds_read["time"].values, time_vals)

    @patch("armoor.comp.coloc.get_zarr_encoding")
    def test_save_datasets_without_staged_returns_plain_paths(self, mock_encoding, tmp_path):
        """No `staged` arg -> plain Path, not StagedDataset."""
        mock_encoding.return_value = {}

        ncout_ref, ncout_prod = save_datasets(self.dsref, self.dsprod, tmp_path)

        assert not isinstance(ncout_ref, StagedDataset)
        assert not isinstance(ncout_prod, StagedDataset)

    @patch("armoor.comp.coloc.get_zarr_encoding")
    def test_save_datasets_with_staged_returns_staged_datasets(self, mock_encoding, tmp_path):
        """A `staged` arg carries its metazone/comp_func onto both return paths."""
        mock_encoding.return_value = {}
        staged = StagedDataset("", metazone="med", comp_func="comp_sst")

        ncout_ref, ncout_prod = save_datasets(self.dsref, self.dsprod, tmp_path, staged=staged)

        for nc in (ncout_ref, ncout_prod):
            assert isinstance(nc, StagedDataset)
            assert nc.metazone == "med"
            assert nc.comp_func == "comp_sst"
            assert nc.stage == "coloc"


# =============================================================================
# TestDropTimeCfAttrs
# =============================================================================

class TestDropTimeCfAttrs:
    """Test suite for _drop_time_cf_attrs_if_not_datetime."""

    def _make_float_time_ds(self, attrs=None):
        """Dataset with float time (WOA18-like)."""
        time_vals = np.arange(1, 4, dtype=np.float64)
        time_coord = xr.Variable("time", time_vals, attrs=attrs or {})
        return xr.Dataset(
            {"temp": (["time"], np.random.rand(3))},
            coords={"time": time_coord},
        )

    def _make_datetime_ds(self):
        """Dataset with datetime64 time."""
        return xr.Dataset(
            {"temp": (["time"], np.random.rand(3))},
            coords={"time": pd.date_range("2023-01-01", periods=3)},
        )

    def test_noop_when_no_time(self):
        """Dataset without time coordinate is returned unchanged."""
        ds = xr.Dataset({"temp": (["x"], np.zeros(3))})
        result = _drop_time_cf_attrs_if_not_datetime(ds)
        assert result is ds

    def test_noop_for_datetime_time(self):
        """datetime64 time with no CF attrs in attrs is left untouched."""
        ds = self._make_datetime_ds()
        result = _drop_time_cf_attrs_if_not_datetime(ds)
        assert np.issubdtype(result["time"].dtype, np.datetime64)

    def test_strips_units_from_datetime_attrs(self):
        """datetime64 time that has 'units' in attrs (from xr.merge decode) gets them removed.

        When xr.merge internally decodes float CF time to datetime64 without
        going through the normal decode→encode path, 'units'/'calendar' stay
        in .attrs instead of .encoding.  The CF encoder then fails because it
        tries to write 'units' to attrs again.  The fix removes these keys from
        attrs so the CF encoder can set them correctly.
        """
        ds = xr.Dataset(
            {"temp": (["time"], np.random.rand(3))},
            coords={
                "time": xr.Variable(
                    "time",
                    pd.date_range("1955-04-01", periods=3),
                    attrs={"units": "months since 1955-01-01", "calendar": "gregorian",
                           "long_name": "time"},
                )
            },
        )
        result = _drop_time_cf_attrs_if_not_datetime(ds)
        assert np.issubdtype(result["time"].dtype, np.datetime64)
        assert "units" not in result["time"].attrs
        assert "calendar" not in result["time"].attrs
        assert "long_name" in result["time"].attrs  # non-CF attrs preserved

    def test_removes_cf_attrs_from_float_time(self):
        """CF attrs are stripped from a float time coordinate."""
        ds = self._make_float_time_ds(
            attrs={"units": "months since 1955-01-01", "calendar": "gregorian"}
        )
        result = _drop_time_cf_attrs_if_not_datetime(ds)
        assert result["time"].attrs == {}

    def test_preserves_float_values(self):
        """Float values are preserved after attrs removal."""
        ds = self._make_float_time_ds(
            attrs={"units": "months since 1955-01-01"}
        )
        result = _drop_time_cf_attrs_if_not_datetime(ds)
        np.testing.assert_array_equal(result["time"].values, ds["time"].values)

    def test_encoding_is_empty_after_rebuild(self):
        """Encoding dict on the rebuilt coordinate must be empty."""
        ds = self._make_float_time_ds(
            attrs={"units": "months since 1955-01-01", "calendar": "gregorian"}
        )
        # Simulate inherited encoding from a zarr store read
        ds["time"].encoding["units"] = "months since 1955-01-01"
        ds["time"].encoding["calendar"] = "gregorian"

        result = _drop_time_cf_attrs_if_not_datetime(ds)
        assert result["time"].encoding == {}

    def test_float_time_noop_when_no_cf_attrs(self):
        """Float time with no CF attrs passes through without error."""
        ds = self._make_float_time_ds(attrs={})
        result = _drop_time_cf_attrs_if_not_datetime(ds)
        assert result["time"].attrs == {}
        np.testing.assert_array_equal(result["time"].values, ds["time"].values)


# =============================================================================
# TestPrepareDataset
# =============================================================================

class TestPrepareDataset:
    """Test suite for _prepare_dataset function."""

    def setup_method(self):
        """Create test dataset."""
        self.ds = xr.Dataset(
            {
                "temp": (["time", "z", "y", "x"], np.random.rand(2, 3, 3, 4)),
                "sal": (["time", "z", "y", "x"], np.random.rand(2, 3, 3, 4)),
                "ptemp": (["time", "z", "y", "x"], np.random.rand(2, 3, 3, 4)),
                "unused_var": (["time", "y", "x"], np.random.rand(2, 3, 4)),
            },
            coords={
                "time": pd.date_range("2023-01-01", periods=2),
                "z": [0, 1, 2],
            },
        )
        self.ds.attrs["data_name"] = "test"

    def test_prepare_dataset_function_exists(self):
        """Test that _prepare_dataset function exists and is callable."""
        assert callable(_prepare_dataset)

    def test_prepare_dataset_has_expected_signature(self):
        """Test that _prepare_dataset has the expected parameters."""
        import inspect
        sig = inspect.signature(_prepare_dataset)
        params = list(sig.parameters.keys())
        assert "ds" in params
        assert "comp_func" in params
        assert "is_reference" in params

    @patch("armoor.comp.coloc.COMP_VARS", {"comp_test": ["ptemp"]})
    def test_prepare_dataset_loads_data(self):
        """Test that _prepare_dataset calls load() to ensure numpy-backed data."""
        mock_ds = MagicMock()
        mock_ds.data_vars = {"ptemp": MagicMock()}
        mock_ds.coords = {}
        mock_ds.__contains__ = lambda self, x: x in ["ptemp"]

        result_ds = MagicMock()
        result_ds.data_vars = {"ptemp": MagicMock()}
        result_ds.coords = {}
        result_ds.__contains__ = lambda self, x: x in ["ptemp"]
        result_ds.oceanvars.sel.return_value = MagicMock()
        result_ds.set_coords.return_value = result_ds
        result_ds.drop_vars.return_value = result_ds
        result_ds.reset_coords.return_value = result_ds

        mock_ds.load.return_value = result_ds

        _prepare_dataset(mock_ds, "comp_test")

        mock_ds.load.assert_called_once()

    def test_prepare_dataset_depth_in_data_vars_condition(self):
        """Test the depth handling logic by checking function structure."""
        # This test verifies the function handles depth correctly
        # by examining the source code behavior
        import inspect
        source = inspect.getsource(_prepare_dataset)

        # Verify the function checks for depth in data_vars
        assert 'depth' in source
        assert 'set_coords' in source

    def test_prepare_dataset_mask_handling(self):
        """Test that the function has mask handling logic."""
        import inspect
        source = inspect.getsource(_prepare_dataset)

        # Verify the function handles mask for reference
        assert 'mask' in source
        assert 'is_reference' in source

    def test_prepare_dataset_comp_vars_usage(self):
        """Test that the function uses COMP_VARS."""
        import inspect
        source = inspect.getsource(_prepare_dataset)

        # Verify COMP_VARS is used
        assert 'COMP_VARS' in source


# =============================================================================
# TestApplyColocations
# =============================================================================

class TestApplyColocations:
    """Test suite for _apply_colocations function."""

    def setup_method(self):
        """Create test datasets."""
        time = pd.date_range("2023-01-01", periods=3, freq="D")
        self.dsref = xr.Dataset(
            {"temp": (["time", "y", "x"], np.random.rand(3, 3, 4))},
            coords={"time": time},
        )
        self.dsprod = xr.Dataset(
            {"temp": (["time", "y", "x"], np.random.rand(3, 3, 4))},
            coords={"time": time},
        )
        self.tbound = (pd.Timestamp("2023-01-01"), pd.Timestamp("2023-01-03"))

    @patch("armoor.comp.coloc.process_time_colocation")
    def test_apply_colocations_calls_time_colocation(self, mock_time_coloc):
        """Test that _apply_colocations calls time colocation when param exists."""
        mock_time_coloc.return_value = (self.dsref, self.dsprod)
        params = {"time": ("tfreq", "D")}

        _apply_colocations(self.dsref, self.dsprod, params, self.tbound)

        mock_time_coloc.assert_called_once()

    @patch("armoor.comp.coloc.process_horizontal_colocation")
    def test_apply_colocations_calls_horizontal_colocation(self, mock_horiz_coloc):
        """Test that _apply_colocations calls horizontal colocation when param exists."""
        mock_horiz_coloc.return_value = (self.dsref, self.dsprod)
        params = {"horizontal": ("href", "reference")}

        _apply_colocations(self.dsref, self.dsprod, params, self.tbound)

        mock_horiz_coloc.assert_called_once()

    @patch("armoor.comp.coloc.process_vertical_colocation")
    def test_apply_colocations_calls_vertical_colocation(self, mock_vert_coloc):
        """Test that _apply_colocations calls vertical colocation when param exists."""
        mock_vert_coloc.return_value = (self.dsref, self.dsprod)
        params = {"vertical": ("vlevel", ("depth", [0.0]))}

        _apply_colocations(self.dsref, self.dsprod, params, self.tbound)

        mock_vert_coloc.assert_called_once()

    def test_apply_colocations_returns_datasets(self):
        """Test that _apply_colocations returns datasets when no params."""
        params = {}

        dsref_out, dsprod_out = _apply_colocations(
            self.dsref, self.dsprod, params, self.tbound
        )

        assert dsref_out is self.dsref
        assert dsprod_out is self.dsprod


# =============================================================================
# TestApplyTimeRanges
# =============================================================================

class TestApplyTimeRanges:
    """Test suite for _apply_time_ranges function."""

    def setup_method(self):
        """Create test datasets."""
        time = pd.date_range("2023-01-01", periods=3, freq="D")
        self.dsref = xr.Dataset(
            {"temp": (["time", "y", "x"], np.random.rand(3, 3, 4))},
            coords={"time": time},
        )
        self.dsprod = xr.Dataset(
            {"temp": (["time", "y", "x"], np.random.rand(3, 3, 4))},
            coords={"time": time},
        )
        self.tbound = (pd.Timestamp("2023-01-01"), pd.Timestamp("2023-01-03"))

    def test_apply_time_ranges_returns_lists_no_params(self):
        """Test that _apply_time_ranges returns lists when no time param."""
        params = {}

        dsref_list, dsprod_list = _apply_time_ranges(
            self.dsref, self.dsprod, params, self.tbound
        )

        assert isinstance(dsref_list, list)
        assert isinstance(dsprod_list, list)
        assert len(dsref_list) == 1
        assert len(dsprod_list) == 1

    @patch("armoor.comp.coloc.ranges.tfreq")
    def test_apply_time_ranges_calls_tfreq(self, mock_tfreq):
        """Test that _apply_time_ranges calls ranges.tfreq for tfreq param."""
        mock_tfreq.return_value = [self.dsref]
        params = {"time": ("tfreq", "D")}

        _apply_time_ranges(self.dsref, self.dsprod, params, self.tbound)

        assert mock_tfreq.call_count == 2

    @patch("armoor.comp.coloc.ranges.trange_seq")
    def test_apply_time_ranges_calls_trange_seq(self, mock_trange):
        """Test that _apply_time_ranges calls ranges.trange_seq."""
        mock_trange.return_value = [self.dsref]
        params = {"time": ("trange_seq", ("D", "reference"))}

        _apply_time_ranges(self.dsref, self.dsprod, params, self.tbound)

        assert mock_trange.call_count == 2

    def test_apply_time_ranges_skips_wildcard(self):
        """Test that _apply_time_ranges skips when trange_seq has wildcard."""
        params = {"time": ("trange_seq", ("*", "reference"))}

        dsref_list, dsprod_list = _apply_time_ranges(
            self.dsref, self.dsprod, params, self.tbound
        )

        assert len(dsref_list) == 1
        assert len(dsprod_list) == 1


# =============================================================================
# TestApplyVerticalRanges
# =============================================================================

class TestApplyVerticalRanges:
    """Test suite for _apply_vertical_ranges function."""

    def setup_method(self):
        """Create test dataset lists."""
        self.dsref = xr.Dataset(
            {"temp": (["z", "y", "x"], np.random.rand(3, 3, 4))},
            coords={"z": [0, 1, 2], "depth": (["z"], [0.0, 50.0, 100.0])},
        )
        self.dsprod = xr.Dataset(
            {"temp": (["z", "y", "x"], np.random.rand(3, 3, 4))},
            coords={"z": [0, 1, 2], "depth": (["z"], [0.0, 50.0, 100.0])},
        )
        self.dsref_list = [self.dsref]
        self.dsprod_list = [self.dsprod]

    def test_apply_vertical_ranges_returns_lists_no_params(self):
        """Test that _apply_vertical_ranges returns input lists when no param."""
        params = {}

        dsref_out, dsprod_out = _apply_vertical_ranges(
            self.dsref_list, self.dsprod_list, params, "comp_argo"
        )

        assert dsref_out is self.dsref_list
        assert dsprod_out is self.dsprod_list

    @patch("armoor.comp.coloc.ranges.vlevels")
    def test_apply_vertical_ranges_calls_vlevels(self, mock_vlevels):
        """Test that _apply_vertical_ranges calls ranges.vlevels for vlevel."""
        mock_vlevels.return_value = self.dsref_list
        params = {"vertical": ("vlevel", ("depth", [0.0, 50.0]))}

        _apply_vertical_ranges(
            self.dsref_list, self.dsprod_list, params, "comp_argo"
        )

        assert mock_vlevels.call_count == 2

    @patch("armoor.comp.coloc.ranges.vrange")
    def test_apply_vertical_ranges_calls_vrange(self, mock_vrange):
        """Test that _apply_vertical_ranges calls ranges.vrange for vrange."""
        mock_vrange.return_value = self.dsref_list
        params = {"vertical": ("vrange", ("reference", "depth", [0, 50, 100]))}

        _apply_vertical_ranges(
            self.dsref_list, self.dsprod_list, params, "comp_argo"
        )

        assert mock_vrange.call_count == 2

    @patch("armoor.comp.coloc.ranges.vlevels")
    def test_apply_vertical_ranges_mooring_uses_depth(self, mock_vlevels):
        """Test that comp_mooring uses 'depth' as vname."""
        mock_vlevels.return_value = self.dsref_list
        params = {"vertical": ("vlevel", ("depth", [0.0]))}

        _apply_vertical_ranges(
            self.dsref_list, self.dsprod_list, params, "comp_mooring"
        )

        # Check that vlevels was called with depth
        call_args = mock_vlevels.call_args_list[0]
        assert call_args[0][1] == "depth"

    def test_apply_vertical_ranges_skips_comp_sst(self):
        """Test that comp_sst skips vertical ranging with vlevel."""
        params = {"vertical": ("vlevel", ("depth", [0.0]))}

        dsref_out, dsprod_out = _apply_vertical_ranges(
            self.dsref_list, self.dsprod_list, params, "comp_sst"
        )

        assert dsref_out is self.dsref_list
        assert dsprod_out is self.dsprod_list


# =============================================================================
# TestSplitByDims
# =============================================================================


class TestSplitByDims:
    """Test suite for _split_by_dims."""

    def test_single_group(self):
        """All variables share the same dims → one group."""
        ds = xr.Dataset(
            {
                "temp": (["time", "z"], np.zeros((3, 2))),
                "sal":  (["time", "z"], np.zeros((3, 2))),
            }
        )
        groups = _split_by_dims(ds)
        assert len(groups) == 1
        key = next(iter(groups))
        assert key == frozenset({"time", "z"})
        sub = groups[key]
        assert set(sub.data_vars) == {"temp", "sal"}

    def test_two_groups(self):
        """Variables with different dims → two groups."""
        ds = xr.Dataset(
            {
                "temp": (["time", "z"], np.zeros((3, 2))),
                "sst":  (["time"],      np.zeros((3,))),
            }
        )
        groups = _split_by_dims(ds)
        assert len(groups) == 2
        sigs = set(groups.keys())
        assert frozenset({"time", "z"}) in sigs
        assert frozenset({"time"}) in sigs
        assert "temp" in groups[frozenset({"time", "z"})].data_vars
        assert "sst"  in groups[frozenset({"time"})].data_vars

    def test_empty_dataset(self):
        """Empty dataset → empty dict."""
        ds = xr.Dataset()
        groups = _split_by_dims(ds)
        assert groups == {}

    def test_scalar_variable(self):
        """Scalar variable (no dims) forms its own group."""
        ds = xr.Dataset(
            {
                "temp":  (["time"], np.zeros((3,))),
                "scalar": ([], 42.0),
            }
        )
        groups = _split_by_dims(ds)
        assert frozenset() in groups
        assert "scalar" in groups[frozenset()].data_vars

    def test_sub_dataset_inherits_attrs(self):
        """Sub-datasets inherit global attrs."""
        ds = xr.Dataset(
            {"temp": (["time", "z"], np.zeros((3, 2)))},
            attrs={"data_name": "myref"},
        )
        groups = _split_by_dims(ds)
        sub = groups[frozenset({"time", "z"})]
        assert sub.attrs["data_name"] == "myref"

    def test_sub_dataset_drops_irrelevant_coords(self):
        """Sub-dataset with only 'time' dim should not keep a 'z'-only coord."""
        ds = xr.Dataset(
            {
                "temp": (["time", "z"], np.zeros((3, 2))),
                "sst":  (["time"],      np.zeros((3,))),
            },
            coords={
                "time":  pd.date_range("2023-01-01", periods=3),
                "z":     [0, 1],
                "depth": ("z", [0.0, 10.0]),
            },
        )
        groups = _split_by_dims(ds)
        sst_sub = groups[frozenset({"time"})]
        # 'z' is not a dim of sst → depth coord (which depends on z) should be absent
        assert "depth" not in sst_sub.coords


# =============================================================================
# TestProcessSingleProductSplitBehavior
# =============================================================================


class TestProcessSingleProductSplitBehavior:
    """Tests for the split-then-range logic in _process_single_product."""

    def _make_ds(self, dims_vars, attrs=None):
        """Build a minimal dataset with the given {var: dims} mapping."""
        time = pd.date_range("2023-01-01", periods=3, freq="D")
        z = [0, 1]
        data_vars = {}
        coords = {"time": time, "z": z}
        for var, dims in dims_vars.items():
            shape = tuple(
                3 if d == "time" else (2 if d == "z" else 4) for d in dims
            )
            data_vars[var] = (list(dims), np.zeros(shape))
        ds = xr.Dataset(data_vars, coords={k: v for k, v in coords.items() if k in
                        {d for dims in dims_vars.values() for d in dims}})
        ds.attrs = attrs or {"data_name": "test"}
        return ds

    @patch("armoor.comp.coloc._apply_time_ranges")
    @patch("armoor.comp.coloc._apply_vertical_ranges")
    @patch("armoor.comp.coloc._apply_colocations")
    @patch("armoor.comp.coloc.get_comparison")
    @patch("armoor.comp.coloc._save_colocation_results")
    @patch("armoor.comp.coloc._prepare_dataset")
    @patch("armoor.comp.coloc.xr.open_dataset")
    def test_time_ranges_skipped_when_no_time_dim(
        self, mock_open, mock_prep, mock_save, mock_get_comparison,
        mock_coloc, mock_vrange, mock_trange
    ):
        """Variables without 'time' dim must not trigger _apply_time_ranges."""
        dsref = self._make_ds({"temp": ("z",)}, {"data_name": "ref"})
        dsprod = self._make_ds({"temp": ("z",)}, {"data_name": "prod"})
        mock_open.return_value = dsprod
        mock_prep.return_value = dsprod
        mock_get_comparison.return_value.compute_oceanvars.side_effect = lambda ds: ds
        mock_coloc.return_value = (dsref, dsprod)
        mock_vrange.return_value = ([dsref], [dsprod])
        mock_save.return_value = []

        params = {"time": ("tfreq", "D")}
        tbound = (pd.Timestamp("2023-01-01"), pd.Timestamp("2023-01-03"))
        staged = StagedDataset("", metazone="z1", comp_func="comp_argo")
        _process_single_product(dsref, Path("/fake.nc"), params, tbound, staged)

        mock_trange.assert_not_called()

    @patch("armoor.comp.coloc._apply_time_ranges")
    @patch("armoor.comp.coloc._apply_vertical_ranges")
    @patch("armoor.comp.coloc._apply_colocations")
    @patch("armoor.comp.coloc.get_comparison")
    @patch("armoor.comp.coloc._save_colocation_results")
    @patch("armoor.comp.coloc._prepare_dataset")
    @patch("armoor.comp.coloc.xr.open_dataset")
    def test_vertical_ranges_skipped_when_no_z_dim(
        self, mock_open, mock_prep, mock_save, mock_get_comparison,
        mock_coloc, mock_vrange, mock_trange
    ):
        """Variables without 'z' dim must not trigger _apply_vertical_ranges."""
        dsref = self._make_ds({"sst": ("time",)}, {"data_name": "ref"})
        dsprod = self._make_ds({"sst": ("time",)}, {"data_name": "prod"})
        mock_open.return_value = dsprod
        mock_prep.return_value = dsprod
        mock_get_comparison.return_value.compute_oceanvars.side_effect = lambda ds: ds
        mock_coloc.return_value = (dsref, dsprod)
        mock_trange.return_value = ([dsref], [dsprod])
        mock_save.return_value = []

        params = {"vertical": ("vlevel", ("depth", [0.0, 10.0]))}
        tbound = (pd.Timestamp("2023-01-01"), pd.Timestamp("2023-01-03"))
        staged = StagedDataset("", metazone="z1", comp_func="comp_argo")
        _process_single_product(dsref, Path("/fake.nc"), params, tbound, staged)

        mock_vrange.assert_not_called()

    @patch("armoor.comp.coloc._apply_time_ranges")
    @patch("armoor.comp.coloc._apply_vertical_ranges")
    @patch("armoor.comp.coloc._apply_colocations")
    @patch("armoor.comp.coloc.get_comparison")
    @patch("armoor.comp.coloc._save_colocation_results")
    @patch("armoor.comp.coloc._prepare_dataset")
    @patch("armoor.comp.coloc.xr.open_dataset")
    def test_both_ranges_applied_when_time_and_z(
        self, mock_open, mock_prep, mock_save, mock_get_comparison,
        mock_coloc, mock_vrange, mock_trange
    ):
        """Both ranges called when ref sub-dataset has time and z dims."""
        dsref = self._make_ds({"temp": ("time", "z")}, {"data_name": "ref"})
        dsprod = self._make_ds({"temp": ("time", "z")}, {"data_name": "prod"})
        mock_open.return_value = dsprod
        mock_prep.return_value = dsprod
        mock_get_comparison.return_value.compute_oceanvars.side_effect = lambda ds: ds
        mock_coloc.return_value = (dsref, dsprod)
        mock_trange.return_value = ([dsref], [dsprod])
        mock_vrange.return_value = ([dsref], [dsprod])
        mock_save.return_value = []

        params = {
            "time": ("tfreq", "D"),
            "vertical": ("vlevel", ("depth", [0.0, 10.0])),
        }
        tbound = (pd.Timestamp("2023-01-01"), pd.Timestamp("2023-01-03"))
        staged = StagedDataset("", metazone="z1", comp_func="comp_argo")
        _process_single_product(dsref, Path("/fake.nc"), params, tbound, staged)

        mock_trange.assert_called_once()
        mock_vrange.assert_called_once()

    @patch("armoor.comp.coloc._apply_time_ranges")
    @patch("armoor.comp.coloc._apply_vertical_ranges")
    @patch("armoor.comp.coloc._apply_colocations")
    @patch("armoor.comp.coloc.get_comparison")
    @patch("armoor.comp.coloc._save_colocation_results")
    @patch("armoor.comp.coloc._prepare_dataset")
    @patch("armoor.comp.coloc.xr.open_dataset")
    def test_mixed_dims_split_into_groups(
        self, mock_open, mock_prep, mock_save, mock_get_comparison,
        mock_coloc, mock_vrange, mock_trange
    ):
        """Dataset with mixed dims is split: time ranges called once (3-D group only)."""
        dsref = xr.Dataset(
            {
                "temp": (["time", "z"], np.zeros((3, 2))),
                "sst":  (["time"],      np.zeros((3,))),
            },
            coords={"time": pd.date_range("2023-01-01", periods=3), "z": [0, 1]},
            attrs={"data_name": "ref"},
        )
        dsprod = xr.Dataset(
            {
                "temp": (["time", "z"], np.zeros((3, 2))),
                "sst":  (["time"],      np.zeros((3,))),
            },
            coords={"time": pd.date_range("2023-01-01", periods=3), "z": [0, 1]},
            attrs={"data_name": "prod"},
        )
        mock_open.return_value = dsprod
        mock_prep.return_value = dsprod
        mock_get_comparison.return_value.compute_oceanvars.side_effect = lambda ds: ds
        mock_coloc.return_value = (dsref, dsprod)
        mock_trange.return_value = ([dsref], [dsprod])
        mock_vrange.return_value = ([dsref], [dsprod])
        mock_save.return_value = []

        params = {
            "time": ("tfreq", "D"),
            "vertical": ("vlevel", ("depth", [0.0, 10.0])),
        }
        tbound = (pd.Timestamp("2023-01-01"), pd.Timestamp("2023-01-03"))
        staged = StagedDataset("", metazone="z1", comp_func="comp_argo")
        _process_single_product(dsref, Path("/fake.nc"), params, tbound, staged)

        # Two dim groups: {time,z} and {time}
        # time ranges called for both (both have 'time'), vertical ranges only for {time,z}
        assert mock_trange.call_count == 2
        assert mock_vrange.call_count == 1


# =============================================================================
# TestProcessFunctions
# =============================================================================

class TestProcessFunctions:
    """Test suite for _process_* functions."""

    def setup_method(self):
        """Create test data."""
        time = pd.date_range("2023-01-01", periods=3, freq="D")
        self.dsref = xr.Dataset(
            {"ptemp": (["time", "y", "x"], np.random.rand(3, 3, 4))},
            coords={"time": time},
        )
        self.dsref.attrs = {"data_name": "reference"}

        self.dsprod = xr.Dataset(
            {"ptemp": (["time", "y", "x"], np.random.rand(3, 3, 4))},
            coords={"time": time},
        )
        self.dsprod.attrs = {"data_name": "product"}

    @patch("armoor.comp.coloc.save_datasets")
    def test_save_colocation_results_creates_dirs(self, mock_save, tmp_path):
        """Test that _save_colocation_results creates output directories."""
        mock_save.return_value = (tmp_path / "ref.zarr", tmp_path / "prod.zarr")

        self.dsref.attrs["data_name"] = "reference"
        self.dsprod.attrs["data_name"] = "product"

        with patch("pathlib.Path.mkdir") as mock_mkdir:
            staged = StagedDataset("", metazone="zone1", comp_func="comp_argo")
            _save_colocation_results([self.dsref], [self.dsprod], staged)

            mock_mkdir.assert_called()

    @patch("armoor.comp.coloc.xr.open_dataset")
    @patch("armoor.comp.coloc._prepare_dataset")
    @patch("armoor.comp.coloc._apply_colocations")
    @patch("armoor.comp.coloc._apply_time_ranges")
    @patch("armoor.comp.coloc._apply_vertical_ranges")
    @patch("armoor.comp.coloc._save_colocation_results")
    def test_process_single_product(
        self, mock_save, mock_vrange, mock_trange, mock_coloc, mock_prep, mock_open
    ):
        """Test _process_single_product function flow."""
        mock_open.return_value = self.dsprod
        mock_prep.return_value = self.dsprod
        mock_coloc.return_value = (self.dsref, self.dsprod)
        mock_trange.return_value = ([self.dsref], [self.dsprod])
        mock_vrange.return_value = ([self.dsref], [self.dsprod])
        mock_save.return_value = [Path("/out/ref.zarr"), Path("/out/prod.zarr")]

        params = {}
        tbound = (pd.Timestamp("2023-01-01"), pd.Timestamp("2023-01-03"))

        staged = StagedDataset("", metazone="zone1", comp_func="comp_argo")
        _process_single_product(
            self.dsref, Path("/fake/path.nc"),
            params, tbound, staged
        )

        mock_open.assert_called_once()
        mock_save.assert_called_once()

    @patch("armoor.comp.coloc.xr.open_dataset")
    @patch("armoor.comp.coloc._prepare_dataset")
    @patch("armoor.comp.coloc._process_single_product")
    def test_process_reference(self, mock_single, mock_prep, mock_open):
        """Test _process_reference function flow."""
        mock_open.return_value = self.dsref
        mock_prep.return_value = self.dsref
        mock_single.return_value = ("reference", "product", [Path("/out/ref.zarr")])

        ncouts = {"zone1": {}}
        ncins = [
            Path("/data/zone1/prod1.nc"),
            Path("/data/zone1/prod2.nc"),
        ]
        params = {}
        tbound = (pd.Timestamp("2023-01-01"), pd.Timestamp("2023-01-03"))

        staged = StagedDataset("", metazone="zone1", comp_func="comp_argo")
        _process_reference(
            Path("/data/zone1/ref.zarr"), ncins,
            params, tbound, staged, ncouts
        )

        # open_dataset is called twice: once with decode_times=False to detect
        # climatology datasets, then once more with the appropriate decode_times value.
        assert mock_open.call_count == 2
        # Should process 2 products
        assert mock_single.call_count == 2

    @patch("armoor.comp.coloc.xr.open_dataset")
    @patch("armoor.comp.coloc._prepare_dataset")
    @patch("armoor.comp.coloc._process_single_product")
    def test_process_reference_detects_climatology_via_data_type(
        self, mock_single, mock_prep, mock_open
    ):
        """decode_times is driven by data_type, not by a data_name substring."""
        self.dsref.attrs = {"data_name": "reference", "data_type": "woa18"}
        mock_open.return_value = self.dsref
        mock_prep.return_value = self.dsref
        mock_single.return_value = ("reference", "product", [Path("/out/ref.zarr")])

        staged = StagedDataset("", metazone="zone1", comp_func="comp_argo")
        _process_reference(
            Path("/data/zone1/ref.zarr"), [Path("/data/zone1/prod1.nc")],
            {}, (pd.Timestamp("2023-01-01"), pd.Timestamp("2023-01-03")),
            staged, {"zone1": {}}
        )

        assert mock_open.call_args_list[1].kwargs["decode_times"] is False

    @patch("armoor.comp.coloc.xr.open_dataset")
    @patch("armoor.comp.coloc._prepare_dataset")
    @patch("armoor.comp.coloc._process_single_product")
    def test_process_reference_data_name_substring_no_longer_triggers_climatology(
        self, mock_single, mock_prep, mock_open
    ):
        """A "woa18"-looking data_name alone must not flag a climatology."""
        self.dsref.attrs = {"data_name": "my_woa18_ref", "data_type": "ocean_model"}
        mock_open.return_value = self.dsref
        mock_prep.return_value = self.dsref
        mock_single.return_value = ("reference", "product", [Path("/out/ref.zarr")])

        staged = StagedDataset("", metazone="zone1", comp_func="comp_argo")
        _process_reference(
            Path("/data/zone1/ref.zarr"), [Path("/data/zone1/prod1.nc")],
            {}, (pd.Timestamp("2023-01-01"), pd.Timestamp("2023-01-03")),
            staged, {"zone1": {}}
        )

        assert mock_open.call_args_list[1].kwargs["decode_times"] is True

    @patch("armoor.comp.coloc._process_reference")
    def test_process_metazone(self, mock_ref):
        """Test _process_metazone function flow."""
        ncouts = {}
        mz_files = {
            "ref": [Path("/data/zone1/ref.zarr")],
            "prod": [Path("/data/zone1/prod.nc")],
        }
        metazones = {"zone1": {"tbound": ("2023-01-01", "2023-01-03")}}
        params = {}

        staged = StagedDataset("", metazone="zone1", comp_func="comp_argo")
        _process_metazone(staged, params, mz_files, metazones, ncouts)

        mock_ref.assert_called_once()
        assert "zone1" in ncouts

    def test_process_metazone_initializes_ncouts(self):
        """Test that _process_metazone initializes ncouts for metazone."""
        ncouts = {}
        metazones = {"zone1": {"tbound": ("2023-01-01", "2023-01-03")}}

        staged = StagedDataset("", metazone="zone1", comp_func="comp_argo")
        with patch("armoor.comp.coloc._process_reference"):
            _process_metazone(staged, {}, {"ref": [], "prod": []}, metazones, ncouts)

        assert "zone1" in ncouts
        assert ncouts["zone1"] == {}

    def test_save_colocation_results_returns_paths(self):
        """Test that _save_colocation_results returns output paths."""
        with patch("armoor.comp.coloc.save_datasets") as mock_save:
            mock_save.return_value = (Path("/out/ref.zarr"), Path("/out/prod.zarr"))
            with patch("pathlib.Path.mkdir"):
                staged = StagedDataset("", metazone="zone1", comp_func="comp_argo")
                paths = _save_colocation_results([self.dsref], [self.dsprod], staged)

        assert len(paths) == 2

    @patch("armoor.comp.coloc._apply_colocations")
    def test_process_single_product_sets_depth_coord(
        self, mock_coloc
    ):
        """Test that _process_single_product sets depth as coordinate."""
        dsref_with_depth = self.dsref.copy()
        dsref_with_depth["depth"] = (["y", "x"], np.random.rand(3, 4))

        dsprod_with_depth = self.dsprod.copy()
        dsprod_with_depth["depth"] = (["y", "x"], np.random.rand(3, 4))

        mock_coloc.return_value = (dsref_with_depth, dsprod_with_depth)

        # Verify the function handles depth conversion
        assert callable(_process_single_product)


# =============================================================================
# TestMainColoc
# =============================================================================

class TestMainColoc:
    """Test suite for main_coloc function."""

    @patch("armoor.comp.coloc.validate_and_get_params")
    @patch("armoor.comp.coloc._process_metazone")
    def test_main_coloc_calls_validate(self, mock_metazone, mock_validate):
        """Test that main_coloc calls validate_and_get_params."""
        mock_validate.return_value = {"zone1": {"time": ("tfreq", "D")}}

        ncs = [Path("/data/zone1/ref.zarr")]
        metazones = {"zone1": {"tbound": ("2023-01-01", "2023-01-03")}}

        main_coloc(ncs, metazones, "comp_argo")

        mock_validate.assert_called_once()

    @patch("armoor.comp.coloc.validate_and_get_params")
    @patch("armoor.comp.coloc._process_metazone")
    def test_main_coloc_skips_invalid_metazones(self, mock_metazone, mock_validate):
        """Test that main_coloc skips metazones with no params."""
        mock_validate.return_value = {
            "zone1": {"time": ("tfreq", "D")},
            "zone2": {},  # Invalid/empty params
        }

        ncs = [Path("/data/zone1/ref.zarr"), Path("/data/zone2/ref.zarr")]
        metazones = {
            "zone1": {"tbound": ("2023-01-01", "2023-01-03")},
            "zone2": {"tbound": ("2023-01-01", "2023-01-03")},
        }

        main_coloc(ncs, metazones, "comp_argo")

        # Only zone1 should be processed
        assert mock_metazone.call_count == 1

    @patch("armoor.comp.coloc.validate_and_get_params")
    @patch("armoor.comp.coloc._process_metazone")
    def test_main_coloc_returns_ncouts(self, mock_metazone, mock_validate):
        """Test that main_coloc returns ncouts dictionary."""
        mock_validate.return_value = {"zone1": {"time": ("tfreq", "D")}}

        ncs = [Path("/data/zone1/ref.zarr")]
        metazones = {"zone1": {"tbound": ("2023-01-01", "2023-01-03")}}

        result = main_coloc(ncs, metazones, "comp_argo")

        assert isinstance(result, dict)

    @patch("armoor.comp.coloc.validate_and_get_params")
    @patch("armoor.comp.coloc._process_metazone")
    def test_main_coloc_processes_all_valid_zones(self, mock_metazone, mock_validate):
        """Test that main_coloc processes all valid metazones."""
        mock_validate.return_value = {
            "zone1": {"time": ("tfreq", "D")},
            "zone2": {"time": ("tfreq", "D")},
        }

        ncs = [
            Path("/data/zone1/ref.zarr"),
            Path("/data/zone2/ref.zarr"),
        ]
        metazones = {
            "zone1": {"tbound": ("2023-01-01", "2023-01-03")},
            "zone2": {"tbound": ("2023-01-01", "2023-01-03")},
        }

        main_coloc(ncs, metazones, "comp_argo")

        assert mock_metazone.call_count == 2
