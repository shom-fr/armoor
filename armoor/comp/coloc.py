import logging, gc, warnings
from pathlib import Path
import numpy as np
import xarray as xr
import pandas as pd
import dask
from typing import Tuple, Optional, List
import xoa.coords as xcoords
import xoa.geo as xgeo

from armoor.__init__ import ArmoorError
from armoor.base.interp import interp_time, grid2loc, regrid, vinterp
from armoor.base.misc import optimize_for_low_swap
from armoor.base.io import create_fast_encoding
import armoor.base.ranges as ranges
from armoor.comp import (
    COLOCATION_PARAMS_USER,
    COLOCATION_PARAMS_DEFAULT,
    COMP_VARS
    )
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
        dsref = interp_time(self.dsref, time)
        dsprod = interp_time(self.dsprod, time)
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
        if "time" in prod_data.dims:
            rename_dims["npts1"] = "time"
        return (
            xgeo.get_distances(prod_data, ref_data)
            .squeeze()
            .rename(rename_dims)
            .assign_coords(member=prod_data.member)
        )
    
    def _handle_time_dependent_case_optimized(self, radius_meters: float) -> None:
        """
        OPTIMISATION MAJEURE: Traite tous les timesteps simultanément au lieu d'une boucle.
        """
        # OPTIMISATION 1: Calcul de distances pour tous les timesteps d'un coup
        dist_prod2ref = self._calculate_distances_vectorized(self.dsprod, self.dsref)
        # if "time" in self.dsprod.dims:
        #     dist_prod2ref = dist_prod2ref.swap_dims({"npts1": "time"})
        # OPTIMISATION 2: Filtrage vectorisé sur toutes les dimensions
        mask = dist_prod2ref < radius_meters

        # OPTIMISATION 3: Appliquer le masque et drop en une seule opération
        filtered_ds = self.dsprod.where(mask, drop=True)
        
        # OPTIMISATION 4: Vérifier s'il reste des données de manière vectorisée
        if filtered_ds.sizes.get("member", 0) == 0:
            # Aucune donnée dans le rayon pour aucun timestep
            self.dsprod = self.dsprod.isel(member=slice(0, 0))
            return
        
        # OPTIMISATION 5: Nettoyage des coordonnées en une fois
        self.dsprod = self._clean_coordinates(filtered_ds)
        
        # OPTIMISATION 6: Filtrer dsref de manière cohérente
        # Identifier les timesteps qui ont des données valides
        valid_times = []
        for time_idx in range(len(self.dsref.time)):
            time_mask = mask.isel(time=time_idx)
            if time_mask.any():
                valid_times.append(time_idx)
        
        if valid_times:
            self.dsref = self.dsref.isel(time=valid_times)
        else:
            # Garder la structure mais vide
            self.dsref = self.dsref.isel(time=slice(0, 0))
    
    def _handle_time_dependent_case_chunked(self, radius_meters: float, chunk_size: int = 50) -> None:
        """
        OPTIMISATION ALTERNATIVE: Traitement par chunks pour économiser la mémoire.
        Utilise cette version si vous avez des problèmes de mémoire.
        """
        n_times = len(self.dsref.time)
        
        if n_times <= chunk_size:
            # Si petit nombre de timesteps, utiliser la version complètement vectorisée
            return self._handle_time_dependent_case_optimized(radius_meters)
        
        prod_chunks = []
        ref_chunks = []
        
        # OPTIMISATION: Traitement par chunks de timesteps
        for start_idx in range(0, n_times, chunk_size):
            end_idx = min(start_idx + chunk_size, n_times)
            time_slice = slice(start_idx, end_idx)
            
            # Extraire le chunk
            prod_chunk = self.dsprod.isel(time=time_slice)
            ref_chunk = self.dsref.isel(time=time_slice)
            
            # Calculer distances pour le chunk
            dist_chunk = self._calculate_distances_vectorized(prod_chunk, ref_chunk)
            mask_chunk = dist_chunk < radius_meters
            
            # Filtrer le chunk
            filtered_chunk = prod_chunk.where(mask_chunk, drop=True)
            
            # Vérifier si le chunk a des données valides
            if filtered_chunk.sizes.get("member", 0) > 0:
                # Nettoyer les coordonnées
                cleaned_chunk = self._clean_coordinates(filtered_chunk)
                prod_chunks.append(cleaned_chunk)
                
                # Filtrer ref_chunk pour les timesteps valides
                valid_times_in_chunk = []
                for local_time_idx in range(len(ref_chunk.time)):
                    time_mask = mask_chunk.isel(time=local_time_idx)
                    if time_mask.any():
                        valid_times_in_chunk.append(local_time_idx)
                
                if valid_times_in_chunk:
                    ref_chunks.append(ref_chunk.isel(time=valid_times_in_chunk))
        
        # OPTIMISATION: Concatenation finale en une seule opération
        if prod_chunks:
            self.dsprod = xr.concat(prod_chunks, dim="time")
            self.dsref = xr.concat(ref_chunks, dim="time")
        else:
            self.dsprod = self.dsprod.isel(member=slice(0, 0))
    
    def _handle_time_dependent_case_lazy(self, radius_meters: float) -> None:
        """
        OPTIMISATION ULTIME: Utilisation de Dask pour le calcul lazy.
        Plus complexe mais potentiellement le plus rapide pour de gros datasets.
        """
        # Force le chunking si pas déjà fait
        if not self.dsprod.chunks:
            # Chunk par timestep pour optimiser le calcul parallèle
            self.dsprod = self.dsprod.chunk({"time": 10, "member": -1})
            self.dsref = self.dsref.chunk({"time": 10})
        
        # Calcul lazy des distances
        dist_prod2ref = self._calculate_distances_vectorized(self.dsprod, self.dsref)
        
        # Masque lazy
        mask = dist_prod2ref < radius_meters
        
        # Application du masque de manière lazy
        filtered_ds = self.dsprod.where(mask, drop=True)
        
        # Force le calcul seulement maintenant
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")  # Ignore les warnings Dask
            filtered_ds = filtered_ds.compute()
        
        if filtered_ds.sizes.get("member", 0) == 0:
            self.dsprod = self.dsprod.isel(member=slice(0, 0))
            return
        
        self.dsprod = self._clean_coordinates(filtered_ds)
        
        # Traitement cohérent de dsref
        mask_computed = mask.compute()
        valid_times = []
        for time_idx in range(len(self.dsref.time)):
            time_mask = mask_computed.isel(time=time_idx)
            if time_mask.any():
                valid_times.append(time_idx)
        
        if valid_times:
            self.dsref = self.dsref.isel(time=valid_times)
    
    def radius(self, radius: float, method: str = "vectorized") -> Tuple[xr.Dataset, xr.Dataset]:
        """
        Version optimisée de la méthode radius.
        
        Parameters
        ----------
        radius : float
            Radius (in km) of the disk around an observation.
        method : str, optional
            Optimization method to use:
            - "vectorized": Calcul vectorisé pour tous les timesteps (par défaut, le plus rapide)
            - "chunked": Traitement par chunks (pour économiser la mémoire)
            - "lazy": Utilisation de Dask pour calcul parallèle (pour très gros datasets)
            
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
            # Cas time-dependent: utiliser la méthode optimisée choisie
            if method == "vectorized":
                self._handle_time_dependent_case_optimized(radius_meters)
            elif method == "chunked":
                self._handle_time_dependent_case_chunked(radius_meters)
            elif method == "lazy":
                self._handle_time_dependent_case_lazy(radius_meters)
            else:
                raise ValueError(f"Unknown method: {method}")
        
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
    validate_colocation(metazones, COLOCATION_PARAMS_USER[comp_func])
    coloc_params = get_colocation_params(
        metazones,
        COLOCATION_PARAMS_USER[comp_func],
        COLOCATION_PARAMS_DEFAULT.get(comp_func)
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
    
    ncout_ref = dirout / f"{ref_name}{ncname}.nc"
    ncout_prod = dirout / f"{prod_name}{ncname}.nc"
    encoding = create_fast_encoding(dsref)
    logger.info(f"Save {ncout_ref}")
    # dsref.to_netcdf(
    #     ncout_ref,
    #     encoding=encoding,
    #     format='NETCDF4',
    #     engine='netcdf4',
    #     compute=True  # Forcer le compute immédiat
    #     )
    # encoding = create_fast_encoding(dsprod)
    # logger.info(f"Save {ncout_prod}")
    # dsprod.to_netcdf(
    #     ncout_prod,
    #     encoding=encoding,
    #     format='NETCDF4',
    #     engine='netcdf4',
    #     compute=True  # Forcer le compute immédiat
    #     )
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
        ncref = [
            nc for nc in ncs if (metazone in str(nc)) & ("ref.nc" in str(nc))
            ][0]
        logger.info(f"Use reference {ncref}")
        dsrefin = xr.open_dataset(ncref)#, engine="h5netcdf")
        logger.info(dsrefin.sizes)
        dsrefin = optimize_for_low_swap(dsrefin, target_chunk_mb=16)
        for var in COMP_VARS[comp_func]:
            dsrefin[var] = dsrefin.oceanvars.sel(var)
        for var in dsrefin.data_vars:
            if var not in COMP_VARS[comp_func]:
                dsrefin = dsrefin.drop_vars(var)
        ncins = [
            nc for nc in ncs if metazone in str(nc) and "ref.nc" not in str(nc)
            ]
        for ncin in ncins:
            logger.info(f"-- Process {ncin}")
            dsprodin = xr.open_dataset(ncin)
            logger.info(dsprodin.sizes)
            dsprodin = optimize_for_low_swap(dsprodin, target_chunk_mb=16)
            for var in COMP_VARS[comp_func]:
                dsprodin[var] = dsprodin.oceanvars.sel(var)
            for var in dsprodin.data_vars:
                if var not in COMP_VARS[comp_func]:
                    dsprodin = dsprodin.drop_vars(var)

            dsref = dsrefin.copy()
            dsprod = dsprodin.copy()
            data_name = dsprodin.attrs['data_name']
            if not ncouts[metazone].get(data_name):
                ncouts[metazone].update({
                    data_name: {
                        "ref": [],
                        "prod": []
                        }
                    })
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
            #     memory_limit='18GB',
            #     silence_logs=True,
            #     dashboard_address=':8787'
            #     ) as client:
            #     dsref = dsref.compute()
            #     dsprod = dsprod.compute()
            
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
                if "vlevel" in params.get("vertical")[0]:
                    vname  = params.get("vertical")[1][0]
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
            
            logger.info("Save coloc data in netcdf")
            for ids in range(len(dssref)):
                dsref = dssref[ids]
                dsprod = dssprod[ids]
                dirout = Path(
                    f"{comp_func}/coloc/{metazone}/{dsprod.attrs['data_name']}"
                    )
                dirout.mkdir(parents=True, exist_ok=True)
                ncout_ref, ncout_prod = save_datasets(
                    dsref,
                    dsprod,
                    dirout,
                    dsref.attrs['data_name'],
                    dsprod.attrs['data_name']
                    )
                ncouts[metazone][data_name]["ref"].append(ncout_ref)
                ncouts[metazone][data_name]["prod"].append(ncout_prod)
                dsref.close()
                dsprod.close()

        dsrefin.close()
        gc.collect()
        logger.info(f"End colocation for {metazone}.")
    return ncouts
