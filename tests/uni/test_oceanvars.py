from unittest.mock import MagicMock, patch

import numpy as np
import pandas as pd
import pytest
import xarray as xr

from armoor import ArmoorError
from armoor.oceanvars import OceanVars


class TestOceanVars:

    def setup_method(self):
        """Setup test data"""
        self.lat = np.array([45.0, 46.0])
        self.lon = np.array([2.0, 3.0])
        self.depth = np.array([0, 10, 20])
        self.temp = np.array([[[20.0, 19.0], [18.0, 17.0]],
                             [[19.5, 18.5], [17.5, 16.5]],
                             [[19.0, 18.0], [17.0, 16.0]]])
        self.sal = np.array([[[35.0, 35.1], [35.2, 35.3]],
                            [[35.1, 35.2], [35.3, 35.4]],
                            [[35.2, 35.3], [35.4, 35.5]]])
        self.pres = np.array([[[0.0, 0.0], [0.0, 0.0]],
                             [[10.0, 10.0], [10.0, 10.0]],
                             [[20.0, 20.0], [20.0, 20.0]]])

        self.ds = xr.Dataset({
            'temp': (['depth', 'lat', 'lon'], self.temp),
            'sal': (['depth', 'lat', 'lon'], self.sal),
            'pres': (['depth', 'lat', 'lon'], self.pres),
            'depth': (['depth'], self.depth),
            'lat': (['lat'], self.lat),
            'lon': (['lon'], self.lon)
        })

    def test_sel_temp_direct(self):
        """Test direct selection of temperature"""
        result = self.ds.oceanvars.sel_temp()
        assert result is not None
        np.testing.assert_array_equal(result.values, self.temp)

    def test_sel_sal_direct(self):
        """Test direct selection of salinity"""
        result = self.ds.oceanvars.sel_sal()
        assert result is not None
        np.testing.assert_array_equal(result.values, self.sal)

    def test_sel_pres_direct(self):
        """Test direct selection of pressure"""
        result = self.ds.oceanvars.sel_pres()
        assert result is not None
        np.testing.assert_array_equal(result.values, self.pres)

    def test_sel_pres_from_depth(self):
        """Test calculation of pressure from depth"""
        ds_no_pres = self.ds.drop_vars('pres')
        result = ds_no_pres.oceanvars.sel_pres()
        assert result is not None

    def test_sel_ptemp_computed(self):
        """Test calculation of potential temperature"""
        ds_no_ptemp = self.ds.copy()
        result = ds_no_ptemp.oceanvars.sel_ptemp()
        assert result is not None
        assert result.attrs['standard_name'] == 'sea_water_potential_temperature'
        assert result.attrs['units'] == 'degrees_celsius'

    def test_sel_ptemp_missing_sal(self):
        """Test potential temperature without salinity"""
        ds_no_sal = self.ds.drop_vars('sal')
        result = ds_no_sal.oceanvars.sel_ptemp()
        assert result is None

    def test_sel_sal_from_conductivity(self):
        """sel_sal() must fall back to gsw.SP_from_C when "sal" is missing
        but raw conductivity is present -- e.g. ODAR-decoded towed-CTD
        sections (seasoar/scanfish/...), which only carry "conduct"."""
        import gsw
        conduct = gsw.C_from_SP(self.sal, self.temp, self.pres)
        ds_conduct = self.ds.drop_vars('sal')
        ds_conduct['conduct'] = (['depth', 'lat', 'lon'], conduct)

        result = ds_conduct.oceanvars.sel_sal()

        assert result is not None
        np.testing.assert_allclose(result.values, self.sal, atol=1e-6)
        assert result.attrs['standard_name'] == 'sea_water_salinity'

    def test_sel_sal_missing_conduct_and_temp(self):
        """No salinity, no conductivity: still None, not an error."""
        ds_no_sal = self.ds.drop_vars('sal')
        result = ds_no_sal.oceanvars.sel_sal()
        assert result is None

    def test_sel_cgeo_zero_for_uniform_section(self):
        """Identical T/S/P at every station (no horizontal density
        gradient) must give ~0 geostrophic velocity everywhere -- the
        simplest possible correctness check for `sel_cgeo`, independent of
        hand-computing an expected dynamic-height value."""
        z = np.array([0.0, 10.0, 20.0])
        n_stations = 4
        temp = np.tile(np.array([18.0, 16.0, 14.0])[:, None], (1, n_stations))
        sal = np.tile(np.array([35.5, 35.6, 35.7])[:, None], (1, n_stations))
        pres = np.tile(z[:, None], (1, n_stations))
        ds = xr.Dataset(
            {
                'temp': (['z', 'time'], temp),
                'sal': (['z', 'time'], sal),
                'pres': (['z', 'time'], pres),
            },
            coords={
                'time': pd.date_range('2024-01-01', periods=n_stations, freq='h'),
                'lon': ('time', np.linspace(-5.0, -4.7, n_stations)),
                'lat': ('time', np.full(n_stations, 48.0)),
            },
        )
        cgeo = ds.oceanvars.sel_cgeo(p_ref=0.0)

        assert cgeo is not None
        assert cgeo.dims == ('pair', 'z')
        assert cgeo.sizes['pair'] == n_stations - 1
        assert cgeo.sizes['z'] == len(z)
        assert 'lon' in cgeo.coords and 'lat' in cgeo.coords
        # Not exactly 0: dynamic-height integration carries its own tiny
        # numerical noise even for a perfectly uniform field. Still ~7
        # orders of magnitude below a real geostrophic signal (0.01-1 m/s).
        np.testing.assert_allclose(cgeo.values, 0.0, atol=1e-6)

    def test_sel_cgeo_fewer_than_two_stations(self):
        """A single-station "section" has no pair to compute a velocity
        between -- must return None, not raise."""
        ds = xr.Dataset(
            {'temp': (['z', 'time'], [[18.0], [16.0]])},
            coords={'time': [pd.Timestamp('2024-01-01')], 'lon': ('time', [-5.0]), 'lat': ('time', [48.0])},
        )
        assert ds.oceanvars.sel_cgeo() is None

    def test_sel_ptemp_from_conductivity(self):
        """sel_ptemp() must derive salinity itself (via sel_sal()'s own
        conductivity fallback) instead of requiring "sal" pre-populated in
        the dataset -- regression test for the ordering bug this exposed:
        sel_ptemp() used to check `"sal" in self.ds` directly, which failed
        whenever comp_vars processes "ptemp" before a lazily-derived "sal"
        gets materialized (see armoor.comp.comparison.Comparison.
        compute_oceanvars, which iterates comp_vars in order)."""
        import gsw
        conduct = gsw.C_from_SP(self.sal, self.temp, self.pres)
        ds_conduct = self.ds.drop_vars('sal')
        ds_conduct['conduct'] = (['depth', 'lat', 'lon'], conduct)

        result = ds_conduct.oceanvars.sel_ptemp()

        assert result is not None
        assert result.attrs['standard_name'] == 'sea_water_potential_temperature'

    def test_sel_pdens_computed(self):
        """Test calculation of potential density"""
        result = self.ds.oceanvars.sel_pdens(ref_dens=0)
        assert result is not None
        assert 'pdens' in self.ds
        assert self.ds['pdens'].attrs['units'] == 'kg m-3'

    def test_computed_attrs(self):
        """The computed variables have their own attributes, not those of an input."""
        ds = self.ds.drop_vars("pres")
        ds["sal"].attrs = {"standard_name": "sea_water_salinity", "long_name": "Salinity"}
        ds["temp"].attrs = {"standard_name": "sea_water_temperature"}
        ds["ptemp"] = ds["temp"].assign_attrs(standard_name="sea_water_potential_temperature")
        ds = ds.drop_vars("temp")
        ds["u"] = ds["sal"] * 0 + 0.3
        ds["v"] = ds["sal"] * 0 + 0.4
        expected = {
            "pdens": "sea_water_sigma_theta",
            "sndspeed": "speed_of_sound_in_sea_water",
            "pres": "sea_water_pressure",
            "temp": "sea_water_temperature",
            "cspeed": "sea_water_speed",
        }
        for name, standard_name in expected.items():
            result = ds.copy().oceanvars.sel(name)
            assert result.attrs["standard_name"] == standard_name, name
            assert result.attrs.get("long_name") != "Salinity", name
        result = ds.copy().oceanvars.sel_pdens(ref_dens=1000)
        assert "standard_name" not in result.attrs
        assert result.attrs["reference_pressure"] == "1000 dbar"
        assert ds.copy().oceanvars.sel("cdir").attrs["units"] == "radian"

    def test_sel_pdens_missing_sal(self):
        """Test potential density without salinity"""
        ds_no_sal = self.ds.drop_vars('sal')
        result = ds_no_sal.oceanvars.sel_pdens()
        assert result is None

    def test_sel_sndspeed(self):
        """Test calculation of sound speed"""
        result = self.ds.oceanvars.sel_sndspeed()
        assert result is not None
        assert 'sndspeed' in self.ds
        assert self.ds['sndspeed'].attrs['units'] == 'm s-1'

    def test_sel_sndspeed_missing_temp(self):
        """Test sound speed without temperature"""
        ds_no_temp = self.ds.drop_vars('temp')
        result = ds_no_temp.oceanvars.sel_sndspeed()
        assert result is None

    def test_sel_mld(self):
        """Test calculation of mld"""
        result = self.ds.oceanvars.sel_mld()
        assert result is not None
        assert 'mld' in self.ds
        assert self.ds['mld'].attrs['units'] == 'm'

    def test_sel_mld_missing_sal(self):
        """Test mld  without salinity"""
        ds_no_sal = self.ds.drop_vars('sal')
        result = ds_no_sal.oceanvars.sel_mld()
        assert result is None

    def test_sel_method_routing(self):
        """Test routing of the sel method"""
        # Test with temperature
        result_temp = self.ds.oceanvars.sel('temp')
        assert result_temp is not None
        np.testing.assert_array_equal(result_temp.values, self.temp)

        # Test with salinity
        result_sal = self.ds.oceanvars.sel('sal')
        assert result_sal is not None
        np.testing.assert_array_equal(result_sal.values, self.sal)

    def test_sel_unknown_variable(self):
        """Test selection of an unknown variable raises rather than silently
        returning None -- dispatched via MethodRegistry.call, see
        armoor.dispatch."""
        with pytest.raises(ArmoorError, match="Unknown ocean variable"):
            self.ds.oceanvars.sel('unknown_var')
