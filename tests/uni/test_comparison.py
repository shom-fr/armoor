"""Unit tests for armoor.comp.comparison.

These pin each Comparison subclass's class attributes against today's
per-func_comp dict entries in armoor.comp (METAZONE_PARAMS,
COLOCATION_PARAMS_USER, COLOCATION_PARAMS_DEFAULT, OUTPUTS_PARAMS,
COMP_VARS, TITLE_PLOTS) so a literal copy mistake is caught immediately,
before any call site starts relying on the new hierarchy.
"""

from armoor.comp import (
    COLOCATION_PARAMS_DEFAULT,
    COLOCATION_PARAMS_USER,
    COMP_VARS,
    METAZONE_PARAMS,
    OUTPUTS_PARAMS,
    TITLE_PLOTS,
)
from armoor.comp.comparison import (
    CompArgo,
    CompClim,
    CompDrifter,
    CompHydrosection,
    CompModels,
    CompMooring,
    CompSst,
    CompAlti,
    _REGISTRY,
    get_comparison,
)

SUBCLASSES = {
    "comp_sst": CompSst,
    "comp_argo": CompArgo,
    "comp_mooring": CompMooring,
    "comp_drifter": CompDrifter,
    "comp_models": CompModels,
    "comp_clim": CompClim,
    "comp_hydrosection": CompHydrosection,
    "comp_alti": CompAlti,
}


def test_registry_has_all_expected():
    assert set(_REGISTRY.keys()) == set(SUBCLASSES.keys())


def test_registry_instances_match_classes():
    for name, cls in SUBCLASSES.items():
        assert isinstance(_REGISTRY[name], cls)


def test_get_comparison_returns_registered_instance():
    for name, cls in SUBCLASSES.items():
        assert isinstance(get_comparison(name), cls)


def test_get_comparison_raises_for_unknown():
    from armoor import ArmoorError
    import pytest

    with pytest.raises(ArmoorError):
        get_comparison("comp_nonexistent")


def test_metazone_params_match():
    for name, cls in SUBCLASSES.items():
        assert cls().metazone_params == METAZONE_PARAMS[name], name


def test_colocation_params_user_match():
    for name, cls in SUBCLASSES.items():
        assert cls().colocation_params_user == COLOCATION_PARAMS_USER[name], name


def test_colocation_params_default_match():
    for name, cls in SUBCLASSES.items():
        expected = COLOCATION_PARAMS_DEFAULT.get(name, {})
        assert cls().colocation_params_default == expected, name


def test_outputs_params_match():
    for name, cls in SUBCLASSES.items():
        assert cls().outputs_params == OUTPUTS_PARAMS[name], name


def test_comp_vars_match():
    for name, cls in SUBCLASSES.items():
        assert cls().comp_vars == COMP_VARS[name], name


def test_title_match():
    for name, cls in SUBCLASSES.items():
        assert cls().title == TITLE_PLOTS[name], name


def test_drifter_otype_remap():
    assert CompDrifter().otype_remap == {
        "timeseries": "timeseries_drifter",
        "maps_current": "maps_current_drifter",
        "maps_trajectory": "maps_trajectory_drifter",
    }


def test_only_drifter_has_otype_remap():
    for name, cls in SUBCLASSES.items():
        if name == "comp_drifter":
            continue
        assert cls().otype_remap == {}, name
