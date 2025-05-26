import logging
from pathlib import Path
import xarray as xr
from xoa.plot import plot_minimap

from armoor.__init__ import ArmoorError
from armoor.base.ranges import trange_seq, vrange
from armoor.base.plot import create_subplots, save_figure, diagdisp
from armoor.base import LINE_COLORS
from armoor.comp import OUTPUTS_VARS
from armoor.comp.stats import StatsComp

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


    def diagdisp(self, dsref, dsprod, figtitle, figname):
        
        for var in self.mparams.get("vars"):
            units = dsref[var].attrs['units']
            fig, ax = create_subplots(
                1, 1,
                title=figtitle.format(**locals())
            )
            ax = diagdisp(dsref[var], dsprod[var], ax,
                     x_label=f"{dsref.attrs['data_name']}",
                     y_label=f"{dsprod.attrs['data_name']}"
                     )
            if ax is None:
                continue
            if "npts" in dsref.dims:
                plot_coords = "points"
            else:
                plot_coords = "filledbox"
            plot_minimap(dsref, plot_coords=plot_coords, extent="global")
            self.save_figure(
                fig,
                figname.format(**locals())
                )
        

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
            
            figtitle = (
                f"{self.func_comp}: global dispersion diagram \n"+
                f"{self.metazone} \n "+
                "{var} [{units}]"
            )
            figname = (
                f"{self.func_comp}/plot/{self.metazone}/{prod}" + 
                "/{var}/diagdisp_glob.png"
                )
            self.diagdisp(
                dsref,
                dsprod,
                figtitle,
                figname
                )
            
            dsprod.close()
            dsref.close()
    
    def diagdisp_sel(self):
        """Plot a dispersion diagram per product and range."""
        for prod, ncins in self.mparams.get("ncins").items():
            logger.info(f"Product: {prod}")
            
            ncprod = [ncin for ncin in ncins if prod in ncin.name][0]
            logger.info(f"ncprod: {ncprod}")
            ncref = [ncin for ncin in ncins if prod not in ncin.name][0]
            logger.info(f"ncref: {ncref}")
            
            dsprod = xr.open_dataset(ncprod)
            dsref = xr.open_dataset(ncref)
            
            if "tfreq" in self.mparams:
                for time in dsref.time:
                    figname = (
                        f"{self.func_comp}/plot/{self.metazone}/{prod}" + 
                        "/{var}/" + 
                        f"diagdisp_sel_{time.values}.png"
                        )
                    figtitle = (
                        f"{self.func_comp}: global dispersion diagram \n"+
                        f"{self.metazone}: {time.values}\n "+
                        "{var} [{units}]"
                    )
                    self.diagdisp(
                        dsref.sel(time=time),
                        dsprod.sel(time=time),
                        figtitle,
                        figname
                        )
            elif "trange_seq" in self.mparams:
                tbin = self.mparams['trange_seq'][0]
                tstart = self.mparams['tbound'][0]
                tend = self.mparams['tbound'][1]
                gprod = trange_seq(dsprod, tstart, tend, tbin)
                gref = trange_seq(dsref, tstart, tend, tbin)
                for (tref, dsref), (tprod, dsprod) in zip(gref, gprod):
                    figname = (
                        f"{self.func_comp}/plot/{self.metazone}/{prod}" + 
                        "/{var}/" + 
                        f"diagdisp_self_{tref}.png"
                        )
                    figtitle = (
                        f"{self.func_comp}: global dispersion diagram \n"+
                        f"{self.metazone}: {tref}\n "+
                        "{var} [{units}]"
                    )
                    self.diagdisp(
                        dsref,
                        dsprod,
                        figtitle,
                        figname
                        )
                
            dsprod.close()
            dsref.close()
        return None
    
    def timeseries_stats(self, dicos, var):
        """Get stats for the timeseries."""
        
        if "npts" in dicos[0]["mean"].get("ref"):
        
            pass
        
        else:
        
            fig, axes = create_subplots(
                5, 1, figsize=(10, 8),
                x_label='Date', y_label=None,
                sharex=True
                )

            for idico, dico in enumerate(dicos):
                
                if idico == 0:
                    units = dico["mean"]["ref"][var].attrs["units"]
                    fig.suptitle(
                        f"Time series of statistics: {var} [{units}] \n"
                        f"{self.metazone}"
                        )
                    plot_minimap(dico["data"]["ref"], plot_coords="filledbox", extent="global")
                    
                
                ref_name = dico["mean"]["ref"].attrs["data_name"]
                prod_name = dico["mean"]["prod"].attrs["data_name"]
                
                lw = 2
                axes[0,0].plot(
                    dico["mean"]["ref"].time,
                    dico["mean"]["ref"][var],
                    color="k",
                    linewidth=lw,
                    label=ref_name if idico == 0 else None
                    )
                axes[0,0].plot(
                    dico["mean"]["prod"].time,
                    dico["mean"]["prod"][var],
                    color=LINE_COLORS[idico],
                    linewidth=lw,
                    label=prod_name
                    )
                
                axes[1,0].plot(
                    dico["std"]["ref"].time,
                    dico["std"]["ref"][var],
                    color="k",
                    linewidth=lw,
                    )
                axes[1,0].plot(
                    dico["std"]["prod"].time,
                    dico["std"]["prod"][var],
                    color=LINE_COLORS[idico],
                    linewidth=lw
                    )
                
                axes[2,0].plot(
                    dico["bias"].time,
                    dico["bias"][var],
                    color=LINE_COLORS[idico], 
                    linewidth=lw,
                    label=f"{prod_name} vs {ref_name}"
                    )
                
                axes[3,0].plot(
                    dico["rmse"].time,
                    dico["rmse"][var],
                    color=LINE_COLORS[idico],
                    linewidth=lw
                    )
                
                axes[4,0].plot(
                    dico["rmsec"].time,
                    dico["rmsec"][var],
                    color=LINE_COLORS[idico],
                    linewidth=lw
                    )
            
            axes[0,0].legend(loc='upper left', fontsize=11, frameon=True, fancybox=True)
            axes[2,0].legend(loc='upper left', fontsize=11, frameon=True, fancybox=True)

            axes[0,0].set_ylabel("Mean")
            axes[1,0].set_ylabel("St.D")
            axes[2,0].set_ylabel("Bias")
            axes[3,0].set_ylabel("Rmse")
            axes[4,0].set_ylabel("C.Rmse")
            
        
        
        
        
        
            figname = (
                f"{self.func_comp}/plot/{self.metazone}" + 
                f"/{var}/" + 
                "timeseries_stats.png"
                )
            
        
        
        self.save_figure(fig,figname)
        return None
    
    
    def timeseries_sel(self):
        
        
        return None
    
    
    def timeseries(self):
        """Plot time series."""
        for var in self.mparams.get("vars"):
            dicos = []
            for prod, ncins in self.mparams.get("ncins").items():
                logger.info(f"Product: {prod}")
                ncprod = [ncin for ncin in ncins if prod in ncin.name][0]
                logger.info(f"ncprod: {ncprod}")
                ncref = [ncin for ncin in ncins if prod not in ncin.name][0]
                logger.info(f"ncref: {ncref}")
                with xr.open_dataset(ncref)[[var]] as dsref:
                    with xr.open_dataset(ncprod)[[var]] as dsprod:        
                        dicos.append(StatsComp(
                            self.mparams, dsref, dsprod
                            ).compute())
                if "mean" in dicos[0].keys():
                    self.timeseries_stats(dicos, var)
                else:
                    self.timeseries_sel(dicos, var)
            
                
            
            

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
                
                
                
