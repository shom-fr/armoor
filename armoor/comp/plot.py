import logging
from pathlib import Path
import cartopy.crs as ccrs
import cartopy.feature as cfeature
from cartopy.mpl.ticker import (LongitudeFormatter, LatitudeFormatter,
                                LatitudeLocator, LongitudeLocator)
from cartopy.mpl.gridliner import LONGITUDE_FORMATTER, LATITUDE_FORMATTER
import cmocean as cmo
import matplotlib.pyplot as plt
from mpl_toolkits.axes_grid1 import make_axes_locatable
import numpy as np
import pandas as pd
import xarray as xr
from xoa.plot import plot_minimap

from armoor.__init__ import ArmoorError
from armoor.base.ranges import trange_seq, vrange
from armoor.base.plot import create_subplots, save_figure, diagdisp
from armoor.base import LINE_COLORS
from armoor.comp import OUTPUTS_VARS, TITLE_PLOTS, CMAP_VARS, METRIC_LABELS
from armoor.comp.stats import StatsComp

logger = logging.getLogger(__name__)

plt.style.use('seaborn-v0_8-whitegrid')
plt.rcParams.update({'font.size': 8})

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
                figtitle.format(**locals()),
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
                    time = pd.to_datetime(tref)
                    figname = (
                        f"{self.func_comp}/plot/{self.metazone}/" + 
                        "/{var}/" + 
                        f"diagdisp_sel_{prod}_{time:%Y%m%d%H%M%S}.png"
                        )
                    figtitle = (
                        f"{self.plot_title} \n"
                        f"{self.metazone}: {time:%Y-%m-%dT%H:%M:%S}\n "
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
            
            axes[0].legend(
                loc='upper left', fontsize=11, frameon=True, fancybox=True
                )
            axes[1].legend(
                loc='upper left', fontsize=11, frameon=True, fancybox=True
                )

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
                prod_name = dsprod.attrs["data_name"]
                ref_name = dsref.attrs["data_name"]
                dicos = StatsComp(
                    self.mparams,
                    dsref[var],
                    dsprod[var]
                    ).compute()
                dsprod.close()
                dsref.close()
                if "trange_seq" in self.mparams:
                    tcoord = "time_bins"
                else:
                    tcoord = "time" 
                if "mean" in dicos.keys():
                    comps = ["bias", "rmse", "rmsec"]
                else:
                    comps = ["diff"]
                for comp in comps:
                    if comp == "diff":
                        ds_prod = dicos["prod"]
                        ds_ref = dicos["ref"]
                        field = None
                    elif comp == "bias":
                        ds_prod = dicos["mean"]["prod"]
                        ds_ref = dicos["mean"]["ref"]
                        field = "Mean"
                    elif (comp == "rmse") or (comp == "rmsec"):
                        ds_prod = dicos["std"]["prod"]
                        ds_ref = dicos["std"]["ref"]
                        field = "St.D"
                    ds_comp = dicos[comp]
                    cmean = np.abs(ds_comp).mean()
                    cstd = cmean + 1.75 * ds_comp.std()
                    if comp in ["rmse", 'rmsec']:
                        cmin, cmax = 0, cstd
                    else:
                        cmin, cmax =  - cstd, cstd
                    if comp == "diff":
                        vmean = np.mean([ds_prod.mean(), ds_ref.mean()])
                        vstd = np.mean([ds_prod.std(), ds_ref.std()])
                        vmin, vmax = vmean - 1.75 * vstd, vmean + 1.75 * vstd
                    else:
                        vmax = np.max([ds_prod.max(), ds_ref.max()])
                        vmin = np.min([ds_prod.min(), ds_ref.min()])
                    dlat = ds_comp.lat.max() - ds_comp.lat.min()
                    dlon = ds_comp.lon.max() - ds_comp.lon.min()
                    aspect_ratio = 3 / 2 * dlat / dlon
                    for it, time in enumerate(ds_comp[tcoord]):
                        time = pd.to_datetime(time.values)
                        fig, axes = create_subplots(
                                layout_type='top_two_bottom_one',
                                figsize=(8 / aspect_ratio, 8),
                                x_label='Date', y_label=None,
                                sharex=True, projection=ccrs.PlateCarree()
                            )
                        da_prod = ds_prod.isel({tcoord: it})
                        da_ref = ds_ref.isel({tcoord: it})
                        da_comp = ds_comp.isel({tcoord: it})
                        if (comp == "bias") or (comp == "diff"):
                            cmap_comp = "cmo.diff"
                        else:
                            cmap_comp = "cmo.amp"
                        if "npts" in ds_prod.dims:
                            m0 = axes[0].scatter(
                                da_prod.lon, da_prod.lat,
                                c=da_prod,
                                vmin=vmin,
                                vmax=vmax,
                                cmap=CMAP_VARS[var]
                                )
                            axes[0].set_title(prod_name)
                            m1 = axes[1].scatter(
                                da_ref.lon, da_ref.lat,
                                c=da_ref,
                                vmin=vmin,
                                vmax=vmax,
                                cmap="cmo.thermal"
                                )
                            axes[1].set_title(ref_name)
                            m2 = axes[2].scatter(
                                da_comp.lon, da_comp.lat,
                                c=da_comp,
                                vmin=cmin,
                                vmax=cmax,
                                cmap=cmap_comp,
                                )
                        else:
                            m0 = axes[0].pcolormesh(
                                da_prod.lon, da_prod.lat, da_prod,
                                vmin=vmin,
                                vmax=vmax,
                                cmap="cmo.thermal"
                                )
                            axes[0].set_title(prod_name)
                            m1 = axes[1].pcolormesh(
                                da_ref.lon, da_ref.lat, da_ref,
                                vmin=vmin,
                                vmax=vmax,
                                cmap=CMAP_VARS[var]
                                )
                            axes[1].set_title(ref_name)
                            m2 = axes[2].pcolormesh(
                                da_comp.lon, da_comp.lat, da_comp,
                                vmin=cmin,
                                vmax=cmax,
                                cmap=cmap_comp,
                                )
                        
                        cbar1 = fig.colorbar(
                            m1, ax=axes[1], orientation='vertical', fraction=0.046, pad=0.04
                            )
                        if field:
                            cbar1.set_label(field)
                        cbar2 = fig.colorbar(
                            m2, ax=axes[2], orientation='vertical', fraction=0.02, pad=0.02, shrink=0.7
                            )
                        cbar2.set_label(METRIC_LABELS[comp])
                        
                        plt.subplots_adjust(hspace=0.02, wspace=0.01)
                        for iax, ax in enumerate(axes):
                            gl = axes[iax].gridlines(
                                crs=ccrs.PlateCarree(),
                                draw_labels=True,
                                linewidth=0.5,
                                color='gray',
                                alpha=0.5,
                                linestyle='--'
                                )
                            gl.top_labels = False
                            gl.right_labels = False
                        units = ds_ref.attrs["units"]
                        
                        figname = (
                            f"{self.func_comp}/plot/{self.metazone}" + 
                            f"/{var}/" + 
                            f"map_{comp}_{prod}_{time:%Y%m%d%H%M%S}.png"
                            )
                        
                        pos0 = axes[0].get_position()
                        pos2 = axes[2].get_position()
                        pos0.x0 = pos2.x0
                        axes[0].set_position(pos0)
                        
                        fig.suptitle(
                            f"{self.plot_title} \n"
                            f"{var} [{units}] \n"
                            f"{self.metazone}: {time:%Y-%m-%dT%H:%M:%S}",
                            #y=pos0.y1 + 0.09 * aspect_ratio
                            )
                        
                        self.save_figure(fig, figname)
                        
        
        return None
    
    
    def save_figure(self, fig, filename):
        """Save figure."""
        filename = Path(filename)
        filename.parent.mkdir(parents=True, exist_ok=True)
        save_figure(fig, filename)
        del fig
    