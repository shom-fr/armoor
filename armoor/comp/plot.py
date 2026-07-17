import os
import logging
import re
from collections import defaultdict
from pathlib import Path

import cartopy.crs as ccrs
import cmocean as cmo
import dask
from dask.diagnostics import ProgressBar
import matplotlib
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import xarray as xr
from matplotlib.collections import LineCollection
from mpl_toolkits.axes_grid1 import make_axes_locatable
from xoa.plot import plot_minimap, plot_ts

from armoor.base import LINE_COLORS, CMAP_VARS
from armoor.base.dispatch import MethodRegistry
from armoor.base.plot import (create_subplots, diagdisp, format_time_label,
                              format_vertical_label, get_output_vminmax,
                              save_figure)
from armoor.comp import GROUP_SUFFIX, METRIC_LABELS
from armoor.comp.comparison import get_comparison
from armoor.data.load import StagedDataset

logger = logging.getLogger(__name__)

_GROUP_SUFFIX_RE = re.compile(rf"{re.escape(GROUP_SUFFIX)}\d+$")


def _drop_group_suffix(ds):
    """Undo the per-group dim/coord renaming `concat_then_merge` applies to
    minor signature-groups (e.g. mld) to avoid cardinality clashes.

    Safe to call on a dataset narrowed to a single variable, since only one
    suffixed variant of any given coord/dim can be present at that point.
    """
    renames = {
        name: _GROUP_SUFFIX_RE.sub("", name)
        for name in set(ds.dims) | set(ds.variables)
        if _GROUP_SUFFIX_RE.search(name)
        }
    return ds.rename(renames) if renames else ds


def _bin_datasets(node):
    """Return the list of per-vrange-bin datasets held by a `data`/`closest`
    node.

    That node is a single dataset when its sort_key matched exactly one
    coloc file, or holds numbered children ("0", "1", ...) -- one per
    vrange-bin file -- when `_concatenate_datasets` (armoor.comp.output)
    left them unfused for uvprofiles/udiagts instead of merging them.
    """
    children = list(node.children)
    if children:
        return [node[c].to_dataset() for c in sorted(children, key=int)]
    return [node.to_dataset()]

matplotlib.use('Agg')
plt.style.use('seaborn-v0_8-whitegrid')
plt.rcParams.update({'font.size': 8})


class PlotComp(MethodRegistry):
    """Generate comparison plots (dispersion diagrams, profiles, maps, time
    series) from a colocated armoor-comp-* output datatree.

    Plot methods are dispatched by name via `call` (see
    `armoor.base.dispatch.MethodRegistry`).
    """

    _dispatch_label = "Comparison plot"

    def __init__(self, nc, func_comp, metazone, vminmax=None):
        """Initialize the plotter and open the output datatree.

        Parameters
        ----------
        nc : str
            Path to the zarr datatree holding the comparison output.
        func_comp : str
            Comparison type identifier (e.g. ``"comp_sst"``), used to look
            up the plot title via `armoor.comp.comparison.get_comparison`.
        metazone : str
            Metazone name, used in plot titles/filenames.
        vminmax : dict, optional
            Mapping of variable name to a ``(vmin, vmax)`` pair, overriding
            the automatic color scaling for that variable (see `maps`).
        """
        self.methods = {}
        self.func_comp = func_comp
        self.metazone = metazone
        self.staged = StagedDataset("", metazone=metazone, comp_func=func_comp, stage="plot")
        self.ax_minimap = [0.7, 0.91, 0.19]
        self.plot_title = get_comparison(func_comp).title
        self.dt = xr.open_datatree(nc)
        self.saved_files = []
        self.vminmax = vminmax
        self.__post_init__()


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
        ax_minimap = plot_minimap(dsref, fig=fig, ax=self.ax_minimap, **kw)
        
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

            for var in dsprod_all.data_vars:
                # Reduce "member" after narrowing to a single variable and
                # resolving the group-suffix rename, not before: a minor
                # signature-group (e.g. mld) may carry its own "member"
                # dim under a suffixed name (see `concat_then_merge`),
                # which a dataset-wide "member" check/mean would miss
                # entirely -- leaving it unreduced and causing dsref/dsprod
                # sizes to diverge for that variable.
                dsref = _drop_group_suffix(dsref_all[[var]])
                dsprod = _drop_group_suffix(dsprod_all[[var]])
                if "member" in dsprod.dims:
                    dsprod = dsprod.mean(dim="member", keep_attrs=True)
                if "member" in dsref.dims:
                    dsref = dsref.mean(dim="member", keep_attrs=True)

                units = dsref[var].attrs.get('units')

                figtitle = (
                    f"{self.plot_title} \n"
                    f"{self.metazone} \n"
                    f"{var}, {units}"
                    )

                figname = (
                    f"{self.staged.output_dir('plot', ref_name=ref_name)}/"
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
            dsprod_all.close()
            dsref_all.close()

    def diagdisp_sel(self):
        """Plot a dispersion diagram per product and range."""
        for prod, node_prod in self.dt.children.items():
            
            dsprod_all = node_prod["prod/data"].to_dataset()
            dsref_all = node_prod["ref/data"].to_dataset()
            
            prod_name = dsprod_all.attrs["data_name"]
            ref_name = dsref_all.attrs["data_name"]

            for var in dsprod_all.data_vars:
                # Reduce "member" after narrowing to a single variable and
                # resolving the group-suffix rename -- see diagdisp_glob.
                dsref = _drop_group_suffix(dsref_all[[var]])
                dsprod = _drop_group_suffix(dsprod_all[[var]])
                if "member" in dsprod.dims:
                    dsprod = dsprod.mean(dim="member", keep_attrs=True)
                if "member" in dsref.dims:
                    dsref = dsref.mean(dim="member", keep_attrs=True)

                attrs = dsref.attrs
                xtitle, ncname = format_time_label(attrs, ds=dsref)
                v_title, v_name = format_vertical_label(attrs)
                if v_title:
                    xtitle += f"\n{v_title}"
                ncname += v_name

                units = dsref[var].attrs.get('units')
                    
                figtitle = (
                    f"{self.plot_title} \n"
                    f"{self.metazone} \n {xtitle}\n "
                    f"{var}, {units}"
                    )
                
                figname = (
                    f"{self.staged.output_dir('plot', ref_name=ref_name)}/"
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
            dsprod_all.close()
            dsref_all.close()
        return None
    
    def _mdiagts(self, dsref, dsprod, figtitle, figname):
        if dsref.depth.size == 0 or dsprod.depth.size == 0:
            logger.warning(f"Empty depth array, skipping mdiagts plot: {figname}")
            return
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
        ax_minimap = plot_minimap(dsref, fig=fig, ax=self.ax_minimap, **kw)
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
            dsref = None
            dsprod = None
            for data, dt_data in node_prod.items():
                logger.debug(f"{data}, Path: {dt_data.path}")
                if "ref" in data:
                    dsref = dt_data["data"].to_dataset()
                elif "prod" in data:
                    dsprod = dt_data["data"].to_dataset()
            if dsref is None or dsprod is None:
                logger.warning(f"Missing ref or prod data for {prod}, skipping")
                continue
            if 'z' not in dsref.dims or 'z' not in dsprod.dims:
                logger.warning(f"z not in ref or prod data for {prod}, skipping")
                continue

            dsprod = dsprod.stack({"npt": list(dsprod.sizes.keys())})
            dsref = dsref.stack({"npt": list(dsref.sizes.keys())})
            dsprod = dsprod.where(~dsprod.ptemp.isnull(), drop=True)
            dsref = dsref.where(~dsref.ptemp.isnull(), drop=True)
            attrs = dsprod.attrs
            xtitle, xfigname = format_time_label(attrs, ds=dsprod)
            v_title, v_name = format_vertical_label(attrs)
            if v_title:
                xtitle += f"\n{v_title}"
            xfigname += v_name

            refname = dsref.attrs.get("data_name")
            prodname = dsprod.attrs.get("data_name")
            figtitle = (
                f"{self.plot_title} \n"
                f"{prodname} vs {refname} \n"
                f"{self.metazone}\n"
                f"{xtitle}"
                )
            figname = (
                f"{self.staged.output_dir('plot', ref_name=refname)}/"
                f"mdiagts_{prod}{xfigname}.png"
                )
                
            self._mdiagts(dsref, dsprod, figtitle, figname)
            dsref.close()
            dsprod.close()

    def udiagts(self):
        """Plot uniquely profiles theta-saln."""
        dssprod_data = []
        dssprod_closest = []
        dsref_bins = None
        for prod, node_prod in self.dt.children.items():
            logger.info(f"{prod}, Path: {node_prod.path}")
            for data, dt_data in node_prod.items():
                logger.info(f"{data}, Path: {dt_data.path}")
                if "ref" in data:
                    dsref_bins = _bin_datasets(dt_data["data"])
                elif "prod" in data:
                    dssprod_data.append(_bin_datasets(dt_data["data"]))
                    dssprod_closest.append(
                        _bin_datasets(dt_data["closest"]) if "closest" in dt_data else None
                        )
        if dsref_bins is None:
            logger.warning("No reference data found, skipping udiagts")
            return
        if 'z' not in dsref_bins[0].dims:
            logger.warning(f"z not in ref, skipping")
            return
        refname = dsref_bins[0].attrs.get("data_name")

        # Each bin is one vrange-split fragment of this single profile (the
        # sort/output stage already guarantees one real profile per call to
        # this method -- see `armoor.comp.output`); the nearest model member
        # was already resolved once upstream, before any vrange split.
        for ibin, dsref in enumerate(dsref_bins):
            vrange = dsref.attrs.get('vrange')
            vlevel = dsref.attrs.get('vlevel')
            dssprod_closest_bin = [
                (closest_bins[ibin].squeeze() if closest_bins is not None
                 else dssprod_data[iprod][ibin].squeeze())
                for iprod, closest_bins in enumerate(dssprod_closest)
                ]
            time = pd.to_datetime(dsref.time.values[0])
            mask = ~dsref.ptemp.isnull()
            if (~mask).all():
                continue
            depth = dsref.depth.where(mask, drop=True)
            zmin = -float(depth.max())
            zmax = -float(depth.min())
            xtitle = f"{time:%Y-%m-%dT%H:%M:%S}"
            xfigname = f"_{time:%Y-%m-%dT%H:%M:%S}"
            if vrange:
                xtitle += f"\n {vrange}"
                xfigname  += f"_{vrange}"
            if vlevel:
                xtitle += f"\n {vlevel}"
                xfigname  += f"_{vlevel}"

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
                    label=refname
                    )
                )
            for iprod, dsprod_closest in enumerate(dssprod_closest_bin):
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
                        label=dssprod_data[iprod][ibin].attrs["data_name"]
                        )
                    )
                ax = tsprod["axes"]
            ax.legend(
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
            plot_minimap(dsref, fig=fig, ax=self.ax_minimap, **kw)
            figname = (
                f"{self.staged.output_dir('plot', ref_name=refname)}/"
                f"udiagts{xfigname}.png"
                )
            self.save_figure(
                fig,
                figname.format(**locals())
                )    
        
    def _mvprofiles(self, dsref, dsprod, figtitle, figname):
        if dsref.depth.size == 0 or dsprod.depth.size == 0:
            logger.warning(f"Empty depth array, skipping mvprofiles plot: {figname}")
            return

        ref_color = "k"
        prod_color = "slateblue"

        dsprod = dsprod.reset_coords("depth")
        dsref = dsref.reset_coords("depth")
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
            vmax = np.nanmax([daref.max(), daprod.max()])

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
            ax_minimap = plot_minimap(dsref, fig=fig, ax=self.ax_minimap, **kw)
            
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
            dsref = None
            dsprod = None
            for data, dt_data in node_prod.items():
                logger.debug(f"{data}, Path: {dt_data.path}")
                if "ref" in data:
                    dsref = dt_data["data"].to_dataset()
                elif "prod" in data:
                    dsprod = dt_data["data"].to_dataset()
            if dsref is None or dsprod is None:
                logger.warning(f"Missing ref or prod data for {prod}, skipping")
                continue
            if 'z' not in dsref.dims or 'z' not in dsprod.dims:
                logger.warning(f"z not in ref or prod data for {prod}, skipping")
                continue

            dsprod = dsprod.where(~dsprod.ptemp.isnull(), drop=True)
            dsref = dsref.where(~dsref.ptemp.isnull(), drop=True)
            attrs = dsprod.attrs
            xtitle, xfigname = format_time_label(attrs, ds=dsprod)
            v_title, v_name = format_vertical_label(attrs)
            if v_title:
                xtitle += f"\n{v_title}"
            xfigname += v_name
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
                f"{self.staged.output_dir('plot', ref_name=refname)}/"
                f"mvprofiles_{prod}_{var}{xfigname}.png"
                )

            self._mvprofiles(dsref, dsprod, figtitle, figname)
            dsref.close()
            dsprod.close()

    def uvprofiles(self):
        """Plot uniquely vertical profiles."""
        dssprod_data = []
        dssprod_closest = []
        dsref_bins = None
        for prod, node_prod in self.dt.children.items():
            logger.info(f"{prod}, Path: {node_prod.path}")
            for data, dt_data in node_prod.items():
                logger.info(f"{data}, Path: {dt_data.path}")
                if "ref" in data:
                    dsref_bins = _bin_datasets(dt_data["data"])
                elif "prod" in data:
                    dssprod_data.append(_bin_datasets(dt_data["data"]))
                    dssprod_closest.append(
                        _bin_datasets(dt_data["closest"]) if "closest" in dt_data else None
                        )
        if dsref_bins is None:
            logger.warning("No reference data found, skipping uvprofiles")
            return
        if 'z' not in dsref_bins[0].dims:
            logger.warning(f"z not in ref, skipping")
            return
        refname = dsref_bins[0].attrs.get("data_name")

        def _safe_reduce(ds, method):
            # "depth" is a position axis, not a statistic: averaging it
            # across "member" is meaningless and can leave it with a
            # leftover "member" dim (whenever it doesn't also vary by "z"
            # and so never qualifies as a proper agg_var) -- always take
            # one representative member's depth instead, like the "closest"
            # profile already effectively does.
            agg_vars = [
                v for v in ds.data_vars
                if v != "depth" and "member" in ds[v].dims and ds[v].ndim > 1
                ]
            other_vars = [v for v in ds.data_vars if v not in agg_vars]
            result = getattr(ds[agg_vars], method)(dim="member")
            for v in other_vars:
                result[v] = ds[v].isel(member=0, drop=True) if "member" in ds[v].dims else ds[v]
            return result

        def _force_1d(da, context):
            # Defensive net for the member/std reduction above: whatever
            # leftover dim slips through, collapse it and log the actual
            # shape so the root cause can be diagnosed from the logs
            # instead of crashing matplotlib deep in fill_betweenx/plot.
            if da.ndim == 1:
                return da
            extra_dims = [d for d in da.dims if d != "z"]
            logger.warning(
                f"{context}: unexpected dims {da.dims} shape {da.shape}, "
                f"collapsing {extra_dims}"
                )
            return da.isel({d: 0 for d in extra_dims}, drop=True)

        # Each bin is one vrange-split fragment of this single profile (the
        # sort/output stage already guarantees one real profile per call to
        # this method -- see `armoor.comp.output`); the nearest model member
        # was already resolved once upstream, before any vrange split.
        for ibin, dsref in enumerate(dsref_bins):
            vrange = dsref.attrs.get('vrange')
            dssprod_bin = []
            dssprod_closest_bin = []
            for iprod, bins in enumerate(dssprod_data):
                ds = bins[ibin].squeeze()
                if "member" in ds.depth.dims:
                    ds = ds.reset_coords("depth")
                dssprod_bin.append(ds)
                closest_bins = dssprod_closest[iprod]
                dssprod_closest_bin.append(
                    closest_bins[ibin].squeeze() if closest_bins is not None else ds
                    )
            dssprod_mean = [_safe_reduce(ds, "mean") for ds in dssprod_bin]
            dssprod_std = [_safe_reduce(ds, "std") for ds in dssprod_bin]
            time = pd.to_datetime(dsref.time.values[0])
            mask = ~dsref.ptemp.isnull()
            if (~mask).all():
                continue
            depth = dsref.depth.where(mask, drop=True)
            zmin = -float(depth.max())
            zmax = -float(depth.min())
            xtitle = f"{time:%Y-%m-%dT%H:%M:%S}"
            xfigname = f"_{time:%Y-%m-%dT%H:%M:%S}"
            if vrange:
                xtitle += f"\n {vrange}"
                xfigname  += f"_{vrange}"
            for varname in dsref.data_vars:
                units = dsref[varname].attrs.get("units")
                daref = dsref[varname].squeeze()
                if 'depth' not in daref.coords:
                    logger.warning(f"depth not in coords for {varname}, skipping")
                    continue
                dasprod_closest= [ds[[varname]].squeeze() for ds in dssprod_closest_bin]
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
                    prod_name = dssprod_mean[iprod].attrs['data_name']
                    data_prod_mean = _force_1d(
                        dssprod_mean[iprod][varname], f"{prod_name} {varname} mean"
                        )
                    data_prod_std = _force_1d(
                        dssprod_std[iprod][varname], f"{prod_name} {varname} std"
                        )
                    mean_depth = _force_1d(
                        data_prod_mean.depth, f"{prod_name} {varname} mean depth"
                        )
                    ax.plot(
                        dasprod_closest[iprod][varname], -dasprod_closest[iprod].depth,
                        color=LINE_COLORS[iprod], linewidth=2.0,
                        label=f"{prod_name} closest"
                        )

                    ax.fill_betweenx(
                        -mean_depth,
                        data_prod_mean - data_prod_std,
                        data_prod_mean + data_prod_std,
                        color=LINE_COLORS[iprod],
                        alpha=0.25,
                        label=f"{prod_name} mean +/- std"
                        )
                ax.legend(
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
                ax_minimap = plot_minimap((daref.lon, daref.lat), fig=fig, ax=self.ax_minimap, **kw)

                figname = (
                    f"{self.staged.output_dir('plot', ref_name=refname)}/"
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

        ds_ref_data = dt_ref["data"].to_dataset()
        ds_ref_mean = dt_ref["mean"].to_dataset()
        ds_ref_std = dt_ref["std"].to_dataset()
        ref_name = ds_ref_data.attrs.get("data_name")
        attrs = ds_ref_data.attrs
        xtitle, ncname = format_vertical_label(attrs)

        if "npts" in ds_ref_mean.dims:
            npts = ds_ref_mean.sizes["npts"]
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

        dss_prod_data = [dt_prod["data"].to_dataset() for dt_prod in dts_prod]
        dss_prod_mean = [dt_prod["mean"].to_dataset() for dt_prod in dts_prod]
        dss_prod_std = [dt_prod["std"].to_dataset() for dt_prod in dts_prod]
        dss_comp_bias = [dt_comp["bias"].to_dataset() for dt_comp in dts_comp]
        dss_comp_rmse = [dt_comp["rmse"].to_dataset() for dt_comp in dts_comp]
        dss_comp_rmsec = [dt_comp["rmsec"].to_dataset() for dt_comp in dts_comp]

        # Only process variables present in both reference and all product datasets
        prod_vars = set(dss_prod_mean[0].data_vars) if dss_prod_mean else set()
        for dsp in dss_prod_mean[1:]:
            prod_vars &= set(dsp.data_vars)
        vars_to_plot = [v for v in ds_ref_data.data_vars if v in prod_vars]

        for var in vars_to_plot:
            for inpt in range(npts):
                fig, axes = create_subplots(
                    nrows=5, figsize=(10, 8),
                    x_label='Date', y_label=None,
                    sharex=True
                    )
                if npts > 1:
                    lon_pt = f"{ds_ref_data.lon.isel(npts=inpt):.2f}"
                    lat_pt = f"{ds_ref_data.lat.isel(npts=inpt):.2f}"
                    xcoord = f"{lat_pt}°N; {lon_pt}°E\n"
                else:
                    xcoord = ""
                for iprod in range(len(dts_prod)):
                    if iprod == 0:
                        da_ref = ds_ref_data[var]
                        units = da_ref.attrs.get("units")
                        fig.suptitle(
                            f"{self.plot_title} \n"
                            f"{self.metazone} \n {xtitle} {xcoord}\n"
                            f"{var}, {units} \n",
                            y=1.01
                            )
                        lw = 2
                        da = ds_ref_mean[var].squeeze()
                        if npts > 1:
                            da = da.isel(npts=inpt)
                        axes[0].plot(
                            da.time,
                            da,
                            color="k",
                            linewidth=lw,
                            label=ref_name
                            )
                        da = ds_ref_std[var]
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
                        _da_map = da_ref if npts == 1 else da_ref.isel(npts=inpt)
                        plot_minimap(
                            (_da_map.lon, _da_map.lat),
                            ax=self.ax_minimap,
                            fig=fig,
                            plot_coords=plot_coords,
                            coords_markersize=4,
                            gridlines_draw_labels=True,
                            gridlines_xlabel_style={'size': 6},
                            gridlines_ylabel_style={'size': 6},
                            )

                    prod_name = dss_prod_data[iprod].attrs["data_name"]

                    da = dss_prod_mean[iprod][var].squeeze()
                    if npts > 1:
                        da = da.isel(npts=inpt)
                    axes[0].plot(
                        da.time,
                        da,
                        color=LINE_COLORS[iprod],
                        linewidth=lw,
                        label=prod_name
                        )
                    da = dss_prod_std[iprod][var].squeeze()
                    if npts > 1:
                        da = da.isel(npts=inpt)
                    axes[1].plot(
                        da.time,
                        da,
                        color=LINE_COLORS[iprod],
                        linewidth=lw,
                        label=prod_name
                        )
                    da = dss_comp_bias[iprod][var].squeeze()
                    if npts > 1:
                        da = da.isel(npts=inpt)
                    axes[2].plot(
                        da.time,
                        da,
                        linewidth=lw,
                        label=f"{prod_name} vs {ref_name}"
                        )
                    da = dss_comp_rmse[iprod][var].squeeze()
                    if npts > 1:
                        da = da.isel(npts=inpt)
                    axes[3].plot(
                        da.time,
                        da,
                        color=LINE_COLORS[iprod],
                        linewidth=lw
                        )
                    da = dss_comp_rmsec[iprod][var].squeeze()
                    if npts > 1:
                        da = da.isel(npts=inpt)
                    axes[4].plot(
                        da.time,
                        da,
                        color=LINE_COLORS[iprod],
                        linewidth=lw
                        )

                handles, labels = axes[0].get_legend_handles_labels()
                fig.legend(handles, labels, ncol=1, loc='center left',
                           edgecolor='gray', bbox_to_anchor=(0.11,1.0))

                axes[0].set_ylabel("Mean")
                axes[1].set_ylabel("St.D")
                axes[2].set_ylabel("Bias")
                axes[3].set_ylabel("Rmse")
                axes[4].set_ylabel("Ce.Rmse")

                self.save_figure(fig, figname.format(**locals()))

        ds_ref_data.close()
        ds_ref_mean.close()
        ds_ref_std.close()
        for ds in dss_prod_data + dss_prod_mean + dss_prod_std + dss_comp_bias + dss_comp_rmse + dss_comp_rmsec:
            ds.close()
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

        xtitle, ncname = format_vertical_label(attrs, allow_vrange=False)
        
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
                    xtitle_pt = xtitle + f"{lat_pt}°N; {lon_pt}°E"
                else:
                    da_ref = ds_ref[var]
                    das_prod = [ds[var] for ds in dss_prod]
                    das_comp = [ds[var] for ds in dss_comp]
                    xtitle_pt = xtitle
                for iprod, da_prod in enumerate(das_prod):

                    if iprod == 0:
                        units = da_ref.attrs.get("units")
                        fig.suptitle(
                            f"{self.plot_title} \n"
                            f"{self.metazone} \n {xtitle_pt}\n"
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
                            (da_ref.lon, da_ref.lat),
                            ax=self.ax_minimap,
                            fig=fig,
                            plot_coords=plot_coords,
                            coords_markersize=4,
                            gridlines_draw_labels=True,
                            gridlines_xlabel_style={'size': 6},
                            gridlines_ylabel_style={'size': 6},
                            )
                    
                    prod_name = dss_prod[iprod].attrs["data_name"]
                    if "member" in da_prod.dims:
                        da_prod = da_prod.mean("member")
                    da_prod = da_prod.squeeze()
                    axes[0].plot(
                        da_prod["time"],
                        da_prod,
                        color=LINE_COLORS[iprod],
                        linewidth=lw,
                        label=prod_name
                        )
                    da_comp = das_comp[iprod]
                    if "member" in da_comp.dims:
                        da_comp = da_comp.mean("member")
                    da_comp = da_comp.squeeze()
                    axes[1].plot(
                        da_comp["time"],
                        da_comp,
                        color=LINE_COLORS[iprod],
                        linewidth=lw,
                        label=prod_name
                        )
                
                axes[0].legend(loc='upper left', fontsize=11, frameon=True, fancybox=True)
                axes[1].legend(loc='upper left', fontsize=11, frameon=True, fancybox=True)
    
                axes[0].set_ylabel("")
                axes[1].set_ylabel("Diff.")
    
                self.save_figure(fig, figname.format(**locals()))
        ds_ref.close()
        for ds in dss_prod + dss_comp:
            ds.close()
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
    
    def timeseries_drifter(self):
        """Plot time series of model/drifter comparison."""
        lw = 2
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
        
        figname = (
            "{self.func_comp}/plot/{self.metazone}/{ref_name}/"
            "timeseries_drifter.png"
            )
        fig, axes = create_subplots(
            nrows=2, figsize=(10, 6),
            x_label='Integration period, day', y_label=None,
            sharex=True
            )
        fig.suptitle(
            f"{self.plot_title} \n"
            f"{self.metazone} \n {ref_name}\n",
            y=1.01
            )
        
        plot_minimap(
            ds_ref.set_coords(["lon", "lat"]),
            ax=self.ax_minimap,
            fig=fig,
            plot_coords="lines",
            coords_markersize=4,
            gridlines_draw_labels=True,
            gridlines_xlabel_style={'size': 6},
            gridlines_ylabel_style={'size': 6},
            )
        for iprod, ds_prod in enumerate(dss_prod):
            
            prod_name = dss_prod[iprod].attrs["data_name"]
            
            axes[0].plot(
                dss_comp[iprod]["time"],
                dss_comp[iprod].distance / 1e3,
                color=LINE_COLORS[iprod],
                linewidth=lw,
                label=prod_name
                )
            
            axes[1].plot(
                dss_comp[iprod]["time"],
                dss_comp[iprod].direction,
                color=LINE_COLORS[iprod],
                linewidth=lw,
                label=prod_name
                )
        
        handles, labels = axes[0].get_legend_handles_labels()
        fig.legend(handles, labels, ncol=1, loc='center left',
                   edgecolor='gray', bbox_to_anchor=(0.11,1.0))


        axes[0].set_ylabel("Distance, km")
        axes[1].set_ylabel("Direction diff., °")

        self.save_figure(fig, figname.format(**locals()))
        ds_ref.close()
        for ds in dss_prod + dss_comp:
            ds.close()
        del axes
        return None

    def maps_trajectory_drifter(self):
        """Plot maps per product."""
        for prod, node_prod in self.dt.children.items():
            dsprod = node_prod["prod/data"].to_dataset()
            dsref = node_prod["ref/data"].to_dataset()
            prod_name = dsprod.attrs.get("data_name")
            ref_name = dsref.attrs.get("data_name")
                                        
            figtitle = (
                f"{self.plot_title} \n"
                f"{self.metazone}"
                )
                
            dlat = dsref.lat.max() - dsref.lat.min()
            dlon = dsref.lon.max() - dsref.lon.min()
            mid_lat = 0.5 * (dsref.lat.min() + dsref.lat.max())
            aspect_ratio = float(dlat / (dlon * np.cos(np.radians(mid_lat))))
            fig, axes = create_subplots(
                layout_type="one",
                figsize=(10, 10 * aspect_ratio),
                x_label=None, y_label=None,
                sharex=True, projection=ccrs.PlateCarree()
                )

            lonmin = dsref.lon.min() - 0.5 * dlon
            lonmax = dsref.lon.max() + 0.5 * dlon
            latmin = dsref.lat.min() - 0.5 * dlat
            latmax = dsref.lat.max() + 0.5 * dlat
            axes[0].set_xlim([lonmin, lonmax])
            axes[0].set_ylim([latmin, latmax])

            axes[0].plot(
                dsref.lon,
                dsref.lat,
                color="k",
                label=ref_name,
                lw=4
                )
            
            for itraj in range(dsprod.sizes["trajectory_parcels"]):
                if itraj == 0:
                    kw = dict(label=prod_name)
                else:
                    kw = dict()
                axes[0].plot(
                    dsprod.lon_parcels.isel(trajectory_parcels=itraj),
                    dsprod.lat_parcels.isel(trajectory_parcels=itraj),
                    color="slateblue",
                    lw=4,
                    alpha=0.65,
                    **kw
                    )
            
            handles, labels = axes[0].get_legend_handles_labels()
            fig.legend(handles, labels, ncol=1, loc='center left',
                       edgecolor='gray', bbox_to_anchor=(0.11,0.94)) 
            
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
                f"{self.staged.output_dir('plot', ref_name=ref_name)}/" +
                f"map_drifter_trajectories_{prod_name}.png"
                )
            
            fig.suptitle(figtitle, fontsize="x-large", y=0.95)
            
            self.save_figure(fig, figname)
            dsprod.close()
            dsref.close()

        return None


    def maps_current_drifter(self):
        """Plot maps per product."""
        for prod, node_prod in self.dt.children.items():
            dsprod = node_prod["prod/data"].to_dataset()
            # "time_drifter" is a coordinate on the "npt" dim, not a
            # dimension itself -- select the first observation via "npt".
            dsprod = dsprod.isel(npt=[0])

            dsref = node_prod["ref/data"].to_dataset()

            prod_name = dsprod.attrs.get("data_name")
            ref_name = dsref.attrs.get("data_name")

            figtitle = (
                f"{self.plot_title} \n"
                f"{self.metazone}"
                )

            dlat = dsref.lat.max() - dsref.lat.min()
            dlon = dsref.lon.max() - dsref.lon.min()
            mid_lat = 0.5 * (dsref.lat.min() + dsref.lat.max())
            aspect_ratio = float(dlat / (dlon * np.cos(np.radians(mid_lat))))
            # Unlike a fixed regional domain, a drifter track is rarely as
            # wide as it is tall -- it's usually a long, mostly one-way
            # meander. Sizing the figure to the raw aspect ratio then
            # makes it absurdly thin or tall. Clamp it to a readable
            # range instead; cartopy's geographic axes keep true-to-scale
            # distances on their own (that's what the cos(mid_lat) factor
            # above is for), so the only visible effect is extra
            # whitespace padding the shorter side, not distortion.
            aspect_ratio = min(max(aspect_ratio, 0.4), 2.5)

            fig, axes = create_subplots(
                layout_type="one",
                figsize=(10, 10 * aspect_ratio),
                x_label=None, y_label=None,
                sharex=True, projection=ccrs.PlateCarree()
                )

            lonmin = dsref.lon.min() - 0.5 * dlon
            lonmax = dsref.lon.max() + 0.5 * dlon
            latmin = dsref.lat.min() - 0.5 * dlat
            latmax = dsref.lat.max() + 0.5 * dlat
            axes[0].set_xlim([lonmin, lonmax])
            axes[0].set_ylim([latmin, latmax])

            dsprod = dsprod.squeeze()
            dsref = dsref.squeeze()

            axes[0].quiver(
                dsref.lon,
                dsref.lat,
                dsref.u,
                dsref.v,
                color="k",
                label=ref_name
                )

            axes[0].quiver(
                dsprod.lon_drifter,
                dsprod.lat_drifter,
                dsprod.u_drifter,
                dsprod.v_drifter,
                color="slateblue",
                label=prod_name,
                alpha=0.65,
                )
            
            handles, labels = axes[0].get_legend_handles_labels()
            fig.legend(handles, labels, ncol=1, loc='center left',
                       edgecolor='gray', bbox_to_anchor=(0.11, 0.94)) 
            
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
                f"{self.staged.output_dir('plot', ref_name=ref_name)}/" +
                f"map_drifter_current_{prod_name}.png"
                )
            
            fig.suptitle(figtitle, fontsize="x-large", y=0.95)
            
            self.save_figure(fig, figname)
            dsprod.close()
            dsref.close()
            del axes
        return None

    def maps(self):
        """Plot maps per product."""
        for prod, node_prod in self.dt.children.items():
            ds_ref_data = node_prod["ref/data"].to_dataset()
            lon = ds_ref_data.lon
            lat = ds_ref_data.lat
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

                if any(s == 0 for s in dscomp_all.sizes.values()):
                    logger.info(
                        "maps: skipping %s — comp dataset is empty (sizes=%s)",
                        comp, dict(dscomp_all.sizes)
                    )
                    continue

                for var in dscomp_all.data_vars:
                    if var not in CMAP_VARS:
                        continue
                    dscomp = dscomp_all[[var]]
                    dsref = dsref_all[[var]]
                    dsprod = dsprod_all[[var]]
                    
                    attrs = dsref.attrs
                    xtitle, ncname = format_time_label(attrs, ds=dsref, allow_clim_month=True)
                    v_title, v_name = format_vertical_label(attrs)
                    if v_title:
                        xtitle += f"\n{v_title}"
                    ncname += v_name

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
                    if self.vminmax and var in self.vminmax:
                        vmin, vmax = self.vminmax[var]
                    elif comp == "diff":
                        vmean = np.mean([dsprod.mean(), dsref.mean()])
                        vstd = np.mean([dsprod.std(), dsref.std()])
                        vmin, vmax = vmean - 1.75 * vstd, vmean + 1.75 * vstd
                    else:
                        vmax = np.max([dsprod.max(), dsref.max()])
                        vmin = np.min([dsprod.min(), dsref.min()])
                    
                    lonmin = lon.min()
                    lonmax = lon.max()
                    latmin = lat.min()
                    latmax = lat.max()
                    dlat = latmax - latmin
                    dlon = lonmax - lonmin
                    if dlon > 0 and dlat > 0:
                        aspect_ratio = 3 / 2 * dlat / dlon
                    else:
                        pad = 1.0
                        lonmin = lon.min() - pad
                        lonmax = lon.max() + pad
                        latmin = lat.min() - pad
                        latmax = lat.max() + pad
                        aspect_ratio = 3 / 2
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
                        axes[iax].set_extent(
                            [lonmin, lonmax, latmin, latmax],
                            crs=ccrs.PlateCarree()
                            )
                    
                    figname = (
                        f"{self.staged.output_dir('plot', ref_name=ref_name)}/" +
                        f"map_{var}_{comp}_{prod_name}{ncname}.png"
                        )
                    
                    pos0 = axes[0].get_position()
                    pos2 = axes[2].get_position()
                    pos0.x0 = pos2.x0
                    axes[0].set_position(pos0)
                    
                    fig.suptitle(figtitle)
                    
                    self.save_figure(fig, figname)

            ds_ref_data.close()

        return None
    
    def save_figure(self, fig, filename):
        """Save figure."""
        filename = Path(filename)
        filename.parent.mkdir(parents=True, exist_ok=True)
        save_figure(fig, filename)
        self.saved_files.append(str(filename.resolve()))
        logger.info(f"{filename} saved")
        plt.close(fig)
        del fig

def _plot_task(nc, func_comp, metazone, output, vminmax=None):
    """Single plot task — must be module-level for spawn pickling."""
    plotcomp = PlotComp(nc, func_comp, metazone, vminmax=vminmax)
    plotcomp.call(output)
    plotcomp.clean()
    saved = plotcomp.saved_files
    del plotcomp
    return saved


def main_plot(ncins, metazones, func_comp, cfg_outputs=None, kw_dask=None):
    """Process plot tasks in parallel using a multiprocessing pool.

    Parameters
    ----------
    ncins : dict
        Mapping of output name to ``{metazone: [zarr_paths]}``.
    metazones : list of str
        Metazone names to plot (others in `ncins` are skipped).
    func_comp : str
        Comparison type identifier (e.g. ``"comp_sst"``).
    cfg_outputs : dict, optional
        Mapping of output name to its output configuration (may hold a
        ``vminmax`` entry), e.g. ``cfg["outputs"]`` from `COMP_INI`.
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
                    task_args.append((nc, func_comp, metazone, output, vminmax))

    if not task_args:
        return []

    # Use the same n_workers as the CLI dask config (e.g. --dask-nworkers 4).
    num_workers = kw_dask[0] if kw_dask else 4
    num_workers = min(num_workers, len(task_args))
    logger.info(f"Plotting {len(task_args)} tasks with {num_workers} workers")
    # Pre-warm cartopy's naturalearth cache in the main process so that
    # concurrent workers don't race to download the same shapefiles.
    import cartopy.feature as cfeature
    list(cfeature.LAND.geometries())

    # Use 'spawn' to create clean child processes: avoids both the
    # "fork() after OpenMP" crash and inherited memory bloat.
    ctx = multiprocessing.get_context("spawn")
    with ctx.Pool(num_workers) as pool:
        results = pool.starmap(_plot_task, task_args)
    png_paths = [p for task_result in results for p in (task_result or [])]
    logger.info(f"Generated {len(png_paths)} PNG file(s)")
    return png_paths
