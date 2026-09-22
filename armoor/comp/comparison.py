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

import armoor.ranges as ranges
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
        """Register `cls` in the module-level registry under its `name`.

        Parameters
        ----------
        cls : type
            The subclass being created.
        **kwargs
            Forwarded to `super().__init_subclass__`.

        Returns
        -------
        None
        """
        super().__init_subclass__(**kwargs)
        if cls.name is not None:
            _REGISTRY[cls.name] = cls()

    # -- colocation -----------------------------------------------------

    def apply_vertical_ranges(self, dsref_list, dsprod_list, params):
        """Apply vertical ranging to reference/product dataset lists.

        Generic implementation shared by comparison types that don't
        override it. Caller (``comp.coloc._apply_vertical_ranges``) already
        guarantees ``params["vertical"]`` is not None.

        Parameters
        ----------
        dsref_list : list of xarray.Dataset
            Reference datasets, one per product.
        dsprod_list : list of xarray.Dataset
            Product datasets, matching `dsref_list`.
        params : dict
            Colocation parameters for the metazone; ``params["vertical"]``
            holds the ``(param_name, param_value)`` pair selecting either a
            vertical level (``vlevel``) or a vertical range (``vrange``).

        Returns
        -------
        tuple of (list of xarray.Dataset, list of xarray.Dataset)
            The ranged `dsref_list` and `dsprod_list`.
        """
        vertical_coloc = params["vertical"]
        if "vlevel" in vertical_coloc[0]:
            vname = vertical_coloc[1]["vname"]
            return ranges.vlevels(dsref_list, vname), ranges.vlevels(dsprod_list, vname)
        elif "vrange" in vertical_coloc[0]:
            vname = vertical_coloc[1]["vname"]
            vbins = list(zip(vertical_coloc[1]["bins_min"], vertical_coloc[1]["bins_max"]))
            return (
                ranges.vrange(dsref_list, vname, vbins),
                ranges.vrange(dsprod_list, vname, vbins),
            )
        return dsref_list, dsprod_list

    # -- output -----------------------------------------------------------

    def compute_oceanvars(self, ds, mparams=None):
        """Compute derived oceanographic variables on a colocated dataset.

        For every variable in `comp_vars` missing from `ds`, attempt to
        select or derive it via the ``ds.oceanvars`` accessor.

        Parameters
        ----------
        ds : xarray.Dataset
            Colocated dataset to augment in place.
        mparams : dict, optional
            Full metazone parameter dict (e.g. carrying CLI-supplied
            extras). Unused by the generic implementation; accepted for a
            uniform hook signature with subclasses that do use it (e.g.
            CompHydrosection's ``cgeo_ref``).

        Returns
        -------
        xarray.Dataset
            `ds`, with any missing `comp_vars` added where derivable.
        """
        for var in self.comp_vars:
            if var not in ds.data_vars:
                da = ds.oceanvars.sel(var)
                if isinstance(da, xr.DataArray):
                    ds[var] = da
        return ds

    def check_output(self, outputs):
        """Validate that every requested output type is implemented.

        Parameters
        ----------
        outputs : dict
            Mapping of output name to output configuration (each holding at
            least an ``"otype"`` key).

        Returns
        -------
        dict
            `outputs`, unchanged.

        Raises
        ------
        ArmoorError
            If an output's ``"otype"`` is not a key of `outputs_params`.
        """
        for oname, output in outputs.items():
            if output.get("otype") not in self.outputs_params.keys():
                raise ArmoorError(f"Not implemented output for {self.name}: {output}")
        return outputs

    def validate_output_compatibility(self, oparams, mparams, metazone, output):
        """Check whether an output type is compatible with a metazone's params.

        Parameters
        ----------
        oparams : dict
            Output configuration for the metazone (unused by the generic
            implementation; kept for a uniform hook signature with
            subclasses that do use it, e.g. CompDrifter).
        mparams : dict
            Metazone parameters (e.g. ``tfreq``, ``vlevel``).
        metazone : str
            Metazone name, used only for logging.
        output : str
            Output type name (``otype``) to check against `outputs_params`.

        Returns
        -------
        bool
            True if `output` can be processed for this metazone, False
            otherwise (required params missing, or conflicting params
            present).
        """
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
        """Preprocess loaded inputs before output computation.

        No-op by default; overridden by comparison types that need to
        transform inputs before comparison (e.g. CompDrifter).

        Parameters
        ----------
        ncs : list of str
            Paths to the loaded/colocated input files.
        **kwargs
            Comparison-specific extra arguments (e.g. ``freq_drift``).

        Returns
        -------
        None or object
            None by default; subclasses may return preprocessed inputs.
        """
        return None

    def compute_comparison(self, dt_comps, ds_ref, ds_prod, output):
        """Compute the comparison result for one output.

        Pass-through by default (the generic `StatsComp` result is used
        as-is); overridden by comparison types that need a different
        computation (e.g. CompDrifter).

        Parameters
        ----------
        dt_comps : xarray.DataTree
            The generic comparison result (statistics per sort group).
        ds_ref : xarray.Dataset
            Reference dataset for this output.
        ds_prod : xarray.Dataset
            Product dataset for this output.
        output : str
            Output type name (``otype``).

        Returns
        -------
        xarray.DataTree
            `dt_comps`, unchanged by default.
        """
        return dt_comps


class CompSst(Comparison):
    """Comparison of satellite sea surface temperature against products."""

    name = "comp_sst"
    title = "Sea surface temperature"
    metazone_params = [
        "tbound",
        "thours",
        "trange_seq",
        "tfreq",
        "polygon",
        "href",
        "cloud",
        "oceanvars",
        "qc",
        "bathy",
    ]
    colocation_params_user = {
        "time": ("trange_seq", "tfreq"),
        "horizontal": ("href", "cloud"),
    }
    colocation_params_default = {
        "vertical": ("vlevel", {"vname": "depth", "levels": [0.0]}),
    }
    outputs_params = {
        "diagdisp_glob": {"concat": ["time"]},
        "diagdisp_sel": {"sort": ["time"], "concat": ["time"]},
        "timeseries": {"concat": ["time"], "stat": ["time", "x", "y"], "output": "merge"},
        "maps": {"sort": ["time"], "stat": ["time"]},
    }
    comp_vars = ["ptemp"]

    def apply_vertical_ranges(self, dsref_list, dsprod_list, params):
        """Return the dataset lists unchanged.

        SST is a surface-only product, so no vertical ranging applies.

        Parameters
        ----------
        dsref_list : list of xarray.Dataset
            Reference datasets, one per product.
        dsprod_list : list of xarray.Dataset
            Product datasets, matching `dsref_list`.
        params : dict
            Colocation parameters for the metazone (unused).

        Returns
        -------
        tuple of (list of xarray.Dataset, list of xarray.Dataset)
            `dsref_list` and `dsprod_list`, unchanged.
        """
        return dsref_list, dsprod_list


class CompAlti(Comparison):
    """Comparison of satellite altimetry against products."""

    name = "comp_alti"
    title = "altimetry"
    metazone_params = [
        "tbound", "thours", "trange_seq", "tfreq", "polygon", "href",
        "cloud", "oceanvars", "qc", "bathy",
    ]
    colocation_params_user = {
        "time": ("trange_seq", "tfreq"),
        "horizontal": ("href", "cloud"),
    }
    colocation_params_default = {
        "vertical": ("vlevel", {"vname": "depth", "levels": [0.0]}),
    }
    outputs_params = {
        "diagdisp_glob": {"concat": ["time"]},
        "diagdisp_sel": {"sort": ["time"], "concat": ["time"]},
        "timeseries": {"concat": ["time"], "stat": ["time", "x", "y"], "output": "merge"},
        "maps": {"sort": ["time"], "stat": ["time"]},
    }
    comp_vars = ["sla", "eke"]

    def apply_vertical_ranges(self, dsref_list, dsprod_list, params):
        """Return the dataset lists unchanged.

        SSH is a surface-only product, so no vertical ranging applies.

        Parameters
        ----------
        dsref_list : list of xarray.Dataset
            Reference datasets, one per product.
        dsprod_list : list of xarray.Dataset
            Product datasets, matching `dsref_list`.
        params : dict
            Colocation parameters for the metazone (unused).

        Returns
        -------
        tuple of (list of xarray.Dataset, list of xarray.Dataset)
            `dsref_list` and `dsprod_list`, unchanged.
        """
        return dsref_list, dsprod_list


class CompArgo(Comparison):
    """Comparison of Argo hydrological profiles against products."""

    name = "comp_argo"
    title = "Hydrological profiles"
    metazone_params = [
        "tbound",
        "thours",
        "trange_seq",
        "vrange",
        "vlevel",
        "polygon",
        "radius",
        "oceanvars",
        "qc",
        "bathy",
    ]
    colocation_params_user = {
        "time": ("trange_seq",),
        "horizontal": ("radius",),
        "vertical": ("vrange", "vlevel"),
    }
    colocation_params_default = {
        "time": ("trange_seq", {"tfreq": "*", "tref": "reference", "method": "nearest"}),
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
            "sort": ["time"],
            "output": "merge",
            "mparams_pro": {"time": ["trange_seq"]},
            "mparams_con": {"vertical": ["vlevel"]},
        },
        "udiagts": {
            "sort": ["time"],
            "output": "merge",
            "mparams_pro": {"time": ["trange_seq"]},
        },
    }
    comp_vars = ["ptemp", "sal", "pdens", "temp", "sndspeed", "mld"]


class _ForcedDepthVLevelMixin:
    """Shared by comp_mooring/comp_drifter: always range on 'depth' via
    ranges.vlevels, regardless of whether the metazone is configured with
    'vlevel' or 'vrange' — reproduces today's quirk exactly, do not "fix"."""

    def apply_vertical_ranges(self, dsref_list, dsprod_list, params):
        """Range reference/product datasets on the 'depth' variable.

        Parameters
        ----------
        dsref_list : list of xarray.Dataset
            Reference datasets, one per product.
        dsprod_list : list of xarray.Dataset
            Product datasets, matching `dsref_list`.
        params : dict
            Colocation parameters for the metazone (unused: 'depth' is
            always used regardless of whether 'vlevel' or 'vrange' is
            configured).

        Returns
        -------
        tuple of (list of xarray.Dataset, list of xarray.Dataset)
            The ranged `dsref_list` and `dsprod_list`.
        """
        return ranges.vlevels(dsref_list, "depth"), ranges.vlevels(dsprod_list, "depth")


class CompMooring(_ForcedDepthVLevelMixin, Comparison):
    """Comparison of hydrological mooring time series against products."""

    name = "comp_mooring"
    title = "Hydrological mooring"
    metazone_params = [
        "tfreq",
        "thours",
        "tbound",
        "trange_seq",
        "polygon",
        "oceanvars",
        "radius",
        "qc",
        "bathy",
    ]
    colocation_params_user = {
        "time": ("trange_seq", "tfreq"),
        "horizontal": ("radius",),
    }
    colocation_params_default = {
        "vertical": ("vrange", {"vref": "reference", "vname": "depth"}),
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
    """Comparison of drifter trajectories against oceanparcels simulations."""

    name = "comp_drifter"
    title = "Drifters"
    metazone_params = [
        "tbound",
        "polygon",
        "oceanvars",
        "freq_drift",
        "period_drift",
        "tresample",
        "tsmooth",
        "bathy",
    ]
    colocation_params_user = {}
    colocation_params_default = {
        "vertical": ("vrange", {"vref": "reference", "vname": "depth"}),
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
        """Remap generic otype names to drifter-specific ones, then validate.

        Parameters
        ----------
        outputs : dict
            Mapping of output name to output configuration; each
            configuration's ``"otype"`` is remapped in place via
            `otype_remap` before validation (e.g. ``"timeseries"`` becomes
            ``"timeseries_drifter"``).

        Returns
        -------
        dict
            `outputs`, with `"otype"` values remapped.

        Raises
        ------
        ArmoorError
            If a (remapped) output's ``"otype"`` is not implemented.
        """
        for oname, output in outputs.items():
            otype = output.get("otype")
            if otype in self.otype_remap:
                output["otype"] = self.otype_remap[otype]
        return super().check_output(outputs)

    def validate_output_compatibility(self, oparams, mparams, metazone, output):
        """Remap a generic otype name to its drifter-specific one, then check.

        Parameters
        ----------
        oparams : dict
            Output configuration for the metazone (unused, see base class).
        mparams : dict
            Metazone parameters.
        metazone : str
            Metazone name, used only for logging.
        output : str
            Output type name, remapped via `otype_remap` if applicable
            before checking compatibility.

        Returns
        -------
        bool
            True if the (remapped) output can be processed, False otherwise.
        """
        if output in self.otype_remap:
            output = self.otype_remap[output]
        return super().validate_output_compatibility(oparams, mparams, metazone, output)

    def preproc(self, ncs, **kwargs):
        """Preprocess drifter/oceanparcels inputs before comparison.

        Parameters
        ----------
        ncs : list of str
            Paths to the loaded/colocated input files.
        **kwargs
            Must include ``freq_drift`` and ``period_drift``, forwarded to
            `armoor.comp.output.preproc_comp_drifter`.

        Returns
        -------
        object
            The result of `preproc_comp_drifter`.
        """
        from armoor.comp.output import preproc_comp_drifter

        return preproc_comp_drifter(
            ncs, kwargs.get("freq_drift"), runtime=kwargs.get("period_drift")
        )

    def compute_comparison(self, dt_comps, ds_ref, ds_prod, output):
        """Compute drifter-specific comparison metrics.

        Parameters
        ----------
        dt_comps : xarray.DataTree
            The generic comparison result (unused; drifter comparisons are
            computed from scratch by `_drifter`).
        ds_ref : xarray.Dataset
            Reference drifter dataset.
        ds_prod : xarray.Dataset
            Product (oceanparcels) dataset.
        output : str
            Output type name (``otype``).

        Returns
        -------
        xarray.DataTree or None
            See `_drifter`.
        """
        return self._drifter(ds_ref, ds_prod, output)

    def _drifter(self, dsref, dsprod, output):
        """Compute drifter-specific comparison metrics.

        For ``timeseries_drifter``: haversine distance and bearing angle
        differences between reference drifter trajectories and
        parcels-simulated trajectories, averaged across all particles per
        time step. For ``maps_current_drifter``/``maps_trajectory_drifter``:
        no comparison is computed.

        Parameters
        ----------
        dsref : xarray.Dataset
            Reference drifter dataset with ``time``/``lon``/``lat``.
        dsprod : xarray.Dataset
            Product (oceanparcels) dataset with
            ``time_parcels``/``lon_parcels``/``lat_parcels`` per particle.
        output : str
            Output type name (``otype``).

        Returns
        -------
        xarray.DataTree or None
            A one-node ``"diff"`` DataTree holding ``distance``/``direction``
            data variables indexed by time, or None for
            ``maps_current_drifter``/``maps_trajectory_drifter``.
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
            data_list.append(
                pd.DataFrame(
                    {
                        "time": (dsparti.time - dsparti.time.min()).values / pd.to_timedelta("1d"),
                        "dist": dist.values if hasattr(dist, "values") else dist,
                        "angle": angle.values if hasattr(angle, "values") else angle,
                    }
                )
            )

        df_all = pd.concat(data_list, ignore_index=True)
        grouped = df_all.groupby("time").agg({"dist": "mean", "angle": "mean"})
        dtcomps = xr.DataTree(name="comps")
        dtcomps.update(
            xr.DataTree.from_dict(
                {
                    "diff": xr.Dataset(
                        data_vars=dict(
                            distance=(["time"], grouped["dist"].values),
                            direction=(["time"], grouped["angle"].values),
                        ),
                        coords=dict(time=grouped.index.values),
                    )
                }
            )
        )
        return dtcomps


class CompModels(Comparison):
    """Comparison of one reference model against other model products."""

    name = "comp_models"
    title = ""
    metazone_params = [
        "tfreq",
        "tbound",
        "thours",
        "trange_seq",
        "polygon",
        "href",
        "cloud",
        "vrange",
        "vlevel",
        "oceanvars",
        "bathy",
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
    """Comparison of model outputs against an observed hydrological climatology."""

    name = "comp_clim"
    title = "Hydrological climatology"
    metazone_params = ["tbound", "polygon", "href", "vlevel", "oceanvars", "bathy"]
    colocation_params_user = {
        "time": ("tmonth",),
        "horizontal": ("href",),
        "vertical": ("vlevel",),
    }
    # Monthly climatological colocation is comp_clim's only sensible time
    # strategy -- force it as the default so it always applies, regardless
    # of whether the metazone sets "tmonth" (or nothing at all, e.g. a
    # metazone shared with other comp_func's that use "tfreq"/"trange_seq"
    # instead -- those aren't even candidates for comp_clim's "time" key,
    # see colocation_params_user above, so they're already ignored here).
    colocation_params_default = {
        "time": ("tmonth",),
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


class CompHydrosection(Comparison):
    """Comparison of 3D model outputs against observed hydrological sections.

    This iteration only covers gliders (already decodable via
    ``fmt=cmems_insitu, platform=glider``): a single glider mission file
    holds several profiles at their own (time, lon, lat), i.e. a whole
    hydrological section. Other towed-instrument radiales (seasoar,
    scanfish, rapidcast, MVP) only differ by decoding and are not covered
    here.
    """

    name = "comp_hydrosection"
    title = "Hydrological sections"
    # "cgeo_ref" isn't a real metazone.cfg field -- it only ends up here
    # because check_metazones_in merges every comp_args entry (including
    # the --cgeo-ref CLI option) into each metazone's own param dict, and
    # this list is what keeps that merge from being silently stripped back
    # out again.
    metazone_params = ["tbound", "polygon", "oceanvars", "bathy", "cgeo_ref"]
    colocation_params_user = {}
    # comp_hydrosection always time-matches nearest-to-reference, always
    # tracks the reference's own (lon, lat) path, and always vinterps the
    # product onto the reference's own (per-profile) depth levels -- none
    # of the three is user configurable (same rationale as CompClim forcing
    # "tmonth", and CompMooring/CompDrifter forcing a depth-based vertical
    # colocation via `_ForcedDepthVLevelMixin`). Forcing the vertical step
    # is not optional here: without it, the product keeps its own native
    # "z" grid (e.g. a handful of model levels) while the reference keeps
    # its own per-profile depth count (e.g. 29 glider bins, sometimes with
    # all-NaN profiles for surface-only segments) -- two differently-sized,
    # uncorrelated "z" axes that a pointwise diff cannot combine. Verified
    # end-to-end against a real glider sample (`GL_PR_GL_8901067_*.nc`).
    colocation_params_default = {
        "time": ("trange_seq", {"tfreq": "*", "tref": "reference", "method": "nearest"}),
        "horizontal": ("track",),
        "vertical": ("vrange", {"vref": "reference", "vname": "depth"}),
    }
    # "output": "merge" routes through `_save_combined_output`, which fans
    # out an unfused list of datasets into numbered children of `ds_name`
    # (`_save_separate_outputs` cannot: it assumes one dataset per
    # ds_name). A list shows up here because `comp_vars` includes "mld"
    # (no "z" dim) alongside depth-resolved vars (with "z"): the coloc
    # step's dims-signature split (`armoor.comp.coloc._split_by_dims`)
    # always produces two groups sharing the same sort_key, same as
    # CompArgo's uvprofiles/udiagts -- see the matching allowlist entry in
    # `armoor.comp.output._concatenate_datasets`.
    outputs_params = {
        "sections": {"output": "merge"},
    }
    comp_vars = ["ptemp", "sal", "pdens", "temp", "sndspeed", "mld"]

    def apply_vertical_ranges(self, dsref_list, dsprod_list, params):
        """Tag depth-resolved datasets with a vlevel sentinel unique to
        their variable set.

        No real vertical range-splitting happens: comp_hydrosection keeps
        the whole depth profile as a single section (the product was
        already vinterp'd onto the reference's own depth levels during
        colocation, see `colocation_params_default["vertical"]` above).

        The tag itself only exists to make `armoor.io.output_suffix`
        give each "z"-having dims-signature group's coloc file a
        *different* filename -- comp_vars now splits into three such
        groups sharing the same sort_key: {ptemp, sal, pdens, temp,
        sndspeed} (dims time, z), {mld} (dims time -- never reaches this
        hook, see the caller's `if "z" in sub_ref.dims` guard, so it keeps
        its own untagged, empty suffix) and {cgeo} (dims pair, z). A fixed
        tag (e.g. a hardcoded "profile") would collide between the first
        and third groups -- both have "z" -- so the tag is derived from
        each group's own sorted variable names instead, guaranteed
        distinct per group and identical between a group's ref and prod
        side (verified against a real glider sample: with a fixed tag,
        the second "z"-having group's write silently clobbered the
        first's).

        Parameters
        ----------
        dsref_list : list of xarray.Dataset
            Reference datasets, one per product.
        dsprod_list : list of xarray.Dataset
            Product datasets, matching `dsref_list`.
        params : dict
            Colocation parameters for the metazone (unused).

        Returns
        -------
        tuple of (list of xarray.Dataset, list of xarray.Dataset)
            `dsref_list` and `dsprod_list`, each dataset tagged with
            ``attrs["vlevel"]`` set from its own sorted variable names.
        """
        for ds in (*dsref_list, *dsprod_list):
            ds.attrs["vlevel"] = "-".join(sorted(ds.data_vars))[:60]
        return dsref_list, dsprod_list

    def compute_oceanvars(self, ds, mparams=None):
        """Compute pointwise oceanvars, then add the geostrophic velocity
        normal to the section.

        Geostrophic velocity (see
        `armoor.oceanvars.OceanVars.sel_cgeo`) collapses N stations
        into N-1 station-pair values -- it can't be assigned back onto the
        dataset's own "time" dim the way the base class's per-point loop
        assumes, so it's merged in separately here as a new "cgeo"
        variable on a new "pair" dim. Its own ``lon``/``lat`` (station-pair
        midpoints) and ``depth`` (station-pair mean, when the reference
        has one) are renamed to ``lon_pair``/``lat_pair``/``depth_pair``
        first, since `xr.Dataset.merge` can't hold two different-dims
        variables under the same name as the existing per-station
        ``lon``/``lat``/``depth``.

        Parameters
        ----------
        ds : xarray.Dataset
            Colocated dataset to augment in place.
        mparams : dict, optional
            Full metazone parameter dict. ``mparams["cgeo_ref"]`` (from
            the ``--cgeo-ref`` CLI option, see
            `armoor.cli.main.get_parser_comp_hydrosection`) is the
            reference pressure (dbar) for the dynamic height calculation;
            defaults to 0 dbar (surface reference) when absent/None.

        Returns
        -------
        xarray.Dataset
            `ds`, with any missing `comp_vars` added, plus "cgeo" when
            derivable.
        """
        ds = super().compute_oceanvars(ds, mparams)
        if "cgeo" not in ds.data_vars:
            p_ref = (mparams or {}).get("cgeo_ref")
            cgeo = ds.oceanvars.sel_cgeo(p_ref=p_ref if p_ref is not None else 0.0)
            if isinstance(cgeo, xr.DataArray):
                renames = {"lon": "lon_pair", "lat": "lat_pair"}
                if "depth" in cgeo.coords:
                    renames["depth"] = "depth_pair"
                cgeo = cgeo.rename(renames)
                ds = ds.merge({"cgeo": cgeo})
        return ds


def get_comparison(func_comp: str) -> Comparison:
    """Look up the Comparison instance registered for a func_comp string.

    Parameters
    ----------
    func_comp : str
        Comparison type identifier (e.g. ``"comp_sst"``, ``"comp_argo"``).

    Returns
    -------
    Comparison
        The registered instance for `func_comp`.

    Raises
    ------
    ArmoorError
        If no `Comparison` subclass is registered under `func_comp`.
    """
    try:
        return _REGISTRY[func_comp]
    except KeyError:
        raise ArmoorError(f"Comparison '{func_comp}' not found")
