"""Comparison type hierarchy for the armoor-comp-* pipeline.

Each `func_comp` string (comp_sst, comp_argo, comp_mooring, comp_drifter,
comp_models, comp_clim) used to index five parallel dicts in
``armoor.comp`` (METAZONE_PARAMS, COLOCATION_PARAMS_USER,
COLOCATION_PARAMS_DEFAULT, OUTPUTS_PARAMS, COMP_VARS) plus TITLE_PLOTS, and
drove a handful of ``if func_comp == "comp_xxx"`` branches scattered across
``comp/coloc.py`` and ``comp/output.py``. This module replaces both with one
``Comparison`` subclass per func_comp, registered by name.

``comp/__init__.py``'s dicts are now *derived* from the registry below (kept
for backward compatibility with existing call sites), not the other way
round -- so this module must not import from ``armoor.comp`` to avoid a
circular import.
"""
import logging

import numpy as np
import pandas as pd
import xarray as xr
from xoa.geo import bearing, haversine

import armoor.base.ranges as ranges
from armoor import ArmoorError

logger = logging.getLogger(__name__)

_REGISTRY = {}


class Comparison:
    """Base class for one armoor-comp-* comparison type.

    Subclasses populate the class attributes below (mirroring today's
    per-func_comp dict entries) and override the hook methods only where
    their behavior genuinely differs from the generic one.
    """

    name = None
    title = ""
    metazone_params = []
    colocation_params_user = {}
    colocation_params_default = {}
    outputs_params = {}
    comp_vars = []
    otype_remap = {}

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        if cls.name is not None:
            _REGISTRY[cls.name] = cls()

    # -- colocation -----------------------------------------------------

    def apply_vertical_ranges(self, dsref_list, dsprod_list, params):
        """Apply vertical ranging to dataset lists (generic case).

        Caller (``comp.coloc._apply_vertical_ranges``) already guarantees
        ``params["vertical"]`` is not None.
        """
        vertical_coloc = params["vertical"]
        if "vlevel" in vertical_coloc[0]:
            vname = vertical_coloc[1][0]
            return ranges.vlevels(dsref_list, vname), ranges.vlevels(dsprod_list, vname)
        elif "vrange" in vertical_coloc[0]:
            vname = vertical_coloc[1][1]
            vbins = vertical_coloc[1][2]
            return (
                ranges.vrange(dsref_list, vname, vbins),
                ranges.vrange(dsprod_list, vname, vbins),
            )
        return dsref_list, dsprod_list

    # -- output -----------------------------------------------------------

    def compute_oceanvars(self, ds):
        """Compute derived oceanographic variables on a colocated dataset."""
        for var in self.comp_vars:
            if var not in ds.data_vars:
                da = ds.oceanvars.sel(var)
                if isinstance(da, xr.DataArray):
                    ds[var] = da
        return ds

    def check_output(self, outputs):
        for oname, output in outputs.items():
            if output.get("otype") not in self.outputs_params.keys():
                raise ArmoorError(f"Not implemented output for {self.name}: {output}")
        return outputs

    def validate_output_compatibility(self, oparams, mparams, metazone, output):
        try:
            output_config = self.outputs_params[output]
        except KeyError:
            logger.warning(f"Output type '{output}' not found in OUTPUTS_PARAMS for {self.name}")
            return False

        if output_config.get("mparams_pro"):
            for dim, required_params in output_config.get("mparams_pro").items():
                if not bool(set(required_params) & set(mparams.keys())):
                    logger.info(
                        f"{output} cannot be processed for {metazone} "
                        f"caused by missing {required_params}"
                    )
                    return False

        if output_config.get("mparams_con"):
            for dim, conflicting_params in output_config.get("mparams_con").items():
                if bool(set(conflicting_params) & set(mparams.keys())):
                    logger.info(
                        f"{output} cannot be processed for {metazone} "
                        f"caused by conflicting {conflicting_params}"
                    )
                    return False

        return True

    def preproc(self, ncs, **kwargs):
        """Preprocess loaded inputs before output computation (no-op by default)."""
        return None

    def compute_comparison(self, dt_comps, ds_ref, ds_prod, output):
        """Override the generic StatsComp result if this comparison type needs
        something else (pass-through by default)."""
        return dt_comps


class CompSst(Comparison):
    name = "comp_sst"
    title = "Sea surface temperature"
    metazone_params = [
        "tbound", "thours", "trange_seq", "tfreq", "polygon", "href",
        "cloud", "oceanvars", "qc", "bathy",
    ]
    colocation_params_user = {
        "time": ("trange_seq", "tfreq"),
        "horizontal": ("href", "cloud"),
    }
    colocation_params_default = {
        "vertical": ("vlevel", ("depth", [0.0])),
    }
    outputs_params = {
        "diagdisp_glob": {"concat": ["time"]},
        "diagdisp_sel": {"sort": ["time"], "concat": ["time"]},
        "timeseries": {"concat": ["time"], "stat": ["time", "x", "y"], "output": "merge"},
        "maps": {"sort": ["time"], "stat": ["time"]},
    }
    comp_vars = ["ptemp"]

    def apply_vertical_ranges(self, dsref_list, dsprod_list, params):
        return dsref_list, dsprod_list


class CompArgo(Comparison):
    name = "comp_argo"
    title = "Hydrological profiles"
    metazone_params = [
        "tbound", "thours", "trange_seq", "vrange", "vlevel", "polygon",
        "radius", "oceanvars", "qc", "bathy",
    ]
    colocation_params_user = {
        "time": ("trange_seq",),
        "horizontal": ("radius",),
        "vertical": ("vrange", "vlevel"),
    }
    colocation_params_default = {
        "time": ("trange_seq", ("*", "reference", "nearest")),
    }
    outputs_params = {
        "maps": {
            "sort": ["time", "z"],
            "stat": ["z"],
            "mparams_pro": {"time": ["trange_seq"], "vertical": ["vlevel", "vrange"]},
        },
        "diagdisp_glob": {
            "concat": ["time"],
            "mparams_pro": {"vertical": ["vlevel", "vrange"]},
        },
        "diagdisp_sel": {
            "sort": ["time", "z"],
            "mparams_pro": {"time": ["trange_seq"], "vertical": ["vlevel", "vrange"]},
        },
        "timeseries": {
            "sort": ["z"],
            "concat": ["time"],
            "stat": ["time", "z"],
            "output": "merge",
            "mparams_pro": {"time": ["trange_seq"], "vertical": ["vlevel", "vrange"]},
        },
        "mvprofiles": {
            "sort": ["time", "z"],
            "mparams_pro": {"time": ["trange_seq"]},
            "mparams_con": {"vertical": ["vlevel"]},
        },
        "mdiagts": {
            "sort": ["time", "z"],
            "mparams_pro": {"time": ["trange_seq"]},
        },
        "uvprofiles": {
            "concat": ["time"],
            "output": "merge",
            "mparams_con": {"vertical": ["vlevel"]},
        },
        "udiagts": {"concat": ["time"], "output": "merge"},
    }
    comp_vars = ["ptemp", "sal", "pdens", "temp", "sndspeed"]


class _ForcedDepthVLevelMixin:
    """Shared by comp_mooring/comp_drifter: always range on 'depth' via
    ranges.vlevels, regardless of whether the metazone is configured with
    'vlevel' or 'vrange' — reproduces today's quirk exactly, do not "fix"."""

    def apply_vertical_ranges(self, dsref_list, dsprod_list, params):
        return ranges.vlevels(dsref_list, "depth"), ranges.vlevels(dsprod_list, "depth")


class CompMooring(_ForcedDepthVLevelMixin, Comparison):
    name = "comp_mooring"
    title = "Hydrological mooring"
    metazone_params = [
        "tfreq", "thours", "tbound", "trange_seq", "polygon", "oceanvars",
        "radius", "qc", "bathy",
    ]
    colocation_params_user = {
        "time": ("trange_seq", "tfreq"),
        "horizontal": ("radius",),
    }
    colocation_params_default = {
        "vertical": ("vrange", ("reference", "depth", "*")),
    }
    outputs_params = {
        "timeseries": {
            "sort": ["z"],
            "stat": ["time"],
            "concat": ["time"],
            "output": "merge",
        },
    }
    comp_vars = ["ptemp", "sal", "pdens", "temp", "sndspeed", "cdir", "cspeed"]


class CompDrifter(_ForcedDepthVLevelMixin, Comparison):
    name = "comp_drifter"
    title = "Drifters"
    metazone_params = [
        "tbound", "polygon", "oceanvars", "freq_drift", "period_drift",
        "tresample", "tsmooth", "bathy",
    ]
    colocation_params_user = {}
    colocation_params_default = {
        "vertical": ("vrange", ("reference", "depth", "*")),
    }
    outputs_params = {
        "preproc": "oceanparcels",
        "timeseries_drifter": {"output": "merge"},
        "maps_current_drifter": {},
        "maps_trajectory_drifter": {},
    }
    comp_vars = ["ptemp", "sal", "u", "v"]
    otype_remap = {
        "timeseries": "timeseries_drifter",
        "maps_current": "maps_current_drifter",
        "maps_trajectory": "maps_trajectory_drifter",
    }

    def check_output(self, outputs):
        for oname, output in outputs.items():
            otype = output.get("otype")
            if otype in self.otype_remap:
                output["otype"] = self.otype_remap[otype]
        return super().check_output(outputs)

    def validate_output_compatibility(self, oparams, mparams, metazone, output):
        if output in self.otype_remap:
            output = self.otype_remap[output]
        return super().validate_output_compatibility(oparams, mparams, metazone, output)

    def preproc(self, ncs, **kwargs):
        from armoor.comp.output import preproc_comp_drifter
        return preproc_comp_drifter(
            ncs, kwargs.get("freq_drift"), runtime=kwargs.get("period_drift")
        )

    def compute_comparison(self, dt_comps, ds_ref, ds_prod, output):
        return self._drifter(ds_ref, ds_prod, output)

    def _drifter(self, dsref, dsprod, output):
        """Compute drifter-specific comparison metrics.

        For timeseries_drifter: haversine distance and bearing angle
        differences between reference drifter trajectories and
        parcels-simulated trajectories, averaged across all particles per
        time step. For maps_current_drifter / maps_trajectory_drifter: no
        comparison is computed (returns None).
        """
        if output in ("maps_current_drifter", "maps_trajectory_drifter"):
            return None

        coords = ["time", "lon", "lat"]
        suff = "_parcels"
        dsref = dsref[coords].set_coords(["time", "lat", "lon"]).squeeze()
        vrenames = {f"{vname}{suff}": vname for vname in coords}
        dsprod = dsprod[[f"{vname}{suff}" for vname in coords]]
        dsprod = dsprod.rename_vars(vrenames)

        data_list = []
        for iptc in range(dsprod.sizes["trajectory_parcels"]):
            dsparti = dsprod.isel(trajectory_parcels=iptc)
            dsparti = dsparti.where(dsparti.time.notnull(), drop=True)
            dsparti = dsparti.swap_dims({"obs_parcels": "time"})
            dsdrift = dsref.sel(time=slice(dsparti.time.min(), dsparti.time.max()))
            dsparti = dsparti.sel(time=slice(dsdrift.time.min(), dsdrift.time.max()))
            dist = haversine(dsdrift.lon, dsdrift.lat, dsparti.lon, dsparti.lat)
            bear_drift = bearing(
                dsdrift.lon.isel(time=slice(1, None)),
                dsdrift.lat.isel(time=slice(1, None)),
                dsdrift.lon.isel(time=slice(None, -1)),
                dsdrift.lat.isel(time=slice(None, -1)),
            )
            bear_parti = bearing(
                dsparti.lon.isel(time=slice(1, None)),
                dsparti.lat.isel(time=slice(1, None)),
                dsparti.lon.isel(time=slice(None, -1)),
                dsparti.lat.isel(time=slice(None, -1)),
            )
            angle = (((bear_drift - bear_parti) + 180) % 360) - 180
            if isinstance(angle, np.float64):
                angle = [angle]
            angle = np.concatenate([[0], angle])
            data_list.append(pd.DataFrame({
                "time": (dsparti.time - dsparti.time.min()).values / pd.to_timedelta("1d"),
                "dist": dist.values if hasattr(dist, "values") else dist,
                "angle": angle.values if hasattr(angle, "values") else angle,
            }))

        df_all = pd.concat(data_list, ignore_index=True)
        grouped = df_all.groupby("time").agg({"dist": "mean", "angle": "mean"})
        dtcomps = xr.DataTree(name="comps")
        dtcomps.update(xr.DataTree.from_dict({
            "diff": xr.Dataset(
                data_vars=dict(
                    distance=(["time"], grouped["dist"].values),
                    direction=(["time"], grouped["angle"].values),
                ),
                coords=dict(time=grouped.index.values),
            )
        }))
        return dtcomps


class CompModels(Comparison):
    name = "comp_models"
    title = ""
    metazone_params = [
        "tfreq", "tbound", "thours", "trange_seq", "polygon", "href",
        "cloud", "vrange", "vlevel", "oceanvars", "bathy",
    ]
    colocation_params_user = {
        "time": ("trange_seq", "tfreq"),
        "horizontal": ("href", "cloud"),
        "vertical": ("vrange", "vlevel"),
    }
    outputs_params = {
        "maps": {
            "sort": ["time", "z"],
            "stat": ["time", "z"],
            "mparams_con": {"time": ["tfreq"]},
        },
        "diagdisp_glob": {"concat": ["time"]},
        "diagdisp_sel": {"sort": ["time", "z"]},
        "timeseries": {
            "sort": ["z"],
            "concat": ["time"],
            "stat": ["time", "z", "y", "x"],
            "output": "merge",
        },
        "mvprofiles": {"sort": ["time", "z"]},
        "mdiagts": {"sort": ["time", "z"]},
        "uvprofiles": {
            "concat": ["time"],
            "output": "merge",
            "mparams_pro": {"horizontal": ["cloud"]},
        },
        "udiagts": {
            "concat": ["time"],
            "output": "merge",
            "mparams_pro": {"horizontal": ["cloud"]},
        },
    }
    comp_vars = ["ptemp", "sal", "pdens", "sndspeed"]


class CompClim(Comparison):
    name = "comp_clim"
    title = "Hydrological climatology"
    metazone_params = ["tbound", "polygon", "href", "vlevel", "oceanvars", "bathy"]
    colocation_params_user = {
        "time": ("tmonth",),
        "horizontal": ("href",),
        "vertical": ("vlevel",),
    }
    outputs_params = {
        "maps": {"sort": ["time", "z"], "stat": ["time"]},
        "timeseries": {
            "sort": ["z"],
            "concat": ["time"],
            "stat": ["y", "x"],
            "output": "merge",
        },
    }
    comp_vars = ["ptemp", "sal"]


def get_comparison(func_comp: str) -> Comparison:
    """Look up the Comparison instance registered for a func_comp string."""
    try:
        return _REGISTRY[func_comp]
    except KeyError:
        raise ArmoorError(f"Comparison '{func_comp}' not found")
