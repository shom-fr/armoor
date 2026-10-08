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

    Attributes
    ----------
    methods : dict
        Mapping of method name to callable, populated by `__post_init__`.
    """

    _dispatch_label = "Method"

    def __init__(self):
        """Initialize an empty method registry.

        Concrete subclasses must call ``self.__post_init__()`` at the end of
        their own ``__init__`` to populate `methods`.
        """
        self.methods = {}

    def register_method(self, func):
        """Register a callable under its own name.

        Parameters
        ----------
        func : callable
            The method to register.

        Returns
        -------
        callable
            The same `func`, unchanged (allows use as a decorator).
        """
        self.methods[func.__name__] = func
        return func

    def __post_init__(self):
        """Populate `methods` with every callable, non-dunder attribute of
        the instance's own class.

        Returns
        -------
        None
        """
        for name, method in vars(type(self)).items():
            if callable(method) and not name.startswith("__"):
                self.register_method(method)

    def call(self, method_name, *args, **kwargs):
        """Call a registered method by name.

        Parameters
        ----------
        method_name : str
            Name of the method to call.
        *args
            Positional arguments forwarded to the method.
        **kwargs
            Keyword arguments forwarded to the method.

        Returns
        -------
        object
            The return value of the called method.

        Raises
        ------
        ArmoorError
            If no method named `method_name` is registered.
        """
        method = self.methods.get(method_name)
        if method:
            return method(self, *args, **kwargs)
        raise ArmoorError(f"{self._dispatch_label} '{method_name}' not found")


class SubclassingMethodRegistry(MethodRegistry):
    """Method-registry dispatch for a genuine abstract base meant to be
    subclassed (e.g. AbstractColocation, AbstractInterpolation), including
    a further subclass meant to inherit another subclass's methods as-is
    (e.g. PlotSstSatellite(PlotOceanModel), which defines none of its own).

    Wires a ``__post_init__`` onto every subclass so each instance
    registers every callable, non-dunder attribute of its actual runtime
    class -- inherited or overridden, resolved through the normal MRO via
    ``dir()``/``getattr`` -- not just what the subclass itself defines.
    """

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)

        def __post_init__(self):
            for name in dir(type(self)):
                if name.startswith("__"):
                    continue
                method = getattr(type(self), name)
                if callable(method):
                    self.register_method(method)
        cls.__post_init__ = __post_init__
