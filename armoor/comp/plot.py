import logging
import os
import re
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Optional

import cartopy.crs as ccrs
import cartopy.feature as cfeature
import cmocean as cmo
import dask
import matplotlib
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import xarray as xr
from cartopy.mpl.gridliner import LATITUDE_FORMATTER, LONGITUDE_FORMATTER
from cartopy.mpl.ticker import (LatitudeFormatter, LatitudeLocator,
                                LongitudeFormatter, LongitudeLocator)
from matplotlib.collections import LineCollection
from mpl_toolkits.axes_grid1 import make_axes_locatable
from xoa.plot import plot_minimap, plot_ts

from armoor.__init__ import ArmoorError
from armoor.base import FILTERS, LINE_COLORS, CMAP_VARS
from armoor.base.filters import create_optimized_mask
from armoor.base.interp import vinterp
from armoor.base.io import setup_dask_client
from armoor.base.plot import create_subplots, diagdisp, save_figure
from armoor.comp import METRIC_LABELS, TITLE_PLOTS
from armoor.comp.stats import StatsComp

logger = logging.getLogger(__name__)

matplotlib.use('Agg')
plt.style.use('seaborn-v0_8-whitegrid')
plt.rcParams.update({'font.size': 8})


class PlotComp:
    """Class for plot comparison."""
    
    def __init__(self, nc, func_comp, metazone):
        """Initialize the AbstractPlotComp instance with an empty dictionary to store methods."""
        self.methods = {}
        self.func_comp = func_comp
        self.metazone = metazone
        self.ax_minimap = [0.7, 0.91, 0.19]
        self.plot_title = TITLE_PLOTS[func_comp]
        self.dt = xr.open_datatree(nc)
        self.__post_init__()

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


    def clean(self):
        self.dt.close()

    def diagdisp(self, dsref, dsprod, varname, figtitle, figname):
        
        fig, ax = create_subplots(
            nrows=1,
            figsize=(8, 8),
            title=figtitle.format(**locals())
            )
        ax = ax[0]
        ax = diagdisp(dsref[varname], dsprod[varname], ax,
            x_label=f"{dsref.attrs['data_name']}",
            y_label=f"{dsprod.attrs['data_name']}"
            )
        if ax is None:
            return
        if dsref.lon.dims != ("x" ,"y"):
            kw = dict(
                plot_coords = "points",
                coords_markersize=4,
                gridlines_draw_labels=True
                )
        else:
            kw = dict(
                plot_coords = "filledbox",
                gridlines_draw_labels=True
                )
        kw.update(
            gridlines_xlabel_style={'size': 6},
            gridlines_ylabel_style={'size': 6}
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

        for prod, node_prod in self.dt.children.items():
        
            dsprod_all = node_prod["prod/data"].to_dataset()
            dsref_all = node_prod["ref/data"].to_dataset()
            
            prod_name = dsprod_all.attrs["data_name"]
            ref_name = dsref_all.attrs["data_name"]
            
            if "member" in dsprod_all.dims:
                dsprod_all = dsprod_all.mean(dim="member")
            if "member" in dsref_all.dims:
                dsref_all = dsref_all.mean(dim="member")
            
            for var in dsprod_all.data_vars:
                dsref = dsref_all[[var]]
                dsprod = dsprod_all[[var]]
                
                units = dsref[var].attrs.get('units')
                    
                figtitle = (
                    f"{self.plot_title} \n"
                    f"{self.metazone} \n"
                    f"{var}, {units}"
                    )
                
                figname = (
                    f"{self.func_comp}/plot/{self.metazone}/{ref_name}/"
                    f"diagdisp_glob_{var}_{prod_name}.png"
                    )
                
                self.diagdisp(
                    dsref,
                    dsprod,
                    var,
                    figtitle,
                    figname
                    )
                
                dsprod.close()
                dsref.close()
    
    def diagdisp_sel(self):
        """Plot a dispersion diagram per product and range."""
        for prod, node_prod in self.dt.children.items():
            
            dsprod_all = node_prod["prod/data"].to_dataset()
            dsref_all = node_prod["ref/data"].to_dataset()
            
            prod_name = dsprod_all.attrs["data_name"]
            ref_name = dsref_all.attrs["data_name"]
            
            if "member" in dsprod_all.dims:
                dsprod_all = dsprod_all.mean(dim="member")
            if "member" in dsref_all.dims:
                dsref_all = dsref_all.mean(dim="member")
            
            for var in dsprod_all.data_vars:
                dsref = dsref_all[[var]]
                dsprod = dsprod_all[[var]]
                
                attrs = dsref.attrs
                ncname = ""
                xtitle = ""
                trange = attrs.get("trange")
                if trange:
                    xtitle += f"{trange} "
                    ncname += f"_{trange}"

                if "vlevel" in attrs:
                    vlevel = attrs.get("vlevel")
                    if isinstance(vlevel, list):
                        vlevel = vlevel[0]
                    ncname += f"_{vlevel}"
                    xtitle += f" {vlevel} m"
                elif "vrange" in attrs:
                    vrange = attrs.get("vrange")
                    if isinstance(vrange, list):
                        vrange = vrange[0]
                    ncname += f"_{vrange}"
                    xtitle += f" {vrange}"
                else:
                    pass
                
                units = dsref[var].attrs.get('units')
                    
                figtitle = (
                    f"{self.plot_title} \n"
                    f"{self.metazone} \n {xtitle}\n "
                    f"{var}, {units}"
                    )
                
                figname = (
                    f"{self.func_comp}/plot/{self.metazone}/{ref_name}/"
                    f"diagdisp_sel_{var}_{prod_name}{ncname}.png"
                    )
                
                self.diagdisp(
                    dsref,
                    dsprod,
                    var,
                    figtitle,
                    figname
                    )
                
                dsprod.close()
                dsref.close()
        return None
    
    def _mdiagts(self, dsref, dsprod, figtitle, figname):
        fig, axes = create_subplots(
            ncols=2,
            figsize=(15, 8),
            title=figtitle.format(**locals())
            )
        ax0 = axes[0]
        ax1 = axes[1]
        vmax = - np.nanmin([dsref.depth.min(), dsprod.depth.min()])
        vmin = - np.nanmax([dsref.depth.max(), dsprod.depth.max()])
        tmin = np.nanmin([dsref.ptemp.min(), dsprod.ptemp.min()])
        tmax = np.nanmax([dsref.ptemp.max(), dsprod.ptemp.max()])
        smin = np.nanmin([dsref.sal.min(), dsprod.sal.min()])
        smax = np.nanmax([dsref.sal.max(), dsprod.sal.max()])
        tsprod = plot_ts(
            dsprod.ptemp, dsprod.sal,
            dens=True, potential=True, absolute=False,
            clabel=True, contour_linewidths=0.2,
            colorbar=False,
            axes=ax0,
            scatter_kwargs=dict(
                c=-dsprod.depth,
                cmap=cmo.cm.deep_r,
                vmin=vmin, vmax=vmax,
                edgecolor='k',
                alpha=0.8,
                linewidths=0.5,
                s=50,
                )
            )
        tsprod["axes"].set_ylabel("ptemp, degrees_C")
        tsprod["axes"].set_xlabel("sal, psu")
        tsprod["axes"].set_xlim([smin, smax])
        tsprod["axes"].set_ylim([tmin, tmax])
        tsprod["axes"].grid(False)
        
        tsref = plot_ts(
            dsref.ptemp, dsref.sal,
            dens=True, potential=True, absolute=False,
            clabel=True, contour_linewidths=0.2,
            colorbar=False,
            axes=ax1,
            scatter_kwargs=dict(
                c=-dsref.depth,
                cmap=cmo.cm.deep_r,
                vmin=vmin, vmax=vmax,
                edgecolor='k',
                alpha=0.8,
                linewidths=0.5,
                s=50,
                )
            )
        tsref["axes"].set_ylabel("")
        tsref["axes"].set_xlabel("sal, psu")
        tsref["axes"].set_xlim([smin, smax])
        tsref["axes"].set_ylim([tmin, tmax])
        tsref["axes"].grid(False)
        divider = make_axes_locatable(tsref["axes"])
        cax = divider.append_axes("right", size="5%", pad=0.1)
        cax.axis('off')
        cbar2 = fig.colorbar(
            tsref["scatter"],
            ax=cax,
            orientation='vertical',
            fraction=0.02,
            pad=0.02,
            shrink=0.7,
            label="Depth, m"
            )
        if dsref.lon.dims != ("x" ,"y"):
            kw = dict(
                plot_coords = "points",
                coords_markersize=4,
                gridlines_draw_labels=True,
                )
        else:
            kw = dict(
                plot_coords = "filledbox",
                gridlines_draw_labels=True,
                )
        kw.update(
            gridlines_xlabel_style={'size': 6},
            gridlines_ylabel_style={'size': 6}
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
    
    def mdiagts(self):
        """Plot multi-profiles theta-saln."""
        for prod, node_prod in self.dt.children.items():
            logger.debug(f"{prod}, Path: {node_prod.path}")
            for data, dt_data in node_prod.items():
                logger.debug(f"{data}, Path: {dt_data.path}")
                if "ref" in data:
                    dsref = dt_data["data"].to_dataset()
                elif "prod" in data:
                    dsprod = dt_data["data"].to_dataset()
            dsprod = dsprod.stack({"npt": list(dsprod.sizes.keys())})
            dsref = dsref.stack({"npt": list(dsref.sizes.keys())})
            dsprod = dsprod.where(~dsprod.ptemp.isnull(), drop=True)
            dsref = dsref.where(~dsref.ptemp.isnull(), drop=True)
            trange = dsprod.attrs.get("trange")
            vlevel = dsprod.attrs.get("vlevel")
            vrange = dsprod.attrs.get("vrange")
            xtitle = ""
            xfigname = ""
            if trange:
                xtitle += f"{trange} "
                xfigname += f"_{trange}"
            if vlevel:
                xtitle += f" {vlevel}"
                xfigname += f"_{vlevel}"
            elif vrange:
                xtitle += f" {vrange}"
                xfigname += f"_{vrange}"
            
            refname = dsref.attrs.get("data_name")
            prodname = dsprod.attrs.get("data_name")
            figtitle = (
                f"{self.plot_title} \n"
                f"{prodname} vs {refname} \n"
                f"{self.metazone}\n"
                f"{xtitle}"
                )
            figname = (
                f"{self.func_comp}/plot/{self.metazone}/{refname}/"
                f"mdiagts_{prod}{xfigname}.png"
                )
                
            self._mdiagts(dsref, dsprod, figtitle, figname)
    
    def udiagts(self):
        """Plot uniquely profiles theta-saln."""
        dssprod = []
        for prod, node_prod in self.dt.children.items():
            logger.info(f"{prod}, Path: {node_prod.path}")
            for data, dt_data in node_prod.items():
                logger.info(f"{data}, Path: {dt_data.path}")
                if "ref" in data:
                    dsref = dt_data["data"].to_dataset()
                elif "prod" in data:
                    dssprod.append(dt_data["data"].to_dataset())
        refname = dsref.attrs.get("data_name")
        vranges = dsref.attrs.get('vrange')
        vlevels = dsref.attrs.get('vlevel')
        for itime in range(dsref.sizes["time"]):
            if isinstance(vranges, list):
                vrange = vranges[itime]
            else:
                vrange = vranges
            if isinstance(vlevels, list):
                vlevel = vlevels[itime]
            else:
                vlevel = vlevels
            dsref_itime = dsref.isel(time=[itime])
            dssprod_itime = [
                dsprod.isel(time=[itime]).squeeze() for dsprod in dssprod
                ]
            dssprod_closest = [
                ds.armoorfilters.sel_closest(
                    dsref_itime
                    ) for ds in dssprod_itime
                ]
            del dssprod_itime
            time = pd.to_datetime(dsref_itime.time.values[0])
            mask = ~dsref_itime.ptemp.isnull()
            if (~mask).all():
                continue
            depth = dsref_itime.depth.where(mask, drop=True)
            zmin = -depth.max()
            zmax = -depth.min()
            xtitle = f"{time:%Y-%m-%dT%H:%M:%S}"
            xfigname = f"_{time:%Y-%m-%dT%H:%M:%S}"
            if vrange:
                xtitle += f"\n {vrange}"
                xfigname  += "_{vrange}"
            if vlevel:
                xtitle += f"\n {vlevel}"
                xfigname  += "_{vlevel}"

            fig, ax = create_subplots(
                nrows=1,
                figsize=(5, 8),
                )
            fig.suptitle(
                f"{self.plot_title} \n"
                f"{self.metazone} \n{xtitle}",
                y=1.01
                )
            ax = ax[0]
            kw_ref = {"label": dsref.attrs["data_name"]}
            tsref = plot_ts(
                dsref_itime.ptemp, dsref_itime.sal,
                dens=True, potential=True, absolute=False,
                clabel=True, contour_linewidths=0.2,
                colorbar=False,
                axes=ax,
                scatter_kwargs=dict(
                    c="k",
                    edgecolor='k',
                    alpha=0.8,
                    linewidths=0.5,
                    s=50,
                    label=refname
                    )
                )
            for iprod, dsprod_closest in enumerate(dssprod_closest):
                tsprod = plot_ts(
                    dsprod_closest.ptemp, dsprod_closest.sal,
                    dens=True, potential=True, absolute=False,
                    clabel=True, contour_linewidths=0.2,
                    colorbar=False,
                    axes=ax,
                    scatter_kwargs=dict(
                        c=LINE_COLORS[iprod],
                        edgecolor='k',
                        alpha=0.8,
                        linewidths=0.5,
                        s=50,
                        label=dssprod[iprod].attrs["data_name"]
                        )
                    )
                ax = tsprod["axes"]
            ax.legend(
                #loc='upper left', 
                fontsize=11, frameon=True, fancybox=True
                )
            ax = tsref["axes"]
            ax.set_ylabel("temp, degrees_C")
            ax.set_xlabel("sal, psu")
            ax.grid(False)
            kw = dict(
                plot_coords = "points",
                coords_markersize=4,
                gridlines_draw_labels=True,
                gridlines_xlabel_style={'size': 6},
                gridlines_ylabel_style={'size': 6},
                )
            plot_minimap(dsref_itime, ax=self.ax_minimap, **kw)
            figname = (
                f"{self.func_comp}/plot/{self.metazone}/{refname}/"
                f"udiagts{xfigname}.png"
                )
            self.save_figure(
                fig,
                figname.format(**locals())
                )    
        
    def _mvprofiles(self, dsref, dsprod, figtitle, figname):
        
        ref_color = "k"
        prod_color = "slateblue"

        dsprod = dsprod.reset_coords("depth")
        dsref = dsref.reset_coords("depth")
        dsprod_mean = dsprod.mean(dim=["time", "member"])
        dsref_mean = dsref.mean(dim="time")
        dsprod_std = dsprod.std(dim=["time", "member"])
        dsref_std = dsref.std(dim="time")
        dsref = dsref.set_coords("depth")
        
        mask = ~dsref.ptemp.isnull()
        depth = dsref.depth.where(mask, drop=True)
        zmin = -depth.max()
        zmax = -depth.min()
        dsprod = dsprod.transpose("z", "time", "member")
        for var in dsref.data_vars:
            units = dsref[var].attrs.get('units')
            fig, ax = create_subplots(
                nrows=1,
                figsize=(5, 8),
                title=figtitle.format(**locals())
                )
            ax = ax[0]

            if "member" not in dsprod.depth.dims:
                dsprod["depth"] = dsprod["depth"].broadcast_like(dsprod[var])
            daref = dsref[var]
            daprod = dsprod[var]
            
            vmin = np.nanmin([daref.min(), daprod.min()])
            vmax = np.nanmin([daref.max(), daprod.max()])
            
            daref_mean = dsref_mean[var]
            daprod_mean = dsprod_mean[var]

            daref_std = dsref_std[var]
            daprod_std = dsprod_std[var]

            ref_data = daref.values
            ref_depth = -dsref["depth"]
            
            prod_data = daprod.values
            prod_depth = -dsprod["depth"].values
            
            n_depths, n_times, n_members = prod_data.shape
            
            ref_segments = [np.column_stack([ref_data[i], ref_depth[i]]) for i in range(n_times)]
            ref_lc = LineCollection(ref_segments, colors=ref_color, linewidths=2.0, alpha=0.5, label=dsref.attrs["data_name"])
            ax.add_collection(ref_lc)
            
            # Create LineCollection for production data
            prod_segments = [np.column_stack([prod_data[:, i, j], prod_depth[:, i, j]]) 
                             for i in range(n_times) for j in range(n_members)]
            prod_lc = LineCollection(prod_segments, colors=prod_color, linewidths=2.0, alpha=0.5, label=dsprod.attrs["data_name"])
            ax.add_collection(prod_lc)
            
            # ax.plot(
            #     daref_mean, -dsref_mean.depth, color=ref_color, linewidth=2.0,
            #     label=f"mean {dsref.attrs['data_name']}"
            #     )
            # ax.fill_betweenx(
            #     -dsref_mean.depth, daref_mean - daref_std, daref_mean + daref_std, color=ref_color,
            #     alpha=0.25,
            #     label=f"{dsref.attrs['data_name']} mean +/- std"
            #     )
            # ax.plot(
            #     daprod_mean, -dsprod_mean.depth, color=prod_color, linewidth=2.0,
            #     label=f"{dsprod.attrs['data_name']}"    
            #     )
            # ax.fill_betweenx(
            #     -dsprod_mean.depth, daprod_mean - daprod_std, daprod_mean + daprod_std, color=prod_color,
            #     alpha=0.25,
            #     label=f"{dsprod.attrs['data_name']} mean +/- std"
            #     )
            
            ax.legend(
                fontsize=11, frameon=True, fancybox=True
                )
                
            ax.set_xlabel(f"{var}, {units}")
            ax.set_ylabel("Depth, m")
            ax.set_xlim([vmin, vmax])
            ax.set_ylim([zmin, zmax])
            kw = dict(
                plot_coords = "points",
                coords_markersize=4,
                gridlines_draw_labels=True,
                gridlines_xlabel_style={'size': 6},
                gridlines_ylabel_style={'size': 6},
                )
            ax_minimap = plot_minimap(dsref, ax=self.ax_minimap, **kw)
            
            fig.suptitle(
                figtitle.format(**locals()),
                y=1.01
                )
            
            self.save_figure(
                fig,
                figname.format(**locals())
                )
    
    def mvprofiles(self):
        """Plot multiple vertical profiles per product."""
        for prod, node_prod in self.dt.children.items():
            logger.debug(f"{prod}, Path: {node_prod.path}")
            for data, dt_data in node_prod.items():
                logger.debug(f"{data}, Path: {dt_data.path}")
                if "ref" in data:
                    dsref = dt_data["data"].to_dataset()
                elif "prod" in data:
                    dsprod = dt_data["data"].to_dataset()
            dsprod = dsprod.where(~dsprod.ptemp.isnull(), drop=True)
            dsref = dsref.where(~dsref.ptemp.isnull(), drop=True)
            trange = dsprod.attrs.get("trange")
            vlevel = dsprod.attrs.get("vlevel")
            vrange = dsprod.attrs.get("vrange")
            xtitle = ""
            xfigname = ""
            if trange:
                xtitle += f"{trange} "
                xfigname += f"_{trange}"
            if vlevel:
                xtitle += f"\n {vlevel}"
                xfigname += f"_{vlevel}"
            elif vrange:
                xtitle += f"\n {vrange}"
                xfigname += f"_{vrange}"
            var = "{var}"
            refname = dsref.attrs.get("data_name")
            prodname = dsprod.attrs.get("data_name")
            figtitle = (
                f"{self.plot_title} \n"
                f"{prodname} vs {refname} \n"
                f"{self.metazone}\n"
                f"{xtitle}"
                )
            figname = (
                f"{self.func_comp}/plot/{self.metazone}/{refname}/"
                f"mvprofiles_{prod}_{var}{xfigname}.png"
                )

            self._mvprofiles(dsref, dsprod, figtitle, figname)  
        # concat_dim = ["time"]
        # if ("trange_seq" in self.mparams) or ("tfreq" in self.mparams):
        #     concat_dim.append("time")
        # for ref_name, prods in self.mparams.get("ncins").items():
        #     logger.info(f"Process comparison for reference: {ref_name}")
        #     for prod, ncins in prods.items():
        #         logger.info(f"Product: {prod}")
        #         ncins_ref = [nc for nc in ncins if "ref_" in str(nc)]
        #         ncins_prod = [nc for nc in ncins if "prod_" in str(nc)]
        #         dsprod = xr.open_mfdataset(ncins_prod, combine="nested", concat_dim="time")
        #         dsref = xr.open_mfdataset(ncins_ref, combine="nested", concat_dim="time")
        #         figtitle = (
        #             f"{self.plot_title} \n"
        #             f"{self.metazone}\n "
        #             )
        #         figname = (
        #             f"{self.func_comp}/plot/{self.metazone}/{ref_name}"
        #             "/{var}/"
        #             f"mvprofiles_{prod}.png"
        #             )
                    
        #         self._mvprofiles(dsref, dsprod, figtitle, figname)
                
        #         dsref.close(); dsprod.close()
        #         del dsref; del dsprod
                
        #         if "trange_seq" in self.mparams:
        #             for icomp in range(len(ncins["ref"])):
        #                 dsref = xr.open_dataset(ncins['ref'][icomp])
        #                 dsprod = xr.open_dataset(ncins['prod'][icomp])
                        
        #                 icomp_name = os.path.basename(ncins['prod'][icomp])[:-3]
        #                 for string in ["prod_", "ref_"]:
        #                     if string in icomp_name:
        #                         icomp_name = icomp_name.replace(string, "")
        #                 figname = (
        #                     f"{self.func_comp}/plot/{self.metazone}" + 
        #                     "/{var}/" + 
        #                     f"mvprofiles_sel_{prod}_{icomp_name}.png"
        #                     )
                        
        #                 time = f"{dsprod.attrs['trange']}"
    
        #                 figtitle = (
        #                     f"{self.plot_title} \n"
        #                     f"{self.metazone} {time}\n "
        #                     )
        #                 self._mvprofiles(dsref, dsprod, figtitle, figname)
                        
        #                 dsref.close(); dsprod.close()
        #                 del dsref; del dsprod

    def uvprofiles(self):
        """Plot uniquely vertical profiles."""
        dssprod = []
        for prod, node_prod in self.dt.children.items():
            logger.info(f"{prod}, Path: {node_prod.path}")
            for data, dt_data in node_prod.items():
                logger.info(f"{data}, Path: {dt_data.path}")
                if "ref" in data:
                    dsref = dt_data["data"].to_dataset()
                elif "prod" in data:
                    dssprod.append(dt_data["data"].to_dataset())
        refname = dsref.attrs.get("data_name")
        vranges = dsref.attrs.get('vrange')
        for itime in range(dsref.sizes["time"]):
            if isinstance(vranges, list):
                vrange = vranges[itime]
            else:
                vrange = vranges
            dsref_itime = dsref.isel(time=[itime])
            dssprod_itime = [dsprod.isel(time=[itime]).squeeze() for dsprod in dssprod]
            dssprod_closest = [ds.armoorfilters.sel_closest(dsref_itime) for ds in dssprod_itime]
            dssprod_mean = [ds.reset_coords("depth").mean(dim="member").set_coords("depth") for ds in dssprod_itime]
            dssprod_std = [ds.reset_coords("depth").std(dim="member").set_coords("depth") for ds in dssprod_itime]
            del dssprod_itime
            time = pd.to_datetime(dsref_itime.time.values[0])
            mask = ~dsref_itime.ptemp.isnull()
            if (~mask).all():
                continue
            depth = dsref_itime.depth.where(mask, drop=True)
            zmin = -depth.max()
            zmax = -depth.min()
            xtitle = f"{time:%Y-%m-%dT%H:%M:%S}"
            xfigname = f"_{time:%Y-%m-%dT%H:%M:%S}"
            if vrange:
                xtitle += f"\n {vrange}"
                xfigname  += "_{vrange}"
            for varname in dsref.data_vars:
                units = dsref[varname].attrs.get("units")
                daref = dsref_itime[varname].squeeze()
                #dasprod_mean= [ds[[varname]].squeeze() for ds in dssprod_mean]
                #dasprod_std= [ds[[varname]].squeeze() for ds in dssprod_std]
                dasprod_closest= [ds[[varname]].squeeze() for ds in dssprod_closest]
                fig, ax = create_subplots(
                    nrows=1,
                    figsize=(5, 8),
                    )
                fig.suptitle(
                    f"{self.plot_title} \n"
                    f"{self.metazone} \n {xtitle}",
                    y=1.01
                    )
                ax = ax[0]
                kw_ref = {"label": dsref.attrs["data_name"]}
                ax.plot(
                    daref,
                    -daref.depth, 
                    color="k",
                    linewidth=2.0,
                    alpha=1.0,
                    **kw_ref
                    )
                for iprod in range(len(dssprod_mean)):
                    data_prod_mean = dssprod_mean[iprod][varname]
                    data_prod_std = dssprod_std[iprod][varname]
                    prod_name = dssprod_mean[iprod].attrs['data_name']
                    ax.plot(
                        dasprod_closest[iprod][varname], -dasprod_closest[iprod].depth,
                        color=LINE_COLORS[iprod], linewidth=2.0,
                        label=f"{prod_name} closest"
                        )
                    
                    ax.fill_betweenx(
                        -data_prod_mean.depth,
                        data_prod_mean - data_prod_std,
                        data_prod_mean + data_prod_std,
                        color=LINE_COLORS[iprod],
                        alpha=0.25,
                        label=f"{prod_name} mean +/- std"
                        )
                ax.legend(
                    #loc='upper left', 
                    fontsize=11, frameon=True, fancybox=True
                    )
                
                ax.set_xlabel(f"{varname}, {units}")
                ax.set_ylabel("Depth, m")
                ax.set_ylim([zmin, zmax])
                
                kw = dict(
                    plot_coords = "points",
                    coords_markersize=4,
                    gridlines_draw_labels=True,
                    gridlines_xlabel_style={'size': 6},
                    gridlines_ylabel_style={'size': 6},
                    )
                ax_minimap = plot_minimap(daref, ax=self.ax_minimap, **kw)
                
                figname = (
                    f"{self.func_comp}/plot/{self.metazone}/{refname}/"
                    f"uvprofiles_{varname}{xfigname}.png"
                    )
    
                self.save_figure(
                    fig,
                    figname.format(**locals())
                    )
        return
    
    def timeseries_stats(self):
        """Plot time series stastistics."""
        prods = list(self.dt.children.keys())
        dt_ref = self.dt.children[f"{prods[0]}"]["ref"]
        dts_prod = [self.dt.children[f"{prod}"]["prod"] for prod in prods]
        dts_comp = [self.dt.children[f"{prod}"]["comp"] for prod in prods]
        
        ref_name = dt_ref["data"].to_dataset().attrs.get("data_name")
        attrs = dt_ref["data"].attrs
        ncname = ""
        xtitle = ""

        if "vlevel" in attrs:
            vlevel = attrs.get("vlevel")
            if isinstance(vlevel, list):
                vlevel = vlevel[0]
            ncname += f"_{vlevel}"
            xtitle += f" {vlevel} m"
        elif "vrange" in attrs:
            vrange = attrs.get("vrange")
            if isinstance(vrange, list):
                vrange = vrange[0]
            ncname += f"_{vrange}"
            xtitle += f" {vrange}"
        else:
            pass
        
        if "npts" in dt_ref["mean"].dims:
            npts = dt_ref["mean"].sizes["npts"]
            figname = (
                "{self.func_comp}/plot/{self.metazone}/{ref_name}/" + 
                "timeseries_stats_{var}_{lat_pt}_{lon_pt}{ncname}.png"
                )
        else:
            npts = 1
            figname = (
                "{self.func_comp}/plot/{self.metazone}/{ref_name}/" + 
                "timeseries_stats_{var}{ncname}.png"
                )
        for var in dt_ref["data"].to_dataset().data_vars:
            for inpt in range(npts):
                fig, axes = create_subplots(
                    nrows=5, figsize=(10, 8),
                    x_label='Date', y_label=None,
                    sharex=True
                    )
                if npts > 1:
                    lon_pt = f"{dt_ref['data'].to_dataset().lon.isel(npts=inpt):.2f}"
                    lat_pt = f"{dt_ref['data'].to_dataset().lat.isel(npts=inpt):.2f}"
                    xcoord = f"{lat_pt}°N; {lon_pt}°E\n"
                else:
                    xcoord = ""
                for iprod, dt_prod in enumerate(dts_prod):
                    dt_comp = dts_comp[iprod]
                    if iprod == 0:
                        da_ref = dt_ref["data"].to_dataset()[var]
                        units = da_ref.attrs.get("units")
                        fig.suptitle(
                            f"{self.plot_title} \n"
                            f"{self.metazone} \n {xtitle} {xcoord}\n"
                            f"{var}, {units} \n",
                            y=1.01
                            )
                        lw = 2
                        da = dt_ref["mean"].to_dataset()[var]
                        if npts > 1:
                            da = da.isel(npts=inpt)
                        axes[0].plot(
                            da.time,
                            da,
                            color="k",
                            linewidth=lw,
                            label=ref_name
                            )
                        da = dt_ref["std"].to_dataset()[var]
                        if npts > 1:
                            da = da.isel(npts=inpt)
                        axes[1].plot(
                            da.time,
                            da,
                            color="k",
                            linewidth=lw,
                            label=ref_name
                            )
                        
                        if da_ref.lon.dims == ("x", "y"):
                            plot_coords = "filledbox"
                        else:
                            plot_coords = "points"
                    plot_minimap(
                        da_ref if npts == 1 else da_ref.isel(npts=inpt),
                        ax=self.ax_minimap,
                        plot_coords=plot_coords,
                        coords_markersize=4,
                        gridlines_draw_labels=True,
                        gridlines_xlabel_style={'size': 6},
                        gridlines_ylabel_style={'size': 6},
                        )
                    
                    prod_name = dt_prod["data"].to_dataset().attrs["data_name"]

                    da = dt_prod["mean"].to_dataset()[var]
                    if npts > 1:
                        da = da.isel(npts=inpt)
                    axes[0].plot(
                        da.time,
                        da,
                        color=LINE_COLORS[iprod],
                        linewidth=lw,
                        label=prod_name
                        )
                    da = dt_prod["std"].to_dataset()[var]
                    if npts > 1:
                        da = da.isel(npts=inpt)
                    axes[1].plot(
                        da.time,
                        da,
                        color=LINE_COLORS[iprod],
                        linewidth=lw,
                        label=prod_name
                        )
                    da = dt_comp["bias"].to_dataset()[var]
                    if npts > 1:
                        da = da.isel(npts=inpt)
                    axes[2].plot(
                        da.time,
                        da, 
                        linewidth=lw,
                        label=f"{prod_name} vs {ref_name}"
                        )
                    da = dt_comp["rmse"].to_dataset()[var]
                    if npts > 1:
                        da = da.isel(npts=inpt)
                    axes[3].plot(
                        da.time,
                        da,
                        color=LINE_COLORS[iprod], 
                        linewidth=lw
                        )
                    da = dt_comp["rmsec"].to_dataset()[var]
                    if npts > 1:
                        da = da.isel(npts=inpt)
                    axes[4].plot(
                        da.time,
                        da,
                        color=LINE_COLORS[iprod], 
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
        
    def timeseries_sel(self):
        """Plot time series differences."""
        prods = list(self.dt.children.keys())
        ds_ref = self.dt.children[f"{prods[0]}"]["ref"]["data"].to_dataset()
        dss_prod = [
            self.dt.children[f"{prod}"]["prod"]["data"].to_dataset() for prod in prods
            ]
        dss_comp = [
            self.dt.children[f"{prod}"]["comp"]["diff"].to_dataset() for prod in prods
            ]
        attrs = ds_ref.attrs
        ref_name = attrs.get("data_name")
        
        ncname = ""
        xtitle = ""

        if "vlevel" in attrs:
            vlevel = attrs.get("vlevel")
            if isinstance(vlevel, list):
                vlevel = vlevel[0]
            ncname += f"_{vlevel}"
            xtitle += f" {vlevel} m"
        else:
            pass
        
        if "npts" in ds_ref.dims:
            npts = ds_ref.sizes["npts"]
            figname = (
                "{self.func_comp}/plot/{self.metazone}/{ref_name}/"
                "timeseries_sel_{var}_{lat_pt}_{lon_pt}{ncname}.png"
                )
        else:
            npts = 1
            figname = (
                "{self.func_comp}/plot/{self.metazone}/{ref_name}/"
                "timeseries_sel_{var}{ncname}.png"
                )
        for var in ds_ref.data_vars:
            for inpt in range(npts):
                fig, axes = create_subplots(
                    nrows=2, figsize=(10, 6),
                    x_label='Date', y_label=None,
                    sharex=True
                    )
                if npts > 1:
                    da_ref = ds_ref[var].isel(npts=inpt)
                    das_prod = [ds[var].isel(npts=inpt) for ds in dss_prod]
                    das_comp = [ds[var].isel(npts=inpt) for ds in dss_comp]
                    lon_pt = f"{ds_ref.lon.isel(npts=inpt):.2f}"
                    lat_pt = f"{ds_ref.lat.isel(npts=inpt):.2f}"
                    xtitle += f"{lat_pt}°N; {lon_pt}°E"
                else:
                    da_ref = ds_ref[var]
                    das_prod = [ds[var] for ds in dss_prod]
                    das_comp = [ds[var] for ds in dss_comp]
                for iprod, da_prod in enumerate(das_prod):
                    
                    if iprod == 0:
                        units = da_ref.attrs.get("units")
                        fig.suptitle(
                            f"{self.plot_title} \n"
                            f"{self.metazone} \n {xtitle}\n"
                            f"{var}, {units} \n",
                            y=1.01
                            )
                        lw = 2
                        axes[0].plot(
                            da_ref["time"],
                            da_ref,
                            color="k",
                            linewidth=lw,
                            label=ref_name
                            )
                        
                        if da_ref.lon.dims == ("x", "y"):
                            plot_coords = "filledbox"
                        else:
                            plot_coords = "points"
                    
                    plot_minimap(
                        da_ref,
                        ax=self.ax_minimap,
                        plot_coords=plot_coords,
                        coords_markersize=4,
                        gridlines_draw_labels=True,
                        gridlines_xlabel_style={'size': 6},
                        gridlines_ylabel_style={'size': 6},
                        )
                    
                    prod_name = dss_prod[iprod].attrs["data_name"]
                    if "member" in da_prod.dims:
                        da_prod = da_prod.mean("member")
                    axes[0].plot(
                        da_prod["time"],
                        da_prod,
                        color=LINE_COLORS[iprod],
                        linewidth=lw,
                        label=prod_name
                        )
                    
                    axes[1].plot(
                        das_comp[iprod]["time"],
                        das_comp[iprod],
                        color=LINE_COLORS[iprod],
                        linewidth=lw,
                        label=prod_name
                        )
                
                axes[0].legend(loc='upper left', fontsize=11, frameon=True, fancybox=True)
                axes[1].legend(loc='upper left', fontsize=11, frameon=True, fancybox=True)
    
                axes[0].set_ylabel("")
                axes[1].set_ylabel("Diff.")
    
                self.save_figure(fig, figname.format(**locals()))
        return None
    
    
    def timeseries(self):
        """Plot time series."""
        for prod, node_prod in self.dt.children.items():
            comps = [comp for comp, _ in node_prod["comp"].items()]
            if "bias" in comps:
                timeseries = self.timeseries_stats
                break
            else:
                timeseries = self.timeseries_sel
                break
        timeseries()

        return None        
        
    def maps(self):
        """Plot maps per product."""
        for prod, node_prod in self.dt.children.items():
            for comp, dt_comp in node_prod["comp"].items():
                dscomp_all = dt_comp.to_dataset()
                if comp == "bias":
                    data = "mean"
                    field = "Mean"
                elif comp in ("rmse", "rmsec"):
                    data = "std"
                    field = "St.D"
                else:
                    data = "data"
                    field = None
                dsprod_all = node_prod[f"prod/{data}"].to_dataset()
                dsref_all = node_prod[f"ref/{data}"].to_dataset()
                if "member" in dsprod_all.dims:
                    if "member" in dsprod_all.lon.dims:
                        dsprod_all = dsprod_all.reset_coords(["lon", "lat"])
                    dsprod_all = dsprod_all.mean(dim="member")
                    if "lon" not in dsprod_all.coords:
                        dsprod_all = dsprod_all.set_coords(["lon", "lat"])
                if "member" in dsref_all.dims:
                    if "member" in dsref_all.lon.dims:
                        dsref_all = dsref_all.reset_coords(["lon", "lat"])
                    dsref_all = dsref_all.mean(dim="member")
                    if "lon" not in dsref_all.coords:
                        dsref_all = dsref_all.set_coords(["lon", "lat"])

                for var in dscomp_all.data_vars:
                    dscomp = dscomp_all[[var]]
                    dsref = dsref_all[[var]]
                    dsprod = dsprod_all[[var]]
                    
                    attrs = dsref.attrs
                    ncname = ""
                    xtitle = ""
                    trange = attrs.get("trange")
                    if trange:
                        xtitle += f"{trange} "
                        ncname += f"_{trange}"

                    if "vlevel" in attrs:
                        vlevel = attrs.get("vlevel")
                        if isinstance(vlevel, list):
                            vlevel = vlevel[0]
                        ncname += f"_{vlevel}"
                        xtitle += f" {vlevel} m"
                    elif "vrange" in attrs:
                        vrange = attrs.get("vrange")
                        if isinstance(vrange, list):
                            vrange = vrange[0]
                        ncname += f"_{vrange}"
                        xtitle += f" {vrange}"
                    else:
                        pass
                    
                    units = dsref[var].attrs.get('units')
                    
                    figtitle = (
                        f"{self.plot_title} \n"
                        f"{self.metazone} \n {xtitle}\n "
                        f"{var}, {units}"
                        )
                
                    prod_name = dsprod.attrs["data_name"]
                    ref_name = dsref.attrs["data_name"]

                    dsprod = dsprod[var]
                    dsref = dsref[var]
                    dscomp = dscomp[var]
                    
                    cmean = np.abs(dscomp).mean()
                    cstd = cmean + 1.75 * dscomp.std()
                    if comp in ["rmse", 'rmsec']:
                        cmin, cmax = 0, cstd
                    else:
                        cmin, cmax =  - cstd, cstd
                    if comp == "diff":
                        vmean = np.mean([dsprod.mean(), dsref.mean()])
                        vstd = np.mean([dsprod.std(), dsref.std()])
                        vmin, vmax = vmean - 1.75 * vstd, vmean + 1.75 * vstd
                    else:
                        vmax = np.max([dsprod.max(), dsref.max()])
                        vmin = np.min([dsprod.min(), dsref.min()])
                    
                    dlat = dsprod.lat.max() - dsprod.lat.min()
                    dlon = dsprod.lon.max() - dsprod.lon.min()
                    aspect_ratio = 3 / 2 * dlat / dlon
                    fig, axes = create_subplots(
                            layout_type='top_two_bottom_one',
                            figsize=(8 / aspect_ratio, 8),
                            x_label='Date', y_label=None,
                            sharex=True, projection=ccrs.PlateCarree()
                        )
                    if (comp == "bias") or (comp == "diff"):
                        cmap_comp = "cmo.diff"
                    else:
                        cmap_comp = "cmo.amp"
                    dsprod = dsprod.squeeze()
                    dsref = dsref.squeeze()
                    dscomp = dscomp.squeeze()
                    if ("npts" in dsprod.dims) or (dsprod.lon.dims != ("y" ,"x")):
                        m0 = axes[0].scatter(
                            dsprod.lon, dsprod.lat,
                            c=dsprod,
                            vmin=vmin,
                            vmax=vmax,
                            cmap=CMAP_VARS[var]
                            )
                        axes[0].set_title(prod_name)
                        m1 = axes[1].scatter(
                            dsref.lon, dsref.lat,
                            c=dsref,
                            vmin=vmin,
                            vmax=vmax,
                            cmap=CMAP_VARS[var]
                            )
                        axes[1].set_title(ref_name)
                        m2 = axes[2].scatter(
                            dsprod.lon, dsprod.lat,
                            c=dscomp,
                            vmin=cmin,
                            vmax=cmax,
                            cmap=cmap_comp,
                            )
                    else:
                        m0 = axes[0].pcolormesh(
                            dsprod.lon, dsprod.lat, dsprod,
                            vmin=vmin,
                            vmax=vmax,
                            cmap=CMAP_VARS[var]
                            )
                        axes[0].set_title(prod_name)
                        m1 = axes[1].pcolormesh(
                            dsref.lon, dsref.lat, dsref,
                            vmin=vmin,
                            vmax=vmax,
                            cmap=CMAP_VARS[var]
                            )
                        axes[1].set_title(ref_name)
                        m2 = axes[2].pcolormesh(
                            dscomp.lon, dscomp.lat, dscomp,
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
                    
                    figname = (
                        f"{self.func_comp}/plot/{self.metazone}/{ref_name}/" + 
                        f"map_{var}_{comp}_{prod_name}{ncname}.png"
                        )
                    
                    pos0 = axes[0].get_position()
                    pos2 = axes[2].get_position()
                    pos0.x0 = pos2.x0
                    axes[0].set_position(pos0)
                    
                    fig.suptitle(figtitle)
                    
                    self.save_figure(fig, figname)
                        
        
        return None
    
    def save_figure(self, fig, filename):
        """Save figure."""
        filename = Path(filename)
        filename.parent.mkdir(parents=True, exist_ok=True)
        save_figure(fig, filename)
        del fig

def main_plot(ncins, metazones, func_comp):
    """Process using dask.bag for functional mapping"""

    def process_task(nc, func_comp, metazone, output):
        plotcomp = PlotComp(nc, func_comp, metazone)
        plotcomp.call(output)
        plotcomp.clean()
        del plotcomp
    
    # Flatten the nested structure into a list of tasks
    tasks = []
    for output, metas in ncins.items():
        for metazone, ncs in metas.items():
            if metazone in metazones:
                for nc in ncs:
                    tasks.append(dask.delayed(process_task)(nc, func_comp, metazone, output))

    # Execute in parallel
    # with setup_dask_client():
    logger.info("Start plot")
    dask.compute(*tasks)
