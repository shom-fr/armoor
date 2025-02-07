# pylint: disable=no-member
"""
Functions to create the plots
"""
import logging
import os
from datetime import datetime

import cartopy.crs as ccrs
import cartopy.feature as cfeature
import cmocean
import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np
import xarray as xr
import pandas as pd
import xoa
from xoa.plot import plot_flow
from matplotlib import colors

logger = logging.getLogger(__name__)

mpl.rcParams["figure.dpi"] = 300
mpl.use("agg")

xoa.register_accessors(decode_sigma=True)

def hmi_image(
    data: xr.Dataset,
    func: str,
    title: str,
    path2save: str,
    cbar_range: (float, float),
    legend: dict,
    stream_legend,
):
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
    if legend is None:
        legend = {}
    legend.update({"title": title})
    legend.update({"cbar_range": cbar_range})

    (
        rarification,
        barbs_length,
        barbs_linewidth,
        quiver_scale,
        quiver_width,
        quiver_headwidth,
        quiver_headlength,
    ) = stream_legend
    legend.update({"rarification": int(rarification) if rarification else 1})
    legend.update({"barbs_length": barbs_length})
    legend.update({"barbs_linewidth": barbs_linewidth})

    legend.update({"quiver_scale": quiver_scale})
    legend.update({"quiver_width": quiver_width})
    legend.update({"quiver_headwidth": quiver_headwidth})
    legend.update({"quiver_headlength": quiver_headlength})

    func_mapping = {
        "visu_temp": base_map,
        "visu_sal": base_map,
        "visu_diff_sst": base_map,
        "visu_diff_sss": base_map,
        "visu_solarflux": base_map,
        "visu_precip": base_map,
        "visu_mixedlayer_clim": base_map,
        "visu_mixedlayer": base_map,
        "visu_current": stream,
        "visu_windforcing": stream_wind,
        "visu_runoff": runoff,
    }

    if func in func_mapping:
        func_mapping[func](data, legend, path2save)
    else:
        logger.error(f"{func} is not yet implemented for {title}")


def save_plot(fig, path2save):
    """
    Function to save the plot in png format
    Parameters
    ----------
    path2save : path to save the plot

    Returns
    -------
    None
    """
    fig.savefig(
        f"{path2save}.png",
        bbox_inches="tight",
        pad_inches=0.0,
        format=None,
        facecolor=None,
        edgecolor=None,
        transparent=False, 
        metadata=None,
        orientation='portrait'
    )
    logger.info("Saved in file :")
    logger.info(f"{path2save}.png")


def base_frame(
    title: str,
    var_name: str,
    var_unit: str,
    lon,
    lat,
    data: xr.Dataset,
    cmap,
    cbar_range,
):
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
    plt.close("all")
    plt.rcParams['lines.linewidth'] = 0.3
    fig = plt.figure(figsize=(9, 5.25))
    axes = plt.axes(projection=ccrs.Mercator())
    axes.set_facecolor("xkcd:light grey")

    if cbar_range:
        vmin, vmax = cbar_range
        norm = plt.Normalize(vmin=vmin, vmax=vmax)
    else:
        norm = colors.Normalize()

    im0 = axes.pcolormesh(
        lon, lat, data.squeeze(), norm=norm, cmap=cmap, transform=ccrs.PlateCarree()
    )

    # colobar
    caxes = fig.add_axes(
        [
            axes.get_position().x1 + 0.01,
            axes.get_position().y0,
            0.01,
            axes.get_position().height,
        ]
    )
    cbar = fig.colorbar(
        im0,
        cax=caxes,
        extend="max" if var_name in ("Wind speed @10m, ", "Speed, ") else "both"
    )
    cbar.set_label(
        f" {var_name} {var_unit}", rotation=270, labelpad=8, fontsize=8
    )
    cbar.ax.tick_params(labelsize=8)
    axes.set_title(f"{title}", fontsize=12)#, fontweight="bold")
    grid_l = axes.gridlines(
        crs=ccrs.PlateCarree(),
        draw_labels=False,
        linewidth=0.5,
        color="k",
        alpha=0.5,
        linestyle="--",
    )
    grid_l.left_labels = True
    grid_l.bottom_labels = True
    grid_l.xlabel_style = {'size': 8}
    grid_l.ylabel_style = {'size': 8}
    axes.coastlines()
    axes.add_feature(cfeature.LAND, zorder=1, edgecolor="k", facecolor="w")
    axes.text(0.0, 1.02,
            pd.to_datetime(data.time.values).strftime("%Y-%m-%d, %H:%M"), 
            fontsize=10, transform=axes.transAxes)
    
    mindata = data.min().values.round(decimals=2)
    maxdata = data.max().values.round(decimals=2)
    if "clim_min" in data.attrs:
        taxes = fig.add_axes(
            [
                axes.get_position().x1 - 0.15,
                axes.get_position().y0 + axes.get_position().height,
                0.15,
                0.05,
            ]
        )
        celltext = [
            [data.attrs["clim_min"], data.attrs["clim_max"]],
            [mindata, maxdata]
        ]
        rowlabels=["clim", "data"]
    else:
        taxes = fig.add_axes(
            [
                axes.get_position().x1 - 0.15,
                axes.get_position().y0 + axes.get_position().height,
                0.15,
                0.1,
            ]
        )
        celltext = [[mindata, maxdata]]
        rowlabels=["data"]
    table = taxes.table(
        cellText=celltext,
        rowLabels=rowlabels,
        colLabels=["min", "max"],
        cellLoc='center',
        rowLoc='center',
        loc="lower right"
    )
    taxes.set_axis_off()
    table.set_fontsize(10)
    for key, cell in table.get_celld().items():
        cell.set(
            alpha=0.75,
            width=0.3,
            height=0.5,
            linewidth=1.0,
            edgecolor="white",
            joinstyle="bevel",
            facecolor="aqua"
        )
       # cell.set_facecolor("aqua")


    return fig, axes


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
    logger.info("2D data on map")
    fig, axes = base_frame(
        legend["title"],
        legend["var_name"],
        legend["var_unit"],
        data.lon,
        data.lat,
        data,
        legend["cmap"],
        legend["cbar_range"],
    )

    save_plot(fig, path2save)


def stream_wind(data: xr.Dataset, legend: dict, path2save: str):
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
    logger.info("Wind plot")
    data = data.squeeze()
    norm = np.sqrt(data["u"] ** 2 + data["v"] ** 2)
    lon = data["lon"]
    lat = data["lat"]
    rarification = legend["rarification"]
    barbs_length = legend["barbs_length"]
    barbs_linewidth = legend["barbs_linewidth"]

    fig, axes = base_frame(
        legend["title"],
        legend["var_name"],
        legend["var_unit"],
        lon,
        lat,
        norm,
        legend["cmap"],
        legend["cbar_range"],
    )

    # extra plot
    _ = axes.barbs(
        lon.values[::rarification],
        lat.values[::rarification],
        data["u"].values[::rarification, ::rarification],
        data["v"].values[::rarification, ::rarification],
        pivot="middle",
        length=barbs_length,
        linewidth=barbs_linewidth,
        color="lightgray",
        transform=ccrs.PlateCarree(),
    )

    save_plot(fig, path2save)


def stream(data: xr.Dataset, legend: dict, path2save: str):
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
    logger.info("Stream plot")
    data = data.squeeze()
    norm = np.sqrt(data["u"] ** 2 + data["v"] ** 2)
    lon = data["lon"]
    lat = data["lat"]
    rarification = legend["rarification"]
    # quiver_scale = legend["quiver_scale"]
    # quiver_width = legend["quiver_width"]
    # quiver_headwidth = legend["quiver_headwidth"]
    # quiver_headlength = legend["quiver_headlength"]

    fig, axes = base_frame(
        legend["title"],
        legend["var_name"],
        legend["var_unit"],
        lon,
        lat,
        norm,
        legend["cmap"],
        legend["cbar_range"],
    )

    # extra plot
    _ = axes.quiver(
        lon.values[::rarification, ::rarification],
        lat.values[::rarification, ::rarification],
        data["u"].values[::rarification, ::rarification],
        data["v"].values[::rarification, ::rarification],
        pivot="mid",
        scale=20,
        
        #scale=quiver_scale,
        # width=quiver_width,
        # headwidth=quiver_headwidth,
        # headlength=quiver_headlength,
        transform=ccrs.PlateCarree(),
        regrid_shape=35,
        color="lightgray"
    )

    # data = data.fillna(0.)
    # h = plot_flow(
    #     data["u"],
    #     data["v"],
    #     axes=axes,
    #     alpha=(0.2, 1),
    #     color='k',
    #     transform=ccrs.PlateCarree()
    # )
    save_plot(fig, path2save)


def runoff(data: xr.Dataset, legend: dict, path2save: str):
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
    logger.info("Runoff from rivers figure")

    plt.close("all")
    _, axes = plt.subplots(figsize=(9, 5.25))

    for dataset in data:
        plt.plot(dataset["TIME"], dataset["RVFL"], marker="o")
    model_time = datetime.strptime(legend["cbar_range"], "%Y-%m-%dT%H:%M")
    axes.axvline(model_time)
    axes.legend([dataset.attrs["platform_name"] for dataset in data])
    plt.gcf().autofmt_xdate()
    plt.grid(color="gray", linestyle="--", linewidth=1, zorder=1)
    axes.set_title(f'{legend["title"]}', fontsize=16)
    axes.set_ylabel(f' {legend["var_name"]} {legend["var_unit"]}', fontsize=14)
    axes.tick_params(axis="both", which="major", labelsize=14)

    save_plot(path2save)
