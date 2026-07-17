"""Per-func_comp dicts, derived from the Comparison registry.

See `armoor.comp.comparison` for the source of truth.
"""
GROUP_SUFFIX = "__armoor_grp"
"""Suffix appended by `concat_then_merge` to dim/coord names of a minor
signature-group (e.g. mld) to avoid colliding with the dominant group's
names of the same size mismatch."""

from armoor.comp.comparison import _REGISTRY

# Derived from the Comparison registry (armoor.comp.comparison) rather than
# hand-maintained in parallel -- this is a deliberate, indefinite transition
# shim kept for backward compatibility with call sites not yet migrated to
# `get_comparison(func_comp)`.
METAZONE_PARAMS = {c.name: c.metazone_params for c in _REGISTRY.values()}
COLOCATION_PARAMS_USER = {c.name: c.colocation_params_user for c in _REGISTRY.values()}
COLOCATION_PARAMS_DEFAULT = {
    c.name: c.colocation_params_default for c in _REGISTRY.values()
    if c.colocation_params_default
    }
OUTPUTS_PARAMS = {c.name: c.outputs_params for c in _REGISTRY.values()}
COMP_VARS = {c.name: c.comp_vars for c in _REGISTRY.values()}
TITLE_PLOTS = {c.name: c.title for c in _REGISTRY.values()}

METRIC_LABELS = {
    "diff": "Difference",
    "bias": "Bias",
    "rmse": "Rmse",
    "rmsec": "Ce.Rmse"
    }
