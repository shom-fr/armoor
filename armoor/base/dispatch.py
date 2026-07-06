"""Shared method-registry dispatch idiom.

Several classes across armoor.comp and armoor.data (AbstractColocation,
PlotComp, PlotData, AbstractInterpolation) each re-implemented an identical
mechanism: a per-instance ``methods`` dict populated by auto-registering
every callable, non-dunder method of the class, plus a ``call(name, ...)``
dispatcher. This module hosts that mechanism once, in two variants matching
the two usage shapes found in the codebase.
"""
from armoor.__init__ import ArmoorError


class MethodRegistry:
    """Method-registry dispatch for a standalone class.

    Use when the class is never subclassed and calls ``self.__post_init__()``
    itself at the end of its own ``__init__`` (e.g. PlotComp, PlotData).
    """

    _dispatch_label = "Method"

    def __init__(self):
        self.methods = {}

    def register_method(self, func):
        """Register a method in the methods dictionary.

        Parameters
        ----------
        func
            The method to be registered.

        Returns
        -------
        The registered method.
        """
        self.methods[func.__name__] = func
        return func

    def __post_init__(self):
        """Register all callable methods of the class after initialization."""
        for name, method in vars(type(self)).items():
            if callable(method) and not name.startswith("__"):
                self.register_method(method)

    def call(self, method_name, *args, **kwargs):
        """Call a method by its name.

        Parameters
        ----------
        method_name: str
            The name of the method to call.

        Returns
        -------
        The result of the called method.

        Raises
        ------
        ArmoorError: If the method is not found.
        """
        method = self.methods.get(method_name)
        if method:
            return method(self, *args, **kwargs)
        raise ArmoorError(f"{self._dispatch_label} '{method_name}' not found")


class SubclassingMethodRegistry(MethodRegistry):
    """Method-registry dispatch for a genuine abstract base meant to be
    subclassed (e.g. AbstractColocation, AbstractInterpolation).

    Wires a ``__post_init__`` onto every subclass so each subclass registers
    its own methods (rather than the base's), mirroring the codebase's
    existing ``__init_subclass__`` idiom.
    """

    def __init_subclass__(cls, **kwargs):
        """Initialize the subclass by adding the __post_init__ method to the class."""
        super().__init_subclass__(**kwargs)

        def __post_init__(self):
            for name, method in vars(cls).items():
                if callable(method) and not name.startswith("__"):
                    self.register_method(method)
        cls.__post_init__ = __post_init__
