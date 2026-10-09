"""Tests of the decoding of the XIOS outputs of CROCO (fmt="croco_xios").

The XIOS outputs are synthetic files with the structure of the outputs of
CROCO with XIOS: dimensions ``x``/``y`` for a file on a single domain,
``x_<domain>``/``y_<domain>`` otherwise, ``time_counter``, coordinates
``nav_lon_<domain>``, extractions of sloop ``<zone>_<T|U|V>`` with the faces
of their rho cells.

On a grid of ``NX`` x ``NY`` rho points, the u face ``p`` (east face of the
rho cell ``p``) has the value ``p + 0.5`` and the v face ``q`` (north face of
the rho cell ``q``) the value ``q + 0.5``: once averaged on the rho points,
u is the xi index and v the eta index of the rho point.
"""

import numpy as np
import pandas as pd
import pytest
import xarray as xr

from armoor import ArmoorError
from armoor.data.open_decode import (
    _croco_s_curves,
    get_decoder,
    open_decode,
    open_decode_croco,
    open_decode_croco_xios,
)

NX, NY, NZ = 6, 5, 3
LON0, LAT0, DLON, DLAT = 10.0, 40.0, 0.1, 0.1
THETA_S, THETA_B, HC = 5.0, 0.4, 10.0
SC_R = (np.arange(1, NZ + 1) - NZ - 0.5) / NZ
TIME_UNITS = "seconds since 1900-01-01 00:00:00"


def grid_lonlat(xi, eta):
    """Coordinates of the (fractional) xi and eta indices of the grid."""
    xi, eta = np.meshgrid(xi, eta)
    return LON0 + DLON * xi, LAT0 + DLAT * eta


def bathy():
    xi, eta = np.meshgrid(np.arange(NX), np.arange(NY))
    return 50.0 + xi + 2.0 * eta


def zeta_values(times):
    return 0.1 * np.arange(1, len(times) + 1)[:, None, None] * np.ones((len(times), NY, NX))


def xios_dataset(name, times, domains, fields, vertical="attrs"):
    """Make an XIOS output.

    Parameters
    ----------
    name : str
        XIOS file id.
    times : list of str
    domains : dict
        ``{domain: (loc, (i0, ni), (j0, nj))}``: 0-based ranges of the points
        of the domain in the whole grid, ``loc`` in rho, u, v. A domain None
        gives the ``x`` and ``y`` dimensions.
    fields : dict
        ``{domain: [field names]}``.
    vertical : {"attrs", "fields", None}
        Parameters of the vertical coordinate as global attributes of CROCO
        or as fields written by XIOS (static fields of sloop), or none.
    """
    seconds = (pd.to_datetime(times) - pd.Timestamp("1900-01-01")).total_seconds().values
    nt = len(times)
    ds = xr.Dataset(
        coords={
            "time_counter": ("time_counter", seconds, {"units": TIME_UNITS, "axis": "T"}),
            "s_rho": ("s_rho", SC_R, {"name": "s_rho"}),
        }
    )
    ds["time_instant"] = ("time_counter", seconds, {"units": TIME_UNITS})
    ds["time_counter_bounds"] = (("time_counter", "axis_nbounds"), np.stack([seconds] * 2, axis=1))
    zeta = zeta_values(times)
    for domain, (loc, (i0, ni), (j0, nj)) in domains.items():
        suffix = f"_{domain}" if domain else ""
        xdim, ydim = f"x{suffix}", f"y{suffix}"
        xi, eta = np.arange(i0, i0 + ni, dtype="d"), np.arange(j0, j0 + nj, dtype="d")
        if loc == "u":
            xi = xi + 0.5
        elif loc == "v":
            eta = eta + 0.5
        lon, lat = grid_lonlat(xi, eta)
        ds[f"nav_lon{suffix}"] = ((ydim, xdim), lon, {"units": "degrees_east"})
        ds[f"nav_lat{suffix}"] = ((ydim, xdim), lat, {"units": "degrees_north"})
        ds = ds.set_coords([f"nav_lon{suffix}", f"nav_lat{suffix}"])
        box = (slice(j0, j0 + nj), slice(i0, i0 + ni))
        for field in fields.get(domain, []):
            if field in ("u", "v"):
                values = xi if field == "u" else eta[:, None]
                values = np.broadcast_to(values, (nt, NZ, nj, ni))
            elif field in ("u_surf", "v_surf"):
                values = xi if field == "u_surf" else eta[:, None]
                values = np.broadcast_to(values, (nt, nj, ni))
                ds[field] = (("time_counter", ydim, xdim), values.astype("f4"))
                continue
            elif field == "zeta":
                ds[field] = (("time_counter", ydim, xdim), zeta[(slice(None),) + box])
                continue
            elif field in ("h", "lon_rho"):
                values = bathy()[box] if field == "h" else lon
                ds[field] = ((ydim, xdim), values)
                continue
            elif field == "angle":
                ds[field] = ((ydim, xdim), np.full((nj, ni), np.pi / 2))
                continue
            elif field == "w":
                ds[field] = (("time_counter", "s_w", ydim, xdim), np.ones((nt, NZ + 1, nj, ni)))
                continue
            else:  # temp, salt: 10 + level index
                values = np.broadcast_to(10.0 + np.arange(NZ)[:, None, None], (nt, NZ, nj, ni))
            ds[field] = (("time_counter", "s_rho", ydim, xdim), values.astype("f4"))
    ds.attrs["name"] = name
    ds.attrs["description"] = "Created by xios"
    if vertical == "attrs":
        ds.attrs.update(theta_s=THETA_S, theta_b=THETA_B, hc=HC, VertCoordType="NEW")
    elif vertical == "fields":
        ds["hc"] = HC
        ds["theta_s"] = THETA_S
        ds["theta_b"] = THETA_B
        ds["Vtransform"] = 2.0
        ds["Cs_rho"] = ("s_rho", _croco_s_curves(SC_R, THETA_S, THETA_B, True))
    return ds


def write(ds, path):
    ds.to_netcdf(path, unlimited_dims=["time_counter"])
    return str(path)


def write_grid(path, angle=0.0):
    lon, lat = grid_lonlat(np.arange(NX, dtype="d"), np.arange(NY, dtype="d"))
    dims = ("eta_rho", "xi_rho")
    ds = xr.Dataset(
        {
            "h": (dims, bathy()),
            "angle": (dims, np.full((NY, NX), angle)),
            "mask_rho": (dims, np.ones((NY, NX))),
            "lon_rho": (dims, lon),
            "lat_rho": (dims, lat),
        }
    )
    return write_netcdf(ds, path)


def write_netcdf(ds, path):
    ds.to_netcdf(path)
    return str(path)


#: Domains of the whole grid, in a file on several domains
WHOLE = {
    "rho": ("rho", (0, NX), (0, NY)),
    "u": ("u", (0, NX - 1), (0, NY)),
    "v": ("v", (0, NX), (0, NY - 1)),
}
#: Rho points of the whole grid, in a file on a single domain
SINGLE = {None: ("rho", (0, NX), (0, NY))}
DAY1 = ["2017-01-01 00:00", "2017-01-01 12:00"]
DAY2 = ["2017-01-02 00:00", "2017-01-02 12:00"]


def expected_depth(h, zeta):
    """Positive depth of the rho levels, surface first (set_depth.F, NEW_S_COORD)."""
    cs = _croco_s_curves(SC_R, THETA_S, THETA_B, True)
    hinv = 1.0 / (h + HC)
    z0 = HC * SC_R[:, None, None] + cs[:, None, None] * h
    z = z0 * h * hinv + zeta * (1.0 + z0 * hinv)
    return -z[::-1]


@pytest.fixture
def whole_grid_files(tmp_path):
    """Outputs on the whole grid: a TS file on a single domain, a UV file on
    the rho, u and v domains, over two days, and the grid file."""
    files = []
    for day, times in (("20170101", DAY1), ("20170102", DAY2)):
        ts = xios_dataset("MED_inst_TS", times, SINGLE, {None: ["temp", "salt", "zeta"]})
        uv = xios_dataset("MED_inst_UV", times, WHOLE, {"u": ["u"], "v": ["v"]})
        files.append(write(ts, tmp_path / f"MED_inst_TS_{day}00-{day}23.nc"))
        files.append(write(uv, tmp_path / f"MED_inst_UV_{day}00-{day}23.nc"))
    files.append(write_grid(tmp_path / "croco_grd.nc"))
    return files


class TestOpenDecodeCrocoXios:
    """Tests of open_decode_croco_xios."""

    def test_dispatch(self, whole_grid_files):
        """fmt="croco_xios" uses the XIOS decoder, also through the registry."""
        ds = open_decode_croco(whole_grid_files, fmt="croco_xios")
        assert ds.sizes == {"time": 4, "z": NZ, "y": NY, "x": NX}
        ds = get_decoder("croco_xios").decode(whole_grid_files, "croco_xios")
        assert ds.sizes["time"] == 4

    def test_whole_grid(self, whole_grid_files):
        """Outputs on the whole grid: files merged and concatenated in time,
        variables renamed, u and v on the rho points, NaN on the boundary
        rho points with a missing face."""
        ds = open_decode_croco_xios(whole_grid_files).compute()
        assert {"ptemp", "sal", "ssh", "u", "v", "bathy", "mask"} <= set(ds.data_vars)
        assert ds.time.values[0] == np.datetime64("2017-01-01T00:00")
        assert ds.time.values[-1] == np.datetime64("2017-01-02T12:00")
        assert ds.ptemp.dims == ("time", "z", "y", "x")
        # surface first
        np.testing.assert_allclose(ds.ptemp.isel(time=0, y=0, x=0), 10.0 + np.arange(NZ)[::-1])
        np.testing.assert_allclose(ds.lon.values[0], LON0 + DLON * np.arange(NX))
        u = ds.u.isel(time=0, z=0, y=2).values
        assert np.isnan(u[0]) and np.isnan(u[-1])
        np.testing.assert_allclose(u[1:-1], np.arange(1, NX - 1))
        v = ds.v.isel(time=0, z=0, x=2).values
        assert np.isnan(v[0]) and np.isnan(v[-1])
        np.testing.assert_allclose(v[1:-1], np.arange(1, NY - 1))

    def test_depth(self, whole_grid_files):
        """Depth of the levels from h (grid file), zeta, the s_rho axis and
        the stretching curves computed with the global attributes."""
        # with the CF attributes of open_decode
        ds = open_decode(whole_grid_files, "croco_xios").compute()
        h = bathy()
        # each file has the free surface 0.1, 0.2...
        for itime, zeta in ((0, zeta_values(DAY1)[0]), (3, zeta_values(DAY2)[1])):
            np.testing.assert_allclose(
                ds.depth.isel(time=itime).values, expected_depth(h, zeta), rtol=1e-6
            )
        assert (ds.depth.diff("z") > 0).all()
        assert ds.depth.attrs["standard_name"] == "depth"
        assert ds.ptemp.attrs["units"] == "degree_celsius"
        assert ds.lon.attrs["standard_name"] == "longitude"
        assert ds.time.attrs["standard_name"] == "time"
        assert ds.depth.attrs["positive"] == "down"
        assert "bounds" not in ds.time.attrs
        np.testing.assert_allclose(ds.bathy.values, h)

    def test_vertical_fields(self, tmp_path):
        """Parameters of the vertical coordinate written as fields by XIOS,
        without global attributes: Vtransform = 2 gives NEW_S_COORD."""
        fields = {None: ["temp", "zeta", "h"]}
        ds = xios_dataset("TS", DAY1, SINGLE, fields, vertical="fields")
        ds = open_decode_croco_xios([write(ds, tmp_path / "ts.nc")]).compute()
        np.testing.assert_allclose(
            ds.depth.isel(time=0).values, expected_depth(bathy(), zeta_values(DAY1)[0]), rtol=1e-6
        )
        assert not {"hc", "theta_s", "theta_b", "Vtransform", "Cs_rho"} & set(ds.variables)

    def test_old_vertical_coordinate(self, tmp_path):
        """Vtransform = 1: generic form 1 of the s-coordinate (set_depth.F
        without NEW_S_COORD)."""
        fields = {None: ["temp", "zeta", "h"]}
        ds = xios_dataset("TS", DAY1, SINGLE, fields, vertical="fields")
        cs = _croco_s_curves(SC_R, THETA_S, THETA_B, False)
        ds["Vtransform"] = 1.0
        ds["Cs_rho"] = ("s_rho", cs)
        ds = open_decode_croco_xios([write(ds, tmp_path / "ts.nc")]).compute()
        h, zeta = bathy(), zeta_values(DAY1)[0]
        z0 = HC * SC_R[:, None, None] + (h - HC) * cs[:, None, None]
        z = z0 + zeta * (1.0 + z0 / h)
        np.testing.assert_allclose(ds.depth.isel(time=0).values, -z[::-1], rtol=1e-6)

    def test_surface_velocities(self, tmp_path):
        """u_surf and v_surf on the rho points and rotated."""
        fields = {"u": ["u_surf"], "v": ["v_surf"], "rho": ["zeta"]}
        uv = xios_dataset("surf_UV", DAY1, WHOLE, fields)
        files = [write(uv, tmp_path / "uv.nc"), write_grid(tmp_path / "grd.nc", angle=np.pi / 2)]
        ds = open_decode(files, "croco_xios").compute()
        assert ds.u_surf.dims == ("time", "y", "x")
        np.testing.assert_allclose(ds.u_surf.isel(time=0, y=2, x=3), -2.0, atol=1e-6)
        np.testing.assert_allclose(ds.v_surf.isel(time=0, y=2, x=3), 3.0, atol=1e-6)
        assert ds.u_surf.attrs["standard_name"] == "surface_eastward_sea_water_velocity"

    def test_velocities_only(self, tmp_path):
        """Outputs on the u and v points only: rho points rebuilt from the
        faces, exact inside the grid."""
        uv = xios_dataset("UV", DAY1, {"u": WHOLE["u"], "v": WHOLE["v"]}, {"u": ["u"], "v": ["v"]})
        ds = open_decode_croco_xios([write(uv, tmp_path / "uv.nc")]).compute()
        assert ds.sizes == {"time": 2, "z": NZ, "y": NY, "x": NX}
        lon, lat = grid_lonlat(np.arange(NX, dtype="d"), np.arange(NY, dtype="d"))
        inner = (slice(1, -1), slice(1, -1))
        np.testing.assert_allclose(ds.lon.values[inner], lon[inner])
        np.testing.assert_allclose(ds.lat.values[inner], lat[inner])
        assert np.isfinite(ds.lon.values).all()
        np.testing.assert_allclose(ds.u.isel(time=0, z=0, y=2).values[1:-1], np.arange(1, NX - 1))

    def test_velocities_only_extraction(self, tmp_path):
        """Extraction on the u and v points only: rho points rebuilt from
        the faces of all the cells."""
        domains = {"zone_U": ("u", (0, 4), (1, 2)), "zone_V": ("v", (1, 3), (0, 3))}
        uv = xios_dataset("UV", DAY1, domains, {"zone_U": ["u"], "zone_V": ["v"]})
        ds = open_decode_croco_xios([write(uv, tmp_path / "uv.nc")]).compute()
        lon, lat = grid_lonlat(np.arange(1, 4, dtype="d"), np.arange(1, 3, dtype="d"))
        np.testing.assert_allclose(ds.lon.values, lon)
        np.testing.assert_allclose(ds.lat.values, lat)
        np.testing.assert_allclose(ds.v.isel(time=0, z=0).values, [[1] * 3, [2] * 3])

    def test_velocity_without_rho_points(self, tmp_path):
        """Outputs on the u points only cannot be decoded."""
        uv = xios_dataset("U", DAY1, {"u": WHOLE["u"], "w": WHOLE["rho"]}, {"u": ["u"]})
        uv = uv.drop_vars(["nav_lon_w", "nav_lat_w"])
        with pytest.raises(ArmoorError, match="need both u and v"):
            open_decode_croco_xios([write(uv, tmp_path / "u.nc")])

    def test_rotation(self, tmp_path):
        """u and v rotated to east and north with the angle of the grid file."""
        times = DAY1
        uv = xios_dataset("MED_inst_UV", times, WHOLE, {"u": ["u"], "v": ["v"]})
        files = [write(uv, tmp_path / "uv.nc"), write_grid(tmp_path / "grd.nc", angle=np.pi / 2)]
        ds = open_decode(files, "croco_xios").compute()
        # angle = pi / 2: east = -v_xi, north = u_xi
        np.testing.assert_allclose(ds.u.isel(time=0, z=0, y=2, x=3), -2.0, atol=1e-6)
        np.testing.assert_allclose(ds.v.isel(time=0, z=0, y=2, x=3), 3.0, atol=1e-6)
        assert ds.u.attrs["standard_name"] == "eastward_sea_water_velocity"
        assert ds.v.attrs["standard_name"] == "northward_sea_water_velocity"

    def test_extraction(self, tmp_path):
        """Extraction of sloop: rho points [1, 3] x [1, 2] with the faces of
        all the cells, h and angle written by XIOS, no grid file."""
        domains = {
            "zone_T": ("rho", (1, 3), (1, 2)),
            "zone_U": ("u", (0, 4), (1, 2)),
            "zone_V": ("v", (1, 3), (0, 3)),
        }
        fields = {"zone_T": ["temp", "zeta", "h"], "zone_U": ["u"], "zone_V": ["v"]}
        files = [
            write(
                xios_dataset("GASC5_zone", times, domains, fields),
                tmp_path / f"GASC5_zone_{day}.nc",
            )
            for day, times in (("20170101", DAY1), ("20170102", DAY2))
        ]
        ds = open_decode_croco_xios(files).compute()
        assert ds.sizes == {"time": 4, "z": NZ, "y": 2, "x": 3}
        np.testing.assert_allclose(ds.u.isel(time=0, z=0).values, [[1, 2, 3]] * 2)
        np.testing.assert_allclose(ds.v.isel(time=0, z=0).values, [[1] * 3, [2] * 3])
        np.testing.assert_allclose(ds.lon.values[0], LON0 + DLON * np.arange(1, 4))
        zeta = zeta_values(DAY1)[0][1:3, 1:4]
        np.testing.assert_allclose(
            ds.depth.isel(time=0).values, expected_depth(bathy()[1:3, 1:4], zeta), rtol=1e-6
        )

    def test_extraction_at_boundary(self, tmp_path):
        """Extraction at the west and south boundaries: one face less, the
        first faces located with the coordinates; grid fields of the
        extraction taken from the grid file."""
        domains = {
            "zone_T": ("rho", (0, 3), (0, 2)),
            "zone_U": ("u", (0, 3), (0, 2)),
            "zone_V": ("v", (0, 3), (0, 2)),
        }
        fields = {"zone_T": ["temp", "zeta"], "zone_U": ["u"], "zone_V": ["v"]}
        files = [
            write(xios_dataset("zone", DAY1, domains, fields), tmp_path / "zone.nc"),
            write_grid(tmp_path / "croco_grd.nc"),
        ]
        ds = open_decode_croco_xios(files).compute()
        u = ds.u.isel(time=0, z=0, y=1).values
        assert np.isnan(u[0])
        np.testing.assert_allclose(u[1:], [1, 2])
        v = ds.v.isel(time=0, z=0, x=1).values
        assert np.isnan(v[0])
        np.testing.assert_allclose(v[1:], [1])
        np.testing.assert_allclose(ds.bathy.values, bathy()[0:2, 0:3])

    def test_ignored_fields(self, tmp_path):
        """Fields on the w levels and lon_rho fields are removed."""
        fields = {None: ["temp", "w", "lon_rho", "h", "zeta"]}
        ds = xios_dataset("TS", DAY1, SINGLE, fields)
        ds = open_decode_croco_xios([write(ds, tmp_path / "ts.nc")])
        assert "w" not in ds and "lon_rho" not in ds
        assert "depth" in ds.coords

    def test_no_bathymetry(self, tmp_path):
        """Without h, the depth is not computed."""
        ds = xios_dataset("TS", DAY1, SINGLE, {None: ["temp"]})
        ds = open_decode_croco_xios([write(ds, tmp_path / "ts.nc")])
        assert "depth" not in ds.coords
        assert ds.ptemp.dims == ("time", "z", "y", "x")

    def test_different_points(self, tmp_path):
        """Outputs on different rho points cannot be merged."""
        a = xios_dataset("A", DAY1, SINGLE, {None: ["temp"]})
        b = xios_dataset("B", DAY1, {None: ("rho", (0, 3), (0, 2))}, {None: ["salt"]})
        files = [write(a, tmp_path / "a.nc"), write(b, tmp_path / "b.nc")]
        with pytest.raises(ArmoorError, match="same points"):
            open_decode_croco_xios(files)

    def test_different_times(self, tmp_path):
        """Outputs at different times cannot be merged."""
        a = xios_dataset("A", DAY1, SINGLE, {None: ["temp"]})
        b = xios_dataset("B", DAY2, SINGLE, {None: ["salt"]})
        files = [write(a, tmp_path / "a.nc"), write(b, tmp_path / "b.nc")]
        with pytest.raises(ArmoorError, match="same times"):
            open_decode_croco_xios(files)

    def test_grid_not_found(self, tmp_path):
        """Outputs that are not on the points of the grid file."""
        ds = xios_dataset("TS", DAY1, SINGLE, {None: ["temp"]})
        ds["nav_lon"] = ds["nav_lon"] + 5.0
        files = [write(ds, tmp_path / "ts.nc"), write_grid(tmp_path / "croco_grd.nc")]
        with pytest.raises(ArmoorError, match="not found in the grid file"):
            open_decode_croco_xios(files)


@pytest.mark.parametrize("new", [True, False])
def test_croco_s_curves(new):
    """Stretching curves: -1 at the bottom, 0 at the surface, increasing."""
    sc = np.linspace(-1, 0, 11)
    cs = _croco_s_curves(sc, THETA_S, THETA_B, new)
    np.testing.assert_allclose(cs[[0, -1]], [-1, 0], atol=1e-12)
    assert (np.diff(cs) > 0).all()


def test_velocities_not_rotated(tmp_path):
    """Without angle, the velocities keep standard names relative to the grid."""
    uv = xios_dataset("MED_inst_UV", DAY1, WHOLE, {"u": ["u"], "v": ["v"]})
    uv["u"].attrs["standard_name"] = "sea_water_x_velocity"
    ds = open_decode([write(uv, tmp_path / "uv.nc")], "croco_xios")
    assert ds.u.attrs["standard_name"] == "sea_water_x_velocity"
    assert ds.u.attrs["long_name"] == "Sea water velocity along X"
