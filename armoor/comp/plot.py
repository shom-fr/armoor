import logging
from pathlib import Path
import xarray as xr
from xoa.plot import plot_minimap

from armoor.__init__ import ArmoorError
from armoor.base.plot import create_subplots, save_figure, diagdisp
from armoor.comp import OUTPUTS_VARS

logger = logging.getLogger(__name__)

class PlotComp:
    """Class for plot comparison."""
    
    def __init__(self, mparams, oparams, func_comp, metazone):
        """Initialize the AbstractPlotComp instance with an empty dictionary to store methods."""
        self.methods = {}
        self.mparams = mparams
        self.oparams = oparams
        self.func_comp = func_comp
        self.metazone = metazone

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
        raise ArmoorError(f"Comparison plot '{method_name}' not found")

    def __init_subclass__(cls):
        """Initialize the subclass by adding the __post_init__ method to the class.
        
        This method is called after the class is defined.
        """
        def __post_init__(self):
            for name, method in vars(cls).items():
                if callable(method) and not name.startswith("__"):
                    self.register_method(method)
        cls.__post_init__ = __post_init__

    def diagdisp_glob(self):
        """Plot a global dispersion diagram per product."""
        for prod, ncins in self.mparams.get("ncins").items():
            logger.info(f"Product: {prod}")
            
            ncprod = [ncin for ncin in ncins if prod in ncin.name][0]
            logger.info(f"ncprod: {ncprod}")
            ncref = [ncin for ncin in ncins if prod not in ncin.name][0]
            logger.info(f"ncref: {ncref}")
            
            dsprod = xr.open_dataset(ncprod)
            dsref = xr.open_dataset(ncref)
            
            for var in self.mparams.get("vars"):
                units = dsref[var].attrs['units']
                fig, ax = create_subplots(
                    1, 1,
                    title=f"Global dispersion diagram of {var} [{units}]"
                )
                diagdisp(dsref[var], dsprod[var], ax, x_label=f"{dsref.attrs['data_name']}",
                y_label=f"{dsprod.attrs['data_name']}",)
                plot_minimap(dsref)
                self.save_figure(
                    fig,
                    f"{self.func_comp}/plot/{self.metazone}/{prod}/{var}/diagdisp_glob.png"
                    )
            dsprod.close()
            dsref.close()
        return None
    
    def diagdisp_sel(self):
        """Plot a dispersion diagram per product and range."""
        return None
    
    def timeseries(self):
        """Plot time series with all products."""
        return None
    
    def maps(self):
        """Plot maps per product."""
        return None
    
    def save_figure(self, fig, filename):
        """Save figure."""
        filename = Path(filename)
        filename.parent.mkdir(parents=True, exist_ok=True)
        save_figure(fig, filename)    
    
    
        
        







            # if
            # for prod, ncins in ncs.get(metazone).items():
            #     logger.info(f"Product: {prod}")
                
            #     ncprod = [ncin for ncin in ncins if prod in ncin.name][0]
            #     logger.info(f"ncprod: {ncprod}")
            #     ncref = [ncin for ncin in ncins if prod not in ncin.name][0]
            #     logger.info(f"ncref: {ncref}")
                
                
                
                
                
                
                
                
                
                
                
                
                
                
                # dsprod = xr.open_dataset(ncprod)
                # dsref = xr.open_dataset(ncref)
                
                # dims_stat = []
                # if "trange_seq" in mparams:
                #     dims_stat.append("time")
                #     tbin = mparams['trange_seq'][0]
                #     tstart = mparams['tbound'][0]
                #     tend = mparams['tbound'][1]
                #     logger.info(f"trange_seq: {tbin}")
                #     dsprod = trange_seq(dsprod, tstart, tend, tbin)
                #     dsref = trange_seq(dsref, tstart, tend, tbin)
    
                # if "vrange" in mparams:
                #     dims_stat.append("z")
                #     vbins = mparams["vrange"][1]
                #     vname = mparams["vrange"][0]
                
                
                
