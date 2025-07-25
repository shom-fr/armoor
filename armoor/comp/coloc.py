import gc
import logging
import warnings
from pathlib import Path
from typing import List, Optional, Tuple

import dask
import numpy as np
import pandas as pd
import xarray as xr
import xoa.coords as xcoords
import xoa.geo as xgeo

import armoor.base.ranges as ranges
from armoor.__init__ import ArmoorError
from armoor.base.interp import grid2loc, interp_time, regrid, vinterp
from armoor.base.io import (create_fast_encoding, get_zarr_encoding,
                            setup_dask_client)
from armoor.base.misc import optimize_for_low_swap
from armoor.comp import (COLOCATION_PARAMS_DEFAULT, COLOCATION_PARAMS_USER,
                         COMP_VARS)
from armoor.comp.misc import get_colocation_params, validate_colocation

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
        self.dsref = interp_time(self.dsref, time)
        self.dsprod = interp_time(self.dsprod, time)
        return self.dsref, self.dsprod
    
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
        tfreq = args[0]
        ref = args[1]
        if len(args) > 2:
            method = args[2]
        else:
            method = "linear"
        if ref == "reference":
            self.dsprod = interp_time(self.dsprod, self.dsref.time, method=method)
            self.dsprod["time"].encoding = self.dsref.time.encoding
            self.dsprod["time"].attrs = self.dsref.time.attrs
        elif ref == "product":
            self.dsref = interp_time(self.dsref, self.dsprod.time, method=method)
            self.dsre["time"].encoding = self.dsprod.time.encoding
            self.dsre["time"].attrs = self.dsprod.time.attrs
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
            if "mask" in self.dsref:
                mask = self.dsref.mask.compute()
                self.dsref = self.dsref.where(mask, drop=True)
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
    
    def _clean_coordinates(self, dataset: xr.Dataset) -> xr.Dataset:
        """Remove temporary coordinates and rename primary ones."""
        coords_to_drop = ["lon", "lat", "lon_1", "lat_1"]
        existing_coords = [coord for coord in coords_to_drop if coord in dataset.coords]
        
        cleaned_ds = dataset.drop_vars(existing_coords)
        return cleaned_ds.rename({"lon_0": "lon", "lat_0": "lat"})
    
    def _calculate_distances_vectorized(self, prod_data: xr.Dataset, ref_data: xr.Dataset) -> xr.DataArray:
        """
        Calculate distances using vectorized operations for all timesteps at once.
        OPTIMISATION 1: Calcul vectorisé pour tous les timesteps simultanément
        """
        rename_dims = {"npts0": "member"}
        if "time" in ref_data.lon.dims:
            rename_dims["npts1"] = "time"
        dist = (xgeo.get_distances(prod_data, ref_data)
                .squeeze()
                .rename(rename_dims)
                .assign_coords(member=prod_data.member)
            )
        return dist
    
    def _handle_time_dependent(self, radius_meters: float) -> None:
        """
        OPTIMISATION MAJEURE: Traite tous les timesteps simultanément au lieu d'une boucle.
        """
        dist_prod2ref = self._calculate_distances_vectorized(self.dsprod, self.dsref)
        mask = dist_prod2ref < radius_meters
        # OPTIMISATION 3: Appliquer le masque et drop en une seule opération
        for coord in ["lon", "lat"]:
            self.dsprod[coord] = self.dsprod[coord].expand_dims({"time": self.dsprod.time})
        self.dsprod = self.dsprod.reset_coords(["lon", "lat"])
        coords = [coord for coord in mask.coords]
        mask = mask.drop_vars(coords)
        self.dsprod = self.dsprod.where(mask, drop=True)
        self.dsprod = self.dsprod.set_coords(["lon", "lat"])

 
    def radius(self, radius: float) -> Tuple[xr.Dataset, xr.Dataset]:
        """
        Version optimisée de la méthode radius.
        
        Parameters
        ----------
        radius : float
            Radius (in km) of the disk around an observation.
        Returns
        -------
        tuple[xarray.Dataset, xarray.Dataset]
            Tuple containing (reference dataset, product dataset)
        """
        if radius <= 0:
            raise ValueError("Radius must be positive")
        
        radius_meters = radius * 1e3
        
        # Préparation des données (unchanged)
        self.dsprod = xcoords.geo_stack(self.dsprod, "member")
        # OPTIMISATION: Choix de la méthode selon le cas
        if "time" not in self.dsref.lon.dims:
            # Cas time-independent (unchanged)
            dist_prod2ref = self._calculate_distances_vectorized(self.dsprod, self.dsref)
            filtered_ds = self.dsprod.where(dist_prod2ref < radius_meters, drop=True)
            self.dsprod = self._clean_coordinates(filtered_ds)
        else:
            self._handle_time_dependent(radius_meters)
        
        # Set depth coordinate if needed (unchanged)
        if "depth" not in self.dsprod.coords and "depth" in self.dsprod.data_vars:
            self.dsprod = self.dsprod.set_coords("depth")
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
        
    def vlevel(self, args: (str, list)):
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
        vname = args[0]
        vlevels = args[1]
        vlevels = xr.DataArray(vlevels, dims="z", name=vname)
        prod_attrs = self.dsprod.attrs
        ref_attrs = self.dsref.attrs
        if "z" in self.dsref.dims:
            self.dsref = vinterp(self.dsref, vname, vlevels)
        else:
            logger.warning("No 'z' dim in reference")
        if "z" in self.dsprod.dims:
            self.dsprod = vinterp(self.dsprod, vname, vlevels)
        else:
            self.logger.warning("no 'z' dim in product")
        self.dsref.attrs.update(ref_attrs)
        self.dsprod.attrs.update(prod_attrs)
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
            attrs = self.dsprod.attrs
            self.dsprod = vinterp(
                self.dsprod.chunk(dict(z=-1)), vcoord, self.dsref[vcoord].chunk(dict(z=-1))
                )
            self.dsprod.attrs.update(attrs)
        elif vref == "product":
            attrs = self.dsref.attrs
            self.dsref = vinterp(
                self.dsref.chunk(dict(z=-1)), vcoord, self.dsprod[vcoord].chunk(dict(z=-1))
                )
            self.dsref.attrs.update(attrs)
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
    metazones = validate_colocation(metazones, COLOCATION_PARAMS_USER[comp_func])
    coloc_params = get_colocation_params(
        metazones,
        COLOCATION_PARAMS_USER[comp_func],
        COLOCATION_PARAMS_DEFAULT.get(comp_func)
        )
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
    attrs = dsref.attrs
    ncname = ""
    if "time" in attrs:
        ncname += f"_{attrs['time']}"
    elif "trange" in attrs:
        ncname += f"_{attrs['trange']}"
    else:
        pass
    
    if "vlevel" in attrs:
        ncname += f"_{attrs['vlevel']}"
    elif "vrange" in attrs:
        ncname += f"_{attrs['vrange']}"
    else:
        pass
    
    ncout_ref = dirout / f"ref{ncname}.zarr"
    ncout_prod = dirout / f"prod{ncname}.zarr"
   
    logger.info(f"Save {ncout_ref}")
    if "mask" in dsref.data_vars:
        dsref = dsref.drop_vars("mask")
    # encoding = create_fast_encoding(dsref)
    dsref = dsref.chunk("auto")
    encoding = get_zarr_encoding(dsref)
    # dsref.to_netcdf(
    #     ncout_ref,
    #     encoding=encoding,
    #     format='NETCDF4',
    #     engine='netcdf4',
    #     compute=True  # Forcer le compute immédiat
    #     )
    dsref.to_zarr(
        store=ncout_ref,
        mode="w",
        encoding=encoding,
        #safe_chunks=False
        # format='NETCDF4',
        # engine='netcdf4',
        #compute=True  # Forcer le compute immédiat
        )
    dsref.close()
    logger.info(f"Save {ncout_prod}")
    if "mask" in dsprod.data_vars:
        dsprod = dsprod.drop_vars("mask")
    # encoding = create_fast_encoding(dsprod)
    dsprod = dsprod.chunk("auto")
    encoding = get_zarr_encoding(dsprod)
    # dsprod.to_netcdf(
    #     ncout_prod,
    #     encoding=encoding,
    #     format='NETCDF4',
    #     engine='netcdf4',
    #     compute=True  # Forcer le compute immédiat
    #     )
    dsprod.to_zarr(
        store=ncout_prod,
        mode="w",
        encoding=encoding,
        #safe_chunks=False
        # format='NETCDF4',
        # engine='netcdf4',
        #compute=True  # Forcer le compute immédiat
        )
    dsprod.close()
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
    
    coloc_check = validate_and_get_params(metazones, comp_func)
    coloc_params = {}
    for metazone, params in coloc_check.items():
        if not params:
            logger.info(f"Skip {metazone}: colocation is not possible for this functionnality.")
        else:
            coloc_params[metazone] = params
    ncouts = {}
    for metazone, params in coloc_params.items():
        logger.info(f"Start colocation for {metazone}.")
        logger.info(f"Colocation parameters are: {params}")
        tbound = metazones[metazone].get("tbound")
        ncrefs = [
            nc for nc in ncs if (metazone in str(nc)) & ("ref" in str(nc))
            ]
        for ncref in ncrefs:
            logger.info(f"Use reference {ncref}")
            dsrefin = xr.open_dataset(ncref)#, engine="h5netcdf")
            logger.info(dsrefin.sizes)
            dsrefin = optimize_for_low_swap(dsrefin, target_chunk_mb=512)
            for var in COMP_VARS[comp_func]:
                da = dsrefin.oceanvars.sel(var)
                if isinstance(da, xr.DataArray):
                    dsrefin[var] = da
            for var in dsrefin.data_vars:
                if (
                    var not in COMP_VARS[comp_func]
                    ) and (
                    var != "mask"
                    ):
                    dsrefin = dsrefin.drop_vars(var)
            ncins = [
                nc for nc in ncs if metazone in str(nc) and "ref" not in str(nc)
                ]
            for ncin in ncins:
                logger.info(f"-- Process {ncin}")
                dsprodin = xr.open_dataset(ncin)
                dsprodin = optimize_for_low_swap(dsprodin, target_chunk_mb=512)
                logger.info(dsprodin.sizes)
                for var in COMP_VARS[comp_func]:
                    dsprodin[var] = dsprodin.oceanvars.sel(var)
                for var in dsprodin.data_vars:
                    if var not in COMP_VARS[comp_func]:
                        dsprodin = dsprodin.drop_vars(var)
                    if (
                        "depth" in dsprodin.coords
                        ) and (
                        "time" in dsprodin.depth.dims
                        ):
                        dsprodin = dsprodin.reset_coords("depth")
                dsref = dsrefin.copy()
                dsprod = dsprodin.copy()
                gattrs_ref = dsref.attrs
                gattrs_prod = dsprod.attrs
                prod_name = dsprodin.attrs['data_name']
                ref_name = dsrefin.attrs['data_name']
                if not ncouts.get(metazone):
                    ncouts[metazone] = {}
                if not ncouts[metazone].get(ref_name):
                    ncouts[metazone][ref_name] = {}
                if not ncouts[metazone][ref_name].get(prod_name):
                    ncouts[metazone][ref_name].update({prod_name: []})
                if params.get("time"):
                    dsref, dsprod = process_time_colocation(
                        dsref,
                        dsprod,
                        params.get("time"),
                        tbound
                        )
                    gc.collect()
                if params.get("horizontal"):
                    dsref, dsprod = process_horizontal_colocation(
                        dsref,
                        dsprod,
                        params.get("horizontal"),
                        )
                    gc.collect()
                if params.get("vertical"):
                    dsref, dsprod = process_vertical_colocation(
                        dsref,
                        dsprod,
                        params.get("vertical"),
                        )
                    gc.collect()
                dsref = dsref.assign_attrs(gattrs_ref)
                dsprod = dsprod.assign_attrs(gattrs_prod)
                # Configuration optimale
                
                # dask.config.set({
                #     'distributed.worker.daemon': False,
                #     'distributed.comm.timeouts.connect': '120s',
                #     'distributed.comm.timeouts.tcp': '120s',
                #     'distributed.worker.memory.target': 0.9,
                #     'distributed.worker.memory.spill': 0.8,
                #     'distributed.worker.memory.pause': 0.9,
                #     'distributed.worker.memory.terminate': 0.95,
                #     'distributed.worker.memory.monitor-interval': '100ms',
                #     'distributed.scheduler.allowed-failures': 2,
                #     'distributed.scheduler.work-stealing': True,
                # })
                
                # with dask.distributed.Client(
                #     n_workers=4,  # Réduire le nombre de workers
                #     threads_per_worker=4,
                #     memory_limit='10GB',
                #     silence_logs=True,
                #     dashboard_address='localhost:8787'
                #     ) as client:
                #     print(client.dashboard_link)
                with setup_dask_client():
                    logger.info("Compute coloc ref")
                    dsref = dsref.compute()
                    logger.info("Compute coloc prod")
                    dsprod = dsprod.compute()
                    
                    time_coloc = params.get("time")
                    if time_coloc != None:
                        if  "tfreq" in params.get("time")[0]:
                            dsref = ranges.tfreq(dsref)
                            dsprod = ranges.tfreq(dsprod)
                        elif "trange_seq" in params.get("time")[0]:
                            if params.get("time")[1][0] != "*":
                                dsref = ranges.trange_seq(dsref, *tbound, params.get("time")[1][0])
                                dsprod = ranges.trange_seq(dsprod, *tbound, params.get("time")[1][0])
                            else:
                                dsref = [dsref]
                                dsprod = [dsprod]
                    else:
                        dsref = [dsref]
                        dsprod = [dsprod]
        
                    vertical_coloc = params.get("vertical")
                    if vertical_coloc != None:
                        if (
                            "vlevel" in params.get("vertical")[0]
                            ) or (
                            comp_func == "comp_mooring"    
                            ):
                            if comp_func == "comp_mooring":
                                vname = "depth"
                            else:
                                vname  = params.get("vertical")[1][0]
                            if comp_func != "comp_sst":
                                dsref = ranges.vlevels(dsref, vname)
                                dsprod = ranges.vlevels(dsprod, vname)
                        elif "vrange" in params.get("vertical")[0]:
                            vname = params.get("vertical")[1][1]
                            vbins = params.get("vertical")[1][2]
                            dsref = ranges.vrange(dsref, vname, vbins)
                            dsprod = ranges.vrange(dsprod, vname, vbins)
                    dssref = dsref
                    dssprod = dsprod
                    del dsref; del dsprod
                    # with setup_dask_client():
                    logger.info("Save coloc data in netcdf")
                    for ids in range(len(dssref)):
                        dsref = dssref[ids]
                        dsprod = dssprod[ids]
                        dirout = Path(
                            f"{comp_func}/coloc/{metazone}/"
                            f"{dsref.attrs['data_name']}/{dsprod.attrs['data_name']}"
                            )
                        dirout.mkdir(parents=True, exist_ok=True)
                        ncout_ref, ncout_prod = save_datasets(
                            dsref,
                            dsprod,
                            dirout,
                            dsref.attrs['data_name'],
                            dsprod.attrs['data_name']
                            )
                        ncouts[metazone][ref_name][prod_name].append(ncout_ref)
                        ncouts[metazone][ref_name][prod_name].append(ncout_prod)
                        dsref.close()
                        dsprod.close()
                    del dssref
                    del dssprod
    
            dsrefin.close()
            gc.collect()
        logger.info(f"End colocation for {metazone}.")
    return ncouts
