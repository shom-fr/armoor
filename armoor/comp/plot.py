import logging
from pathlib import Path
import pandas as pd
import xarray as xr
from xoa.plot import plot_minimap

from armoor.__init__ import ArmoorError
from armoor.base.ranges import trange_seq, vrange
from armoor.base.plot import create_subplots, save_figure, diagdisp
from armoor.base import LINE_COLORS
from armoor.comp import OUTPUTS_VARS, TITLE_PLOTS
from armoor.comp.stats import StatsComp

logger = logging.getLogger(__name__)


class PlotComp:
    """Class for plot comparison."""
    
    def __init__(self, mparams, oparams, func_comp, metazone, ax_minimap):
        """Initialize the AbstractPlotComp instance with an empty dictionary to store methods."""
        self.methods = {}
        self.mparams = mparams
        self.oparams = oparams
        self.func_comp = func_comp
        self.metazone = metazone
        self.ax_minimap = ax_minimap
        self.plot_title = TITLE_PLOTS[func_comp]

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
                nrows=1,
                figsize=(8, 8),
                title=figtitle.format(**locals())
                )
            ax = ax[0]
            ax = diagdisp(dsref[var], dsprod[var], ax,
                x_label=f"{dsref.attrs['data_name']}",
                y_label=f"{dsprod.attrs['data_name']}"
                )
            if ax is None:
                continue
            if "npts" in dsref.dims:
                kw = dict(
                    plot_coords = "points",
                    coords_markersize=4
                    )
            else:
                kw = dict(
                    plot_coords = "filledbox",
                    )
            ax_minimap = plot_minimap(dsref, ax=self.ax_minimap, **kw)
            
            fig.suptitle(
                f"{self.plot_title} \n"
                f"{var} [{units}] \n"
                f"{self.metazone}",
                y=1.02
                )
            
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
                f"{self.plot_title} \n"
                f"{self.metazone} \n "
                "{var} [{units}]"
            )
            figname = (
                f"{self.func_comp}/plot/{self.metazone}"
                "/{var}/"
                f"diagdisp_glob_{prod}.png"
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
                    time = pd.to_datetime(time.values)
                    figname = (
                        f"{self.func_comp}/plot/{self.metazone}" + 
                        "/{var}/" + 
                        f"diagdisp_sel_{prod}_{time:%Y%m%d%H%M%S}.png"
                        )
                    figtitle = (
                        f"{self.plot_title} \n"
                        f"{self.metazone}: {time:%Y-%m-%dT%H:%M:%S}\n "
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
                        f"{self.func_comp}/plot/{self.metazone}/" + 
                        "/{var}/" + 
                        f"diagdisp_sel_{prod}_{tref}.png"
                        )
                    figtitle = (
                        f"{self.plot_title} \n"
                        f"{self.metazone}: {tref}\n "
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
        """Plot time series stastistics."""
        if "npts" in dicos[0]["mean"]["ref"].dims:
            npts = dicos[0]["mean"]["ref"].sizes["npts"]
            figname = (
                "{self.func_comp}/plot/{self.metazone}" + 
                "/{var}/" + 
                "timeseries_stats_{lat_pt}_{lon_pt}.png"
                )
        else:
            npts = 1
            figname = (
                "{self.func_comp}/plot/{self.metazone}" + 
                "/{var}/" + 
                "timeseries_stats.png"
                ) 
        for inpt in range(npts):
            fig, axes = create_subplots(
                nrows=5, figsize=(10, 8),
                x_label='Date', y_label=None,
                sharex=True
                )
            for idico, dico in enumerate(dicos):
                
                if idico == 0:
                    units = dico["mean"]["ref"][var].attrs["units"]
                    fig.suptitle(
                        f"{self.plot_title} \n"
                        f"{var} [{units}] \n"
                        f"{self.metazone}",
                        y=1.01
                        )
                
                if npts > 1:
                    rmean = dico["mean"]["ref"][var].isel(npts=inpt)
                    pmean = dico["mean"]["prod"][var].isel(npts=inpt)
                    rstd = dico["std"]["prod"][var].isel(npts=inpt)
                    pstd = dico["std"]["prod"][var].isel(npts=inpt)
                    bias = dico["bias"][var].isel(npts=inpt)
                    rmse = dico["rmse"][var].isel(npts=inpt)
                    rmsec = dico["rmsec"][var].isel(npts=inpt)
                    
                    plot_coords = "points"
                    lon_pt = rmean.lon.values
                    lat_pt = rmean.lat.values
                
                else:
                    rmean = dico["mean"]["ref"][var]
                    pmean = dico["mean"]["prod"][var]
                    rstd = dico["std"]["prod"][var]
                    pstd = dico["std"]["prod"][var]
                    bias = dico["bias"][var]
                    rmse = dico["rmse"][var]
                    rmsec = dico["rmsec"][var]
                    
                    plot_coords = "filledbox"
                
                plot_minimap(
                    dico["data"]["ref"],
                    ax=self.ax_minimap,
                    plot_coords=plot_coords,
                    coords_markersize=4
                    )

                ref_name = dico["mean"]["ref"].attrs["data_name"]
                prod_name = dico["mean"]["prod"].attrs["data_name"]
                tcoord = "time"
                if "time_bins" in dico["mean"]["ref"].coords:
                    tcoord = "time_bins"
                lw = 2
                axes[0].plot(
                    rmean[tcoord],
                    rmean,
                    color="k",
                    linewidth=lw,
                    label=ref_name if idico == 0 else None
                    )
                axes[0].plot(
                    pmean[tcoord],
                    pmean,
                    color=LINE_COLORS[idico],
                    linewidth=lw,
                    label=prod_name
                    )
                
                axes[1].plot(
                    rstd[tcoord],
                    rstd,
                    color="k",
                    linewidth=lw,
                    )
                axes[1].plot(
                    pstd[tcoord],
                    pstd,
                    color=LINE_COLORS[idico],
                    linewidth=lw
                    )
                
                axes[2].plot(
                    bias[tcoord],
                    bias,
                    color=LINE_COLORS[idico], 
                    linewidth=lw,
                    label=f"{prod_name} vs {ref_name}"
                    )
                
                axes[3].plot(
                    rmse[tcoord],
                    rmse,
                    color=LINE_COLORS[idico],
                    linewidth=lw
                    )
                
                axes[4].plot(
                    rmsec[tcoord],
                    rmsec,
                    color=LINE_COLORS[idico],
                    linewidth=lw
                    )
            
            axes[0].legend(loc='upper left', fontsize=11, frameon=True, fancybox=True)
            axes[2].legend(loc='upper left', fontsize=11, frameon=True, fancybox=True)

            axes[0].set_ylabel("Mean")
            axes[1].set_ylabel("St.D")
            axes[2].set_ylabel("Bias")
            axes[3].set_ylabel("Rmse")
            axes[4].set_ylabel("Ce.Rmse")

            self.save_figure(fig, figname.format(**locals()))
        return None
    
    
    def timeseries_sel(self, dicos, var):
        """Plot time series differences."""
        npts = dicos[0]["ref"].sizes["npts"]
        figname = (
            "{self.func_comp}/plot/{self.metazone}" + 
            "/{var}/" + 
            "timeseries_sel_{lat_pt}_{lon_pt}.png"
            )
        for inpt in range(npts):
            fig, axes = create_subplots(
                nrows=2, figsize=(10, 3.1),
                x_label='Date', y_label=None,
                sharex=True
                )
            for idico, dico in enumerate(dicos):
                
                ref = dico["ref"][var].isel(npts=inpt)
                prod = dico["prod"][var].isel(npts=inpt)
                diff = dico["diff"][var].isel(npts=inpt)

                plot_coords = "points"
                lon_pt = ref.lon.values
                lat_pt = prod.lat.values
                
                if idico == 0:
                    units = dico["ref"][var].attrs["units"]
                    fig.suptitle(
                        f"{self.plot_title} \n"
                        f"{var} [{units}] \n"
                        f"{self.metazone}: {lat_pt}°N, {lon_pt}°E",
                        y=1.05
                        )
            
                plot_minimap(
                    ref,
                    ax=self.ax_minimap,
                    plot_coords=plot_coords,
                    coords_markersize=4
                    )
                 
                ref_name = dico["ref"].attrs["data_name"]
                prod_name = dico["prod"].attrs["data_name"]
                tcoord = "time"

                lw = 2
                axes[0].plot(
                    ref[tcoord],
                    ref,
                    color="k",
                    linewidth=lw,
                    label=ref_name if idico == 0 else None
                    )
                axes[0].plot(
                    prod[tcoord],
                    prod,
                    color=LINE_COLORS[idico],
                    linewidth=lw,
                    label=prod_name
                    )
                
                axes[1].plot(
                    diff[tcoord],
                    diff,
                    color=LINE_COLORS[idico],
                    linewidth=lw,
                    label=f"{prod_name} vs {ref_name}"
                    )
            
            axes[0].legend(loc='upper left', fontsize=11, frameon=True, fancybox=True)
            axes[1].legend(loc='upper left', fontsize=11, frameon=True, fancybox=True)

            axes[0].set_ylabel(var)
            axes[1].set_ylabel("Diff.")

            self.save_figure(fig, figname.format(**locals()))
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
                            self.mparams, dsref, dsprod, extra_dims=["x", "y"]
                            ).compute())
                if "mean" in dicos[0].keys():
                    self.timeseries_stats(dicos, var)
                else:
                    self.timeseries_sel(dicos, var)
            
        return None        
        
    def maps(self):
        """Plot maps per product."""
        for var in self.mparams.get("vars"):
            for prod, ncins in self.mparams.get("ncins").items():
                logger.info(f"Product: {prod}")
                
                ncprod = [ncin for ncin in ncins if prod in ncin.name][0]
                logger.info(f"ncprod: {ncprod}")
                ncref = [ncin for ncin in ncins if prod not in ncin.name][0]
                logger.info(f"ncref: {ncref}")
                
                dsprod = xr.open_dataset(ncprod)
                dsref = xr.open_dataset(ncref)
                
                dicos = StatsComp(
                    self.mparams, dsref[var], dsprod[var]
                    ).compute()
                
                # if "trange" in self.mparams:
                #     tcoord = "time_bins"
                #     plot_comps = ["bias", "rmse"]
                # else:
                #     self.maps_diff(dicos, tcoord)
                #     plot_comps = ["diff"]

                # for plot_comp in plot_comps:
                    
                #     comp = [dicos[plot_comp]]
                #     if plot_comp == "bias":
                #         param = dicos["mean"]
                #         fig, axes = create_subplots(2, 2)
                #     elif plot_comp == "rmse":
                #         comp.append(dicos["rmsec"])
                #         param = dicos["std"]
                #     else:
                #         param = dicos
                #     ref = param["ref"]
                #     prod = param["prod"]   
                    
                    
                    
                
                dsprod.close()
                dsref.close()
        
        return None
    
    
    def save_figure(self, fig, filename):
        """Save figure."""
        filename = Path(filename)
        filename.parent.mkdir(parents=True, exist_ok=True)
        save_figure(fig, filename)    
    