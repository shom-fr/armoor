"""Plot functions."""
# matplotlib, scipy and gridspec are imported lazily (inside each function)
# to avoid the several-second NFS penalty on HPC clusters where hundreds of
# .py/.so files are stat'd during a standard matplotlib/__init__.py traversal.
import re

import numpy as np
import pandas as pd


def get_output_vminmax(cfg_outputs, output):
    """Extract the configured vminmax mapping for one output, if any.

    Shared by `armoor.data.plot.main_plot` and `armoor.comp.plot.main_plot`,
    both of which call this once per output name while flattening their
    ``{otype: {metazone: [paths]}}`` input into per-file plot tasks.

    `cfg_outputs` is keyed by the user-chosen config *section* name (e.g.
    ``"global_dispersion"``), not by `output` -- `output` is an *otype*
    string (e.g. ``"diagdisp_glob"``), a field *inside* each section, and
    the two only coincide when a user happens to name a section after its
    otype. So this scans section values for the one whose ``otype``
    matches, rather than indexing `cfg_outputs` directly with `output`.

    Parameters
    ----------
    cfg_outputs : dict or None
        Mapping of config section name to its output configuration (may
        hold ``otype``/``vminmax`` entries), e.g. ``cfg["outputs"]`` from
        `DATA_INI`/`COMP_INI`. ``None`` when no config is available (e.g.
        HPC --plot-only calls that predate this option).
    output : str
        Otype to look up (e.g. ``"maps"``, ``"diagdisp_glob"``).

    Returns
    -------
    dict or None
        Mapping of variable name to a ``(vmin, vmax)`` pair, or ``None``.
    """
    if not cfg_outputs:
        return None
    for section in cfg_outputs.values():
        if hasattr(section, "get") and section.get("otype") == output:
            return section.get("vminmax")
    return None


def format_trange(trange):
    """Format a bracketed ``trange`` attr (e.g. ``"[t1_t2["``) for display/filenames.

    Parameters
    ----------
    trange : str
        A ``"[<start>_<end>["`` bracketed range, as set by
        `armoor.base.ranges.trange_seq`.

    Returns
    -------
    tuple of str
        ``(title_str, filename_safe_str)`` -- e.g.
        ``("[2020-01-01T00:00-2020-01-31T00:00[", "2020-01-01T00_00_2020-01-31T00_00")``.
    """
    t1, t2 = [pd.to_datetime(t).strftime('%Y-%m-%dT%H:%M') for t in trange.strip('[').split('_')]
    title_str = f"[{t1}-{t2}["
    suffix_str = re.sub('-', '_', re.sub(r'[\[\]]', '', title_str))
    return title_str, suffix_str


def format_time_label(attrs, ds=None, allow_clim_month=False):
    """Build the temporal part of a figure title/filename from range attrs.

    Shared by `armoor.data.plot` and `armoor.comp.plot`, which independently
    tag output datasets with the same attrs set by `armoor.base.ranges`:
    ``trange`` (a date range, from `trange_seq`) takes priority over
    ``time`` (a single per-day timestamp, from `tfreq`) -- both must be
    checked, since a `tfreq`-configured metazone (e.g. a native daily
    split) never sets `trange`, and skipping it means every native
    timestep's figure silently shares one filename.

    Parameters
    ----------
    attrs : dict
        A dataset's ``.attrs``.
    ds : xarray.Dataset, optional
        Consulted for a single "time" value as a last resort, when neither
        `trange` nor `time` is set but `ds` still has exactly one time
        step (e.g. a single-date comparison with no range/tfreq config).
    allow_clim_month : bool
        Whether to fall back to a ``clim_month`` attr (set for climatology
        references, e.g. WOA18, when comparing against a multi-time
        product with no overlapping time step -- see
        `armoor.comp.stats.StatsComp.get_diff`).

    Returns
    -------
    tuple of str
        ``(xtitle_part, ncname_part)`` -- empty strings when nothing
        applies; `ncname_part` already includes its leading ``"_"``.
    """
    trange = attrs.get("trange")
    tfreq = attrs.get("time")
    if trange:
        title_str, suffix_str = format_trange(trange)
        return title_str, f"_{suffix_str}"
    if tfreq:
        return tfreq, f"_{tfreq}"
    if ds is not None and ds.sizes.get("time") == 1:
        time_str = f"{pd.to_datetime(ds.time.values[0]):%Y-%m-%dT%H:%M:%S}"
        return time_str, f"_{time_str}"
    if allow_clim_month and "clim_month" in attrs:
        import calendar
        return calendar.month_name[attrs["clim_month"]], f"_m{attrs['clim_month']:02d}"
    return "", ""


def format_vertical_label(attrs, allow_vrange=True):
    """Build the vertical part of a figure title/filename from range attrs.

    Shared by `armoor.data.plot` and `armoor.comp.plot`: ``vlevel`` (a
    single depth, from `armoor.base.ranges.vlevels`) takes priority over
    ``vrange`` (a depth bin, from `armoor.base.ranges.vrange`).

    Parameters
    ----------
    attrs : dict
        A dataset's ``.attrs``.
    allow_vrange : bool
        Whether to fall back to a ``vrange`` attr when there's no
        ``vlevel``. Some otypes (e.g. a single-point vertical profile
        selection) only ever carry ``vlevel`` and don't need the fallback.

    Returns
    -------
    tuple of str
        ``(xtitle_part, ncname_part)`` -- empty strings when neither attr
        is set; `ncname_part` already includes its leading ``"_"``.
    """
    vlevel = attrs.get("vlevel")
    if vlevel is not None:
        if isinstance(vlevel, list):
            vlevel = vlevel[0]
        return f" \n depth={vlevel}m", f"_{vlevel}"
    if allow_vrange:
        vrange = attrs.get("vrange")
        if vrange is not None:
            if isinstance(vrange, list):
                vrange = vrange[0]
            return f"\n depth=[{vrange}]m", f"_{vrange}"
    return "", ""


def _get_plt():
    """Return matplotlib.pyplot, applying the armoor style on first import."""
    import matplotlib.pyplot as _plt
    _plt.style.use('seaborn-v0_8-whitegrid')
    return _plt


def create_figure(width, height):
    """
    Creates and returns a Matplotlib Figure object with the specified dimensions.

    Parameters
    ----------
    width : float
        Width of the figure in inches.
    height : float
        Height of the figure in inches.

    Returns
    -------
    matplotlib.figure.Figure
        Matplotlib Figure object.
    """
    plt = _get_plt()
    fig = plt.figure(figsize=(width, height))
    return fig

def create_subplots(nrows=None, ncols=None, layout_type=None, figsize=(8, 10), x_label='X-axis', y_label='Y-axis', title='Subplots', sharex=False, sharey=False, projection=None):  # noqa: E501
    """Create and return a figure with a specified number of subplots arranged in a grid.

    Parameters
    ----------
    nrows: int
        Number of rows in the subplot grid.
    ncols: int
        Number of columns in the subplot grid.
    figsize: tuple, optional
        Figure size (width, height) in inches. Default is (10, 8).
    x_label: str, optional
        Label for the x-axis. Default is 'X-axis'.
    y_label: str, optional
        Label for the y-axis. Default is 'Y-axis'.
    title: str, optional
        Title of the plot. Default is 'Subplots'.
    sharex: bool, optional
        Whether to share the x-axis across subplots. Default is False.
    sharey: bool, optional
        Whether to share the y-axis across subplots. Default is False.

    Returns
    -------
    tuple
        A tuple containing the Figure object and an array of Axes objects.
    """
    # Create a figure and a set of subplots
    # fig, axes = plt.subplots(
    #     nrows=nrows,
    #     ncols=ncols,
    #     figsize=figsize,
    #     sharex=sharex,
    #     sharey=sharey,
    #     subplot_kw=subplot_kw)
    
    # if ncols == 1 and nrows > 1:
    #     axes = axes.reshape(-1, 1) 

    # # Set a common title for the entire figure
    # fig.suptitle(title)
    # # Set labels for each subplot, conditionally based on sharex and sharey
    # if sharex:
    #     if ncols < 2:
    #         for ax in axes[-1]:
    #             ax.set_xlabel(x_label)
    #         for row in axes[:-1]:
    #             for ax in row:
    #                 ax.set_xlabel('')
    #     else:
    #         for ax in axes[-1, :]:
    #             ax.set_xlabel(x_label)
    #         for row in axes[:-1, :]:
    #             for ax in row:
    #                 ax.set_xlabel('')
    # if sharey:
    #     # Set y label in the middle of the first column
    #     for ax in axes[:, 0]:
    #         ax.set_ylabel(y_label)
    #     # Remove y labels from other columns
    #     for col in axes[:, 1:]:
    #         for ax in col:
    #             ax.set_ylabel('')
    
    # Create a figure
    # projection=ccrs.PlateCarree()
    import matplotlib.gridspec as gridspec
    plt = _get_plt()
    subplot_kw = {}
    if projection is not None:
        subplot_kw['projection'] = projection

    fig = plt.figure(figsize=figsize)
    axes = []   
 
    if layout_type == 'top_two_bottom_one':
        # Layout: Two subplots on top, one subplot below
        gs = gridspec.GridSpec(3, 2, figure=fig,
                               height_ratios=[1, 1, 2],
                               width_ratios=[1, 1])

        ax1 = fig.add_subplot(gs[0, 0], **subplot_kw)
        ax2 = fig.add_subplot(gs[0, 1], **subplot_kw)
        ax3 = fig.add_subplot(gs[1:, :], **subplot_kw)

        axes = [ax1, ax2, ax3]

    elif layout_type == 'one':
        gs = gridspec.GridSpec(1, 1, figure=fig,
                               height_ratios=[1],
                               width_ratios=[1])
        ax1 = fig.add_subplot(gs[0, 0], **subplot_kw)
        axes = [ax1]

    elif layout_type == 'two_by_two':
        # Layout: Two rows of two subplots each
        gs = gridspec.GridSpec(2, 2, figure=fig)
        ax1 = fig.add_subplot(gs[0, 0], **subplot_kw)
        ax2 = fig.add_subplot(gs[0, 1], **subplot_kw)
        ax3 = fig.add_subplot(gs[1, 0], **subplot_kw)
        ax4 = fig.add_subplot(gs[1, 1], **subplot_kw)
        axes = [ax1, ax2, ax3, ax4]
 
    elif layout_type == 'left_large_right_stacked':
        # Layout: One large subplot on the left, stacked subplots on the right
        gs = gridspec.GridSpec(2, 2, figure=fig, width_ratios=[2, 1])
        ax1 = fig.add_subplot(gs[:, 0], **subplot_kw)
        ax2 = fig.add_subplot(gs[0, 1], **subplot_kw)
        ax3 = fig.add_subplot(gs[1, 1], **subplot_kw)
        axes = [ax1, ax2, ax3]
 
    elif layout_type == 'left_stacked_right_large':
        # Layout: Stacked subplots on the left, one large subplot on the right
        gs = gridspec.GridSpec(2, 2, figure=fig, width_ratios=[1, 2])
        ax1 = fig.add_subplot(gs[0, 0], **subplot_kw)
        ax2 = fig.add_subplot(gs[1, 0], **subplot_kw)
        ax3 = fig.add_subplot(gs[:, 1], **subplot_kw)
        axes = [ax1, ax2, ax3]
 
    elif nrows:
        gs = gridspec.GridSpec(nrows, 1, figure=fig)
        for irow in range(nrows):
            ax = fig.add_subplot(gs[irow, 0], **subplot_kw)
            if irow == nrows - 1:
                ax.set_xlabel(x_label)
            axes.append(ax)
        if sharex:
            for irow in range(nrows):
                if irow < nrows - 1:
                    axes[irow].set_xticklabels([])
                    axes[irow].sharex(axes[0])
                    
    elif ncols:
        gs = gridspec.GridSpec(1, ncols, figure=fig)
        for icol in range(ncols):
            ax = fig.add_subplot(gs[0, icol], **subplot_kw)
            if icol == ncols - 1:
                ax.set_ylabel(y_label)
            axes.append(ax)
        if sharey:
            for icol in range(ncols):
                if icol < ncols - 1:
                    axes[icol].set_yticklabels([])
                    axes[icol].sharey(axes[0])
                    
    else:
        raise ValueError("Invalid layout_type or None nrows. Please choose a valid layout type or nrows.")

    return fig, axes



def save_figure(fig, filename, dpi=300):
    """Save a Matplotlib figure as a PNG file with high resolution.

    Parameters
    ----------
    fig: matplotlib.figure.Figure
        The Matplotlib Figure object to save.
    filename: str
        The name of the file to save the figure to, including the .png extension.
    dpi: int, optional
        The resolution in dots per inch. Default is 300.
    """
    plt = _get_plt()
    # Save the figure with the specified filename and DPI
    fig.savefig(filename, dpi=dpi, bbox_inches='tight')
    plt.close(fig)
    
def diagdisp(x_data, y_data, ax, x_label, y_label):
    from scipy.stats import linregress
    plt = _get_plt()

    x = x_data.values.ravel()
    y = y_data.values.ravel()

    mask = ~np.isnan(x) & ~np.isnan(y)
    x = x[mask]
    y = y[mask]

    if (x.size == 0) or (y.size == 0):
        return None
    global_min = min(x.min(), y.min())
    global_max = max(x.max(), y.max())
    ax.set_xlim(global_min, global_max)
    ax.set_ylim(global_min, global_max)

    res = linregress(x, y)
    x_fit = np.linspace(global_min,global_max, 100)
    y_fit = res.slope * x_fit + res.intercept

    ax.scatter(x, y, color='#1f77b4', edgecolor='k', alpha=0.6, label='Colocated data', s=50)
    ax.plot([global_min, global_max], [global_min, global_max], linestyle='--', color='gray', linewidth=2, label='x = y')
    ax.plot(x_fit, y_fit, color='#2ca02c', linewidth=3, label=f'y = {res.slope:.2f}x + {res.intercept:.2f}')

    stats_text = f'$R^2$ = {res.rvalue**2:.2f}'#'\nσ = {res.stderr:.4f}'
    ax.text(0.98, 0.05, stats_text, transform=plt.gca().transAxes,
             verticalalignment='bottom', horizontalalignment='right',
             fontsize=12, bbox=dict(boxstyle='round', facecolor='white', alpha=0.9))
    ax.set_xlabel(x_label)
    ax.set_ylabel(y_label)
    ax.legend(loc='upper left', fontsize=11, frameon=True, fancybox=True)
    ax.set_aspect('equal', adjustable='box')
    #plt.tight_layout()
    return ax
    
def shadow_line(x, y, ax, label=None, color='k'):
    """Plot a shadow line."""
    ax.plot(x, y - 0.2, color='gray', linewidth=3, alpha=0.3)
    ax.plot(x, y, label=label, color=color, linewidth=2)
