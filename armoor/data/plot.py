import logging
import os
import re
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Optional

import cartopy.crs as ccrs
import cartopy.feature as cfeature
import cmocean as cmo
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

from armoor.base import LINE_COLORS, CMAP_VARS
from armoor.base.dispatch import SubclassingMethodRegistry
from armoor.base.filters import create_optimized_mask
from armoor.base.interp import vinterp
from armoor.base.plot import create_subplots, diagdisp, format_trange, get_output_vminmax, save_figure
from armoor.data.datatype import DataEddies, DataOceanModel, get_data_type_by_name
# from armoor.comp.stats import StatsComp

logger = logging.getLogger(__name__)

matplotlib.use('Agg')
plt.style.use('seaborn-v0_8-whitegrid')
plt.rcParams.update({'font.size': 8})


class _PlotDataBase(SubclassingMethodRegistry):
    """Shared plumbing for all data-source plot types: open the datatree,
    dispatch plot methods by name (see armoor.base.dispatch)."""

    _dispatch_label = "Data plot"

    def __init__(self, dt, metazone, vminmax=None):
        """Initialize with an already-open datatree (see `get_plotter`).

        Parameters
        ----------
        dt : xarray.DataTree
            Already-open output datatree to plot from.
        metazone : str
            Metazone name, used in plot titles/filenames.
        vminmax : dict, optional
            Mapping of variable name to a ``(vmin, vmax)`` pair, overriding
            the automatic color/axis scaling for that variable.
        """
        self.methods = {}
        self.metazone = metazone
        self.ax_minimap = [0.7, 0.91, 0.19]
        self.dt = dt
        self.vminmax = vminmax
        self.saved_files = []
        self.__post_init__()

    def clean(self):
        """Close the underlying datatree.

        Returns
        -------
        None
        """
        self.dt.close()

    def save_figure(self, fig, filename):
        """Save a matplotlib figure to disk, creating parent directories.

        Parameters
        ----------
        fig : matplotlib.figure.Figure
            Figure to save.
        filename : str or Path
            Destination path.

        Returns
        -------
        None
        """
        logger.info(f'save plot {filename}')
        filename = Path(filename)
        filename.parent.mkdir(parents=True, exist_ok=True)
        save_figure(fig, filename)
        self.saved_files.append(str(filename.resolve()))
        del fig


class PlotOceanModel(_PlotDataBase):
    """Plot methods for ocean-model gridded output (ptemp/sal/depth profiles
    and maps) -- today's only real-world data type, moved verbatim."""

    def _mdiagts(self, dsprod, figtitle, figname):
        """Render and save a multi-profile theta-salinity diagram.

        Parameters
        ----------
        dsprod : xarray.Dataset
            Stacked product profiles with ``ptemp``/``sal``/``depth``.
        figtitle : str
            Title template, formatted with the local namespace.
        figname : str
            Output path template, formatted with the local namespace.

        Returns
        -------
        None
        """
        fig, axes = create_subplots(
            ncols=1,
            figsize=(8, 8),
            title=figtitle.format(**locals())
            )
        ax0 = axes[0]
        if 'depth' in self.vminmax:
            vmin, vmax = self.vminmax['depth']
        else:
            vmin = -dsprod.depth.max()
            vmax = -dsprod.depth.min()
        if 'ptemp' in self.vminmax:
            tmin,tmax = self.vminmax['ptemp']
        else:
            tmin = dsprod.ptemp.min()
            tmax = dsprod.ptemp.max()
        if 'ptemp' in self.vminmax:
            smin,smax = self.vminmax['sal']
        else:
            smin = dsprod.sal.min()
            smax = dsprod.sal.max()
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
    
        divider = make_axes_locatable(tsprod["axes"])
        cax = divider.append_axes("right", size="5%", pad=0.1)
        cax.axis('off')
        cbar2 = fig.colorbar(
            tsprod["scatter"],
            ax=cax,
            orientation='vertical',
            fraction=0.02,
            pad=0.02,
            shrink=0.7,
            label="Depth, m"
            )
        if dsprod.lon.dims != ("x" ,"y"):
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
        ax_minimap = plot_minimap(dsprod, ax=self.ax_minimap, **kw)
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
        dsprod = self.dt.children["data"].to_dataset()
        dsprod = dsprod.stack({"npt": list(dsprod.sizes.keys())})
        dsprod = dsprod.where(~dsprod.ptemp.isnull(), drop=True)
        data_name = dsprod.attrs.get("data_name")
        trange = dsprod.attrs.get("trange")
        tfreq = dsprod.attrs.get("time")
        vlevel = dsprod.attrs.get("vlevel")
        vrange = dsprod.attrs.get("vrange")
        xtitle = ""
        xfigname = ""
        if trange:
            title_str, suffix_str = format_trange(trange)
            xtitle += f"{title_str} "
            xfigname += f"_{suffix_str}"
        elif tfreq:
            xtitle += f"{tfreq} "
            xfigname += f"_{tfreq}"
        if vlevel:
            xtitle += f"\n {vlevel}"
            xfigname += f"_{vlevel}"
        elif vrange:
            xtitle += f"\n {vrange}"
            xfigname += f"_{vrange}"
        figtitle = (
            f"{data_name} \n"
            f"{self.metazone}\n"
            f"{xtitle}"
            )
        figname = (
            f"data/plot/{self.metazone}/"
            f"mdiagts_{data_name}{xfigname}.png"
            )
        self._mdiagts(dsprod, figtitle, figname)
    
    def udiagts(self):
        """Plot uniquely profiles theta-saln."""
        dsprod = self.dt.children["data"].to_dataset()
        vranges = dsprod.attrs.get('vrange')
        vlevels = dsprod.attrs.get('vlevel')
        npts = dsprod.sizes["npts"]
        data_name = dsprod.attrs.get("data_name")
        for inpt in range(npts):
            for itime in range(dsprod.sizes["time"]):
                if isinstance(vranges, list):
                    vrange = vranges[itime]
                else:
                    vrange = vranges
                if isinstance(vlevels, list):
                    vlevel = vlevels[itime]
                else:
                    vlevel = vlevels
                ds = dsprod.isel(time=[itime], npts=inpt)#.squeeze()
                lon_pt = f"{ds.lon:.2f}"
                lat_pt = f"{ds.lat:.2f}"
                time = pd.to_datetime(ds.time.values[0])
                mask = ~ds.ptemp.isnull()
                if (~mask).all():
                    continue
                depth = ds.depth.where(mask, drop=True)
                if 'depth' in self.vminmax:
                    zmin, zmax = self.vminmax['depth']
                else:
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
                figname = (
                    f"data/plot/{self.metazone}/"
                    f"udiagts_{data_name}_{lat_pt}_{lon_pt}{xfigname}.png"
                    )
                figtitle = (
                    f"{data_name} \n"
                    f"{self.metazone}\n"
                    f"{lat_pt}N; {lon_pt}E\n"
                    f"{xtitle}"
                    )
                fig, ax = create_subplots(
                    nrows=1,
                    figsize=(5, 8),
                    )
                fig.suptitle(
                    figtitle,
                    y=1.01
                    )
                ax = ax[0]
                kw_prod = {"label": data_name}
                tsprod = plot_ts(
                    ds.ptemp, ds.sal,
                    dens=True, potential=True, absolute=False,
                    clabel=True, contour_linewidths=0.2,
                    colorbar=False,
                    axes=ax,
                    scatter_kwargs=dict(
                        c=-ds.depth,
                        cmap=cmo.cm.deep_r,
                        vmin=zmin, vmax=zmax,
                        edgecolor='k',
                        alpha=0.8,
                        linewidths=0.5,
                        s=50,
                        **kw_prod
                        )
                    )
                divider = make_axes_locatable(tsprod["axes"])
                cax = divider.append_axes("right", size="5%", pad=0.1)
                cax.axis('off')
                cbar2 = fig.colorbar(
                    tsprod["scatter"],
                    ax=cax,
                    orientation='vertical',
                    fraction=0.02,
                    pad=0.02,
                    shrink=0.7,
                    label="Depth, m"
                    )
                # ax.legend(
                #     #loc='upper left', 
                #     fontsize=11, frameon=True, fancybox=True
                #     )
                ax = tsprod["axes"]
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
                plot_minimap(ds, ax=self.ax_minimap, **kw)
                self.save_figure(
                    fig,
                    figname.format(**locals())
                    )    
        
    def _mvprofiles(self, dsprod, figtitle, figname):
        """Render and save multiple vertical profiles, one figure per variable.

        Parameters
        ----------
        dsprod : xarray.Dataset
            Product profiles with a ``z``/``depth`` vertical dimension.
        figtitle : str
            Title template, formatted per variable via the local namespace.
        figname : str
            Output path template, formatted per variable via the local
            namespace.

        Returns
        -------
        None
        """
        ref_color = "k"
        prod_color = "slateblue"

        dsprod = dsprod.reset_coords("depth")

        if set(["x", "y"]).issubset(set(dsprod.dims)):
            dsprod = dsprod.stack(member=['x', 'y'])
        mask = ~dsprod.ptemp.isnull()
        depth = dsprod.depth.where(mask, drop=True)
        if 'depth' in self.vminmax:
            zmin, zmax = self.vminmax['depth']
        else:
            zmin = -depth.max()
            zmax = -depth.min()
        if "member" in dsprod.dims:
            dsprod = dsprod.transpose("z", "time", "member")
        elif "npts" in dsprod.dims:
            dsprod = dsprod.transpose("z", "time", "npts")
        else:
            dsprod = dsprod.transpose("z", "time")
        for var in dsprod.data_vars:
            if "z" not in dsprod[var].squeeze().dims:
                continue
            units = dsprod[var].attrs.get('units')
            fig, ax = create_subplots(
                nrows=1,
                figsize=(5, 8),
                title=figtitle.format(**locals())
                )
            ax = ax[0]

            if "member" not in dsprod.depth.dims:
                dsprod["depth"] = dsprod["depth"].broadcast_like(dsprod[var])
            daprod = dsprod[var]
            
            if var in self.vminmax:
                vmin, vmax = self.vminmax[var]
            else:
                vmin = daprod.min()
                vmax = daprod.max()
            
            prod_data = daprod.values
            prod_depth = -dsprod["depth"].values
            
            n_depths, n_times, n_members = prod_data.shape
            
            # Create LineCollection for production data
            prod_segments = [np.column_stack([prod_data[:, i, j], prod_depth[:, i, j]]) 
                             for i in range(n_times) for j in range(n_members)]
            prod_lc = LineCollection(prod_segments, colors=prod_color, linewidths=1.0, alpha=0.5, label=dsprod.attrs["data_name"])
            ax.add_collection(prod_lc)

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
            ax_minimap = plot_minimap(dsprod, ax=self.ax_minimap, **kw)
            
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
        dsprod = self.dt.children["data"].to_dataset()
        # dsprod = dsprod.where(~dsprod.ptemp.isnull(), drop=True)
        trange = dsprod.attrs.get("trange")
        vlevel = dsprod.attrs.get("vlevel")
        vrange = dsprod.attrs.get("vrange")
        xtitle = ""
        xfigname = ""
        if trange:
            title_str, suffix_str = format_trange(trange)
            xtitle += f"{title_str} "
            xfigname += f"_{suffix_str}"
        if vlevel:
            xtitle += f"\n {vlevel}"
            xfigname += f"_{vlevel}"
        elif vrange:
            xtitle += f"\n {vrange}"
            xfigname += f"_{vrange}"
        var = "{var}"
        prodname = dsprod.attrs.get("data_name")
        figtitle = (
            f"{prodname} \n"
            f"{self.metazone}\n"
            f"{xtitle}"
            )
        figname = (
            f"data/plot/{self.metazone}/"
            f"mvprofiles_{prodname}_{var}{xfigname}.png"
            )
        self._mvprofiles(dsprod, figtitle, figname)

    def uvprofiles(self):
        """Plot uniquely vertical profiles."""
        dsprod = self.dt.children["data"].to_dataset()
        data_name = dsprod.attrs.get("data_name")
        npts = dsprod.sizes["npts"]
        trange = dsprod.attrs.get("trange")
        vlevel = dsprod.attrs.get("vlevel")
        vrange = dsprod.attrs.get("vrange")[0]
        xtitle = ""
        xfigname = ""
        if trange:
            title_str, suffix_str = format_trange(trange)
            xtitle += f"{title_str} "
            xfigname += f"_{suffix_str}"
        if vlevel:
            xtitle += f"\n {vlevel}"
            xfigname += f"_{vlevel}"
        elif vrange:
            xtitle += f"\n {vrange}"
            xfigname += f"_{vrange}"
        for inpt in range(npts):
            ds = dsprod.isel(npts=inpt)

            lon_pt = f"{ds.lon:.2f}"
            lat_pt = f"{ds.lat:.2f}"

            for var in ds.data_vars:
                figname = (
                    f"data/plot/{self.metazone}/"
                    "uvprofiles_{data_name}_{var}_{lat_pt}_{lon_pt}{xfigname}.png"
                    )
                figtitle = (
                    f"{data_name} \n"
                    f"{self.metazone}\n"
                    f"{lat_pt}N; {lon_pt}E\n"
                    f"{xtitle}"
                    )
                daprod = ds[var].copy()
                if "z" not in daprod.dims:
                    continue
                else:
                    daprod = daprod.transpose("z", "time")
                    depth = ds.depth.transpose("z", "time")
                mask = ~daprod.isnull()
                depth = depth.where(mask, drop=True)
                daprod = daprod.where(mask, drop=True)
                
                units = daprod.attrs.get('units')
                fig, ax = create_subplots(
                    nrows=1,
                    figsize=(5, 8),
                    title=figtitle.format(**locals())
                    )
                ax = ax[0]
                        
                if var in self.vminmax:
                    vmin, vmax = self.vminmax[var]
                else:
                    vmin = daprod.min()
                    vmax = daprod.max()
                prod_data = daprod.values
                
                if 'depth' in self.vminmax:
                    zmin, zmax = self.vminmax['depth']
                else:
                    zmin = -depth.max()
                    zmax = -depth.min()
                depth_data = depth.values

                n_depths, n_times = daprod.shape

                # Create LineCollection for production data
                prod_segments = [np.column_stack([prod_data[:, i], -depth_data[:, i]]) 
                                  for i in range(n_times)]
                prod_lc = LineCollection(prod_segments, colors="slateblue", linewidths=2.0, alpha=0.8, label=data_name)
                ax.add_collection(prod_lc)
                
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
                ax_minimap = plot_minimap(ds, ax=self.ax_minimap, **kw)
                
                fig.suptitle(
                    figtitle.format(**locals()),
                    y=1.01
                    )
                
                self.save_figure(
                    fig,
                    figname.format(**locals())
                    )
        
    def timeseries(self):
        """Plot time series differences."""
        ds_data = self.dt.children["data"].to_dataset()
        ds_mean = self.dt.children["mean"].to_dataset()
        ds_std = self.dt.children["std"].to_dataset()
        attrs = ds_data.attrs
        data_name = attrs.get("data_name")
        
        if "npts" in ds_data.dims:
            npts = ds_data.sizes["npts"]
            figname = (
                "data/plot/{self.metazone}/"
                "timeseries_{data_name}_{var}_{lat_pt}_{lon_pt}{ncname}.png"
                )
        else:
            npts = 1
            figname = (
                "data/plot/{self.metazone}/"
                "timeseries_{data_name}_{var}{ncname}.png"
                )
        vars2plot = [var for var in ds_data.data_vars if var != "depth"]
        for var in vars2plot:
            for inpt in range(npts):
                xtitle = ""
                ncname = ""
                if "z" in ds_data[var].dims:
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
                if "trange_seq" in attrs:
                    xtitle += f" time range {attrs.get('trange_seq')}"
                fig, axes = create_subplots(
                    nrows=2, figsize=(10, 6),
                    x_label='Date', y_label=None,
                    sharex=True
                    )
                if npts > 1:
                    da_mean = ds_mean[var].isel(npts=inpt)
                    da_std = ds_std[var].isel(npts=inpt)
                    lon_pt = f"{da_mean.lon:.2f}"
                    lat_pt = f"{da_mean.lat:.2f}"
                    xtitle += f" {lat_pt}°N; {lon_pt}°E"
                else:
                    da_mean = ds_mean[var]
                    da_std = ds_std[var]

                units = da_mean.attrs.get("units")
                fig.suptitle(
                    f"{data_name} \n"
                    f"{self.metazone} \n {xtitle}\n"
                    f"{var}, {units} \n",
                    y=1.01
                    )
                lw = 2
                
                if ds_data.lon.dims == ("x", "y"):
                    plot_coords = "filledbox"
                else:
                    plot_coords = "points"
                plot_minimap(
                    da_mean if npts > 1 else ds_data,
                    ax=self.ax_minimap,
                    plot_coords=plot_coords,
                    coords_markersize=4,
                    gridlines_draw_labels=True,
                    gridlines_xlabel_style={'size': 6},
                    gridlines_ylabel_style={'size': 6},
                )
                
                if "member" in da_mean.dims:
                    da_mean = da_mean.mean("member")
                    da_std = da_std.mean("member")
                    
                axes[0].plot(
                    da_mean["time"],
                    da_mean,
                    color="slateblue",
                    linewidth=lw,
                    )
                
                axes[1].plot(
                    da_std["time"],
                    da_std,
                    color="slateblue",
                    linewidth=lw,
                    )
                
                axes[0].set_ylabel("Mean")
                axes[1].set_ylabel("St. D.")
    
                self.save_figure(fig, figname.format(**locals()))
        return None    
        
    def maps(self):
        """Plot maps per product."""
        ds_data_all = self.dt.children["data"].to_dataset()
        ds_mean_all = self.dt.children["mean"].to_dataset()
        ds_std_all = self.dt.children["std"].to_dataset()
        
        if "member" in ds_mean_all.dims:
            if "member" in ds_mean_all.lon.dims:
                ds_mean_all = ds_mean_all.reset_coords(["lon", "lat"])
                ds_std_all = ds_std_all.reset_coords(["lon", "lat"])
            ds_mean_all = ds_mean_all.mean(dim="member")
            ds_std_all = ds_std_all.mean(dim="member")
            if "lon" not in ds_mean_all.coords:
                ds_mean_all = ds_mean_all.set_coords(["lon", "lat"])
                ds_std_all = ds_std_all.set_coords(["lon", "lat"])
                
        vars2plot = [var for var in ds_data_all.data_vars if var != "depth"]
        for var in vars2plot:
            ds_data = ds_data_all[[var]]
            ds_mean = ds_mean_all[[var]]
            ds_std = ds_std_all[[var]]
            
            attrs = ds_data.attrs
            ncname = ""
            xtitle = ""
            trange = attrs.get("trange")
            if trange:
                title_str, suffix_str = format_trange(trange)
                xtitle += title_str
                ncname += f"_{suffix_str}"
            if "z" in ds_data[var].dims:
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
            else:
                pass
            units = ds_data[var].attrs.get('units')
            data_name = ds_mean_all.attrs["data_name"]
            
            figtitle = (
                f"{data_name} \n {self.metazone}\n {xtitle}\n "
                f"{var}, {units}"
                )

            ds_data = ds_data[var]
            ds_mean = ds_mean[var]
            ds_std = ds_std[var]
            
            cmean = ds_mean.mean()
            cstd =  1.75 * ds_mean.std()
            if var in self.vminmax:
                cmin, cmax = self.vminmax[var]
            else:
                cmin, cmax = cmean - cstd, cmean + cstd
            vmean = ds_std.mean()
            vstd = vmean + 1.75 * ds_std.std()
            vmin, vmax =  - vstd, vstd
            
            dlat = ds_mean.lat.max() - ds_mean.lat.min()
            dlon = ds_mean.lon.max() - ds_mean.lon.min()
            aspect_ratio = 3 / 2 * dlat / dlon
            fig, axes = create_subplots(
                    nrows=2,
                    figsize=(8 / aspect_ratio, 8),
                    x_label='Date', y_label=None,
                    sharex=True, projection=ccrs.PlateCarree()
                )
            ds_mean = ds_mean.squeeze()
            ds_std = ds_std.squeeze()
            if ("npts" in ds_data.dims) or (ds_data.lon.dims != ("y" ,"x")):
                m0 = axes[0].scatter(
                    ds_mean.lon, ds_mean.lat,
                    c=ds_mean,
                    vmin=cmin,
                    vmax=cmax,
                    cmap=CMAP_VARS[var]
                    )
                # axes[0].set_title("Mean")
                m1 = axes[1].scatter(
                    ds_std.lon, ds_std.lat,
                    c=ds_std,
                    vmin=0,
                    vmax=vmax,
                    cmap=CMAP_VARS[var]
                    )
                # axes[1].set_title("St.D.")
            else:
                m0 = axes[0].pcolormesh(
                    ds_mean.lon, ds_mean.lat, ds_mean,
                    vmin=cmin,
                    vmax=cmax,
                    cmap=CMAP_VARS[var]
                    )
                # axes[0].set_title("Mean")
                m1 = axes[1].pcolormesh(
                    ds_std.lon, ds_std.lat, ds_std,
                    vmin=0,
                    vmax=vmax,
                    cmap=CMAP_VARS[var]
                    )
                # axes[1].set_title("St.D.")
                
            cbar0 = fig.colorbar(
                m0, ax=axes[0], orientation='vertical', label="Mean",
                fraction=0.05, shrink=0.5#, pad=0.04
                )
            cbar1 = fig.colorbar(
                m1, ax=axes[1], orientation='vertical', label="St.D.",
                fraction=0.05, shrink=0.5#, pad=0.02,
                )
            
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
                f"data/plot/{self.metazone}/" + 
                f"map_{var}_{data_name}{ncname}.png"
                )
            
            # pos0 = axes[0].get_position()
            # pos1 = axes[1].get_position()
            # pos0.x0 = pos1.x0
            # axes[0].set_position(pos0)
            
            fig.suptitle(figtitle)

            self.save_figure(fig, figname)


        return None


class PlotEddies(_PlotDataBase):
    """Plot methods for eddy-detection tool output (contour_lat/contour_lon,
    center_lat/center_lon, eddy_type, vmax_area -- no depth/ptemp/sal, so
    none of PlotOceanModel's methods apply).

    No methods yet -- calling any output method raises a clear ArmoorError
    via the inherited call() dispatch until eddy plotting is designed.
    """


DataOceanModel.plotter_cls = PlotOceanModel
DataEddies.plotter_cls = PlotEddies


def get_plotter(nc, metazone, vminmax=None):
    """Open a zarr datatree and return the plotter for its data type.

    Falls back to PlotOceanModel for datatrees missing the data_type attr
    (older outputs written before this attr existed) or carrying an
    unrecognized one.

    Parameters
    ----------
    nc : str
        Path to the zarr datatree holding the output to plot.
    metazone : str
        Metazone name, used in plot titles/filenames.
    vminmax : dict, optional
        Mapping of variable name to a ``(vmin, vmax)`` pair, forwarded to
        the plotter.

    Returns
    -------
    _PlotDataBase
        A `PlotOceanModel` or `PlotEddies` instance, with the datatree
        already open.
    """
    dt = xr.open_datatree(nc)
    type_name = dt.children["data"].attrs.get("data_type")
    plot_cls = get_data_type_by_name(type_name).plotter_cls
    return plot_cls(dt, metazone, vminmax)


def _plot_task(nc, metazone, output, vminmax=None):
    """Single plot task — must be module-level for spawn pickling."""
    plotcomp = get_plotter(nc, metazone, vminmax)
    plotcomp.call(output)
    plotcomp.clean()
    saved = plotcomp.saved_files
    del plotcomp
    return saved


def main_plot(ncins, metazones, cfg_outputs=None, kw_dask=None):
    """Process plot tasks in parallel using a multiprocessing pool.

    Parameters
    ----------
    ncins : dict
        Mapping of output name to ``{metazone: [zarr_paths]}``.
    metazones : list of str
        Metazone names to plot (others in `ncins` are skipped).
    cfg_outputs : dict, optional
        Mapping of output name to its output configuration (may hold a
        ``vminmax`` entry).
    kw_dask : tuple, optional
        Dask args as returned by `get_dask_args` (only `[0]`, the worker
        count, is used here).

    Returns
    -------
    list of str
        Absolute paths of all PNG files generated.
    """
    import multiprocessing

    logger.info("Start plot")
    task_args = []
    for output, metas in ncins.items():
        vminmax = get_output_vminmax(cfg_outputs, output)
        for metazone, ncs in metas.items():
            if metazone in metazones:
                for nc in ncs:
                    task_args.append((nc, metazone, output, vminmax))

    if not task_args:
        return []

    # Use the same n_workers as the CLI dask config (e.g. --dask-nworkers 4).
    num_workers = kw_dask[0] if kw_dask else 4
    num_workers = min(num_workers, len(task_args))
    logger.info(f"Plotting {len(task_args)} tasks with {num_workers} workers")
    # Pre-warm cartopy's naturalearth cache in the main process so that
    # concurrent workers don't race to download the same shapefiles.
    list(cfeature.LAND.geometries())

    # Use 'spawn' to create clean child processes: avoids both the
    # "fork() after OpenMP" crash and inherited memory bloat.
    # ctx = multiprocessing.get_context("spawn")
    # with ctx.Pool(num_workers) as pool:
    #     results = pool.starmap(_plot_task, task_args)
    results = []
    for arg in task_args:
        results.append(_plot_task(*arg))
    png_paths = [p for task_result in results for p in (task_result or [])]
    logger.info(f"Generated {len(png_paths)} PNG file(s)")
    return png_paths
