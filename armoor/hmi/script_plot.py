# pylint: disable=no-member
"""
Functions to create the plots
"""
import os
from datetime import datetime

import xarray as xr
import xoa
from xoa import cfgm
import numpy as np

from matplotlib import colors
import matplotlib.pyplot as plt
import matplotlib as mpl

import cartopy.crs as ccrs
import cartopy.feature as cfeature

import cmocean

import logging
logger = logging.getLogger(__name__)

mpl.rcParams['figure.dpi'] = 300
mpl.use('agg')

xoa.register_accessors(decode_sigma=True)


def hmi_image(data: xr.Dataset,
              func: str,
              title: str,
              path2save: str,
              cbar_range: (float, float),
              stream_legend: int):
    """
    Create an image of the plot
    Parameters
    ----------
    data : data to plot
    func : function selected for the plot
    title: title of the plot
    path2save : path to save the plot
    cbar_range : color bar consistent through all the model time steps
    rarification : rarification factor

    Returns
    -------

    """
    rootdir = os.path.abspath(os.path.dirname(__file__))
    with open(os.path.join(rootdir, "hmi_plot.ini"), "r", encoding="utf-8") as hmi_plot_spec:
        cfgm_plots = cfgm.ConfigManager(hmi_plot_spec)
    with open(os.path.join(rootdir, '..', '..', 'config', 'hmi_plot.cfg'), "r", encoding="utf-8") as hmi_plot_config:
        cfgm_plots_dict = cfgm_plots.load(hmi_plot_config)

    legend = cfgm_plots_dict.get('legend').get(func)
    legend.update({"title": title})
    legend.update({"cbar_range": cbar_range})

    rarification, barbs_length, barbs_linewidth = stream_legend
    legend.update({"rarification": int(rarification) if rarification else 1})
    legend.update({"barbs_length": barbs_length})
    legend.update({"barbs_linewidth": barbs_linewidth})

    func_mapping = {
        "visu_temp": base_map,
        "visu_sal": base_map,
        "visu_diff_sst": base_map,
        "visu_diff_sss": base_map,
        "visu_solarflux": base_map,
        'visu_precip': base_map,
        'visu_mixedlayer_clim': base_map,
        "visu_mixedlayer": base_map,
        "visu_current": stream,
        "visu_windforcing": stream_wind,
        "visu_runoff": runoff
    }

    if func in func_mapping:
        func_mapping[func](data, legend, path2save)
    else:
        logger.error(f'{func} is not yet implemented for {title}')


def save_plot(path2save):
    """
    Function to save the plot in png format
    Parameters
    ----------
    path2save : path to save the plot

    Returns
    -------
    None
    """
    plt.savefig(f"{path2save}.png", bbox_inches='tight', format="png")
    logger.info(f'Saved in file :')
    logger.info(f'{path2save}.png')


def base_frame(title: str,
               var_name: str,
               var_unit: str,
               lon,
               lat,
               data: xr.Dataset,
               cmap,
               cbar_range):
    """
    Frame of the plot
    Parameters
    ----------
    title : title of the plot
    var_name : variable name
    var_unit : variable units
    lon : longitudes
    lat : latitudes
    data : data to plot
    cmap : color map for the plot
    cbar_range : color bar consistent through all the model time steps

    Returns
    -------
    axis
    """
    plt.close('all')
    fig = plt.figure(figsize=(9, 5.25))
    axes = plt.axes(projection=ccrs.Mercator())
    axes.set_facecolor('xkcd:light grey')

    if cbar_range:
        vmin, vmax = cbar_range
        norm = plt.Normalize(vmin=vmin, vmax=vmax)
    else:
        norm = colors.Normalize()

    im0 = axes.pcolormesh(lon,
                          lat,
                          data,
                          norm=norm,
                          cmap=cmap,
                          transform=ccrs.PlateCarree())

    # colobar
    caxes = fig.add_axes([axes.get_position().x1 + 0.01,
                          axes.get_position().y0, 0.02,
                          axes.get_position().height])
    cbar = plt.colorbar(im0, cax=caxes)
    cbar.set_label(f' {var_name} {var_unit}', rotation=270, labelpad=15)

    axes.set_title(f'{title}', fontsize=16, fontweight='bold')
    grid_l = axes.gridlines(crs=ccrs.PlateCarree(),
                            draw_labels=False,
                            linewidth=1,
                            color='gray',
                            alpha=0.2,
                            linestyle='--')
    grid_l.left_labels = True
    grid_l.bottom_labels = True
    axes.coastlines()
    axes.add_feature(cfeature.LAND, zorder=1, edgecolor='k', facecolor='w')
    return axes


def base_map(data: xr.Dataset, legend: dict, path2save: str):
    """
    Function called to plot simple 2D data on map, like temperature, salinity, mixed layer depth.
    Parameters
    ----------
    data : data to plot
    legend : all information needed to customise the plot
    path2save : path to save the plot

    Returns
    -------
    None
    """
    logger.info('2D data on map')
    _ = base_frame(legend["title"],
                   legend["var_name"],
                   legend["var_unit"],
                   data.xoa.lon,
                   data.xoa.lat,
                   data,
                   legend["cmap"],
                   legend["cbar_range"])

    save_plot(path2save)


def stream_wind(data: xr.Dataset,
                legend: dict,
                path2save: str):
    """
    Function called to plot wind
    Parameters
    ----------
    data : data to plot
    legend : all information needed to customise the plot
    path2save : path to save the plot
    rarification : rarification factor

    Returns
    -------
    None
    """
    logger.info('Wind plot')
    data = data.squeeze()
    norm = np.sqrt(data['u'] ** 2 + data['v'] ** 2)
    lon = data['lon']
    lat = data['lat']
    rarification = legend["rarification"]
    barbs_length = legend["barbs_length"]
    barbs_linewidth = legend["barbs_linewidth"]

    axes = base_frame(legend["title"],
                      legend["var_name"],
                      legend["var_unit"],
                      lon,
                      lat,
                      norm,
                      legend["cmap"],
                      legend["cbar_range"])

    # extra plot
    _ = axes.barbs(lon.values[::rarification],
                   lat.values[::rarification],
                   data['u'].values[::rarification, ::rarification],
                   data['v'].values[::rarification, ::rarification],
                   pivot='middle',
                   length=barbs_length,
                   linewidth=barbs_linewidth,
                   transform=ccrs.PlateCarree())

    save_plot(path2save)


def stream(data: xr.Dataset,
           legend: dict,
           path2save: str):
    """
    Function called to plot current
    Parameters
    ----------
    data : data to plot
    legend : all information needed to customise the plot
    path2save : path to save the plot
    rarification : rarification factor

    Returns
    -------

    """
    logger.info('Stream plot')
    data = data.squeeze()
    norm = np.sqrt(data['u'] ** 2 + data['v'] ** 2)
    lon = data['lon']
    lat = data['lat']
    rarification = legend["rarification"]

    axes = base_frame(legend["title"],
                      legend["var_name"],
                      legend["var_unit"],
                      lon,
                      lat,
                      norm,
                      legend["cmap"],
                      legend["cbar_range"])

    # extra plot
    _ = axes.quiver(lon.values[::rarification],
                    lat.values[::rarification],
                    data['u'].values[::rarification, ::rarification],
                    data['v'].values[::rarification, ::rarification],
                    transform=ccrs.PlateCarree())

    save_plot(path2save)


def runoff(data: xr.Dataset,
           legend: dict,
           path2save: str):
    """
    Function called to plot runoff from rivers

    Note: the cbar_range in legend is use to store the  model time step

    Parameters
    ----------
    data : data to plot
    legend : all information needed to customise the plot
    path2save : path to save the plot

    Returns
    -------
    None
    """
    logger.info('Runoff from rivers figure')

    plt.close('all')
    _, axes = plt.subplots(figsize=(9, 5.25))

    for dataset in data:
        plt.plot(dataset['TIME'], dataset['RVFL'], marker="o")
    model_time = datetime.strptime(legend["cbar_range"], '%Y-%m-%dT%H:%M')
    axes.axvline(model_time)
    axes.legend([dataset.attrs['platform_name'] for dataset in data])
    plt.gcf().autofmt_xdate()
    plt.grid(color='gray', linestyle='--', linewidth=1, zorder=1)
    axes.set_title(f'{legend["title"]}', fontsize=16)
    axes.set_ylabel(f' {legend["var_name"]} {legend["var_unit"]}', fontsize=14)
    axes.tick_params(axis='both', which='major', labelsize=14)

    save_plot(path2save)
