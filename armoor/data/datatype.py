"""Data source type hierarchy for armoor-data.

Different kinds of input (ocean-model output vs. output from ocean analysis
tools such as eddy-detection trackers) need different variables, different
metazone-parameter compatibility rules, and eventually different output/plot
behavior. This mirrors ``armoor.comp.comparison``'s ``Comparison`` hierarchy,
which solves the same shape of problem for ``armoor-comp-*``.
"""
from armoor import ArmoorError

_REGISTRY = {}  # fmt string -> DataType instance


class DataType:
    """One kind of armoor-data input.

    Subclasses register themselves under every fmt string listed in
    ``fmts`` (many fmt values can map to the same type).
    """

    name = None
    fmts = ()
    data_vars = []
    forbidden_params = []
    outputs_params = {}

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        if cls.name is not None:
            instance = cls()
            for fmt in cls.fmts:
                _REGISTRY[fmt] = instance

    def validate_load_params(self, fmt, metazones):
        """Raise ArmoorError if a metazone config is incompatible with this
        data type. No-op when the type has no forbidden params.
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
    """
    return _REGISTRY.get(fmt, _REGISTRY["hycom"])
