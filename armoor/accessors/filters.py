"""ds.filters accessor — wraps ArmoorFilters."""

import xarray as xr

from armoor.base.filters import ArmoorFilters


@xr.register_dataset_accessor("filters")
class FiltersAccessor:
    """Filtering accessor for xr.Dataset.

    Examples
    --------
    >>> ds2 = ds.filters.combined({"polygon": {"coords": [...]}})
    >>> ds2 = ds.filters.sel_closest(ds_obs)
    """

    def __init__(self, obj):
        self._obj = obj
        self._impl = ArmoorFilters(obj)

    def combined(self, filters_config: dict):
        """Apply multiple filters in a single operation.

        Parameters
        ----------
        filters_config : dict
            Keys: 'quality', 'polygon', 'data_selection', 'time_selection',
            'hours_selection', 'tide', 'tresample', 'tsmooth', 'bathy', 'oceanvars'.

        Returns
        -------
        xr.Dataset or None
        """
        return self._impl.apply_combined_filters(filters_config)

    def sel_closest(self, ds_obs):
        """Select the nearest grid point to each observation.

        Parameters
        ----------
        ds_obs : xr.Dataset
            Observation dataset with lon/lat coordinates.

        Returns
        -------
        xr.Dataset
        """
        return self._impl.sel_closest(ds_obs)
