# pylint: disable=no-member
"""
Functions to create the plots
"""
from datetime import datetime

import xarray as xr
import xoa
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
              rarification: int):
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
    legend = {"visu_temp": {"title": title,
                            "var_name": "Temperature",
                            "var_unit": "(°C)",
                            "cmap": cmocean.cm.thermal,
                            "cbar_range": cbar_range
                            },
              "visu_sal": {"title": title,
                           "var_name": "Salinity",
                           "var_unit": "(g/kg)",
                           "cmap": cmocean.cm.haline,
                           "cbar_range": cbar_range
                           },
              "visu_current": {"title": title,
                               "var_name": "Current",
                               "var_unit": "(m/s)",
                               "cmap": cmocean.cm.speed,
                               "cbar_range": cbar_range
                               },
              "visu_windforcing": {"title": title,
                                   "var_name": "Wind 10m",
                                   "var_unit": "(m/s)",
                                   "cmap": cmocean.cm.matter,
                                   "cbar_range": cbar_range
                                   },
              "visu_diff_sss": {"title": title,
                                "var_name": "SSS difference (model - climatology)",
                                "var_unit": "(g/kg)",
                                "cmap": 'PiYG',
                                "cbar_range": cbar_range
                                },
              "visu_diff_sst": {"title": title,
                                "var_name": "SST difference (model - satellite)",
                                "var_unit": "(°C)",
                                "cmap": 'RdBu_r',
                                "cbar_range": cbar_range
                                },
              "visu_solarflux": {"title": title,
                                 "var_name": "Solar sensible heat flux",
                                 "var_unit": "(J/m²)",
                                 "cmap": 'cmo.solar',
                                 "cbar_range": cbar_range
                                 },
              "visu_precip": {"title": title,
                              "var_name": "Total precipitation",
                              "var_unit": "(mm)",
                              "cmap": cmocean.cm.rain,
                              "cbar_range": cbar_range
                              },
              "visu_mixedlayer_clim":
                  {"title": title,
                   "var_name": "Mixed layer thickness at standard depth levels",
                   "var_unit": "(m)",
                   "cmap": cmocean.cm.deep,
                   "cbar_range": cbar_range
                   },
              "visu_mixedlayer": {"title": title,
                                  "var_name": "Mixed layer thickness at 10 m",
                                  "var_unit": "(m)",
                                  "cmap": cmocean.cm.deep,
                                  "cbar_range": cbar_range
                                  },
              "visu_runoff": {"title": title,
                              "var_name": "River runoff",
                              "var_unit": "($m^3$/s)",
                              }
              }

    rarification = int(rarification) if rarification else 1

    if func in ["visu_temp", "visu_sal", "visu_diff_sst",
                "visu_diff_sss", "visu_solarflux", 'visu_precip',
                'visu_mixedlayer_clim', "visu_mixedlayer"]:
        base_map(data,
                 legend[func],
                 path2save)

    elif func in ["visu_current"]:
        stream(data,
               legend[func],
               path2save,
               rarification)

    elif func in ["visu_windforcing"]:
        stream_wind(data,
                    legend[func],
                    path2save,
                    rarification)

    elif func == "visu_runoff":
        runoff(data,
               legend[func],
               cbar_range,
               path2save)

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
                path2save: str,
                rarification: int):
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
                   length=3,
                   linewidth=0.5,
                   transform=ccrs.PlateCarree())

    save_plot(path2save)


def stream(data: xr.Dataset,
           legend: dict,
           path2save: str,
           rarification: int):
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
           model_time: str,
           path2save: str):
    """
    Function called to plot runoff from rivers
    Parameters
    ----------
    data : data to plot
    legend : all information needed to customise the plot
    model_time : model time step
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
    model_time = datetime.strptime(model_time, '%Y-%m-%dT%H:%M')
    axes.axvline(model_time)
    axes.legend([dataset.attrs['platform_name'] for dataset in data])
    plt.gcf().autofmt_xdate()
    plt.grid(color='gray', linestyle='--', linewidth=1, zorder=1)
    axes.set_title(f'{legend["title"]}', fontsize=16)
    axes.set_ylabel(f' {legend["var_name"]} {legend["var_unit"]}', fontsize=14)
    axes.tick_params(axis='both', which='major', labelsize=14)

    save_plot(path2save)
