"""Data source type hierarchy for armoor-data.

Different kinds of input (ocean-model output vs. output from ocean analysis
tools such as eddy-detection trackers) need different variables, different
metazone-parameter compatibility rules, and eventually different output/plot
behavior. This mirrors ``armoor.comp.comparison``'s ``Comparison`` hierarchy,
which solves the same shape of problem for ``armoor-comp-*``.
"""
from armoor import ArmoorError

_REGISTRY = {}     # fmt string -> DataType instance
_BY_NAME = {}      # DataType.name -> DataType instance


class DataType:
    """One kind of armoor-data input.

    Subclasses register themselves under every fmt string listed in
    ``fmts`` (many fmt values can map to the same type), and under their
    own ``name`` (used to recover the type later from ``ds.attrs["data_type"]``,
    since `fmt` itself doesn't survive past the initial load -- see
    armoor.data.load).
    """

    name = None
    fmts = ()
    data_vars = []
    forbidden_params = []
    outputs_params = {}
    plotter_cls = None
    is_climatology = False

    def __init_subclass__(cls, **kwargs):
        """Register `cls` in the module-level registries.

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
            instance = cls()
            _BY_NAME[cls.name] = instance
            for fmt in cls.fmts:
                _REGISTRY[fmt] = instance

    def validate_load_params(self, fmt, metazones):
        """Check that metazone configs are compatible with this data type.

        No-op when the type has no `forbidden_params`.

        Parameters
        ----------
        fmt : str
            The data.ini `fmt` value being loaded, used only in the error
            message.
        metazones : dict
            Mapping of metazone name to its parameters.

        Returns
        -------
        None

        Raises
        ------
        ArmoorError
            If any metazone configures one of `forbidden_params`.
        """
        if not self.forbidden_params:
            return
        for mz_name, mparams in metazones.items():
            if any(p in mparams for p in self.forbidden_params):
                raise ArmoorError(
                    f"Outputs from {self.name} cannot use {self.forbidden_params}. "
                    f"Metazone '{mz_name}' configures one of them even though "
                    f"fmt={fmt!r}."
                )


class DataOceanModel(DataType):
    """Ocean-model gridded output (hycom, croco, cmems_model, ...)."""

    name = "ocean_model"
    fmts = ("hycom", "croco", "croco_xios", "cmems_model")
    outputs_params = {
        "maps": {
            "sort": ["time", "z"],
            "stat": ["time", "z"],
            },
        "timeseries": {
            "sort": ["z"],
            "concat": ["time"],
            "stat": ["time", "z", "y", "x"],
            "output": "merge",
            },
        "vprofiles_sel": {
            # Vertical profiles, one figure per trange/time and/or
            # vrange/vlevel group -- works with or without cloud
            # (_mvprofiles overlays every point/member as its own line).
            # Needs an actual grouping param configured: a bare metazone
            # (no tfreq/trange_seq/vlevel/vrange at all) only has the
            # native-z fallback to split by, which isn't a real
            # "selection" -- use mvprofiles there instead.
            "sort": ["time", "z"],
            "mparams_pro": {
                "selection": ["tfreq", "trange_seq", "vlevel", "vrange"],
                },
            "mparams_con": {
                "vertical": ["vlevel"],
                }
            },
        "mvprofiles": {
            # Vertical profiles, every point/member overlaid on one figure
            # per variable, merged across the whole series -- works with
            # or without cloud. concat over both time and z (not just
            # time) so the native-z-fallback case (no vlevel/vrange
            # configured, one file per native level) gets reassembled
            # into one full profile instead of 384 single-level slices;
            # _merge_z_group keeps vrange bins from being wrongly
            # duplicated along z.
            "concat": ["time", "z"],
            "output": "merge",
            "mparams_con": {
                "vertical": ["vlevel"],
                }
            },
        "uvprofiles": {
            # Cloud vertical profiles, one figure per point in the cloud.
            # concat (not sort) over both time and z -- see mvprofiles.
            "concat": ["time", "z"],
            "output": "merge",
            "mparams_pro": {
                "horizontal": ["cloud"]
                },
            "mparams_con": {
                "vertical": ["vlevel"],
                }
            },
        "diagts_sel": {
            # Theta-saln diagram, one figure per trange/time and/or
            # vrange/vlevel group -- works with or without cloud
            # (_mdiagts stacks every point into "npt" regardless). Needs
            # an actual grouping param configured -- see vprofiles_sel.
            "sort": ["time", "z"],
            "mparams_pro": {
                "selection": ["tfreq", "trange_seq", "vlevel", "vrange"],
                },
            },
        "mdiagts": {
            # Theta-saln diagram merging every time/z group into one
            # dataset (no sort -> single group; concat over both dims) so
            # mdiagts() -- which stacks everything into a single "npt"
            # dim -- draws one figure over the whole dataset, with no
            # splitting and no time/z loop in the plot function itself.
            # Works with or without cloud.
            "concat": ["time", "z"],
            "output": "merge",
            "mparams_con": {
                "vertical": ["vrange", "vlevel"],
                }
            },
        "udiagts": {
            # Cloud theta-saln diagram, one figure per profile in the cloud.
            "concat": ["time", "z"],
            "output": "merge",
            "mparams_pro": {
                "horizontal": ["cloud"],
                },
            "mparams_con": {
                "vertical": ["vlevel"],
                }
            },
        }


class DataWoa18(DataOceanModel):
    """WOA18 climatology (ocean-model-shaped output, but a climatology)."""

    name = "woa18"
    fmts = ("woa18",)
    is_climatology = True


class DataBobyclim(DataOceanModel):
    """Bobyclim climatology (ocean-model-shaped output, but a climatology)."""

    name = "bobyclim"
    fmts = ("bobyclim",)
    is_climatology = True


class DataEddies(DataType):
    """Eddy-detection tool output (py-eddy-tracker, sacso, shoot)."""

    name = "eddies"
    fmts = ("eddy_pet", "eddy_sacso", "eddy_shoot")
    data_vars = ["vmax_area", "vmax_radius"]
    forbidden_params = ["tfreq", "vlevel", "vrange", "cloud"]
    outputs_params = {
        "pdf_eddies": {
            # Eddy detections are obs-indexed (one row per detection), not
            # on a regular time/z grid -- concatenate along "obs" instead
            # of the time/z-based stat/sort armoor.data.datatype.py's
            # other types use. See armoor.diags.eddies.pdf.
            "concat": ["obs"],
            },
        }


def get_data_type(fmt: str) -> DataType:
    """Look up the DataType for a data.ini `fmt` value.

    Any fmt not explicitly registered is treated as ocean_model, matching
    today's implicit, universal behavior.

    Parameters
    ----------
    fmt : str
        The data.ini `fmt` value (e.g. ``"hycom"``, ``"eddy_pet"``).

    Returns
    -------
    DataType
        The registered instance for `fmt`, or the `DataOceanModel`
        instance if `fmt` is not registered.
    """
    return _REGISTRY.get(fmt, _REGISTRY["hycom"])


def get_data_type_by_name(name) -> DataType:
    """Look up the DataType by its canonical name (e.g. ds.attrs["data_type"]).

    Falls back to ocean_model for None/unrecognized names -- covers older
    outputs written before this attr existed.

    Parameters
    ----------
    name : str or None
        Canonical `DataType.name` (e.g. ``"ocean_model"``, ``"eddies"``).

    Returns
    -------
    DataType
        The registered instance for `name`, or the `DataOceanModel`
        instance if `name` is None/unrecognized.
    """
    return _BY_NAME.get(name, _BY_NAME["ocean_model"])
