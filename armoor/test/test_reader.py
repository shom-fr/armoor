import xarray as xr
import xoa

class TestReader:
    path_CROCO = 'N:\\1144-FE_Shom_Outils_validation_et_bulletins\\REALISATION\\Technique\\old\\Donnees\\Sorties de modeles\\CROCO\\loire.nc'
    path_TOPAZ = 'N:\\1144-FE_Shom_Outils_validation_et_bulletins\\REALISATION\\Technique\\old\\Donnees\\Sorties de modeles\\TOPAZ\\dataset-ran-arc-day-myoceanv2-be_1627999680806.nc'
    path_NEMO = 'N:\\1144-FE_Shom_Outils_validation_et_bulletins\\REALISATION\\Technique\\old\\Donnees\\Sorties de modeles\\NEMO\\global-reanalysis-phy-001-030-monthly_1621524026022.nc'

    mod_CROCO = xr.open_dataset(path_CROCO)
    mod_TOPAZ = xr.open_dataset(path_TOPAZ)
    mod_NEMO = xr.open_dataset(path_NEMO)
    mod_HYCOM = xoa.open_data_sample("hycom.gdp.v.nc")
    mod_HYCOM_h = xoa.open_data_sample("hycom.gdp.h.nc")

    def test_DecodeHYCOM(self):
        mod = self.mod_HYCOM.read.decode(self.mod_HYCOM_h)
        print(mod)
        assert 'lon' in mod.variables

    def test_DecodeCROCO(self):
        mod = self.mod_CROCO.read.decode()
        print(mod)
        assert 'lon' in mod.variables

    def test_DecodeNEMO(self):
        mod = self.mod_NEMO.read.decode()
        print(mod)
        assert 'lon' in mod.variables

    def test_DecodeTOPAZ(self):
        mod = self.mod_TOPAZ.read.decode()
        print(mod)
        assert 'lon' in mod.variables