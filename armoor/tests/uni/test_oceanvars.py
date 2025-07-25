from unittest.mock import MagicMock, patch

import numpy as np
import pytest
import xarray as xr

from armoor.base.oceanvars import OceanVars


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

    def test_sel_pdens_computed(self):
        """Test calculation of potential density"""
        result = self.ds.oceanvars.sel_pdens(ref_dens=0)
        assert result is not None
        assert 'pdens' in self.ds
        assert self.ds['pdens'].attrs['units'] == 'kg/m3'

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
        assert self.ds['sndspeed'].attrs['units'] == 'm/s'

    def test_sel_sndspeed_missing_temp(self):
        """Test sound speed without temperature"""
        ds_no_temp = self.ds.drop_vars('temp')
        result = ds_no_temp.oceanvars.sel_sndspeed()
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
        """Test selection of an unknown variable"""
        result = self.ds.oceanvars.sel('unknown_var')
        assert result is None