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
            "mparams_con": {
                "time": ["tfreq"],
                }
            },
        "timeseries": {
            "sort": ["z"],
            "concat": ["time"],
            "stat": ["time", "z", "y", "x"],
            "output": "merge",
            },
        "mvprofiles": {
            "sort": ["time", "z"],
            "mparams_con": {
                "vertical": ["vlevel"],
                }
            },
        "mdiagts": {
            "sort": ["time", "z"],
            },
        "uvprofiles": {
            "concat": ["time"],
            "output": "merge",
            "mparams_pro": {
                "horizontal": ["cloud"]
                },
            "mparams_con": {
                "vertical": ["vlevel"],
                }
            },
        "udiagts": {
            "concat": ["time"],
            "output": "merge",
            "mparams_pro": {
                "horizontal": ["cloud"]
                },
            "mparams_con": {
                "vertical": ["vlevel"],
                }
            },
        }


class DataEddies(DataType):
    """Eddy-detection tool output (py-eddy-tracker, sacso, shoot).

    Inert until the fmt values below are actually produced by
    ``armoor.data.open_decode`` (tracked separately) — registering them now
    reserves the extension point.
    """

    name = "eddies"
    fmts = ("eddy_pet", "eddy_sacso", "eddy_shoot")
    data_vars = ["vmax_area", "vmax_radius"]
    forbidden_params = ["tfreq", "vlevel", "vrange", "cloud"]
    outputs_params = {}


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
