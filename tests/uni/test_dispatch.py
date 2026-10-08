"""Unit tests for armoor.dispatch.SubclassingMethodRegistry.

Regression coverage for a three-level subclassing gap: the generated
__post_init__ used to scan only the exact subclass's own vars(), so a
subclass meant to inherit another subclass's methods without overriding
any of them (e.g. PlotSstSatellite(PlotOceanModel) in armoor.data.plot)
registered nothing at all.
"""
import pytest

from armoor.__init__ import ArmoorError
from armoor.dispatch import SubclassingMethodRegistry


class _Base(SubclassingMethodRegistry):

    def __init__(self):
        self.methods = {}
        self.__post_init__()

    def greet(self):
        return "hello from base"


class _Child(_Base):

    def farewell(self):
        return "bye from child"


class _GrandchildNoOverrides(_Child):
    """Defines nothing of its own -- should still dispatch to both
    _Base's and _Child's methods."""


class TestSubclassingMethodRegistry:

    def test_direct_subclass_registers_own_methods(self):
        obj = _Child()
        assert obj.call("farewell") == "bye from child"

    def test_direct_subclass_inherits_base_methods(self):
        obj = _Child()
        assert obj.call("greet") == "hello from base"

    def test_empty_grandchild_inherits_all_ancestor_methods(self):
        obj = _GrandchildNoOverrides()
        assert obj.call("greet") == "hello from base"
        assert obj.call("farewell") == "bye from child"

    def test_unknown_method_raises(self):
        obj = _GrandchildNoOverrides()
        with pytest.raises(ArmoorError, match="nope"):
            obj.call("nope")
