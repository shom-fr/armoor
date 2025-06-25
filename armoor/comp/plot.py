import logging, os, re
from pathlib import Path
import cartopy.crs as ccrs
import cartopy.feature as cfeature
from cartopy.mpl.ticker import (LongitudeFormatter, LatitudeFormatter,
                                LatitudeLocator, LongitudeLocator)
from cartopy.mpl.gridliner import LONGITUDE_FORMATTER, LATITUDE_FORMATTER
import cmocean as cmo
import matplotlib.pyplot as plt
from matplotlib.collections import LineCollection
from mpl_toolkits.axes_grid1 import make_axes_locatable
import numpy as np
import pandas as pd
import xarray as xr
import dask
from xoa.plot import plot_minimap, plot_ts

from collections import defaultdict
from typing import List, Dict, Optional
from pathlib import Path

from armoor.__init__ import ArmoorError
from armoor.base.interp import vinterp
from armoor.base.ranges import trange_seq, vrange
from armoor.base.plot import create_subplots, save_figure, diagdisp
from armoor.base import LINE_COLORS
from armoor.base import FILTERS
from armoor.base.filters import create_optimized_mask
from armoor.comp import TITLE_PLOTS, CMAP_VARS, METRIC_LABELS
from armoor.comp.stats import StatsComp

logger = logging.getLogger(__name__)

plt.style.use('seaborn-v0_8-whitegrid')
plt.rcParams.update({'font.size': 8})

def sort_ncs_by_suffix(ncs: List[str], pattern: str) -> Dict[str, List[str]]:
    """Sort a list of NetCDF files by their numeric suffix.

    Parameters
    ----------
    ncs : List[str]
        List of file names
    pattern : str
        Regular expression with suffix in group 2

    Returns
    -------
    Dict[str, List[str]]
        Dictionary with suffixes as keys and file lists as values

    Raises
    ------
    ValueError
        If pattern doesn't match any files
    """
    compiled_pattern = re.compile(pattern)
    suffs = defaultdict(list)
    unmatched = []

    for nc in ncs:
        if not isinstance(nc, str):
            nc = str(nc)
        match = compiled_pattern.search(nc)
        if match and len(match.groups()) >= 2:
            suff = match.group(2)
            suffs[suff].append(nc)
        else:
            unmatched.append(nc)

    if not suffs and ncs:
        raise ValueError(f"No files match the pattern: {pattern}")

    if unmatched:
        print(f"Warning: {len(unmatched)} unmatched file(s): {unmatched}")

    # Sort files in each group alphabetically
    for suff in suffs:
        suffs[suff].sort()

    return dict(suffs)

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
            units = dsref[var].attrs.get('units')
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
        
        concat_dim = []
        if ("vlevel" in self.mparams) or ("vrange" in self.mparams):
            concat_dim.append("z")
        if ("trange_seq" in self.mparams) or ("tfreq" in self.mparams):
            concat_dim.append("time")
            
        for prod, ncins in self.mparams.get("ncins").items():
            logger.info(f"Product: {prod}")

            dssprod = [xr.open_dataset(ncin) for ncin in ncins["prod"]]
            dssref = [xr.open_dataset(ncin) for ncin in ncins["ref"]]
            
            if len(concat_dim) > 0:
                dssprod = [ds.stack({'dim_stacked': concat_dim}) for ds in dssprod]
                dssref = [ds.stack({'dim_stacked': concat_dim}) for ds in dssref]
                
                dsprod = xr.concat(dssprod, dim="dim_stacked")
                dsref = xr.concat(dssref, dim="dim_stacked")
            else:
                dsprod = dssprod[0]
                dsref = dssref[0]
            
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
                
            if "member" in dsprod.dims:
                dsprod = dsprod.mean(dim="member")
            if "member" in dsref.dims:
                dsref = dsref.mean(dim="member")
            if dsprod.sizes == dsref.sizes:
                self.diagdisp(
                    dsref,
                    dsprod,
                    figtitle,
                    figname
                    )
            else:
                logger.warning(
                    "No global dispersion diagram: "
                    "no compatible dimension btw ref and prod datasets."
                    )
            
            dsprod.close()
            dsref.close()
    
    def diagdisp_sel(self):
        """Plot a dispersion diagram per product and range."""
        for prod, ncins in self.mparams.get("ncins").items():
            logger.info(f"Product: {prod}")

            for icomp in range(len(ncins["ref"])):
                dsref = xr.open_dataset(ncins['ref'][icomp])
                dsprod = xr.open_dataset(ncins['prod'][icomp])
                
                icomp_name = os.path.basename(ncins['prod'][icomp])[:-3]                
                
                figname = (
                    f"{self.func_comp}/plot/{self.metazone}" + 
                    "/{var}/" + 
                    f"diagdisp_sel_{icomp_name}.png"
                    )
                
                if "tfreq" in self.mparams:
                    time = f"{dsprod.attrs['time']}"
                elif "trange_seq" in self.mparams:
                    time = f"{dsprod.attrs['trange']}"
                else:
                    time = ""
                    
                if "vlevel" in self.mparams:
                    vertical = f"{dsprod.attrs['vlevel']} m"
                elif "trange_seq" in self.mparams:
                    vertical = f"{dsprod.attrs['vrange']} m"
                else:
                    vertical = ""
                    
                figtitle = (
                    f"{self.plot_title} \n"
                    f"{self.metazone} {time} {vertical}\n "
                    "{var} [{units}]"
                    )
                
                if "member" in dsprod.dims:
                    dsprod = dsprod.mean(dim="member")
                if "member" in dsref.dims:
                    dsref = dsref.mean(dim="member")
                
                self.diagdisp(
                    dsref,
                    dsprod,
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
        
        concat_dim = []
        if ("trange_seq" in self.mparams) or ("tfreq" in self.mparams):
            concat_dim.append("time")
        
        for prod, ncins in self.mparams.get("ncins").items():
            logger.info(f"Product: {prod}")
            dsprod = xr.open_mfdataset(ncins.get("prod"), combine="nested", concat_dim="time")
            dsref = xr.open_mfdataset(ncins.get("ref"), combine="nested", concat_dim="time")
            refname = dsref.attrs.get("data_name")
            prodname = dsprod.attrs.get("data_name")
            figtitle = (
                f"{self.plot_title} \n"
                f"{self.metazone}\n"
                f"{prodname} vs {refname}"
                )
            figname = (
                f"{self.func_comp}/plot/{self.metazone}/"
                f"mdiagts_{prod}.png"
                )
                
            self._mdiagts(dsref, dsprod, figtitle, figname)
            
            dsref.close(); dsprod.close()
            del dsref; del dsprod
            
            if "trange_seq" in self.mparams:
                for icomp in range(len(ncins["ref"])):
                    dsref = xr.open_dataset(ncins['ref'][icomp])
                    dsprod = xr.open_dataset(ncins['prod'][icomp])
                    
                    icomp_name = os.path.basename(ncins['prod'][icomp])[:-3]                
                    figname = (
                        f"{self.func_comp}/plot/{self.metazone}/" + 
                        f"mdiagts_{icomp_name}.png"
                        )
                    
                    time = f"{dsprod.attrs['trange']}"

                    figtitle = (
                        f"{self.plot_title} \n"
                        f"{self.metazone} {time}\n"
                        f"{prodname} vs {refname}"
                        )
                    self._mdiagts(dsref, dsprod, figtitle, figname)
                    
                    dsref.close(); dsprod.close()
                    del dsref; del dsprod
    
    def udiagts(self):
        """Plot uniquely profiles theta-saln."""
        
        dss_prod = []
        dss_ref = []
        ntime = []
        for iprod, (prod, ncins) in enumerate(self.mparams.get("ncins").items()):
            logger.info(f"Product: {prod}")
            dss_prod.append(
                xr.open_mfdataset(
                    ncins.get("prod"), combine="nested", concat_dim="time"
                   
                    )
                )
            dss_ref.append(
                xr.open_mfdataset(
                    ncins.get("ref"), combine="nested", concat_dim="time"
                    )
                )
            ntime.append(dss_ref[iprod].sizes["time"])
        ntime = np.unique(ntime)
        if len(ntime) == 1:
            ntime = ntime[0]
        else:
            raise "Colocated datasets do not have the same number of profiles."
            
        for itime in range(ntime):
            time = pd.to_datetime(dss_ref[0].time.isel(time=itime).values)
            dsref = dss_ref[0].isel(time=itime)
            dsprod = [ds.isel(time=itime) for ds in dss_prod]
            xtitle = f"{time:%Y-%m-%dT%H:%M:%S}"
            fig, ax = create_subplots(
                nrows=1,
                figsize=(8, 8),
                )
            fig.suptitle(
                f"{self.plot_title} \n"
                f"{self.metazone} \n {xtitle}",
                y=1.01
                )
            ax = ax[0]
            tsref = plot_ts(
                dsref.ptemp, dsref.sal,
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
                    label=dsref.attrs["data_name"]
                    )
                )
            for iprod, data_prod in enumerate(dsprod):
                data_prod = data_prod.armoorfilters.sel_closest(dsref)
                tsprod = plot_ts(
                    data_prod.ptemp, data_prod.sal,
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
                        label=data_prod.attrs["data_name"]
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
            ax_minimap = plot_minimap(dsref, ax=self.ax_minimap, **kw)
            figname = (
                f"{self.func_comp}/plot/{self.metazone}/"
                f"udiagts_{time:%Y-%m-%dT%H:%M:%S}.png"
                )
            
            self.save_figure(
                fig,
                figname.format(**locals())
                )
    
        
    def _mvprofiles(self, dsref, dsprod, figtitle, figname):
        
        ref_color = "slateblue"
        prod_color = "coral"

        depth_mean = xr.DataArray(
            data=np.arange(0, 5000, 10),
            dims="z"
            )
        dsprod_member = dsprod.reset_coords("depth").stack(
            {"x": ["time", "member"]}
            ).swap_dims({"x": "time"}).set_coords("depth")
        dsprod_interp = vinterp(dsprod_member, "depth", depth_mean)
        dsprod_member.close(); del dsprod_member
        dsref_interp = vinterp(dsref, "depth", depth_mean)
        dsprod_mean = dsprod_interp.mean(dim="time")
        dsref_mean = dsref_interp.mean(dim="time")
        dsprod_std = dsprod_interp.std(dim="time")
        dsref_std = dsref_interp.std(dim="time")
        depth_mean = -1 * depth_mean
        
        dsprod = dsprod.transpose("time", "z", "member")#.reshape(-1, prod_data.sizes["member"]
        for var in self.mparams.get("vars"):
            units = dsref[var].attrs.get('units')
            fig, ax = create_subplots(
                nrows=1,
                figsize=(5, 8),
                title=figtitle.format(**locals())
                )
            ax = ax[0]

            daref = dsref[var]
            daprod = dsprod[var]
            
            daref_mean = dsref_mean[var]
            daprod_mean = dsprod_mean[var]

            daref_std = dsref_std[var]
            daprod_std = dsprod_std[var]

            # Données de référence
            ref_data = daref.values
            ref_depth = -daref["depth"]
            
            # Données produit - reshape pour faciliter le plotting
            prod_data = daprod.values  # (time, member, depth)
            prod_depth = -daprod["depth"].values
            
            # Reshape les données produit pour plotting en une seule opération
            n_times, n_depths, n_members = prod_data.shape
            
            # Plot référence
            for itime in range(n_times):
                kw_ref = {"label": dsref.attrs["data_name"]} if itime == 0 else {}
                ax.plot(ref_data[itime], ref_depth[itime], 
                        color=ref_color, linewidth=0.15, alpha=0.2, **kw_ref)
            
            segments = np.stack([
                prod_data.reshape(-1, n_members),
                prod_depth.reshape(-1, n_members)
            ], axis=-1)
            lc = LineCollection(segments, colors=prod_color, linewidths=0.15, alpha=0.2)
            ax.add_collection(lc)
            
            if hasattr(dsprod.attrs, "data_name"):
                ax.plot([], [], color=prod_color, linewidth=0.15, alpha=0.2, 
                        label=dsprod.attrs["data_name"])
            
            ax.plot(
                daref_mean, depth_mean, color=ref_color, linewidth=2.0,
                label=f"mean {dsref.attrs['data_name']}"
                )
            ax.fill_betweenx(
                depth_mean, daref_mean - daref_std, daref_mean + daref_std, color=ref_color,
                alpha=0.25,
                label=f"{dsref.attrs['data_name']} mean +/- std"
                )
            ax.plot(
                daprod_mean, depth_mean, color=prod_color, linewidth=2.0,
                label=f"{dsprod.attrs['data_name']}"    
                )
            ax.fill_betweenx(
                depth_mean, daprod_mean - daprod_std, daprod_mean + daprod_std, color=prod_color,
                alpha=0.25,
                label=f"{dsprod.attrs['data_name']} mean +/- std"
                )
            
            ax.legend(
                #loc='upper left', 
                fontsize=11, frameon=True, fancybox=True
                )
                
            ax.set_xlabel(f"{var}, {units}")
            ax.set_ylabel("Depth, m")
            ax.set_ylim([ref_depth.min(), 0])
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
        
        concat_dim = ["time"]
        if ("trange_seq" in self.mparams) or ("tfreq" in self.mparams):
            concat_dim.append("time")
        
        for prod, ncins in self.mparams.get("ncins").items():
            logger.info(f"Product: {prod}")
            dsprod = xr.open_mfdataset(ncins.get("prod"), combine="nested", concat_dim="time")
            dsref = xr.open_mfdataset(ncins.get("ref"), combine="nested", concat_dim="time")
            figtitle = (
                f"{self.plot_title} \n"
                f"{self.metazone}\n "
                )
            figname = (
                f"{self.func_comp}/plot/{self.metazone}"
                "/{var}/"
                f"mvprofiles_{prod}.png"
                )
                
            self._mvprofiles(dsref, dsprod, figtitle, figname)
            
            dsref.close(); dsprod.close()
            del dsref; del dsprod
            
            if "trange_seq" in self.mparams:
                for icomp in range(len(ncins["ref"])):
                    dsref = xr.open_dataset(ncins['ref'][icomp])
                    dsprod = xr.open_dataset(ncins['prod'][icomp])
                    
                    icomp_name = os.path.basename(ncins['prod'][icomp])[:-3]                
                    figname = (
                        f"{self.func_comp}/plot/{self.metazone}" + 
                        "/{var}/" + 
                        f"mvprofiles_sel_{icomp_name}.png"
                        )
                    
                    time = f"{dsprod.attrs['trange']}"

                    figtitle = (
                        f"{self.plot_title} \n"
                        f"{self.metazone} {time}\n "
                        )
                    self._mvprofiles(dsref, dsprod, figtitle, figname)
                    
                    dsref.close(); dsprod.close()
                    del dsref; del dsprod

    def uvprofiles(self):
        """Plot uniquely vertical profiles."""
                
        dss_prod = []
        dss_ref = []
        ntime = []
        for iprod, (prod, ncins) in enumerate(self.mparams.get("ncins").items()):
            logger.info(f"Product: {prod}")
            dss_prod.append(
                xr.open_mfdataset(
                    ncins.get("prod"), combine="nested", concat_dim="time"
                   
                    )
                )
            dss_ref.append(
                xr.open_mfdataset(
                    ncins.get("ref"), combine="nested", concat_dim="time"
                    )
                )
            ntime.append(dss_ref[iprod].sizes["time"])
        ntime = np.unique(ntime)
        if len(ntime) == 1:
            ntime = ntime[0]
        else:
            raise "Colocated datasets do not have the same number of profiles."
            
        depth_mean = xr.DataArray(
            data=np.arange(0, 5000, 10),
            dims="z"
            )
        
        for var in self.mparams.get("vars"):
            da_ref = dss_ref[0][[var]]
            das_prod = [ds[[var]] for ds in dss_prod]
            units = da_ref[var].attrs.get('units')
            for itime in range(ntime):
                time = pd.to_datetime(da_ref.time.isel(time=itime).values)
                data_ref = da_ref.isel(time=itime)
                datas_prod = [da_prod.isel(time=itime) for da_prod in das_prod]
                xtitle = f"{time:%Y-%m-%dT%H:%M:%S}"
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
                kw_ref = {"label": da_ref.attrs["data_name"]}
                ax.plot(
                    data_ref[var],
                    -data_ref.depth, 
                    color="k",
                    linewidth=2.0,
                    alpha=1.0,
                    **kw_ref
                    )
                for iprod, data_prod in enumerate(datas_prod):
                    data_prod_closest = data_prod.armoorfilters.sel_closest(data_ref)
                    data_prod_interp = vinterp(data_prod, "depth", depth_mean)
                    data_prod_mean = data_prod_interp.mean(dim="member")
                    data_prod_std = data_prod_interp.std(dim="member")
                    ax.plot(
                        data_prod_closest[var], -data_prod_closest.depth,
                        color=LINE_COLORS[iprod], linewidth=2.0,
                        label=f"{data_prod.attrs['data_name']} closest"
                        )
                    
                    ax.fill_betweenx(
                        -depth_mean,
                        data_prod_mean[var] - data_prod_std[var],
                        data_prod_mean[var] + data_prod_std[var],
                        color=LINE_COLORS[iprod],
                        alpha=0.25,
                        label=f"{data_prod.attrs['data_name']} mean +/- std"
                        )
                ax.legend(
                    #loc='upper left', 
                    fontsize=11, frameon=True, fancybox=True
                    )
                
                ax.set_xlabel(f"{var}, {units}")
                ax.set_ylabel("Depth, m")
                ax.set_ylim([-data_ref.depth.max(), 0])
                
                kw = dict(
                    plot_coords = "points",
                    coords_markersize=4,
                    gridlines_draw_labels=True,
                    gridlines_xlabel_style={'size': 6},
                    gridlines_ylabel_style={'size': 6},
                    )
                ax_minimap = plot_minimap(data_ref, ax=self.ax_minimap, **kw)
                
                figname = (
                    f"{self.func_comp}/plot/{self.metazone}"
                    "/{var}/"
                    f"uvprofiles_{prod}_{time:%Y-%m-%dT%H:%M:%S}.png"
                    )

                self.save_figure(
                    fig,
                    figname.format(**locals())
                    )

        return
    
    def timeseries_stats(self, dicos, var):
        """Plot time series stastistics."""
        attrs = dicos[0]["mean_ref"].attrs
        ncname = ""
        xtitle = ""

        if "vlevel" in attrs:
            ncname += f"_{attrs['vlevel']}"
            xtitle += f" {attrs['vlevel']} m"
        elif "vrange" in attrs:
            ncname += f"_{attrs['vrange']}"
            xtitle += f" {attrs['vrange']} m"
        else:
            pass
        
        
        if "npts" in dicos[0]["mean_ref"].dims:
            npts = dicos[0]["mean_ref"].sizes["npts"]
            figname = (
                "{self.func_comp}/plot/{self.metazone}" + 
                "/{var}/" + 
                "timeseries_stats_{lat_pt}_{lon_pt}{ncname}.png"
                )
        else:
            npts = 1
            figname = (
                "{self.func_comp}/plot/{self.metazone}" + 
                "/{var}/" + 
                "timeseries_stats{ncname}.png"
                ) 
        for inpt in range(npts):
            fig, axes = create_subplots(
                nrows=5, figsize=(10, 8),
                x_label='Date', y_label=None,
                sharex=True
                )
            for idico, dico in enumerate(dicos):
                if idico == 0:
                    units = dico["data"][var].attrs.get("units")
                    fig.suptitle(
                        f"{self.plot_title} \n"
                        f"{var}, {units} \n"
                        f"{self.metazone} {xtitle}\n",
                        y=1.01
                        )
                
                if npts > 1:
                    rmean = dico["mean_ref"][var].isel(npts=inpt)
                    pmean = dico["mean_prod"][var].isel(npts=inpt)
                    rstd = dico["std_prod"][var].isel(npts=inpt)
                    pstd = dico["std_prod"][var].isel(npts=inpt)
                    bias = dico["bias"][var].isel(npts=inpt)
                    rmse = dico["rmse"][var].isel(npts=inpt)
                    rmsec = dico["rmsec"][var].isel(npts=inpt)
                    
                    plot_coords = "points"
                    lon_pt = rmean.lon.values
                    lat_pt = rmean.lat.values
                
                else:
                    rmean = dico["mean_ref"][var]
                    pmean = dico["mean_prod"][var]
                    rstd = dico["std_prod"][var]
                    pstd = dico["std_prod"][var]
                    bias = dico["bias"][var]
                    rmse = dico["rmse"][var]
                    rmsec = dico["rmsec"][var]
                    
                    if dico["data"].lon.dims == ("x", "y"):
                        plot_coords = "filledbox"
                    else:
                        plot_coords = "points"
                
                plot_minimap(
                    dico["data"],
                    ax=self.ax_minimap,
                    plot_coords=plot_coords,
                    coords_markersize=4,
                    gridlines_draw_labels=True,
                    gridlines_xlabel_style={'size': 6},
                    gridlines_ylabel_style={'size': 6},
                    )
                ref_name = dico["mean_ref"].attrs["data_name"]
                prod_name = dico["mean_prod"].attrs["data_name"]
                tcoord = "time"
                
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
                        f"{var}, {units} \n"
                        f"{self.metazone}: {lat_pt}°N, {lon_pt}°E",
                        y=1.05
                        )
            
                plot_minimap(
                    ref,
                    ax=self.ax_minimap,
                    plot_coords=plot_coords,
                    coords_markersize=4,
                    gridlines_draw_labels=True,
                    gridlines_xlabel_style={'size': 6},
                    gridlines_ylabel_style={'size': 6},
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
        pattern = r'([^/]+)_\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}_(\d+\.?\d*|\d+-\d+)\.nc$'
        dicos = {}
        for prod, ncins in self.mparams.get("ncins").items():
            ncins_prod = sort_ncs_by_suffix(ncins["prod"], pattern)
            ncins_ref = sort_ncs_by_suffix(ncins["ref"], pattern)
            for suff in ncins_prod.keys():
                if suff not in dicos.keys():
                    dicos[suff] = []
                dicos[suff].append({
                    "ref": ncins_ref.get(suff),
                    "prod": ncins_prod.get(suff)
                })
        for pool in dicos.keys():
            timeseries = []
            for dico in dicos[pool]:
                stats = []
                for inc in range(len(dico.get("prod"))):
                    dsprod = xr.open_dataset(dico.get("prod")[inc])
                    dsref = xr.open_dataset(dico.get("ref")[inc])
                    if dsref.lon.dims == ("y", "x"):
                        extra_dims = ["x", "y"]
                    else:
                        extra_dims = None
                    if "member" in dsprod.dims:
                        dsprod = dsprod.mean(dim="member")
                    if "member" in dsref.dims:
                        dsref = dsref.mean(dim="member")    
                    stat = StatsComp(
                          self.mparams, dsref, dsprod, extra_dims=extra_dims
                          ).compute()
                    stats.append(stat)
                    dsprod.close()
                    dsref.close()
                keys = set().union(*stats)
                timeserie = {
                    key: [d[key] for d in stats if key in d] for key in keys
                    }
                for k, v in timeserie.items():
                    timeserie.update({
                        k: xr.concat(v, dim="time")
                        })
                timeseries.append(timeserie)
            for var in self.mparams.get("vars"):
                if "mean_ref" in timeseries[0].keys():
                    self.timeseries_stats(timeseries, var)
                else:
                    self.timeseries_sel(timeseries, var)
            
        return None        
        
    def maps(self):
        """Plot maps per product."""
        for prod, ncins in self.mparams.get("ncins").items():
            logger.info(f"Product: {prod}")
            
            for icomp in range(len(ncins["ref"])):
                dsref_allvars = xr.open_dataset(ncins['ref'][icomp])
                dsprod_allvars = xr.open_dataset(ncins['prod'][icomp])
                
                icomp_name = os.path.basename(ncins['prod'][icomp])[:-3]
                
                for var in self.mparams.get("vars"):
                    
                    dsref = dsref_allvars[[var]]
                    dsprod = dsprod_allvars[[var]]

                    if "tfreq" in self.mparams:
                        time = f"{dsprod.attrs['time']}"
                    elif "trange_seq" in self.mparams:
                        time = f"{dsprod.attrs['trange']}"
                    else:
                        time = ""
                        
                    if "vlevel" in self.mparams:
                        vertical = f"{dsprod.attrs['vlevel']} m"
                    elif "trange_seq" in self.mparams:
                        vertical = f"{dsprod.attrs['vrange']} m"
                    else:
                        vertical = ""
                    
                    units = dsref[var].attrs.get('units')
                    
                    figtitle = (
                        f"{self.plot_title} \n"
                        f"{self.metazone} {time} {vertical}\n "
                        f"{var}, {units}"
                        )
                    
                    if "member" in dsprod.dims:
                        if "member" in dsprod.lon.dims:
                            dsprod = dsprod.reset_coords(["lon", "lat"])
                        dsprod = dsprod.mean(dim="member")
                        if "lon" not in dsprod.coords:
                            dsprod = dsprod.set_coords(["lon", "lat"])
                    if "member" in dsref.dims:
                        if "member" in dsref.lon.dims:
                            dsref = dsref.reset_coords(["lon", "lat"])
                        dsref = dsref.mean(dim="member")
                        if "lon" not in dsref.coords:
                            dsref = dsref.set_coords(["lon", "lat"])
                
                    prod_name = dsprod.attrs["data_name"]
                    ref_name = dsref.attrs["data_name"]
                    
                    if "time" in dsref.lon.dims:
                        exclude_dims = ["time"]
                    else:
                        exclude_dims = None
                    
                    dicos = StatsComp(
                        self.mparams,
                        dsref,
                        dsprod,
                        exclude_dims=exclude_dims
                        ).compute()
                    dsprod.close()
                    dsref.close()
                    if "trange_seq" in self.mparams:
                        tcoord = "time_bins"
                    else:
                        tcoord = "time" 
                    if "mean_ref" in dicos.keys():
                        comps = ["bias", "rmse", "rmsec"]
                    else:
                        comps = ["diff"]
                    for comp in comps:
                        if comp == "diff":
                            ds_prod = dicos["prod"][var]
                            ds_ref = dicos["ref"][var]
                            field = None
                        elif comp == "bias":
                            ds_prod = dicos["mean_prod"][var]
                            ds_ref = dicos["mean_ref"][var]
                            field = "Mean"
                        elif (comp == "rmse") or (comp == "rmsec"):
                            ds_prod = dicos["std_prod"][var]
                            ds_ref = dicos["std_ref"][var]
                            field = "St.D"
                        ds_comp = dicos[comp][var]
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
                        dlat = ds_prod.lat.max() - ds_prod.lat.min()
                        dlon = ds_prod.lon.max() - ds_prod.lon.min()
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
                        if ("npts" in ds_prod.dims) or (ds_prod.lon.dims != ("x" ,"y")):
                            m0 = axes[0].scatter(
                                ds_prod.lon, ds_prod.lat,
                                c=ds_prod,
                                vmin=vmin,
                                vmax=vmax,
                                cmap=CMAP_VARS[var]
                                )
                            axes[0].set_title(prod_name)
                            m1 = axes[1].scatter(
                                ds_ref.lon, ds_ref.lat,
                                c=ds_ref,
                                vmin=vmin,
                                vmax=vmax,
                                cmap=CMAP_VARS[var]
                                )
                            axes[1].set_title(ref_name)
                            m2 = axes[2].scatter(
                                ds_prod.lon, ds_prod.lat,
                                c=ds_comp,
                                vmin=cmin,
                                vmax=cmax,
                                cmap=cmap_comp,
                                )
                        else:
                            m0 = axes[0].pcolormesh(
                                ds_prod.lon, ds_prod.lat, ds_prod,
                                vmin=vmin,
                                vmax=vmax,
                                cmap="cmo.thermal"
                                )
                            axes[0].set_title(prod_name)
                            m1 = axes[1].pcolormesh(
                                ds_ref.lon, ds_ref.lat, ds_ref,
                                vmin=vmin,
                                vmax=vmax,
                                cmap=CMAP_VARS[var]
                                )
                            axes[1].set_title(ref_name)
                            m2 = axes[2].pcolormesh(
                                ds_comp.lon, ds_comp.lat, ds_comp,
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
                            f"{self.func_comp}/plot/{self.metazone}" + 
                            f"/{var}/" + 
                            f"map_{icomp_name}.png"
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
        logger.info(f"Saving {filename}")
        save_figure(fig, filename)
        del fig
    