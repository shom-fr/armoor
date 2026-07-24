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
from tqdm import tqdm
from cartopy.mpl.gridliner import LATITUDE_FORMATTER, LONGITUDE_FORMATTER
from cartopy.mpl.ticker import (LatitudeFormatter, LatitudeLocator,
                                LongitudeFormatter, LongitudeLocator)
from matplotlib.collections import LineCollection
from mpl_toolkits.axes_grid1 import make_axes_locatable
from xoa.plot import plot_minimap, plot_ts, plot_flow
from xoa import geo as xgeo

from armoor.base import LINE_COLORS, CMAP_VARS, MINMAX_VARS
from armoor.base.dispatch import SubclassingMethodRegistry
from armoor.base.filters import create_optimized_mask
from armoor.base.interp import vinterp
from armoor.base.plot import (create_subplots, diagdisp, format_time_label,
                              format_vertical_label, get_output_vminmax,
                              save_figure)
from armoor.data.datatype import (
    DataEddies, DataMeteo, DataOceanModel, DataSstSatellite, get_data_type_by_name
)
# from armoor.comp.stats import StatsComp

logger = logging.getLogger(__name__)

matplotlib.use('Agg')
plt.style.use('seaborn-v0_8-whitegrid')
plt.rcParams.update({'font.size': 8})

MS_TO_KNOTS = 1.9438444924406046


def _cbar_range(da_all, var, vminmax, nstd, group_range=None,
                series_mean=None, series_std=None):
    """Compute a scalar variable's color scale, fixed once over a whole
    mapseries -- not recomputed per frame like maps()/`_maps_raw` do.

    Precedence: explicit `vminmax` > pooled `group_range` (cbar_group) >
    `series_mean`/`series_std` (the otype's own series-wide stats, from
    armoor.data.output._resolve_series_ranges) > `da_all`'s own mean/std
    (fallback, e.g. if series stats weren't resolved for some reason).

    Kept as a plain function (no cartopy/matplotlib) so it's testable on
    its own -- see armoor.tests.uni.test_data_plot.
    """
    if vminmax and var in vminmax:
        return vminmax[var]
    if group_range is not None:
        return group_range
    if series_mean is not None and series_std is not None:
        mean, std = series_mean, series_std
    else:
        mean, std = float(da_all.mean()), float(da_all.std())
    if MINMAX_VARS.get(var) == "rel":
        bound = nstd * std
        return -bound, bound
    return mean - nstd * std, mean + nstd * std


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
        fig.subplots_adjust(top=0.85)
        self.save_figure(
            fig,
            figname.format(**locals())
            )
    
    def _diagts_merged(self, prefix, include_vertical):
        """Render one theta-saln diagram merging every point it is given.

        Shared by the two "merge everything into one figure" variants
        (`mdiagts`, and -- per group -- `diagts_sel`): stacking every
        remaining dim into a single ``npt`` axis works uniformly whether
        there's one profile, a handful of named stations, or a full
        lat/lon grid, so there's no need to loop over individual points
        here -- and it works identically with or without `cloud`
        configured (`_mdiagts`'s minimap already branches on
        ``lon.dims``).

        Parameters
        ----------
        prefix : str
            Output-file/otype prefix (``"diagts_sel"`` or ``"mdiagts"``).
        include_vertical : bool
            Whether to append a vlevel/vrange label -- only meaningful
            when this call covers a single vertical group, not a full
            merge across every vlevel/vrange.

        Returns
        -------
        None
        """
        dsprod = self.dt.children["data"].to_dataset()
        dsprod = dsprod.stack({"npt": list(dsprod.sizes.keys())})
        dsprod = dsprod.where(~dsprod.ptemp.isnull(), drop=True)
        if dsprod.sizes.get("npt", 0) == 0:
            logger.warning(f"No valid ptemp points for {prefix}, skipping")
            return
        data_name = dsprod.attrs.get("data_name")
        attrs = dsprod.attrs
        xtitle, xfigname = format_time_label(attrs, ds=dsprod)
        if include_vertical:
            v_title, v_name = format_vertical_label(attrs)
            if v_title:
                xtitle += f"\n{v_title}"
            xfigname += v_name
        figtitle = (
            f"{data_name}\n"
            f"{self.metazone}\n"
            f"{xtitle}"
            )
        figname = (
            f"data/plot/{self.metazone}/"
            f"{prefix}_{data_name}{xfigname}.png"
            )
        self._mdiagts(dsprod, figtitle, figname)

    def diagts_sel(self):
        """Plot one theta-saln diagram per trange/time and/or vrange/vlevel group."""
        self._diagts_merged("diagts_sel", include_vertical=True)

    def mdiagts(self):
        """Plot one theta-saln diagram merging the whole series, cloud or not."""
        self._diagts_merged("mdiagts", include_vertical=False)

    def udiagts(self):
        """Plot one theta-saln diagram per profile in a cloud of points, per timestep.

        (When several profiles should be merged per time interval instead
        of one figure per single timestep, use `diagts_sel`.)
        """
        dsprod = self.dt.children["data"].to_dataset()
        npts = dsprod.sizes["npts"]
        data_name = dsprod.attrs.get("data_name")
        for inpt in range(npts):
            ds_pt = dsprod.isel(npts=inpt)
            lon_pt = f"{ds_pt.lon:.2f}"
            lat_pt = f"{ds_pt.lat:.2f}"
            for itime in range(ds_pt.sizes["time"]):
                ds = ds_pt.isel(time=itime)
                time = pd.to_datetime(ds.time.values)
                ds = ds.stack({"npt": list(ds.sizes.keys())})
                ds = ds.where(~ds.ptemp.isnull(), drop=True)
                if ds.sizes.get("npt", 0) == 0:
                    continue
                depth = ds.depth
                if 'depth' in self.vminmax:
                    zmin, zmax = self.vminmax['depth']
                else:
                    zmin = -depth.max()
                    zmax = -depth.min()
                xtitle = f"{time:%Y-%m-%dT%H:%M:%S}"
                xfigname = f"_{time:%Y-%m-%dT%H:%M:%S}"
                figname = (
                    f"data/plot/{self.metazone}/"
                    f"udiagts_{data_name}_{lat_pt}_{lon_pt}{xfigname}.png"
                    )
                figtitle = (
                    f"{data_name}\n"
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
                fig.subplots_adjust(top=0.85)
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
        # depth may only vary along "z" (a clean per-level coordinate),
        # not share mask's other dims (time/member/npts) -- reduce the
        # mask down to "z" first so .where() has matching dims, keeping
        # whichever levels have at least one valid point.
        z_mask = mask if mask.dims == ("z",) else mask.any(
            dim=[d for d in mask.dims if d != "z"]
            )
        depth = dsprod.depth.where(z_mask, drop=True)
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
            if var == "depth":
                continue
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
            fig.subplots_adjust(top=0.85)

            self.save_figure(
                fig,
                figname.format(**locals())
                )
    
    def _vprofiles_merged(self, prefix):
        """Render vertical profiles, one figure per variable, for whatever
        points/times this call is given (shared by `vprofiles_sel` and
        `mvprofiles` -- `_mvprofiles` already overlays every point/member
        as its own line, so no per-point loop is needed whether there's
        one profile, a handful of named stations, or a full cloud; this
        works identically with or without `cloud` configured).

        Parameters
        ----------
        prefix : str
            Output-file/otype prefix (``"vprofiles_sel"`` or
            ``"mvprofiles"``).

        Returns
        -------
        None
        """
        dsprod = self.dt.children["data"].to_dataset()
        attrs = dsprod.attrs
        xtitle, xfigname = format_time_label(attrs, ds=dsprod)
        v_title, v_name = format_vertical_label(attrs)
        if v_title:
            xtitle += f"\n{v_title}"
        xfigname += v_name
        var = "{var}"
        prodname = dsprod.attrs.get("data_name")
        figtitle = (
            f"{prodname}\n"
            f"{self.metazone}\n"
            f"{xtitle}"
            )
        figname = (
            f"data/plot/{self.metazone}/"
            f"{prefix}_{prodname}_{var}{xfigname}.png"
            )
        self._mvprofiles(dsprod, figtitle, figname)

    def vprofiles_sel(self):
        """Plot vertical profiles per trange/time and/or vrange/vlevel group."""
        self._vprofiles_merged("vprofiles_sel")

    def mvprofiles(self):
        """Plot vertical profiles merging the whole series, cloud or not."""
        self._vprofiles_merged("mvprofiles")

    def uvprofiles(self):
        """Plot uniquely vertical profiles."""
        dsprod = self.dt.children["data"].to_dataset()
        data_name = dsprod.attrs.get("data_name")
        npts = dsprod.sizes["npts"]
        attrs = dsprod.attrs
        xtitle, xfigname = format_time_label(attrs, ds=dsprod)
        v_title, v_name = format_vertical_label(attrs)
        if v_title:
            xtitle += f"\n{v_title}"
        xfigname += v_name
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
                    f"{data_name}\n"
                    f"{self.metazone}\n"
                    f"{lat_pt}N; {lon_pt}E\n"
                    f"{xtitle}"
                    )
                daprod = ds[var].copy()
                if "z" not in daprod.dims:
                    continue
                else:
                    daprod = daprod.transpose("z", "time")
                    # depth may only vary along "z" (a clean per-level
                    # coordinate) -- broadcast it to daprod's full (z,time)
                    # shape before transposing, since the LineCollection
                    # below needs one depth value per (z,time) cell.
                    depth = ds.depth.broadcast_like(daprod).transpose("z", "time")
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
                fig.subplots_adjust(top=0.85)

                self.save_figure(
                    fig,
                    figname.format(**locals())
                    )

    def _timeseries_raw(self, ds_data):
        """Plot the raw per-point (and, when depth-resolved, per-native-
        level) series directly, one figure per variable/point/level.

        Fallback for otype=timeseries when neither trange_seq nor
        vrange/vlevel is configured and there's no x/y grid to reduce
        either (e.g. a bare cloud metazone): `get_dim_stats`
        (armoor.data.output) then has no axis left to average over, so
        no mean/std subtree gets built.

        Parameters
        ----------
        ds_data : xarray.Dataset
            The unreduced "data" child, straight from disk.

        Returns
        -------
        None
        """
        attrs = ds_data.attrs
        data_name = attrs.get("data_name")
        npts = ds_data.sizes["npts"] if "npts" in ds_data.dims else 1
        vars2plot = [var for var in ds_data.data_vars if var != "depth"]
        for var in vars2plot:
            da_var = ds_data[var]
            nz = da_var.sizes["z"] if "z" in da_var.dims else 1
            for inpt in range(npts):
                da_pt = da_var.isel(npts=inpt) if npts > 1 else da_var
                depth_pt = ds_data.depth
                if npts > 1:
                    pt = ds_data.isel(npts=inpt)
                    if "npts" in depth_pt.dims:
                        depth_pt = depth_pt.isel(npts=inpt)
                    lon_pt = f"{pt.lon:.2f}"
                    lat_pt = f"{pt.lat:.2f}"
                    pt_title = f" {lat_pt}°N; {lon_pt}°E"
                    pt_name = f"_{lat_pt}_{lon_pt}"
                else:
                    pt_title = ""
                    pt_name = ""
                for iz in range(nz):
                    da = da_pt.isel(z=iz) if "z" in da_pt.dims else da_pt
                    if "z" in da_pt.dims:
                        depth_val = float(depth_pt.isel(z=iz))
                        z_title = f" {depth_val:.1f} m"
                        z_name = f"_{depth_val:.1f}"
                    else:
                        z_title = ""
                        z_name = ""
                    units = da.attrs.get("units")
                    figname = (
                        f"data/plot/{self.metazone}/"
                        f"timeseries_{data_name}_{var}{pt_name}{z_name}.png"
                        )
                    fig, axes = create_subplots(
                        nrows=1, figsize=(10, 5),
                        x_label='Date', y_label=None,
                        )
                    ax = axes[0]
                    title_lines = [data_name, self.metazone]
                    if z_title.strip():
                        title_lines.append(z_title.strip())
                    if pt_title.strip():
                        title_lines.append(pt_title.strip())
                    title_lines.append(f"{var}, {units}")
                    fig.suptitle("\n".join(title_lines), y=1.01)
                    fig.subplots_adjust(top=0.78)
                    if ds_data.lon.dims == ("x", "y"):
                        plot_coords = "filledbox"
                    else:
                        plot_coords = "points"
                    plot_minimap(
                        ds_data.isel(npts=inpt) if npts > 1 else ds_data,
                        ax=self.ax_minimap,
                        plot_coords=plot_coords,
                        coords_markersize=4,
                        gridlines_draw_labels=True,
                        gridlines_xlabel_style={'size': 6},
                        gridlines_ylabel_style={'size': 6},
                        )
                    ax.plot(da["time"], da, color="slateblue", linewidth=2)
                    ax.set_ylabel(var)
                    self.save_figure(fig, figname)

    def timeseries(self):
        """Plot time series differences."""
        ds_data = self.dt.children["data"].to_dataset()
        if "mean" not in self.dt.children:
            return self._timeseries_raw(ds_data)
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
                v_part = ""
                ncname = ""
                if "z" in ds_data[var].dims:
                    if "vlevel" in attrs:
                        vlevel = attrs.get("vlevel")
                        if isinstance(vlevel, list):
                            vlevel = vlevel[0]
                        ncname += f"_{vlevel}"
                        v_part = f"{vlevel} m"
                    elif "vrange" in attrs:
                        vrange = attrs.get("vrange")
                        if isinstance(vrange, list):
                            vrange = vrange[0]
                        ncname += f"_{vrange}"
                        v_part = f"{vrange}"
                t_part = f"time range {attrs.get('trange_seq')}" if "trange_seq" in attrs else ""
                fig, axes = create_subplots(
                    nrows=2, figsize=(10, 6),
                    x_label='Date', y_label=None,
                    sharex=True
                    )
                pt_part = ""
                if npts > 1:
                    da_mean = ds_mean[var].isel(npts=inpt)
                    da_std = ds_std[var].isel(npts=inpt)
                    lon_pt = f"{da_mean.lon:.2f}"
                    lat_pt = f"{da_mean.lat:.2f}"
                    pt_part = f"{lat_pt}°N; {lon_pt}°E"
                else:
                    da_mean = ds_mean[var]
                    da_std = ds_std[var]

                units = da_mean.attrs.get("units")
                title_lines = [data_name, self.metazone]
                if t_part:
                    title_lines.append(t_part)
                if v_part:
                    title_lines.append(v_part)
                if pt_part:
                    title_lines.append(pt_part)
                title_lines.append(f"{var}, {units}")
                fig.suptitle("\n".join(title_lines), y=1.01)
                fig.subplots_adjust(top=0.85)
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
        
    def _plot_current_background(self, ax, u, v, vmin, vmax, show_flow=True):
        """Plot current speed (module) as a pcolormesh/scatter background,
        optionally with current direction overlaid via xoa.plot.plot_flow
        (gridded data) or a quiver plot (cloud data).

        Parameters
        ----------
        ax : matplotlib.axes.Axes
        u, v : xarray.DataArray
            Zonal/meridional current components (same shape, lon/lat coords).
        vmin, vmax : float
            Color scale bounds for the speed background.
        show_flow : bool
            Whether to overlay plot_flow tracks. False for a std panel --
            standard deviation has no direction, so a flow overlay there
            doesn't mean anything.

        Returns
        -------
        matplotlib.collections.QuadMesh or PathCollection
            The background mappable, for colorbar attachment.
        """
        speed = np.sqrt(u ** 2 + v ** 2)
        is_cloud = ("npts" in u.dims) or (u.lon.dims != ("y", "x"))
        if is_cloud:
            m = ax.scatter(
                u.lon, u.lat, c=speed,
                vmin=vmin, vmax=vmax, cmap=CMAP_VARS["cspeed"]
                )
        else:
            m = ax.pcolormesh(
                u.lon, u.lat, speed,
                vmin=vmin, vmax=vmax, cmap=CMAP_VARS["cspeed"]
                )

        if not show_flow:
            return m

        # plot_flow/xoa.dyn.flow2d needs a genuine 2D grid to trace
        # pathlines -- meaningless (and a hard XoaError) for a handful of
        # scattered cloud points with no spatial structure to flow across.
        # A quiver plot needs no such structure, so use that instead.
        if is_cloud:
            ax.quiver(u.lon, u.lat, u, v, color="black", scale_units="xy")
            return m

        # plot_flow's own default duration/step estimate divides by a plain
        # (non-nan-aware) mean of |u|/|v| to pick an integration duration --
        # ocean model data is land-masked (NaN over land), so that mean is
        # always NaN, crashing xoa.dyn.flow2d with "cannot convert float NaN
        # to integer". Reproduce the same estimate with nanmean instead, and
        # skip the overlay entirely if there's no usable (finite, nonzero)
        # speed at all (e.g. an all-land tile).
        mean_speed = np.sqrt(
            np.nanmean(np.abs(u.values)) ** 2 + np.nanmean(np.abs(v.values)) ** 2
        )
        if mean_speed and np.isfinite(mean_speed):
            dist = xgeo.haversine(
                float(u.lon.min()), float(u.lat.min()),
                float(u.lon.max()), float(u.lat.max()),
                )
            duration = dist / mean_speed / 30
            plot_flow(
                u, v, duration=duration, step=duration / 10, axes=ax,
                color="white", linewidth=0.6,
                )
        else:
            logger.warning("Current speed is zero or all-NaN -- skipping flow overlay")
        return m

    def _plot_current_map(self, ds_data_all, ds_mean_all, ds_std_all):
        """Plot current (u, v) as a map: current speed (module) as
        background, current direction overlaid via xoa.plot.plot_flow.

        Mean panel shows speed + flow overlay; std panel shows speed std
        only (no flow overlay -- std has no natural direction). Speed std
        is approximated from u/v stds assuming independence -- a display
        heuristic, not a rigorous propagation of uncertainty.
        """
        data_name = ds_mean_all.attrs["data_name"]
        attrs = ds_data_all.attrs
        xtitle, ncname = format_time_label(attrs)
        v_title = ""
        if "z" in ds_data_all["u"].dims:
            v_title, v_name = format_vertical_label(attrs)
            ncname += v_name

        units = ds_data_all["u"].attrs.get("units")
        title_lines = [data_name, self.metazone]
        if xtitle.strip():
            title_lines.append(xtitle.strip())
        if v_title.strip():
            title_lines.append(v_title.strip())
        title_lines.append(f"current speed, {units}")
        figtitle = "\n".join(title_lines)

        ds_mean = ds_mean_all[["u", "v"]].squeeze()
        ds_std = ds_std_all[["u", "v"]].squeeze()
        speed_mean = np.sqrt(ds_mean["u"] ** 2 + ds_mean["v"] ** 2)
        speed_std = np.sqrt(ds_std["u"] ** 2 + ds_std["v"] ** 2)

        if "cspeed" in self.vminmax:
            cmin, cmax = self.vminmax["cspeed"]
        else:
            cmin, cmax = 0, speed_mean.mean() + 1.75 * speed_mean.std()
        vmax = speed_std.mean() + 1.75 * speed_std.std()

        dlat = ds_mean.lat.max() - ds_mean.lat.min()
        dlon = ds_mean.lon.max() - ds_mean.lon.min()
        aspect_ratio = 3 / 2 * dlat / dlon
        fig, axes = create_subplots(
                nrows=2,
                figsize=(8 / aspect_ratio, 8),
                x_label='Date', y_label=None,
                sharex=True, projection=ccrs.PlateCarree()
            )

        m0 = self._plot_current_background(axes[0], ds_mean["u"], ds_mean["v"], cmin, cmax)
        m1 = self._plot_current_background(
            axes[1], ds_std["u"], ds_std["v"], 0, vmax, show_flow=False
            )

        cbar0 = fig.colorbar(
            m0, ax=axes[0], orientation='vertical', label="Mean speed",
            fraction=0.05, shrink=0.5
            )
        cbar1 = fig.colorbar(
            m1, ax=axes[1], orientation='vertical', label="St.D. speed",
            fraction=0.05, shrink=0.5
            )

        plt.subplots_adjust(hspace=0.02, wspace=0.01, top=0.88)
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
            f"data/plot/{self.metazone}/"
            f"map_current_{data_name}{ncname}.png"
            )
        fig.suptitle(figtitle)
        self.save_figure(fig, figname)

    def maps(self):
        """Plot maps per product."""
        ds_data_all = self.dt.children["data"].to_dataset()

        if "mean" not in self.dt.children:
            # Nothing configured (no tfreq/trange_seq nor vrange): unlike
            # comp_*, which always has one of these set, armoor-data lets
            # this case through with no mean/std to show (see
            # armoor.data.output.get_dim_stats). Fall back to plotting the
            # raw native data directly, one single-panel map per native
            # time step, instead of the usual mean/std pair.
            return self._maps_raw(ds_data_all)

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
        if "u" in vars2plot and "v" in vars2plot:
            vars2plot = [var for var in vars2plot if var not in ("u", "v")]
            self._plot_current_map(ds_data_all, ds_mean_all, ds_std_all)

        for var in vars2plot:
            ds_data = ds_data_all[[var]]
            ds_mean = ds_mean_all[[var]]
            ds_std = ds_std_all[[var]]
            
            attrs = ds_data.attrs
            xtitle, ncname = format_time_label(attrs)
            v_title = ""
            if "z" in ds_data[var].dims:
                v_title, v_name = format_vertical_label(attrs)
                ncname += v_name
            units = ds_data[var].attrs.get('units')
            data_name = ds_mean_all.attrs["data_name"]

            title_lines = [data_name, self.metazone]
            if xtitle.strip():
                title_lines.append(xtitle.strip())
            if v_title.strip():
                title_lines.append(v_title.strip())
            title_lines.append(f"{var}, {units}")
            figtitle = "\n".join(title_lines)

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
            
            plt.subplots_adjust(hspace=0.02, wspace=0.01, top=0.88)
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

    def _maps_raw(self, ds_data_all):
        """Plot native, unreduced data as single-panel maps.

        One figure per variable and per native time step, since there is
        no mean/std to show (see maps()). "z" is expected to already be
        size 1 by this point (armoor.data.output._apply_range_processing
        splits by native vertical level when neither vlevel nor vrange is
        configured), so only "time" is looped over here.
        """
        data_name = ds_data_all.attrs.get("data_name")
        vlevel = ds_data_all.attrs.get("vlevel")
        vlevel_str = f"{vlevel}m" if vlevel is not None else ""
        vars2plot = [var for var in ds_data_all.data_vars if var != "depth"]
        if "u" in vars2plot and "v" in vars2plot:
            vars2plot = [var for var in vars2plot if var not in ("u", "v")]
            self._plot_current_map_raw(ds_data_all)

        for var in vars2plot:
            da_full = ds_data_all[var]
            # Squeeze away size-1 dims (e.g. "z", already split to one
            # native level per file) but keep "time" as a real dim even
            # when it's also size-1 -- native per-day splitting means it
            # normally is, and a bare .squeeze() would otherwise collapse
            # it to a scalar coord, making every day's figure share the
            # same date-less filename.
            squeeze_dims = [d for d, s in da_full.sizes.items() if s == 1 and d != "time"]
            da_all = da_full.squeeze(dim=squeeze_dims) if squeeze_dims else da_full
            times = da_all["time"].values if "time" in da_all.dims else [None]
            for time_val in times:
                da = da_all.sel(time=time_val) if time_val is not None else da_all
                units = da.attrs.get("units")
                time_str = (
                    pd.Timestamp(time_val).strftime("%Y%m%dT%H%M%S")
                    if time_val is not None else ""
                    )
                title_lines = [data_name, self.metazone]
                if time_str:
                    title_lines.append(time_str)
                if vlevel_str:
                    title_lines.append(vlevel_str)
                title_lines.append(f"{var}, {units}")
                figtitle = "\n".join(title_lines)

                if var in self.vminmax:
                    vmin, vmax = self.vminmax[var]
                else:
                    vmin, vmax = float(da.min()), float(da.max())

                dlat = da.lat.max() - da.lat.min()
                dlon = da.lon.max() - da.lon.min()
                aspect_ratio = 3 / 2 * dlat / dlon
                fig, axes = create_subplots(
                        nrows=1,
                        figsize=(8 / aspect_ratio, 8),
                        x_label='Date', y_label=None,
                        projection=ccrs.PlateCarree()
                    )
                ax = axes[0]
                if ("npts" in da.dims) or (da.lon.dims != ("y", "x")):
                    m0 = ax.scatter(
                        da.lon, da.lat,
                        c=da,
                        vmin=vmin,
                        vmax=vmax,
                        cmap=CMAP_VARS[var]
                        )
                else:
                    m0 = ax.pcolormesh(
                        da.lon, da.lat, da,
                        vmin=vmin,
                        vmax=vmax,
                        cmap=CMAP_VARS[var]
                        )

                fig.colorbar(
                    m0, ax=ax, orientation='vertical', label=var,
                    fraction=0.05, shrink=0.5
                    )

                gl = ax.gridlines(
                    crs=ccrs.PlateCarree(),
                    draw_labels=True,
                    linewidth=0.5,
                    color='gray',
                    alpha=0.5,
                    linestyle='--'
                    )
                gl.top_labels = False
                gl.right_labels = False

                vlevel_suffix = f"_{vlevel}" if vlevel is not None else ""
                figname = (
                    f"data/plot/{self.metazone}/"
                    f"map_{var}_{data_name}_{time_str}{vlevel_suffix}.png"
                    )
                fig.suptitle(figtitle)
                fig.subplots_adjust(top=0.88)
                self.save_figure(fig, figname)

        return None

    def _plot_current_map_raw(self, ds_data_all):
        """Plot native, unreduced current (u, v) as single-panel maps: one
        figure per native time step, speed (module) as background,
        direction overlaid via xoa.plot.plot_flow (see _maps_raw())."""
        data_name = ds_data_all.attrs.get("data_name")
        vlevel = ds_data_all.attrs.get("vlevel")
        vlevel_str = f"{vlevel}m" if vlevel is not None else ""
        # Squeeze away size-1 dims (e.g. "z") but keep "time" as a real dim
        # even when it's also size-1 -- see _maps_raw()'s identical guard.
        squeeze_dims = [
            d for d, s in ds_data_all["u"].sizes.items() if s == 1 and d != "time"
            ]
        u_all = ds_data_all["u"].squeeze(dim=squeeze_dims) if squeeze_dims else ds_data_all["u"]
        v_all = ds_data_all["v"].squeeze(dim=squeeze_dims) if squeeze_dims else ds_data_all["v"]
        units = ds_data_all["u"].attrs.get("units")
        times = u_all["time"].values if "time" in u_all.dims else [None]
        for time_val in times:
            u = u_all.sel(time=time_val) if time_val is not None else u_all
            v = v_all.sel(time=time_val) if time_val is not None else v_all
            speed = np.sqrt(u ** 2 + v ** 2)
            time_str = (
                pd.Timestamp(time_val).strftime("%Y%m%dT%H%M%S")
                if time_val is not None else ""
                )
            title_lines = [data_name, self.metazone]
            if time_str:
                title_lines.append(time_str)
            if vlevel_str:
                title_lines.append(vlevel_str)
            title_lines.append(f"current speed, {units}")
            figtitle = "\n".join(title_lines)

            if "cspeed" in self.vminmax:
                vmin, vmax = self.vminmax["cspeed"]
            else:
                vmin, vmax = float(speed.min()), float(speed.max())

            dlat = u.lat.max() - u.lat.min()
            dlon = u.lon.max() - u.lon.min()
            aspect_ratio = 3 / 2 * dlat / dlon
            fig, axes = create_subplots(
                    nrows=1,
                    figsize=(8 / aspect_ratio, 8),
                    x_label='Date', y_label=None,
                    projection=ccrs.PlateCarree()
                )
            ax = axes[0]
            m0 = self._plot_current_background(ax, u, v, vmin, vmax)

            fig.colorbar(
                m0, ax=ax, orientation='vertical', label="speed",
                fraction=0.05, shrink=0.5
                )

            gl = ax.gridlines(
                crs=ccrs.PlateCarree(),
                draw_labels=True,
                linewidth=0.5,
                color='gray',
                alpha=0.5,
                linestyle='--'
                )
            gl.top_labels = False
            gl.right_labels = False

            vlevel_suffix = f"_{vlevel}" if vlevel is not None else ""
            figname = (
                f"data/plot/{self.metazone}/"
                f"map_current_{data_name}_{time_str}{vlevel_suffix}.png"
                )
            fig.suptitle(figtitle)
            fig.subplots_adjust(top=0.88)
            self.save_figure(fig, figname)

        return None

    def mapseries(self):
        """Plot one map per native time step for every scalar variable,
        plus current/wind vectors when present, with a color scale fixed
        once over the whole series.

        otype "mapseries" (armoor.data.datatype) never has a "mean"/"std"
        child -- unlike maps(), this is always the single-panel,
        per-timestep case, so there's no mean/std branch to check here.
        """
        ds_data_all = self.dt.children["data"].to_dataset()
        attrs = ds_data_all.attrs

        vars2plot = [var for var in ds_data_all.data_vars if var != "depth"]
        if "u" in vars2plot and "v" in vars2plot:
            vars2plot = [var for var in vars2plot if var not in ("u", "v")]
            self._mapseries_vector(ds_data_all, attrs)

        for var in vars2plot:
            if var not in CMAP_VARS:
                continue
            self._mapseries_scalar(ds_data_all, var, attrs)

        return None

    def _style_mapseries_axes(self, ax, date_str):
        """Shared map styling for mapseries frames: coastlines, dashed
        gridlines, a small top-left date/level label -- reused by both
        _mapseries_scalar and _mapseries_vector."""
        gl = ax.gridlines(
            crs=ccrs.PlateCarree(),
            draw_labels=True,
            linewidth=0.5,
            color='gray',
            alpha=0.5,
            linestyle='--'
            )
        gl.top_labels = False
        gl.right_labels = False
        ax.coastlines()
        if date_str:
            # loc='left' shares the same vertical baseline as the default
            # (center) title set via ax.set_title(...), unlike a manually
            # positioned ax.text(), which drifted out of alignment with it.
            ax.set_title(date_str, loc='left', fontsize=9)
        # Without this, matplotlib's default top margin (~0.88) leaves a
        # wide blank band between the title/date row and the map frame --
        # tighten it to match the compact reference rendering.
        ax.figure.subplots_adjust(top=0.95)

    def _add_minmax_table(self, ax, rowlabels, celltext):
        """Compact min/max reference table, top-right of `ax`, matching
        the reference forecaster rendering (uniform light-cyan cells).
        Anchored via `ax.transAxes` (like the date/level text) so it sits
        tight against the axes' top-right corner regardless of the
        colorbar/title layout."""
        height = 0.09 * len(rowlabels)
        taxes = ax.inset_axes([0.8, 1.0, 0.2, height], transform=ax.transAxes)
        table = taxes.table(
            cellText=celltext,
            rowLabels=rowlabels,
            colLabels=["min", "max"],
            cellLoc='center',
            rowLoc='center',
            loc="upper right",
            )
        taxes.set_axis_off()
        table.set_fontsize(8)
        for (irow, icol), cell in table.get_celld().items():
            cell.set_facecolor("lightcyan")
        return table

    def _mapseries_scalar(self, ds_data_all, var, attrs):
        """Render one map per native time step for a single scalar
        variable, with a color scale fixed over the whole series and a
        min/max reference table (top-right of each frame): a "data" row
        (this frame's own min/max, always shown) and a "clim" row (a
        reference climatology's min/max, shown only when
        `clim_min_<var>`/`clim_max_<var>` attrs are present -- see
        `armoor.data.output.OutputProcessor._attach_clim_range`).
        """
        data_name = attrs.get("data_name")
        nstd = attrs.get("nstd", 2.5)
        vlevel = attrs.get("vlevel")
        if isinstance(vlevel, list):
            vlevel = vlevel[0]
        vlevel_str = f"{vlevel}m" if vlevel is not None else ""
        vlevel_suffix = f"_{vlevel}" if vlevel is not None else ""

        da_full = ds_data_all[var]
        # Squeeze away size-1 dims (e.g. "z", already split to one native
        # level per file) but keep "time" as a real dim even when it's
        # also size-1 -- see PlotOceanModel._maps_raw's identical guard.
        squeeze_dims = [d for d, s in da_full.sizes.items() if s == 1 and d != "time"]
        da_all = da_full.squeeze(dim=squeeze_dims) if squeeze_dims else da_full
        units = da_all.attrs.get("units")

        cbar_min = attrs.get(f"cbar_min_{var}")
        cbar_max = attrs.get(f"cbar_max_{var}")
        group_range = (cbar_min, cbar_max) if cbar_min is not None and cbar_max is not None else None
        series_mean = attrs.get(f"series_mean_{var}")
        series_std = attrs.get(f"series_std_{var}")
        vmin, vmax = _cbar_range(
            da_all, var, self.vminmax, nstd, group_range, series_mean, series_std
        )
        clim_min = attrs.get(f"clim_min_{var}")
        clim_max = attrs.get(f"clim_max_{var}")
        has_clim = clim_min is not None and clim_max is not None

        times = da_all["time"].values if "time" in da_all.dims else [None]
        for time_val in times:
            da = da_all.sel(time=time_val) if time_val is not None else da_all
            time_str = (
                pd.Timestamp(time_val).strftime("%Y%m%dT%H%M%S")
                if time_val is not None else ""
                )
            date_str = (
                pd.Timestamp(time_val).strftime("%Y-%m-%d, %H:%M")
                if time_val is not None else ""
                )
            if vlevel_str:
                date_str = f"{date_str} - {vlevel_str}" if date_str else vlevel_str

            dlat = da.lat.max() - da.lat.min()
            dlon = da.lon.max() - da.lon.min()
            aspect_ratio = 3 / 2 * dlat / dlon
            fig, axes = create_subplots(
                    nrows=1,
                    figsize=(8 / aspect_ratio, 8),
                    x_label='Date', y_label=None,
                    projection=ccrs.PlateCarree()
                )
            ax = axes[0]
            if ("npts" in da.dims) or (da.lon.dims != ("y", "x")):
                m0 = ax.scatter(
                    da.lon, da.lat,
                    c=da,
                    vmin=vmin,
                    vmax=vmax,
                    cmap=CMAP_VARS[var]
                    )
            else:
                m0 = ax.pcolormesh(
                    da.lon, da.lat, da,
                    vmin=vmin,
                    vmax=vmax,
                    cmap=CMAP_VARS[var]
                    )

            fig.colorbar(
                m0, ax=ax, orientation='vertical', label=f"{var}, {units}",
                fraction=0.05, shrink=0.5
                )

            ax.set_title(f"{var} ({data_name})")
            self._style_mapseries_axes(ax, date_str)

            celltext = [[f"{float(da.min()):.2f}", f"{float(da.max()):.2f}"]]
            rowlabels = ["data"]
            if has_clim:
                celltext.insert(0, [f"{clim_min:.2f}", f"{clim_max:.2f}"])
                rowlabels.insert(0, "clim")
            self._add_minmax_table(ax, rowlabels, celltext)

            figname = (
                f"data/plot/{self.metazone}/"
                f"mapseries_{var}_{data_name}_{time_str}{vlevel_suffix}.png"
                )
            self.save_figure(fig, figname)

        return None

    def _mapseries_vector(self, ds_data_all, attrs):
        """Render one current/wind map per native time step: magnitude as
        a pcolormesh/scatter background (color scale fixed over the whole
        series, like `_mapseries_scalar`), direction overlaid via quiver
        or barbs depending on `attrs["vector_style"]`. Min/max table
        (top-right) has a single "data" row only -- no climatology
        concept for current/wind."""
        data_name = attrs.get("data_name")
        nstd = attrs.get("nstd", 2.5)
        vector_style = attrs.get("vector_style", "quiver")
        vector_scale = attrs.get("vector_scale", 1.0)
        rarification = attrs.get("rarification")
        barbs_length = attrs.get("barbs_length", 4.0)
        barbs_linewidth = attrs.get("barbs_linewidth", 0.3)
        quiver_scale = attrs.get("quiver_scale")
        vlevel = attrs.get("vlevel")
        if isinstance(vlevel, list):
            vlevel = vlevel[0]
        vlevel_str = f"{vlevel}m" if vlevel is not None else ""
        vlevel_suffix = f"_{vlevel}" if vlevel is not None else ""

        squeeze_dims = [
            d for d, s in ds_data_all["u"].sizes.items() if s == 1 and d != "time"
            ]
        u_all = ds_data_all["u"].squeeze(dim=squeeze_dims) if squeeze_dims else ds_data_all["u"]
        v_all = ds_data_all["v"].squeeze(dim=squeeze_dims) if squeeze_dims else ds_data_all["v"]

        if rarification is None:
            # No explicit cfgfile override -- aim for ~30 arrows along the
            # grid's longer horizontal axis regardless of native
            # resolution, instead of a fixed spacing that turns into an
            # unreadable hatch on high-resolution model grids.
            if "x" in u_all.dims:
                npts_dim = max(u_all.sizes["x"], u_all.sizes["y"])
            elif "npts" in u_all.dims:
                npts_dim = u_all.sizes["npts"]
            else:
                npts_dim = 30
            rarification = max(1, round(npts_dim / 30))
        else:
            rarification = int(rarification)

        # Always displayed in knots (forecaster convention for wind/current
        # speed), independent of vector_scale which only tunes arrow glyphs.
        speed_all = np.sqrt(u_all ** 2 + v_all ** 2) * MS_TO_KNOTS

        if "cspeed" in self.vminmax:
            vmin, vmax = self.vminmax["cspeed"]
        else:
            series_mean = attrs.get("series_mean_cspeed")
            series_std = attrs.get("series_std_cspeed")
            if series_mean is not None and series_std is not None:
                mean, std = series_mean * MS_TO_KNOTS, series_std * MS_TO_KNOTS
            else:
                mean, std = float(speed_all.mean()), float(speed_all.std())
            vmin = 0.0
            vmax = mean + nstd * std

        times = u_all["time"].values if "time" in u_all.dims else [None]
        for time_val in times:
            u = u_all.sel(time=time_val) if time_val is not None else u_all
            v = v_all.sel(time=time_val) if time_val is not None else v_all
            speed = np.sqrt(u ** 2 + v ** 2) * MS_TO_KNOTS
            time_str = (
                pd.Timestamp(time_val).strftime("%Y%m%dT%H%M%S")
                if time_val is not None else ""
                )
            date_str = (
                pd.Timestamp(time_val).strftime("%Y-%m-%d, %H:%M")
                if time_val is not None else ""
                )
            if vlevel_str:
                date_str = f"{date_str} - {vlevel_str}" if date_str else vlevel_str

            dlat = u.lat.max() - u.lat.min()
            dlon = u.lon.max() - u.lon.min()
            aspect_ratio = 3 / 2 * dlat / dlon
            fig, axes = create_subplots(
                    nrows=1,
                    figsize=(8 / aspect_ratio, 8),
                    x_label='Date', y_label=None,
                    projection=ccrs.PlateCarree()
                )
            ax = axes[0]
            is_cloud = ("npts" in u.dims) or (u.lon.dims != ("y", "x"))
            if is_cloud:
                m0 = ax.scatter(
                    u.lon, u.lat, c=speed,
                    vmin=vmin, vmax=vmax, cmap=CMAP_VARS["cspeed"]
                    )
            else:
                m0 = ax.pcolormesh(
                    u.lon, u.lat, speed,
                    vmin=vmin, vmax=vmax, cmap=CMAP_VARS["cspeed"]
                    )

            if u.lon.dims == ("y", "x"):
                u_r = u.isel(y=slice(None, None, rarification), x=slice(None, None, rarification))
                v_r = v.isel(y=slice(None, None, rarification), x=slice(None, None, rarification))
            elif "npts" in u.dims:
                u_r = u.isel(npts=slice(None, None, rarification))
                v_r = v.isel(npts=slice(None, None, rarification))
            else:
                u_r, v_r = u, v

            if vector_style == "barbs":
                ax.barbs(
                    u_r.lon, u_r.lat,
                    u_r * MS_TO_KNOTS * vector_scale, v_r * MS_TO_KNOTS * vector_scale,
                    length=barbs_length, linewidth=barbs_linewidth,
                    transform=ccrs.PlateCarree(),
                    )
            else:
                ax.quiver(
                    u_r.lon, u_r.lat,
                    u_r * MS_TO_KNOTS * vector_scale, v_r * MS_TO_KNOTS * vector_scale,
                    scale=quiver_scale, color="black",
                    transform=ccrs.PlateCarree(),
                    )

            fig.colorbar(
                m0, ax=ax, orientation='vertical', label="speed, kt",
                fraction=0.05, shrink=0.5
                )

            ax.set_title(f"speed ({data_name})")
            self._style_mapseries_axes(ax, date_str)
            self._add_minmax_table(
                ax, ["data"],
                [[f"{float(speed.min()):.2f}", f"{float(speed.max()):.2f}"]],
                )

            figname = self._vector_figname(data_name, time_str, vlevel_suffix)
            self.save_figure(fig, figname)

        return None

    def _vector_figname(self, data_name, time_str, vlevel_suffix):
        return (
            f"data/plot/{self.metazone}/"
            f"mapseries_current_{data_name}_{time_str}{vlevel_suffix}.png"
            )


class PlotEddies(_PlotDataBase):
    """Plot methods for eddy-detection tool output (contour_lat/contour_lon,
    center_lat/center_lon, eddy_type, vmax_area -- no depth/ptemp/sal, so
    none of PlotOceanModel's methods apply).

    No methods yet -- calling any output method raises a clear ArmoorError
    via the inherited call() dispatch until eddy plotting is designed.
    """


class PlotSstSatellite(PlotOceanModel):
    """Plot methods for satellite SST products -- surface-only (ptemp),
    reuses every PlotOceanModel method as-is."""


class PlotMeteo(PlotOceanModel):
    """Plot methods for atmospheric forcing (wind u/v, ...) -- reuses
    every PlotOceanModel method as-is, except mapseries's vector
    rendering, forced to barbs (meteorological convention for wind)
    regardless of any configured vector_style, with a plain "wind"
    figname instead of "current_{data_name}"."""

    def _mapseries_vector(self, ds_data_all, attrs):
        super()._mapseries_vector(ds_data_all, {**attrs, "vector_style": "barbs"})

    def _vector_figname(self, data_name, time_str, vlevel_suffix):
        return (
            f"data/plot/{self.metazone}/"
            f"mapseries_wind_{time_str}{vlevel_suffix}.png"
            )


DataOceanModel.plotter_cls = PlotOceanModel
DataEddies.plotter_cls = PlotEddies
DataSstSatellite.plotter_cls = PlotSstSatellite
DataMeteo.plotter_cls = PlotMeteo


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


def _plot_task_star(args):
    """Unpack one `main_plot` task tuple -- `imap_unordered` (unlike
    `starmap`) only maps over a single iterable, so this adapts
    `_plot_task`'s multi-arg signature to it."""
    return _plot_task(*args)


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
    ctx = multiprocessing.get_context("spawn")
    with ctx.Pool(num_workers) as pool:
        results = list(tqdm(
            pool.imap_unordered(_plot_task_star, task_args),
            total=len(task_args),
            desc="Plotting figures",
            ))
    png_paths = [p for task_result in results for p in (task_result or [])]
    logger.info(f"Generated {len(png_paths)} PNG file(s)")
    return png_paths
