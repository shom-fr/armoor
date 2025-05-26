"""Plot functions."""
import numpy as np
import matplotlib.pyplot as plt
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

def create_subplots(nrows, ncols, figsize=(10, 8), x_label='X-axis', y_label='Y-axis', title='Subplots', sharex=False, sharey=False):
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
    fig, axes = plt.subplots(nrows=nrows, ncols=ncols, figsize=figsize, sharex=sharex, sharey=sharey)
    
    if ncols == 1:
        axes = axes.reshape(-1, 1) 

    # Set a common title for the entire figure
    fig.suptitle(title)
    # Set labels for each subplot, conditionally based on sharex and sharey
    if sharex:
        if ncols < 2:
            for ax in axes[-1]:
                ax.set_xlabel(x_label)
            for row in axes[:-1]:
                for ax in row:
                    ax.set_xlabel('')
        else:
            for ax in axes[-1, :]:
                ax.set_xlabel(x_label)
            for row in axes[:-1, :]:
                for ax in row:
                    ax.set_xlabel('')
    if sharey:
        # Set y label in the middle of the first column
        for ax in axes[:, 0]:
            ax.set_ylabel(y_label)
        # Remove y labels from other columns
        for col in axes[:, 1:]:
            for ax in col:
                ax.set_ylabel('')
    # Adjust layout to prevent overlap
    plt.tight_layout(rect=[0, 0, 1, 0.95])
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
    #plt.tight_layout()
    return ax
    
def shadow_line(x, y, ax, label=None, color='k'):
    """Plot a shadow line."""
    ax.plot(x, y - 0.2, color='gray', linewidth=3, alpha=0.3)
    ax.plot(x, y, label=label, color=color, linewidth=2)
    