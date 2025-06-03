"""Plot functions."""
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
from scipy.stats import linregress

plt.style.use('seaborn-v0_8-whitegrid')

def create_figure(width, height):
    """
    Creates and returns a Matplotlib Figure object with the specified dimensions.

    :param width: Width of the figure in inches.
    :param height: Height of the figure in inches.
    :return: Matplotlib Figure object.
    """
    fig = plt.figure(figsize=(width, height))
    return fig

def create_subplots(nrows=None, layout_type=None, figsize=(8, 10), x_label='X-axis', y_label='Y-axis', title='Subplots', sharex=False, sharey=False, projection=None):
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
    # Save the figure with the specified filename and DPI
    fig.savefig(filename, dpi=dpi, bbox_inches='tight')
    plt.close()
    
def diagdisp(x_data, y_data, ax, x_label, y_label):
    
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
    plt.legend(loc='upper left', fontsize=11, frameon=True, fancybox=True)
    ax.set_aspect('equal', adjustable='box')
    #plt.tight_layout()
    return ax
    
def shadow_line(x, y, ax, label=None, color='k'):
    """Plot a shadow line."""
    ax.plot(x, y - 0.2, color='gray', linewidth=3, alpha=0.3)
    ax.plot(x, y, label=label, color=color, linewidth=2)
