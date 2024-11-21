import os, glob
import xarray as xr
from armoor.__init__ import ROOTDIR
from armoor.base.open_decode import open_decode, get_paths
import pytest

samples_dir = os.path.join(ROOTDIR, "_samples")

@pytest.mark.parametrize(
    "paths_in", [
        (["*.nc"]),
        #("hycom_[h/temp]*.nc"),
    ],
)
def test_get_paths(paths_in):
    paths_in = [
        os.path.join(samples_dir, path) for path in paths_in
    ]
    paths_out = get_paths(paths_in)
    assert isinstance(paths_out, list)


# class TestSSTFormat:

#     def test_cmems_l4(self):   
#         ncins = glob.glob(
#             os.path.join(samples_dir, "*L4_*.nc")
#         )
#         ds = open_decode(
#             ncins,
#             "cmems_sst_l4",
#         )
#         assert len(ds) == 1
#         ds = ds[0]
#         assert isinstance(ds, xr.Dataset)
#         assert set(["time", "y", "x"]).issubset(ds.dims)
#         assert set(["lon", "lat", "time"]).issubset(ds.coords)
#         assert ds.lon.dims == ("y", "x")
#         assert ds.lat.dims == ("y", "x")
#         assert ds.time.dims == ("time",)
#         assert "ptemp" in ds.data_vars
        
#     def test_cmems_l3(self):   
#         ncins = glob.glob(
#             os.path.join(samples_dir, "*IFR-L3C_*.nc")
#         )
#         ds = open_decode(
#             ncins,
#             "cmems_sst_l3",
#         )
#         assert len(ds) == 1
#         ds = ds[0]
#         assert isinstance(ds, xr.Dataset)
#         assert set(["time", "y", "x"]).issubset(ds.dims)
#         assert set(["lon", "lat", "time"]).issubset(ds.coords)
#         assert ds.lon.dims == ("y", "x")
#         assert ds.lat.dims == ("y", "x")
#         assert ds.time.dims == ("time",)
#         assert "ptemp" in ds.data_vars
        
#     def test_cersat_l3(self):   
#         ncins = glob.glob(
#             os.path.join(samples_dir, "*OSISAF-L3C_*.nc")
#         )
#         ds = open_decode(
#             ncins,
#             "cersat_sst_l3",
#         )
#         assert len(ds) == 1
#         ds = ds[0]
#         assert isinstance(ds, xr.Dataset)
#         assert set(["time", "y", "x"]).issubset(ds.dims)
#         assert set(["lon", "lat", "time"]).issubset(ds.coords)
#         assert ds.lon.dims == ("y", "x")
#         assert ds.lat.dims == ("y", "x")
#         assert ds.time.dims == ("time",)
#         assert "ptemp" in ds.data_vars

# class TestCoraFormat:

#     def test_argo(self):   
#         ncins = glob.glob(
#             os.path.join(samples_dir, "CO_*_PR_PF.nc")
#         )
#         ds = open_decode(
#             ncins,
#             "cora_insitu",
#             platform="argo",
#         )
#         assert len(ds) == 1
#         ds = ds[0]
#         assert isinstance(ds, xr.Dataset)
#         assert set(["z", "time"]).issubset(ds.dims)
#         assert set(["depth", "lon", "lat", "time"]).issubset(ds.coords)
#         assert ds.lon.dims == ("time",)
#         assert ds.lat.dims == ("time",)
#         assert ds.depth.dims == ("time", "z")
        

# class TestCmemsFormat:

#     def test_argo(self):   
#         ncins = glob.glob(
#             os.path.join(samples_dir, "GL_PR_PF_*.nc")
#         )
#         ds = open_decode(
#             ncins,
#             "cmems_insitu",
#             platform="argo",
#         )
#         assert len(ds) == 1
#         ds = ds[0]
#         assert isinstance(ds, xr.Dataset)
#         assert set(["z", "time"]).issubset(ds.dims)
#         assert set(["depth", "lon", "lat", "time"]).issubset(ds.coords)
#         assert ds.lon.dims == ("time",)
#         assert ds.lat.dims == ("time",)
#         assert ds.depth.dims == ("time", "z")
    
#     def test_mooring(self):
#         ncins = glob.glob(
#             os.path.join(samples_dir, "GL_TS_MO_*.nc")
#         )
#         dss = open_decode(
#             ncins,
#             "cmems_insitu",
#             platform="mooring",
#         )
#         assert isinstance(dss, list)
#         assert all([isinstance(ds, xr.Dataset) for ds in dss])
#         assert all([set(["z", "time"]).issubset(ds.dims) for ds in dss])
#         assert all([set(
#             ["depth", "lon", "lat", "time"]
#         ).issubset(ds.coords) for ds in dss])
#         assert all(["time" not in ds.lon.dims for ds in dss])
#         assert all(["time" not in ds.lat.dims for ds in dss])
        
#     def test_drifter(self):
#         ncins = glob.glob(
#             os.path.join(samples_dir, "GL_TS_DB_*.nc")
#         )
#         dss = open_decode(
#             ncins,
#             "cmems_insitu",
#             platform="drifter",
#         )
#         assert isinstance(dss, list)
#         assert all([isinstance(ds, xr.Dataset) for ds in dss])
#         assert all([set(["z", "time"]).issubset(ds.dims) for ds in dss])
#         assert all([set(
#             ["depth", "lon", "lat", "time"]
#         ).issubset(ds.coords) for ds in dss])
#         assert all(["time" in ds.lon.dims for ds in dss])
#         assert all(["time" in ds.lat.dims for ds in dss])
#         assert all(["z" in ds.depth.dims for ds in dss])
        
#     def test_glider(self):
#         ncins = glob.glob(
#             os.path.join(samples_dir, "GL_PR_GL_*.nc")
#         )
#         dss = open_decode(
#             ncins,
#             "cmems_insitu",
#             platform="glider",
#         )
#         assert isinstance(dss, list)
#         assert all([isinstance(ds, xr.Dataset) for ds in dss])
#         assert all([set(["z", "time"]).issubset(ds.dims) for ds in dss])
#         assert all([set(
#             ["depth", "lon", "lat", "time"]
#         ).issubset(ds.coords) for ds in dss])
#         assert all(["time" in ds.lon.dims for ds in dss])
#         assert all(["time" in ds.lat.dims for ds in dss])
#         assert all(["z" in ds.depth.dims for ds in dss])

# class TestModel:
    
#     def test_cmems_model(self):   
#         ncins = [os.path.join(samples_dir, "cmems_glo12.nc")]
#         ds = open_decode(
#             ncins,
#             fmt="model",
#         )
#         print(ds)
#         assert isinstance(ds, xr.Dataset)
#         assert set(["z", "time", "x", "y"]).issubset(ds.dims)
#         assert set(["depth", "time", "lon", "lat"]).issubset(ds.coords)
        
#     def test_hycom_model(self):   
#         ncins = glob.glob(
#             os.path.join(samples_dir, "hycom_*.nc")
#         )
#         ds = open_decode(
#             ncins,
#             fmt="hycom",
#         )
#         assert isinstance(ds, xr.Dataset)
#         assert set(["z", "time", "x", "y"]).issubset(ds.dims)
#         assert set(["depth", "time", "lon", "lat"]).issubset(ds.coords)