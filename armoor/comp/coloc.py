import logging
from pathlib import Path
import xarray as xr
import pandas as pd
from dask.distributed import Client
from armoor.__init__ import ArmoorError
from armoor.base.interp import interp_time, grid2loc, regrid, vinterp
from armoor.comp import COLOCATION_PARAMS_USER, COLOCATION_PARAMS_DEFAULT
from armoor.comp.misc import validate_colocation, get_colocation_params

logger = logging.getLogger(__name__)

class AbstractColocation:
    """Abstract class for coloction."""
    
    def __init__(self):
        """Initialize the AbstractColocation instance with an empty dictionary to store methods."""
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
        """Register all callable methods of the class after initialization.
        
        This method is called after the instance is initialized.
        """
        for name, method in vars(self.__class__).items():
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
            AttributeError: If the method is not found.
        """
        method = self.methods.get(method_name)
        if method:
            return method(self, *args, **kwargs)
        raise ArmoorError(f"Colocation '{method_name}' not found")

    def __init_subclass__(cls):
        """Initialize the subclass by adding the __post_init__ method to the class.
        
        This method is called after the class is defined.
        """
        def __post_init__(self):
            for name, method in vars(cls).items():
                if callable(method) and not name.startswith("__"):
                    self.register_method(method)
        cls.__post_init__ = __post_init__


class TimeColocation(AbstractColocation):
    """Colocate timely two datasets.

    Parameters
    ----------
    xarray_obj : xarray.Dataset
        Observation dataset to subset.
    """
    
    def __init__(self, dsref, dsprod, tbound):
        self.dsref = dsref
        self.dsprod = dsprod
        self.methods = {}
        self.start = tbound[0]
        self.end = tbound[1]

    def tfreq(self, tfreq: str) -> xr.Dataset:
        """Subset dataset selecting elements at specific terms.
    
        Parameters
        ----------
        freq : str
            See :ref:`here <timeseries.offset_aliases>` for a list of
            frequency aliases.
            
        Returns
        -------
        xarray.Dataset, xarray.Dataset
        """
        time = pd.date_range(start=self.start, end=self.end, freq=tfreq)
        return interp_time(self.dsref, time), interp_time(self.dsprod, time)
    
    def trange_seq(self, args: [str, str]) -> xr.Dataset:
        """
        Colocate reference and product on the same time axis before ranging.

        Parameters
        ----------
        args: list
            List of two elements, the first one is the bin period
            (See :ref:`here <timeseries.offset_aliases>` for a list of
            bin aliases), 
            the second one is the reference time axis (reference or product).

        Returns
        -------
        xarray.Dataset, xarray.Dataset
        """
        ref = args[1]
        if ref == "reference":
            self.dsprod = interp_time(self.dsprod, self.dsref.time)
        elif ref == "product":
            self.dsref = interp_time(self.dsref, self.dsprod.time)
        else:
            raise ArmoorError(
                "Use 'reference' or 'product' to specify the reference time"
                "for ranging then."
                )
        return self.dsref, self.dsprod


class HorizontalColocation(AbstractColocation):
    """Colocate horizontaly two datasets.

    Parameters
    ----------
    xarray_obj : xarray.Dataset
        Observation dataset to subset.
    """
    
    def __init__(self, dsref, dsprod):
        self.dsref = dsref
        self.dsprod = dsprod
        self.methods = {}

    def cloud(self, coords: [(float, float)]):
        """Interpolate datasets at specific coordinates.

        Parameters
        ----------
        coordinates : list of tuples
            Set of points coordinates (lon, lat) defining the coordinates to select.

        Returns
        -------
        xarray.Dataset, xarray.Dataset
            Dataset with elements located at specific coordinates.
        """
        return grid2loc(self.dsref, coords), grid2loc(self.dsprod, coords)
        
    def href(self, ref: str):
        """Regrid dataset on 'ref' grid.

        Parameters
        ----------
        ref : str
            'reference' or 'product'.

        Returns
        -------
        xarray.Dataset, xarray.Dataset
            Datasets with elements located at specific coordinates.
        """
        if ref == "reference":
            if "mask" in self.dsprod:
                self.dsref = self.dsref.where(self.dsref.mask, drop=True)
            self.dsprod = regrid(self.dsprod, self.dsref) 
        else:
            if "mask" in self.dsprod:
                self.dsprod = self.dsprod.where(self.dsprod.mask, drop=True)
            self.dsref = regrid(self.dsref, self.dsprod)
        if "mask" in self.dsprod:
            self.dsprod = self.dsprod.drop_vars("mask")
        if "mask" in self.dsref:
            self.dsref= self.dsref.drop_vars("mask")
        return self.dsref, self.dsprod
    

class VerticalColocation(AbstractColocation):
    """Colocate horizontaly two datasets.

    Parameters
    ----------
    xarray_obj : xarray.Dataset
        Observation dataset to subset.
    """
    
    def __init__(self, dsref, dsprod):
        self.dsref = dsref
        self.dsprod = dsprod
        self.methods = {}
        self.logger = logging.getLogger(__name__)
        
    def vlevel(self, args: {str: list}):
        """Interpolate datasets to specified vertical levels.
        
        Parameters
        ----------
        args: dict
            A dictionary with a single key-value pair where the key is the vertical coordinate name
            and the value is a list of vertical levels to interpolate to.
        
        Returns
        -------
        xarray.Dataset, xarray.Dataset
            A tuple containing the verticaly interpolated reference dataset and product dataset.
        """
        vname = list(args.keys())[0]
        vlevels = args.get(vname)
        vlevels = xr.DataArray(vlevels, dims="z", name=vname)
        if "z" in self.dsref.dims:
            self.dsref = vinterp(self.dsref, vname, vlevels)
        else:
            logger.warning("No 'z' dim in reference")
        if "z" in self.dsprod.dims:
            self.dsprod = vinterp(self.dsprod, vname, vlevels)
        else:
            self.logger.warning("no 'z' dim in product")
        return self.dsref, self.dsprod
    
    def vrange(self, args: [str, str, list]) -> xr.Dataset:
        """
        Colocate reference and product on the same vertical axis before ranging.

        Parameters
        ----------
        args: list
            List of three elements, the first one is the vertical reference (reference or product),
            the second one is the vertical coodinate,
            the third one is the list of bounds of the vertical bins.

        Returns
        -------
        xarray.Dataset, xarray.Dataset
        """
        vref = args[0]
        vcoord = args[1]
        if vref == "reference":
            self.dsprod = vinterp(self.dsprod, vcoord, self.dsref[vcoord])
        elif vref == "product":
            self.dsref = vinterp(self.dsref, vcoord, self.dsprod[vcoord])
        else:
            raise ArmoorError(
                "Use 'reference' or 'product' to specify the vertical "
                "reference for ranging then."
                )
        return self.dsref, self.dsprod


def validate_and_get_params(metazones, comp_func):
    """Validate and get colocation parameters.
    
    Parameters
    ----------
    metazones: dict
        Dictionary containing metazone information.
    comp_func: str
        Comparison function identifier.
    
    Returns
    -------
    dict
        Colocation parameters.
    """
    validate_colocation(metazones, COLOCATION_PARAMS_USER[comp_func])
    coloc_params = get_colocation_params(
        metazones,
        COLOCATION_PARAMS_USER[comp_func],
        COLOCATION_PARAMS_DEFAULT[comp_func]
        )
    logger.info(f"Colocation parameters are: {coloc_params}")
    return coloc_params

def process_time_colocation(dsref, dsprod, param, tbound):
    """Process colocation for time dimension.
    
    Parameters
    ----------
    dsref: xr.Dataset
        Reference dataset.
    dsprod: xr.Dataset
        Product dataset.
    param: list
        Parameters for time colocation.
    tbound: list
        Time bounds for colocation.
    
    Returns
    -------
    tuple
        Colocated reference and product datasets.
    """
    logger.info("---- Time colocation")
    coloc = TimeColocation(dsref, dsprod, tbound)
    coloc.__post_init__()
    dsref, dsprod = coloc.call(*param)
    return dsref, dsprod
    
def process_horizontal_colocation(dsref, dsprod, param):
    """Process colocation for horizontal dimensions.
    
    Parameters
    ----------
    dsref: xr.Dataset
        Reference dataset.
    dsprod: xr.Dataset
        Product dataset.
    param: list
        Parameters for horizontal colocation.
    
    Returns
    -------
    tuple
        Colocated reference and product datasets.
    """
    logger.info("---- Horizontal colocation")
    coloc = HorizontalColocation(dsref, dsprod)
    coloc.__post_init__()
    dsref, dsprod = coloc.call(*param)
    return dsref, dsprod

def process_vertical_colocation(dsref, dsprod, param):
    """Process colocation for vertical dimensions.
    
    Parameters
    ----------
    dsref: xr.Dataset
        Reference dataset.
    dsprod: xr.Dataset
        Product dataset.
    param: list
        Parameters for vertical colocation.
    
    Returns
    -------
    tuple
        Colocated reference and product datasets.
    """
    logger.info("---- Vertical colocation")
    coloc = VerticalColocation(dsref, dsprod)
    coloc.__post_init__()
    dsref, dsprod = coloc.call(*param)
    return dsref, dsprod

def save_datasets(dsref, dsprod, dirout, ref_name, prod_name):
    """Save datasets to NetCDF files.

    Parameters
    ----------
    dsref: xr.Dataset
        Reference dataset to save.
    dsprod: xr.Dataset
        Product dataset to save.
    dirout: Path
        Directory to save the datasets.
    ref_name: str
        Name for the reference dataset file.
    prod_name: str
        Name for the product dataset file.
    
    Returns
    -------
    tuple
        Paths to the saved reference and product NetCDF files.
    """
    ncout_ref = dirout / f"{ref_name}.nc"
    ncout_prod = dirout / f"{prod_name}.nc"
    dsref.to_netcdf(ncout_ref)
    dsprod.to_netcdf(ncout_prod)
    return ncout_ref, ncout_prod

def main_coloc(ncs, metazones, comp_func):
    """Colocate reference and products.

    Parameters
    ----------
    ncs: list
        List of NetCDF file paths.
    metazones: dict
        Dictionary containing metazone information.
    comp_func: str
        Comparison function identifier.
    
    Returns
    -------
        Dict of paths to the saved reference and product NetCDF files.
    """
    coloc_params = validate_and_get_params(metazones, comp_func)
    ncouts = {}
    for metazone, params in coloc_params.items():
        logger.info(f"Start colocation for {metazone}.")
        tbound = metazones[metazone].get("tbound")
        ncouts[metazone] = {}
        ncref = [nc for nc in ncs if metazone in str(nc) and "ref.nc" in str(nc)][0]
        logger.info(f"Use reference {ncref}")
        dsrefin = xr.open_dataset(ncref)
        ncins = [nc for nc in ncs if metazone in str(nc) and "ref.nc" not in str(nc)]
        for ncin in ncins:
            logger.info(f"-- Process {ncin}")
            dsprodin = xr.open_dataset(ncin)
            dsref = dsrefin.copy()
            dsprod = dsprodin.copy()
            data_name = dsprodin.attrs['data_name']
            if not ncouts[metazone].get(data_name):
                ncouts[metazone].update({data_name: []})
            if params.get("time"):
                dsref, dsprod = process_time_colocation(
                    dsref,
                    dsprod,
                    params.get("time"),
                    tbound
                    )
            if params.get("horizontal"):
                dsref, dsprod = process_horizontal_colocation(
                    dsref,
                    dsprod,
                    params.get("horizontal"),
                    )
            if params.get("vertical"):
                dsref, dsprod = process_vertical_colocation(
                    dsref,
                    dsprod,
                    params.get("vertical"),
                    )

            dsref.attrs = {"data_name": dsrefin.attrs['data_name']}
            dsprod.attrs = {"data_name": dsprodin.attrs['data_name']}

            dirout = Path(f"{comp_func}/coloc/{metazone}/{dsprod.attrs['data_name']}")
            dirout.mkdir(parents=True, exist_ok=True)

            ncout_ref, ncout_prod = save_datasets(
                dsref, dsprod, dirout, dsref.attrs['data_name'], dsprod.attrs['data_name']
                )
            ncouts[metazone][data_name] += [ncout_ref, ncout_prod]
            
            dsref.close()
            dsprod.close()
            dsprodin.close()
        dsrefin.close()
        logger.info(f"End colocation for {metazone}.")

    return ncouts