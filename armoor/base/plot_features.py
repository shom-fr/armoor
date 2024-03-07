"""Plot figures and outpout for all features"""
import os
import math
import logging
import numpy as np
import xarray as xr
import gsw
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from scipy import stats
import cartopy.crs as ccrs
import cartopy.feature as cfeature
import cmocean
from armoor.algo import calculation
from xoa.geo import haversine
from armoor.base.tools_features import manage_output, angle_between_vectors

logger = logging.getLogger(__name__)

LABELS_TS = ['Obs Co-located / Model Co-located : Mean ',
             'Mean(Model Colocated - Obs Co-located) : Bias',
             'Obs Co-located / Model Co-located : Standard Deviation ',
             'Obs Co-located / Model Co-located : RMSE',
             'Obs Co-located / Model Co-located : Centered RMSE',
             'Obs Co-located / Model Co-located : Values',
             'Obs Co-located / Model Co-located : Difference']

LABELS_DIFF = ['Obs Co-located ', 'Model Co-located', 'Difference']

LABELS_PROFILE = ['Observation profile / Model profiles']
LABELS_STICKPLOT = ['Current stick plot - models / observation']
LABELS_MAP = ['Observation - Meta-zone', 'Observation - Co-located', 'Model - Meta-zone',
              'Model - Co-located', 'Comparison Model / Obs']

LABELS_MAP_HARM = ['Model - Amplitude [m/s]', 'Model - Phase [°]', 'Observation - Amplitude [m/s]',
                   'Observation - Phase [°]', 'Difference - Amplitude [m/s]',
                   'Difference - Phase [°]']

COLORS = ["tab:blue", "tab:green", "tab:orange", "tab:red", "tab:purple"]
xr.set_options(keep_attrs=True)


def get_title_figname(figtitle, obs, mod_name, obs_name):
    """
    Provides generic figure title and file name.
    Parameters
    ----------
    figtitle : str
        title of the figure
    obs : xr.dataset
        dataset from which to retrieve the lon/lat/time/depth information
    mod_name : str
        model name
    obs_name : str
        observation name

    Returns
    -------
    title : str
        figure title to display
    figname : str
        name of the figure to save

    """
    # Adapt figtitle
    if "RMSEc" in figtitle:
        figtitle = figtitle.replace("RMSEc", 'centered RMSE')

    # Variable
    if 'Theta-S' in figtitle:
        title_type = f"{figtitle}"
        var_name = ''
    elif "tidal wave" in figtitle or "Tidal" in figtitle:
        title_type = f"{figtitle}"
        var_name = ''
    elif "Stick plot" in figtitle:
        title_type = f"{figtitle}"
        var_name, var_unit = find_var_title(obs)
    elif "rajector" in figtitle:  # for trajectories
        title_type = f"{figtitle}"
        var_name = ''
    else:
        var_name, var_unit = find_var_title(obs)
        title_type = f"{figtitle} : {var_name} [{var_unit}]"

    # Location
    if 'lon' in obs.coords and np.size(obs.lon.data) == 1:
        if obs.lon.data.shape == (1,):
            title_loc = f'Longitude : {obs.lon.data[0]:.2f}° - Latitude : {obs.lat.data[0]:.2f}°\n'
            loc = f"{obs.lon.data[0]:.2f}_{obs.lat.data[0]:.2f}"
        elif obs.lon.data.shape == (1, 1):
            title_loc = f'Longitude : {obs.lon.data[0][0]:.2f}° - Latitude : {obs.lat.data[0][0]:.2f}°\n'
            loc = f"{obs.lon.data[0][0]:.2f}_{obs.lat.data[0][0]:.2f}"
        else:
            title_loc = f'Longitude : {obs.lon.data:.2f}° - Latitude : {obs.lat.data:.2f}°\n'
            loc = f"{obs.lon.data:.2f}_{obs.lat.data:.2f}"

    else:
        title_loc = ''
        loc = ''
    # Seuil bathy
    if "bathy_thresh" in obs.attrs:
        loc += f"_bathythresh_{obs.attrs['bathy_thresh']}"

    # Radius
    if "radius" in obs.attrs:
        title_loc += f" Radius : {obs.attrs['radius'][:-2]} km\n"
        loc += f"_radius_{obs.attrs['radius'][:-2]}"

    # Time
    if 'interval' in obs.coords:
        title_time = f"{obs.interval.data[0].split(' to ')[0]} to {obs.interval.data[-1].split(' to ')[1]} - Interval {obs['interval_duration'].data}\n"
        time = f"intervals_{obs.interval.data[0].split(' to ')[0]}_to_{obs.interval.data[-1].split(' to ')[1]}"
        # if 'interval_duration' in obs.coords:
        #     title_time = title_time[:-2] + f" - Interval {obs['interval_duration'].data}\n"

    elif 'analysis_period' in obs.attrs:
        title_time = f"Obs analysis period : {obs.analysis_period.replace(':00', '')} with {obs.attrs['tide_tool']}\n"
        time = f"analysis_{obs.attrs['tide_tool']}_{obs.analysis_period.replace(':00', '')}"
    else:
        if 'time' in obs.coords and np.size(obs.time.data) == 1:
            if 'U' in str(obs.time.data.dtype):  # Check if times are months names
                title_time = f"Date : {obs.time.data}\n"
                time = obs.time.data
            else:
                title_time = f"Date : {np.datetime_as_string(obs.time.values, unit='s')}\n"
                time = np.datetime_as_string(obs.time.values, unit='s')
        elif 'time' in obs.coords and np.size(obs.time.data) > 1:
            if isinstance(obs.time.data[0], str):
                title_time = f"Date : {obs.time.data[0]} to {obs.time.data[-1]}\n"
                time = f"{obs.time.data[0]}_to_{obs.time.data[-1]}"
            else:
                time_min = np.datetime_as_string(obs.time.min(skipna=True).values, unit='s')
                time_max = np.datetime_as_string(obs.time.max(skipna=True).values, unit='s')
                title_time = f'Dates : {time_min} to {time_max}\n'
                time = f"{time_min}_to_{time_max}"

    # Depth
    if 'profile' in figtitle or 'Theta-S' in figtitle:
        if 'pdens' in obs.coords and np.size(obs.pdens) > 1:
            title_depth = f"P. Density: {obs.pdens.min().values:.1f} to {obs.pdens.max().values:.1f} kg/m3"
            depth = f"{obs.pdens.min().values:.1f}_to_{obs.pdens.max().values:.1f}"
        else:
            title_depth = f"Depth: {obs.attrs['depth_meta_zone'].split('_to_')[0]} m to {obs.attrs['depth_meta_zone'].split('_to_')[1]} m"
            depth = f"{obs.attrs['depth_meta_zone']}m"

    elif 'slice' in obs.dims:
        title_depth = f"Slice: {obs.slice.data[0].split(' to ')[0]} to {obs.slice.data[0].split(' to ')[1]} m"
        depth = f"{obs.slice.data}m"
    elif 'pdens' in obs.coords and np.size(obs.pdens) == 1:
        title_depth = f"P. Density: {obs.pdens.values:.1f} kg/m3"
        depth = f"{obs.pdens.values:.1f}"
    elif 'depth' in obs.coords and np.size(obs.depth) > 1:
        # title_depth = f"Depth: {obs.depth.min().values:.1f} m to {obs.depth.max().values:.1f} m"
        title_depth = f"Depth: {obs.attrs['depth_meta_zone'].split('_to_')[0]} m to {obs.attrs['depth_meta_zone'].split('_to_')[1]} m"
        # depth = f"{obs.depth.min().values:.1f}m_to_{obs.depth.max().values:.1f} m"
        depth = f"{obs.attrs['depth_meta_zone']}m"
    elif 'pdens' in obs.coords and np.size(obs.pdens) > 1:
        title_depth = f"P. Density: {obs.pdens.min().values:.1f} to {obs.pdens.max().values:.1f} kg/m3"
        depth = f"{obs.pdens.min().values:.1f}_to_{obs.pdens.max().values:.1f}"
    elif 'depth' in obs.coords and np.size(obs.depth) == 1:
        if obs.depth.data.shape == (1,):
            title_depth = f"Depth: {obs.depth.values[0]:.1f} m"
            depth = f"{obs.depth.values[0]:.1f}m"
        else:
            title_depth = f"Depth: {obs.depth.values:.1f} m"
            depth = f"{obs.depth.values:.1f}m"
    else:
        title_depth = "Depth : 0 m"
        depth = '0m'

    # Results
    title = f"{title_type}\n" \
            f"Model(s) : {mod_name} \nObservation : {obs_name}\n" \
            f"{title_time}" \
            f"{title_loc} {title_depth}" #\n{title_rad}"

    figname = f"{figtitle}_{var_name}_{mod_name}_{obs_name}_{time}_{loc}_{depth}"

    title = title.replace("\'", '')
    figname = figname.replace("\'", '')
    figname = figname.replace("__", '_')
    figname = figname.replace("__", '_')
    figname = figname.replace(",", '')

    return title, figname


def figure_5_maps(ds):
    """
    Column of 3 map subplots for model, observation and their comparison.

    Returns
    -------
    f : figure
    axs : list
        5 axes for observation, model and comparison maps over observation extent.
    """

    f = plt.figure(figsize=(10, 17))
    ax0 = plt.subplot2grid((4, 2), (0, 0), projection=ccrs.Mercator(), aspect='equal')
    ax1 = plt.subplot2grid((4, 2), (0, 1), projection=ccrs.Mercator(), aspect='equal')
    ax2 = plt.subplot2grid((4, 2), (1, 0), projection=ccrs.Mercator(), aspect='equal')
    ax3 = plt.subplot2grid((4, 2), (1, 1), projection=ccrs.Mercator(), aspect='equal')
    ax4 = plt.subplot2grid((4, 2), (2, 0), colspan=2, rowspan=2, projection=ccrs.Mercator(),
                           aspect='equal')

    axs = [ax0, ax1, ax2, ax3, ax4]

    labels = LABELS_MAP[:5]

    for ax, label in zip(axs, labels):
        ax.set_extent(get_extent(ds))
        gl = ax.gridlines(draw_labels=True)
        gl.right_labels = False
        gl.top_labels = False
        gl.xlabel_style = {'size': 12}
        gl.ylabel_style = {'size': 12}
        ax.add_feature(cfeature.LAND, zorder=1, edgecolor='k')
        ax.set_title(label, fontsize=13)
    f.subplots_adjust(left=0.02, bottom=0.02, right=0.99, top=0.87, hspace=0.25)

    return f, axs


def figure_6_maps(ds):
    """
    Column of 6 map subplots for model, observation and their comparison, amplitude and phase.

    Returns
    -------
    f : figure
    axs : list
        6 axes for observation, model and comparison maps over observation extent.
    """

    f = plt.figure(figsize=(10, 15))
    ax0 = plt.subplot2grid((3, 2), (0, 0), projection=ccrs.Mercator())
    ax1 = plt.subplot2grid((3, 2), (0, 1), projection=ccrs.Mercator())
    ax2 = plt.subplot2grid((3, 2), (1, 0), projection=ccrs.Mercator())
    ax3 = plt.subplot2grid((3, 2), (1, 1), projection=ccrs.Mercator())
    ax4 = plt.subplot2grid((3, 2), (2, 0), projection=ccrs.Mercator())
    ax5 = plt.subplot2grid((3, 2), (2, 1), projection=ccrs.Mercator())

    axs = [ax0, ax1, ax2, ax3, ax4, ax5]

    labels = LABELS_MAP_HARM[:]

    for ax, label in zip(axs, labels):
        ax.set_extent(get_extent(ds))
        gl = ax.gridlines(draw_labels=True)
        gl.right_labels = False
        gl.top_labels = False
        gl.xlabel_style = {'size': 12}
        gl.ylabel_style = {'size': 12}
        ax.add_feature(cfeature.LAND, zorder=1, edgecolor='k')
        ax.set_title(label, fontsize=13)
    f.subplots_adjust(left=0.03, bottom=0.03, right=0.98, top=0.9, hspace=0.2)
    return f, axs


def figure_1_map(ds):
    """
    1 map

    Returns
    -------
    f : figure
    ax : ax
        ax for the map
    """

    f = plt.figure(figsize=(10, 10))
    ax = plt.subplot2grid((1, 1), (0, 0), projection=ccrs.Mercator())

    ax.set_extent(get_extent(ds))
    gl = ax.gridlines(draw_labels=True)
    gl.right_labels = False
    gl.top_labels = False
    gl.xlabel_style = {'size': 12}
    gl.ylabel_style = {'size': 12}
    ax.add_feature(cfeature.LAND, zorder=1, edgecolor='k')
    f.subplots_adjust(left=0.04, bottom=0.03, right=0.98, top=0.85, hspace=0.2)
    return f, ax


def figure_3_maps(ds, type):
    """
    Column of 3 map subplots for model, observation and their comparison.

    Returns
    -------
    f : figure
    axs : list
        3 axes for observation, model and comparison maps over observation extent.
    """

    f = plt.figure(figsize=(10, 18))
    ax0 = plt.subplot2grid((3, 2), (0, 0), projection=ccrs.Mercator(), aspect='equal')
    ax1 = plt.subplot2grid((3, 2), (0, 1), projection=ccrs.Mercator(), aspect='equal')
    ax2 = plt.subplot2grid((3, 2), (1, 0), colspan=2, rowspan=2, projection=ccrs.Mercator(),
                           aspect='equal')

    axs = [ax0, ax1, ax2]
    if type == 'harm':
        labels = [LABELS_MAP_HARM[0], LABELS_MAP_HARM[2], LABELS_MAP_HARM[4]]
    elif type == 'classic':
        labels = [LABELS_MAP[0], LABELS_MAP[3], LABELS_MAP[4]]

    for ax, label in zip(axs, labels):
        ax.set_extent(get_extent(ds))
        gl = ax.gridlines(draw_labels=True)
        gl.right_labels = False
        gl.top_labels = False
        gl.xlabel_style = {'size': 12}
        gl.ylabel_style = {'size': 12}
        ax.add_feature(cfeature.LAND, zorder=1, edgecolor='k')
        ax.set_title(label, fontsize=13)
    f.subplots_adjust(left=0.03, bottom=0.03, right=0.98, top=0.9, hspace=0.2)

    return f, axs


def figure_5lin_ts():
    """
    Column of 5 graph subplots for model, observation and their comparison according
     metrics available(biais RMSE,
    centered RMSE).

    Returns
    -------
    f : figure
    axs : list
        5 axes for observation, model and comparison time series.
    """
    f = plt.figure(figsize=(12, 10))
    ax0 = plt.subplot2grid((5, 1), (0, 0))
    ax1 = plt.subplot2grid((5, 1), (1, 0))
    ax2 = plt.subplot2grid((5, 1), (2, 0))
    ax3 = plt.subplot2grid((5, 1), (3, 0))
    ax4 = plt.subplot2grid((5, 1), (4, 0))

    axs = [ax0, ax1, ax2, ax3, ax4]
    labels = LABELS_TS[:5]

    for ax, label in zip(axs, labels):
        ax.grid()
        ax.set_title(label, fontsize=10)
    f.subplots_adjust(top=1, bottom=0.75, wspace=0.5, hspace=0.4)

    return f, axs


def figure_3lin_ts():
    """
    Column of 3 graph subplots for model, observation and their difference.

    Returns
    -------
    f : figure
    axs : list
        3 axes for observation, model and comparison time series.
    """
    f = plt.figure(figsize=(11, 8))
    ax0 = plt.subplot2grid((3, 1), (0, 0))
    ax1 = plt.subplot2grid((3, 1), (1, 0))
    ax2 = plt.subplot2grid((3, 1), (2, 0))

    axs = [ax0, ax1, ax2]
    labels = LABELS_DIFF[:3]

    for ax, label in zip(axs, labels):
        ax.grid()
        ax.set_title(label, fontsize=10)
        ax.set_ylabel('Depth [m]', fontsize=10)
    f.subplots_adjust(left=0.1, bottom=0.03, right=0.98, top=0.9, hspace=0.4)

    return f, axs


def figure_2lin_ts():
    """
    Column of 2 graph subplots for model, observation / and their comparison(écart).

    Returns
    -------
    f : figure
    axs : list
        2 axes for observation, model and comparison time series.
    """
    f = plt.figure(figsize=(15, 9))
    ax0 = plt.subplot2grid((2, 1), (0, 0))
    ax1 = plt.subplot2grid((2, 1), (1, 0))

    axs = [ax0, ax1]
    labels = LABELS_TS[5:7]

    for ax, label in zip(axs, labels):
        ax.grid()
        ax.set_title(label, fontsize=15)
    f.subplots_adjust(top=1, bottom=0.75, wspace=0.5, hspace=0.5)

    return f, axs


def figure_1_profile():
    """
    1 graph plot containing profile for model, observation.

    Returns
    -------
    f : figure
    ax : 1 ax for observation and model(s).
    """
    f = plt.figure(figsize=(10, 10))
    ax = plt.gca()

    label = LABELS_PROFILE[0]

    ax.grid()
    ax.set_title(label, fontsize=15)
    f.subplots_adjust(left=0.1, bottom=0.03, right=0.98, top=0.85, wspace=0.25, hspace=0.15)
    return f, ax


def figure_1_stickplot():
    """
    1 graph plot prepared for the stickplot.

    Returns
    -------
    f : figure
    ax : 1 ax for the stickplot.
    """
    f = plt.figure(figsize=(12, 7))
    ax = plt.gca()

    label = LABELS_STICKPLOT[0]

    ax.grid()
    ax.set_title(label, fontsize=20)
    f.subplots_adjust(left=0.1, bottom=0.03, right=0.9, top=0.85, wspace=0.25, hspace=0.15)
    return f, ax


def get_extent(extent, margin=0.05, square=True, min_extent=1.0):
    """Compute the geographic extent in degrees
    Parameters
    ----------
    extent: xarray.DataArray, xarray.Dataset, dict, tuple, list
        Either:
        - An array or dataset with longitude and latitude coordinates.
        - A dict with ``lon`` and ``lat`` keys: ``dict(lon=..., lat=...)``
        - A two-element tuple of longitudes and latitudes: ``(lon, lat)``
        - A extent list: ``[xmin, xmax, ymin, ymax]``.
    margin: float
        A relative fraction of the width and height that is used to set margins.
        For instance, a value of ``-0.1`` shrinks the box of 10% on each side.
    square: bool
        Force the box to be square in degrees.
    min_extent: None, float, (float, float)
        Minimal extent along x and y: ``(dx, dy)``.
        If a single floating value is provided, it is valid for both x and y.
    Return
    ------
    list
        ``[xmin, xmax, ymin, ymax]``
    Example
    -------
    .. ipython:: python
        @suppress
        from xoa.geo import get_extent
        @suppress
        import numpy as np
        get_extent([10., 20., 10., 20.], margin=0.1)
        get_extent({"lon": np.linspace(10, 20, 5), "lat": np.linspace(10, 20, 5)}, square=True)
        get_extent((np.linspace(10, 20, 5), np.linspace(10, 20, 5)), margin=-.1, square=True)
    """
    # Get min and max
    lon, lat = extent['lon'], extent['lat']
    lon = lon.where(lon < 1e3)
    lat = lat.where(lat < 1e3)
    xmin = float(np.nanmin(lon))
    xmax = float(np.nanmax(lon))
    ymin = float(np.nanmin(lat))
    ymax = float(np.nanmax(lat))

    # Scale
    if square or margin or min_extent is not None:
        dx = xmax - xmin
        dy = ymax - ymin
        x0 = 0.5 * (xmin + xmax)
        y0 = 0.5 * (ymin + ymax)
        if min_extent is not None:
            if isinstance(min_extent, (float, int)):
                min_extent = (min_extent, min_extent)
            dx_min, dy_min = min_extent
            dx = max(dx, dx_min)
            dy = max(dy, dy_min)
        if square and dy != 0:
            aspect = dx * math.cos(y0 * math.pi / 180) / dy
            if aspect > 1:
                dy *= aspect
            else:
                dx /= aspect
        xmargin = margin * dx
        ymargin = margin * dy
        xmin = x0 - 0.5 * dx - xmargin
        xmax = x0 + 0.5 * dx + xmargin
        ymin = y0 - 0.5 * dy - ymargin
        ymax = y0 + 0.5 * dy + ymargin

    return [xmin, xmax, ymin, ymax]


def add_mini_map(f, extent=None):
    """
    Add the mini map ax to the figure
    Parameters
    ----------
    f : figure
        figure where to add the minimap
    extent : xarray.dataset
    Returns
    -------
    ax_mini_map
        ax of the minimap
    """
    f.subplots_adjust(top=0.8, bottom=0.05)
    ax_mini_map = f.add_axes([0.75, 0.85, 0.2, 0.15], projection=ccrs.Mercator())
    ax_mini_map.set_xmargin(1)
    ax_mini_map.set_ymargin(0.3)
    gl = ax_mini_map.gridlines(draw_labels=True)
    gl.right_labels = False
    gl.top_labels = False
    ax_mini_map.add_feature(cfeature.LAND, zorder=1, edgecolor='k')
    ax_mini_map.set_extent(get_extent(extent), crs=ccrs.PlateCarree())

    return ax_mini_map


def add_plg_minimap(ax_mini_map, ds, plg):
    """
    Add the mini map ax to the figure
    Parameters
    ----------
    ax_mini_map
        ax of the minimap
    ds: DataArray
        DataArray whose lon / lat to plot.
    plg : list
        Polygon coordinates list.
    """
    if plg:
        lons = [point[0] for point in plg]
        lats = [point[1] for point in plg]
        polygon = mpatches.Polygon(list(zip(lons, lats)), closed=True, facecolor='blue', alpha=0.5,
                                   transform=ccrs.PlateCarree())
        ax_mini_map.add_patch(polygon)
        ax_mini_map.set_extent([min(lons), max(lons), min(lats), max(lats)])
    else:
        lons = []
        lats = []
        if 'time' in ds.dims:
            ds = ds.isel(time=0)
        if 'depth' in ds.dims:
            ds = ds.isel(depth=0)
        if 'interval' in ds.dims:
            ds = ds.isel(interval=0, idx_time=0)
        if 'slice' in ds.dims:
            ds = ds.isel(slice=0)
        if 'idx_depth' in ds.dims:
            ds = ds.isel(idx_depth=0)
        if 'idx_dens' in ds.dims:
            ds = ds.isel(idx_dens=0)
        for i_lon, lon in enumerate(ds.lon.data):
            for i_lat, lat in enumerate(ds.lat.data):
                if not np.isnan(ds.isel(lon=i_lon, lat=i_lat)):
                    lons.append(lon)
                    lats.append(lat)
        ax_mini_map.scatter(lons, lats, transform=ccrs.PlateCarree())


def diag_disp(flag_interval, flag_slice, diag_type, mod, obs, output_path=None):
    """
    Plot of dispersion diagram between model and observation along with point density.
    Selection of all points, time, lon, lat, depth if diag_type =  diag_disp_g
    Selection of all points lon lat, depth by time_step/time_group if diag_type = diag_disp
    Parameters
    ----------
    flag_interval : bool
        Indicates if the figures must be plot by intervals or not.
    flag_slice : bool
        Indicates if the figures must be plot by slices or not.
    diag_type :
        type of diagram : diag_disp_g (global) or diag_disp.
    mod : xarray.Dataset
        Model dataset.
    obs : xarray.Dataset
        Observation dataset.
    output_path : str
        Path where to save the figures.

    """
    # Plot the diagrams
    if diag_type == "diag_disp_g":
        title, figname = get_title_figname('Dispersion diagram', obs, mod.attrs['name'],
                                           obs.attrs['name'])
        diag_disp_figure(mod, obs, title)
        manage_output(figname, output_path)

    elif diag_type == "diag_disp":
        if flag_interval:
            for index_interval, _ in enumerate(mod['interval']):
                if flag_slice:
                    for index_slice, _ in enumerate(mod['slice']):
                        mod_inter = mod.isel(interval=[index_interval], slice=[index_slice])
                        obs_inter = obs.isel(interval=[index_interval], slice=[index_slice])
                        title, figname = get_title_figname('Dispersion diagram', obs_inter,
                                                           mod.attrs['name'], obs.attrs['name'])
                        diag_disp_figure(mod_inter, obs_inter, title)
                        manage_output(figname, output_path)
                elif 'depth' in mod.dims and len(mod.depth) > 1:
                    for index_depth, _ in enumerate(mod['depth']):
                        mod_depth = mod.isel(depth=[index_depth])
                        obs_depth = obs.isel(depth=[index_depth])
                        title, figname = get_title_figname('Dispersion diagram', obs_depth,
                                                           mod.attrs['name'], obs.attrs['name'])
                        diag_disp_figure(mod_depth, obs_depth, title)
                        manage_output(figname, output_path)
                else:
                    mod_inter = mod.isel(interval=[index_interval])
                    obs_inter = obs.isel(interval=[index_interval])
                    title, figname = get_title_figname('Dispersion diagram', obs_inter,
                                                       mod.attrs['name'], obs.attrs['name'])
                    diag_disp_figure(mod_inter, obs_inter, title)
                    manage_output(figname, output_path)
        else:
            if flag_slice:
                for index_slice, _ in enumerate(mod['slice']):
                    mod_inter = mod.isel(slice=[index_slice])
                    obs_inter = obs.isel(slice=[index_slice])
                    title, figname = get_title_figname('Dispersion diagram', obs_inter,
                                                       mod.attrs['name'], obs.attrs['name'])
                    diag_disp_figure(mod_inter, obs_inter, title)
                    manage_output(figname, output_path)
            elif 'depth' in mod.dims and len(mod.depth) > 1:
                for index_depth, _ in enumerate(mod['depth']):
                    mod_depth = mod.isel(depth=[index_depth])
                    obs_depth = obs.isel(depth=[index_depth])
                    title, figname = get_title_figname('Dispersion diagram', obs_depth,
                                                       mod.attrs['name'], obs.attrs['name'])
                    diag_disp_figure(mod_depth, obs_depth, title)
                    manage_output(figname, output_path)
            else:
                title, figname = get_title_figname('Dispersion diagram', obs, mod.attrs['name'],
                                                   obs.attrs['name'])
                diag_disp_figure(mod, obs, title)
                manage_output(figname, output_path)


def diag_disp_figure(mod, obs, title):
    """
    Creates the figures for the dispersion diagram
    Parameters
    ----------
    mod : xarray.Dataset
        Model dataset.
    obs : xarray.Dataset
        Observation dataset.
    var_title : str
        Formatted title of the variable.
    title : str
        Title of the figure.
    output_path : str
        Path where to save the figures.
    figname : str
        Figure name.

    """

    logger.info('Dispersion diagram')
    f, axes = plt.subplots(figsize=(10, 10))
    f.suptitle(title, fontsize=12, fontweight='bold')
    plt.xlabel(f"{obs.attrs['name']} Observations")
    plt.ylabel(f"{mod.attrs['name']} Model ")

    # Flatten dataarray because dask array doesn't work with flatten
    obs = obs.values.ravel()
    mod = mod.values.ravel()

    x = obs[~np.isnan(obs)]
    y = mod[~np.isnan(mod)]

    n = len(x)
    if n != 0:
        # Sturge's rule
        nbins = int(1 + 3.322 * np.log2(n))
        # Compute histogram
        data, x_e, y_e = np.histogram2d(x, y, bins=nbins, density=True)

        slope, intercept, r, _, std_err = stats.linregress(x, y)
        rmse = calculation.rmsec_diag_disp(x, y)

        def myfunc(x):
            return slope * x + intercept

        mymodel = list(map(myfunc, x))

        vmin = np.nanmin([np.nanmin(obs), np.nanmin(mod)])
        vmax = np.nanmax([np.nanmax(obs), np.nanmax(mod)])

        markersize = np.tanh(1e5 / n)
        treshold = 1e-2
        markersize = max(markersize, treshold)
        axes.scatter(x, y, c='slateblue', s=2 * markersize)
        plt.plot([vmin, vmax], [vmin, vmax], color='gray', linestyle='dashed', markersize=5)
        plt.grid(color='gray', linestyle='--', linewidth=1, zorder=1)
        plt.plot(x, mymodel, color='red', linestyle='solid', markersize=5,
                 label=f'y = {slope:.3f}*x + {intercept:.3f} \n'
                       f'Correlation Coef = {r:.3f}\n'
                       f'Std Err = {std_err:.3f}\n'
                       f'RMSE = {rmse:.3f}\n'
                       f'Npts = {n}')
        plt.legend(loc='upper left')
        cs = axes.contour(np.convolve(x_e, np.ones(2, dtype=int), 'valid') / 2.0,
                          np.convolve(y_e, np.ones(2, dtype=int), 'valid') / 2.0,
                          data.T / data.max(), levels=np.arange(0.1, 1.2, 0.2), cmap="Reds",
                          linewidths=1)
        axes.clabel(cs, cs.levels, inline=True, fontsize=5, fmt="%1.1f")


def plot_map_metr_profiles(flag_interval, flag_slice, mod_coloc, obs_coloc, metric,
                           cmap=cmocean.cm.thermal, vmin=None, vmax=None, output_path=None,
                           dvmin=None, dvmax=None):
    """
    Plot the map of the profiles for functionality 2.
    Parameters
    ----------
    flag_interval : bool
        Indicates if the figures must be plot by intervals or not.
    flag_slice : bool
        Indicates if the figures must be plot by slices or not.
    mod_coloc : xarray.dataset
        Model dataset.
    obs_coloc : xarray.dataset
        Observation dataset.
    metric : str
           metric to plot : difference, bias, RMSEc or RMSE.
    cmap : str
       cmocean colour map.
    vmin : float
       min colour value of profile to plot.
    vmax : float
       max colour value of profile to plot.
    dvmin : float
       min colour value of comparison to plot.
    dvmax : float
       max colour value of comparison to plot.
    output_path :
        Path where to save the figures.
    """
    logger.info('Map of profiles')

    # calculate the variables required by the metric to plot
    if metric == "difference":
        comparison = mod_coloc - obs_coloc

    elif metric == "bias":
        if flag_slice is False:
            raise ValueError("Oops, pour utiliser cette carte de métrique, vous devriez fournir "
                             "un découpage vertical par tranches dans votre meta-zone")
        if 'idx_depth' in obs_coloc.dims:
            var_slice = 'idx_depth'
        elif 'idx_dens' in obs_coloc.dims:
            var_slice = 'idx_dens'
        obs_coloc = obs_coloc.mean(var_slice)
        mod_coloc = mod_coloc.mean(var_slice)
        comparison = mod_coloc - obs_coloc

    elif metric == "RMSE":
        if flag_slice is False:
            raise ValueError("Oops, pour utiliser cette carte de métrique, vous devriez fournir un "
                             "découpage vertical par tranches dans votre meta-zone")

        if 'idx_depth' in obs_coloc.dims:
            var_slice = 'idx_depth'
        elif 'idx_dens' in obs_coloc.dims:
            var_slice = 'idx_dens'
        comparison = calculation.rmse_generic(obs_coloc, mod_coloc, [var_slice])
        obs_coloc = obs_coloc.std(var_slice)
        mod_coloc = mod_coloc.std(var_slice)

    elif metric == "RMSEc":
        if flag_slice is False:
            raise ValueError(
                "Oops, pour utiliser cette carte de métrique, vous devriez fournir un découpage "
                "vertical par tranches dans votre meta-zone")
        if 'idx_depth' in obs_coloc.dims:
            var_slice = 'idx_depth'
        elif 'idx_dens' in obs_coloc.dims:
            var_slice = 'idx_dens'
        comparison = calculation.rmse_center_generic(obs_coloc, mod_coloc, [var_slice])
        obs_coloc = obs_coloc.std(var_slice)
        mod_coloc = mod_coloc.std(var_slice)

    # Plot the figures
    if flag_interval:
        for index_time, _ in enumerate(interval_str_to_date(obs_coloc.interval)):
            if flag_slice:
                for index_slice, _ in enumerate(obs_coloc.slice):
                    # Select the data to plot
                    obs_coloc_inter = obs_coloc.isel(interval=[index_time], slice=[index_slice])
                    mod_coloc_inter = mod_coloc.isel(interval=[index_time], slice=[index_slice])
                    comparison_inter = comparison.isel(interval=[index_time], slice=[index_slice])
                    title, figname = get_title_figname(f'Map {metric}', mod_coloc_inter,
                                                       mod_coloc.attrs['name'],
                                                       obs_coloc.attrs['name'])
                    plot_map_metr_profiles_figure(mod_coloc_inter, obs_coloc_inter,
                                                  comparison_inter, title, vmin, vmax, metric, cmap,
                                                  dvmin=dvmin, dvmax=dvmax)
                    # Save figure
                    manage_output(figname, output_path)

            elif 'depth' in obs_coloc.dims and len(obs_coloc.depth) > 0:
                for index_depth, _ in enumerate(obs_coloc.depth):
                    # Select the data to plot
                    obs_coloc_inter = obs_coloc.isel(interval=[index_time], depth=[index_depth])
                    mod_coloc_inter = mod_coloc.isel(interval=[index_time], depth=[index_depth])
                    comparison_inter = comparison.isel(interval=[index_time], depth=[index_depth])
                    title, figname = get_title_figname(f'Map {metric}', mod_coloc_inter,
                                                       mod_coloc.attrs['name'],
                                                       obs_coloc.attrs['name'])
                    plot_map_metr_profiles_figure(mod_coloc_inter, obs_coloc_inter,
                                                  comparison_inter, title, vmin, vmax, metric, cmap,
                                                  dvmin=dvmin, dvmax=dvmax)
                    # Save figure
                    manage_output(figname, output_path)

            elif 'dens' in obs_coloc.dims and len(obs_coloc.dens) > 0:
                for index_dens, _ in enumerate(obs_coloc.dens):
                    # Select the data to plot
                    obs_coloc_inter = obs_coloc.isel(interval=[index_time], dens=[index_dens])
                    mod_coloc_inter = mod_coloc.isel(interval=[index_time], dens=[index_dens])
                    comparison_inter = comparison.isel(interval=[index_time],
                                                       dedenspth=[index_dens])
                    title, figname = get_title_figname(f'Map {metric}', mod_coloc_inter,
                                                       mod_coloc.attrs['name'],
                                                       obs_coloc.attrs['name'])
                    plot_map_metr_profiles_figure(mod_coloc_inter, obs_coloc_inter,
                                                  comparison_inter, title, vmin, vmax, metric, cmap,
                                                  dvmin=dvmin, dvmax=dvmax)
                    # Save figure
                    manage_output(figname, output_path)
            else:
                # Select the data to plot
                obs_coloc_inter = obs_coloc.isel(interval=[index_time])
                mod_coloc_inter = mod_coloc.isel(interval=[index_time])
                comparison_inter = comparison.isel(interval=[index_time])
                title, figname = get_title_figname(f'Map {metric}', mod_coloc_inter,
                                                   mod_coloc.attrs['name'], obs_coloc.attrs['name'])
                plot_map_metr_profiles_figure(mod_coloc_inter, obs_coloc_inter, comparison_inter,
                                              title, vmin, vmax, metric, cmap, dvmin=dvmin,
                                              dvmax=dvmax)
                # Save figure
                manage_output(figname, output_path)
    else:
        if flag_slice:
            for index_slice, _ in enumerate(obs_coloc.slice):
                # Select the data to plot
                obs_coloc_slice = obs_coloc.isel(slice=[index_slice])
                mod_coloc_slice = mod_coloc.isel(slice=[index_slice])
                comparison_slice = comparison.isel(slice=[index_slice])
                title, figname = get_title_figname(f'Map {metric}', obs_coloc_slice,
                                                   mod_coloc.attrs['name'], obs_coloc.attrs['name'])
                plot_map_metr_profiles_figure(mod_coloc_slice, obs_coloc_slice, comparison_slice,
                                              title, vmin, vmax, metric, cmap, dvmin=dvmin,
                                              dvmax=dvmax)
                # Save figure
                manage_output(figname, output_path)

        elif 'depth' in obs_coloc.dims and len(obs_coloc.depth) > 0:
            for index_depth, _ in enumerate(obs_coloc.depth):
                # Select the data to plot
                obs_coloc_depth = obs_coloc.isel(depth=[index_depth])
                mod_coloc_depth = mod_coloc.isel(depth=[index_depth])
                comparison_depth = comparison.isel(depth=[index_depth])
                title, figname = get_title_figname(f'Map {metric}', obs_coloc_depth,
                                                   mod_coloc.attrs['name'], obs_coloc.attrs['name'])
                plot_map_metr_profiles_figure(mod_coloc_depth, obs_coloc_depth, comparison_depth,
                                              title, vmin, vmax, metric, cmap, dvmin=dvmin,
                                              dvmax=dvmax)
                # Save figure
                manage_output(figname, output_path)

        elif 'dens' in obs_coloc.dims and len(obs_coloc.dens) > 0:
            for index_dens, _ in enumerate(obs_coloc.dens):
                # Select the data to plot
                obs_coloc_dens = obs_coloc.isel(dens=[index_dens])
                mod_coloc_dens = mod_coloc.isel(dens=[index_dens])
                comparison_dens = comparison.isel(dens=[index_dens])
                title, figname = get_title_figname(f'Map {metric}', obs_coloc_dens,
                                                   mod_coloc.attrs['name'], obs_coloc.attrs['name'])
                plot_map_metr_profiles_figure(mod_coloc_dens, obs_coloc_dens, comparison_dens,
                                              title, vmin, vmax, metric, cmap, dvmin=dvmin,
                                              dvmax=dvmax)
                # Save figure
                manage_output(figname, output_path)
        else:
            title, figname = get_title_figname(f'Map {metric}', obs_coloc, mod_coloc.attrs['name'],
                                               obs_coloc.attrs['name'])

            plot_map_metr_profiles_figure(mod_coloc, obs_coloc, comparison, title, vmin, vmax,
                                          metric, cmap, dvmin=dvmin, dvmax=dvmax)
            # Save figure
            manage_output(figname, output_path)


def plot_map_metr_profiles_figure(mod_coloc, obs_coloc, comparison, title, vmin, vmax, metric, cmap,
                                  dvmin=None, dvmax=None):
    """
    Plot the map of the profiles for functionality 2. Display the figures.
    Parameters
    ----------
    mod_coloc : xarray.dataset
        Model dataset.
    obs_coloc : xarray.dataset
        Observation dataset.
    comparison : str
        Comparison to plot (Bias, RMSE etc).
    title : str
        Title of fthe figure to plot.
    vmin : float
       min colour value of variable to plot.
    vmax : float
       max colour value of variable to plot.
    metric : str
        metric to be plotted.
    dvmin : float
       min colour value of variable comparison to plot.
    dvmax : float
       max colour value of variable comparison to plot.
    cmap : str
        cmocean colour map for the variable.
    file_name : str
        Name of the figure file to save.
    output_path :
        Path where to save the figures.
    """
    # Get min/max colobar values
    vmin, vmax, comparison_vmin, comparison_vmax, _, comparison_cmap = get_min_max_values(vmin,
                                                                                          vmax,
                                                                                          obs_coloc,
                                                                                          comparison,
                                                                                          metric,
                                                                                          dvmin,
                                                                                          dvmax)

    # Squeeze
    mod_coloc, obs_coloc = mod_coloc.squeeze(), obs_coloc.squeeze()
    comparison = comparison.squeeze()

    # Plot the map
    f, axs = figure_3_maps(mod_coloc, 'classic')
    im0 = axs[0].scatter(obs_coloc.lon, obs_coloc.lat, 30, obs_coloc, vmin=vmin, vmax=vmax,
                         cmap=cmap, transform=ccrs.PlateCarree())
    im1 = axs[1].scatter(mod_coloc.lon, mod_coloc.lat, 30, mod_coloc, vmin=vmin, vmax=vmax,
                         cmap=cmap, transform=ccrs.PlateCarree())
    im2 = axs[2].scatter(comparison.lon.values, comparison.lat.values, 30, comparison,
                         vmin=comparison_vmin, vmax=comparison_vmax, cmap=comparison_cmap,
                         transform=ccrs.PlateCarree())

    # Add colorbars and title
    f.colorbar(im0, ax=axs[0], orientation='horizontal', fraction=0.046, pad=0.1)
    f.colorbar(im1, ax=axs[1], orientation='horizontal', fraction=0.046, pad=0.1)
    f.colorbar(im2, ax=axs[2], orientation='horizontal', fraction=0.046, pad=0.1)
    f.suptitle(title, fontsize=17, fontweight='bold')


def plot_map_metr(flag_interval, flag_slice, mod_meta, mod_coloc, obs_meta, obs_coloc, metric,
                  cmap=cmocean.cm.thermal, vmin=None, vmax=None, output_path=None, dvmin=None,
                  dvmax=None):
    """
    Plot map of the model and observation and their comparison required in functionality 1,2,3,5.

    Parameters
    ----------
    flag_interval : bool
        Indicates if the figures must be plot by intervals or not.
    flag_slice : bool
        Indicates if the figures must be plot by slices or not.
    mod_meta : xarray.DataArray
        Variable from model product, subset along the meta-zone.
    mod_coloc : xarray.DataArray
        Variable from model product, colocated with the observation.
    obs_meta : xarray.DataArray
        Variable from observation product, subset along the meta-zone.
    obs_coloc : xarray.DataArray
        Variable from observation product, colocated with the model.
    metric : str
        Comparison to plot.
    cmap : str
        cmocean colour map for the variable.
    vmin : float
       min colour value of variable to plot.
    vmax : float
       max colour value of variable to plot.
    output_path :
        Path where to save the figures.
    dvmin : float
       min colour value of comparison to plot.
    dvmax : float
       max colour value of comparison to plot.
    """
    logger.info('Map of the model and observation and their comparison')
    # Get product names
    mod_name = mod_coloc.attrs['name']
    obs_name = obs_coloc.attrs['name']

    # Get the dimensions on which the stats are calculated
    list_dims_mean = []
    if 'idx_time' in mod_coloc.dims:
        list_dims_mean.append('idx_time')

    # Calculate the variables to plot
    if metric == "difference":
        if flag_interval is True:
            raise ValueError(
                "Oops, pour utiliser cette carte de métrique, vous ne devriez pas fournir"
                " une spécification d'intervalles successifs dans votre meta-zone")

        comparison = mod_coloc - obs_coloc

    elif metric == "bias":
        if flag_interval is False and flag_slice is False:
            raise ValueError(
                "Oops, pour utiliser cette carte de métrique, vous devriez fournir une "
                "spécification d'intervalles temporels "
                "ou de tranches verticales dans votre meta-zone")
        obs_coloc = obs_coloc.mean(list_dims_mean)
        obs_meta = obs_meta.mean(list_dims_mean)
        mod_coloc = mod_coloc.mean(list_dims_mean)
        mod_meta = mod_meta.mean(list_dims_mean)
        comparison = mod_coloc - obs_coloc

    elif metric == "RMSE":
        if flag_interval is False and flag_slice is False:
            raise ValueError(
                "Oops, pour utiliser cette carte de métrique, vous devriez fournir une "
                "spécification d'intervalles temporels "
                "ou de tranches verticales dans votre meta-zone")
        comparison = calculation.rmse_generic(obs_coloc, mod_coloc, list_dims_mean)
        obs_coloc = obs_coloc.std(list_dims_mean)
        obs_meta = obs_meta.std(list_dims_mean)
        mod_coloc = mod_coloc.std(list_dims_mean)
        mod_meta = mod_meta.std(list_dims_mean)

    elif metric == "RMSEc":
        if flag_interval is False and flag_slice is False:
            raise ValueError(
                "Oops, pour utiliser cette carte de métrique, vous devriez fournir une "
                "spécification d'intervalles temporels "
                "ou de tranches verticales dans votre meta-zone")
        comparison = calculation.rmse_center_generic(obs_coloc, mod_coloc, list_dims_mean)
        obs_coloc = obs_coloc.std(list_dims_mean)
        obs_meta = obs_meta.std(list_dims_mean)
        mod_coloc = mod_coloc.std(list_dims_mean)
        mod_meta = mod_meta.std(list_dims_mean)

    # Warning if stats calculated on only 1 value
    if obs_coloc.max() == 0 or obs_meta.max() == 0 or mod_meta.max() == 0 or obs_coloc.max() == 0:
        logger.warning(
            f'Caution : the stats calculation returned only 0, probably due to too short intervals/depth slices.')

    # Plot the values
    if metric == "difference":
        if np.size(mod_coloc.time) == 1:
            # Make sure to select the closest date
            if np.size(obs_meta.time) > 1:
                obs_meta = obs_meta.sel(time=obs_coloc.time, method='nearest')
            if np.size(mod_meta.time) > 1:
                mod_meta = mod_meta.sel(time=mod_coloc.time, method='nearest')

            # Plot, save and display
            title, figname = get_title_figname('Map difference', obs_coloc, mod_name, obs_name)
            plot_map_metr_figure(obs_meta, mod_meta, obs_coloc, mod_coloc, comparison, vmin, vmax,
                                 cmap, title, metric, dvmin=dvmin, dvmax=dvmax)

            manage_output(figname, output_path)

        else:
            for i_time, time in enumerate(mod_coloc.time):

                # Plot, save and display
                if 'U' in str(time.data.dtype):  # Check if times are months names
                    # Get the title
                    title, figname = get_title_figname('Climatology map difference',
                                                       obs_coloc.isel(time=i_time), mod_name,
                                                       obs_name)

                    plot_map_metr_figure(obs_meta.isel(time=i_time), mod_meta.isel(time=i_time),
                                         obs_coloc.isel(time=i_time), mod_coloc.isel(time=i_time),
                                         comparison.isel(time=i_time), vmin, vmax, cmap, title,
                                         metric, dvmin=dvmin, dvmax=dvmax)

                else:
                    # Get the title
                    title, figname = get_title_figname('Map difference', obs_coloc.sel(time=time),
                                                       mod_name, obs_name)
                    plot_map_metr_figure(obs_meta.sel(time=time, method='nearest'),
                                         mod_meta.sel(time=time, method='nearest'),
                                         obs_coloc.isel(time=i_time), mod_coloc.isel(time=i_time),
                                         comparison.isel(time=i_time), vmin, vmax, cmap, title,
                                         metric, dvmin=dvmin, dvmax=dvmax)

                manage_output(figname, output_path)

    # Other metric than difference
    else:
        if flag_interval:
            for i_inter, _ in enumerate(mod_coloc.interval):
                # Get the title
                title, figname = get_title_figname(f'Map {metric}',
                                                   obs_coloc.isel(interval=i_inter), mod_name,
                                                   obs_name)

                # Plot, save and display
                plot_map_metr_figure(obs_meta.isel(interval=i_inter),
                                     mod_meta.isel(interval=i_inter),
                                     obs_coloc.isel(interval=i_inter),
                                     mod_coloc.isel(interval=i_inter),
                                     comparison.isel(interval=i_inter), vmin, vmax, cmap, title,
                                     metric, dvmin=dvmin, dvmax=dvmax)

                manage_output(figname, output_path)
        # no interval
        else:
            if obs_coloc.time.size == 1:
                # Make sure to select the closest date
                if np.size(obs_meta.time) > 1:
                    obs_meta = obs_meta.sel(time=obs_coloc.time, method='nearest')
                if np.size(mod_meta.time) > 1:
                    mod_meta = mod_meta.sel(time=mod_coloc.time, method='nearest')

            title, figname = get_title_figname(f'Map {metric}', obs_coloc, mod_name, obs_name)
            # Plot, save and display
            plot_map_metr_figure(obs_meta, mod_meta, obs_coloc, mod_coloc, comparison, vmin, vmax,
                                 cmap, title, metric, dvmin=dvmin, dvmax=dvmax)

            manage_output(figname, output_path)


def plot_map_metr_figure(obs_meta, mod_meta, obs_coloc, mod_coloc, comparison, vmin, vmax, cmap,
                         title, metric, dvmin=None, dvmax=None):
    """
    Plot the map figures with comparison metric.
    Parameters
    ----------
    mod_meta : xarray.DataArray
        Variable from model product, subset along the meta-zone.
    mod_coloc : xarray.DataArray
        Variable from model product, colocated with the observation.
    obs_meta : xarray.DataArray
        Variable from observation product, subset along the meta-zone.
    obs_coloc : xarray.DataArray
        Variable from observation product, colocated with the model.
    comparison : str
        Comparison metric to plot.
    vmin : float
       min colour value of variable to plot.
    vmax : float
       max colour value of variable to plot.
    cmap : str
        cmocean colour map for the variable.
    title : str
        Title of the figure.
    metric : str
        Comparison to plot.
    dvmin : float
       min colour value of comparison to plot.
    dvmax : float
       max colour value of comparison to plot.

    Returns
    -------
    f : figure
    axs : axs of the figure
    """
    logger.info('map figures with comparison metric')
    # Get min/max colobar values
    vmin, vmax, comparison_vmin, comparison_vmax, _, comparison_cmap = get_min_max_values(vmin,
                                                                                          vmax,
                                                                                          obs_meta,
                                                                                          comparison,
                                                                                          metric,
                                                                                          dvmin,
                                                                                          dvmax)
    # Squeeze
    obs_meta, obs_coloc = clean_dim_order(obs_meta), clean_dim_order(obs_coloc)
    mod_meta, mod_coloc = clean_dim_order(mod_meta), clean_dim_order(mod_coloc)
    comparison = clean_dim_order(comparison)

    # Plot
    f, axs = figure_5_maps(obs_coloc)
    axs[0].pcolormesh(obs_meta.lon.data, obs_meta.lat.data, obs_meta.data, vmin=vmin, vmax=vmax,
                      cmap=cmap, transform=ccrs.PlateCarree())
    axs[1].pcolormesh(obs_coloc.lon, obs_coloc.lat, obs_coloc, vmin=vmin, vmax=vmax, cmap=cmap,
                      transform=ccrs.PlateCarree())

    axs[2].pcolormesh(mod_meta.lon, mod_meta.lat, mod_meta, vmin=vmin, vmax=vmax, cmap=cmap,
                      transform=ccrs.PlateCarree())

    im3 = axs[3].pcolormesh(mod_coloc.lon, mod_coloc.lat, mod_coloc, vmin=vmin, vmax=vmax,
                            cmap=cmap, transform=ccrs.PlateCarree())
    im4 = axs[4].pcolormesh(obs_coloc.lon, obs_coloc.lat, comparison, vmin=comparison_vmin,
                            vmax=comparison_vmax, cmap=comparison_cmap,
                            transform=ccrs.PlateCarree())

    cbar1 = f.colorbar(im3, ax=[axs[1], axs[3]])
    cbar1.ax.tick_params(labelsize=12)
    cbar2 = f.colorbar(im4, ax=axs[4])
    cbar2.ax.tick_params(labelsize=12)
    f.suptitle(title, fontsize=17, fontweight='bold')

    return f, axs


def clean_dim_order(ds):
    """
    Clean the dimension order in the dataset.
    Parameters
    ----------
    ds : xarray.dataset

    """
    if list(ds.dims) == ['lon', 'lat']:
        ds = ds.transpose('lat', 'lon')
    return ds.squeeze()


def plot_map_trajectory(observation, models, traj_duration_plot, traj_freq_plot, time_step,
                        output_path):
    """
    Plot the modelled and observed trajectories.
    Parameters
    ----------
    observation : xarray.dataset
        Trajectory from the observation dataset.
    models : list of xarray.dataset
        Trajectories from the models datasets.
    traj_duration_plot : int
        duration of the simulated trajectory to plot.
    traj_freq_plot : int
        frequency at which the trajectories are plotted (ex : one ine 3).
    time_step : float
        calculation time step.
    output_path : str
        Path where to save the figure.

    """
    logger.info('Trajectory map')
    # Set the figure parameters
    f, ax = figure_1_map(observation["xarray_meta"])

    # Plot observation
    obs = observation["xarray_meta"].squeeze()
    ax.plot(obs.lon, obs.lat, 'k', transform=ccrs.PlateCarree(), label=observation["name"])

    # Convert parameters
    traj_duration_plot_int = max(int(traj_duration_plot / time_step), 1)
    traj_freq_plot_int = int(traj_freq_plot / time_step)

    # Plot models
    for i_mod, mod in enumerate(models):
        traj_mod = mod['traj'].squeeze()
        for i in range(0, len(traj_mod.trajectory.values), traj_freq_plot_int):
            obs_lon, obs_lat = obs.isel(time=i).lon.values, obs.isel(time=i).lat.values
            if i < len(traj_mod.time.values) - traj_duration_plot_int:
                traj = traj_mod.isel(trajectory=i, time=slice(i, i + traj_duration_plot_int))
                lons, lats = traj.lon.values, traj.lat.values
                lons, lats = np.insert(lons, 0, obs_lon), np.insert(lats, 0, obs_lat)
                ax.plot(lons, lats, COLORS[i_mod], linewidth=0.5, transform=ccrs.PlateCarree(),
                        label=mod['name'])
            else:
                traj = traj_mod.isel(trajectory=i)
                traj = traj.where(traj.lon < 1e+30, drop=True)
                ax.plot(traj.lon, traj.lat, COLORS[i_mod], linewidth=0.5,
                        transform=ccrs.PlateCarree(), label=mod['name'])

    # Add legend, show and save figure
    mod_names = [mod["name"] for mod in models]
    handles, labels = plt.gca().get_legend_handles_labels()
    by_label = dict(zip(labels, handles))
    plt.legend(by_label.values(), by_label.keys())
    title, figname = get_title_figname(
        f'Trajectories with frequency {traj_freq_plot}s duration {traj_duration_plot}s',
        observation['xarray_meta'], mod_names, observation['name'])

    f.suptitle(title, fontsize=15, fontweight='bold')

    manage_output(figname, output_path)


def plot_map_current_trajectory(obs, mod, output_path=None):
    """
    Plot the current vectors along the trajectories.
    Parameters
    ----------
    obs : xarray.dataset
        Observation trajectory and current dataset.
    mod : xarray.dataset
        Model trajectory and current dataset.
    output_path : str
        Path where to save the figures.

    """
    logger.info('Current along the trajectories')
    f, ax = figure_1_map(obs["xarray_meta"])

    # Plot Observation current
    obs = obs["xarray_meta"].squeeze()
    ax.quiver(obs.lon, obs.lat, obs.u, obs.v, angles='uv', width=0.001, headwidth=0.001,
              headlength=0.001, headaxislength=0.001, color='b', label=obs.attrs['name'],
              transform=ccrs.PlateCarree())

    # Plot model current
    mod = mod["xarray_meta_coloc"].squeeze()
    ax.quiver(mod.lon, mod.lat, mod.u, mod.v, angles='uv', width=0.001, headwidth=0.001,
              headlength=0.001, headaxislength=0.001, color='r', label=mod.attrs['name'],
              transform=ccrs.PlateCarree())

    # Add legend
    handles, labels = plt.gca().get_legend_handles_labels()
    by_label = dict(zip(labels, handles))
    plt.legend(by_label.values(), by_label.keys())
    title, figname = get_title_figname(f"Current along trajectory", obs, mod.attrs['name'],
                                       obs.attrs['name'])

    f.suptitle(title, fontsize=15, fontweight='bold')

    # Add scale
    add_scale(ax, 1)

    manage_output(figname, output_path)


def plot_difference_trajectory(obs, mod, output_path=None):
    """
    Plot the difference in terms of distance and direction between the model and
     observation trajectories.
    Parameters
    ----------
    obs : xarray.dataset
        Observation trajectory dataset.
    mod : xarray.dataset
        Model trajectory dataset.
    output_path : str
        Path where to save the figures.

    """
    logger.info(f'Difference in terms of distance and direction between '
                f'the model and observation trajectories')
    angles = []
    distances = []
    duree = []

    obs_ini = obs.isel(time=0)
    for i_time, time in enumerate(mod.time):
        duree.append((time.data - obs_ini.time.data).astype('timedelta64[h]'))
        mod_time_mean = mod.isel(time=i_time).mean('trajectory', skipna=True)
        obs_time = obs.sel(time=time, method='nearest')

        # Calculate angles
        angle = angle_between_vectors(obs_ini, obs_time, mod_time_mean)
        angles.append(angle)
        # Calculate distances
        distance = haversine(obs_time.lon, obs_time.lat, mod_time_mean.lon,
                             mod_time_mean.lat) / 1000
        distances.append(distance)

    # Get title and fignames
    title, figname = get_title_figname('Difference trajectory', obs, mod.attrs['name'],
                                       obs.attrs['name'])
    # Plot
    f = plt.figure(figsize=(11, 10))
    f.suptitle(title, x=0.35, fontsize=15, fontweight='bold')
    ax0 = plt.subplot2grid((2, 1), (0, 0))
    ax1 = plt.subplot2grid((2, 1), (1, 0))
    ax0.plot(duree, distances)
    ax0.set_title('Mean distance difference [m]', fontsize=15)
    ax0.set_ylabel(f'm', fontsize=12)
    ax0.set_xlabel(f'Duration (h)', fontsize=12)
    ax1.plot(duree, angles)
    ax1.set_title('Mean direction difference [°]', fontsize=15)
    ax1.set_ylabel(f'°', fontsize=12)
    ax1.set_xlabel(f'Duration (h)', fontsize=12)

    # Add minimap
    ax_mini_map = add_mini_map(f, obs)
    ax_mini_map.plot(obs.lon.values, obs.lat.values, transform=ccrs.PlateCarree())

    manage_output(figname, output_path)


def plot_map_harm(models, observations, output_path=None):
    """
    Plot the map of amplitude, phase and norm of each tidal harmonic.
    Parameters
    ----------
    models: xarray.dataset
        Model harmonic datasets.
    observations : xarray.dataset
        Observation harmonic dataset.
    output_path : str
        Path where to save the figures.

    """
    logger.info('Map of amplitude, phase and norm of each tidal harmonic.')
    for i_wave, wave in enumerate(observations.wave.data):
        if wave in models.wave.data:
            # Get the variables of interest
            observation = observations.sel(wave=wave).squeeze()
            model = models.sel(wave=wave).squeeze()

            # Clean dim order
            model, observation = clean_dim_order(model), clean_dim_order(observation)

            observation['norm'] = np.sqrt(observation['u_a'] ** 2 + observation['v_a'] ** 2)
            model['norm'] = np.sqrt(model['u_a'] ** 2 + model['v_a'] ** 2)

            # Plot current constituents
            for var in ['U', 'V']:
                if var == 'U':
                    ampl, phase = 'u_a', 'u_g'
                elif var == 'V':
                    ampl, phase = 'v_a', 'v_g'
                diff_ampl = model[ampl] - observation[ampl]
                diff_phase = model[phase] - observation[phase]

                # Get the min and max values
                vmax = model[ampl].max()
                vmin = 0
                vmin_diff = -np.nanmax(np.abs(model[ampl]))
                vmax_diff = -vmin_diff

                # Plot the amplitudes and phases
                f, axs = figure_6_maps(model)

                a_mod = axs[0].pcolormesh(model.lon, model.lat, np.abs(model[ampl]), vmin=vmin,
                                          vmax=vmax, cmap='jet', transform=ccrs.PlateCarree(),
                                          shading='nearest')
                g_mod = axs[1].pcolormesh(model.lon, model.lat, model[phase], vmin=-180, vmax=+180,
                                          cmap=cmocean.cm.phase, transform=ccrs.PlateCarree(),
                                          shading='nearest')
                a_obs = axs[2].pcolormesh(observation.lon, observation.lat,
                                          np.abs(observation[ampl]), vmin=vmin, vmax=vmax,
                                          cmap='jet', transform=ccrs.PlateCarree(),
                                          shading='nearest')
                g_obs = axs[3].pcolormesh(observation.lon, observation.lat, observation[phase],
                                          vmin=-180, vmax=+180, cmap=cmocean.cm.phase,
                                          transform=ccrs.PlateCarree(), shading='nearest')
                a_diff = axs[4].pcolormesh(diff_ampl.lon, diff_ampl.lat, diff_ampl, vmin=vmin_diff,
                                           vmax=vmax_diff, cmap=cmocean.cm.balance,
                                           transform=ccrs.PlateCarree(), shading='nearest')
                g_diff = axs[5].pcolormesh(diff_phase.lon, diff_phase.lat, diff_phase, vmin=-180,
                                           vmax=+180, cmap=cmocean.cm.balance,
                                           transform=ccrs.PlateCarree(), shading='nearest')

                # Add the colorbar, titles etc.
                title, figname = get_title_figname(f'{wave} tidal wave {var}', observation,
                                                   model.attrs['name'], observation.attrs['name'])
                f.suptitle(title, fontsize=15, fontweight='bold')

                # colorbar_am
                f.colorbar(a_mod, ax=axs[0], orientation='horizontal', fraction=0.046, pad=0.1)
                # colorbar_ao
                f.colorbar(a_obs, ax=axs[2], orientation='horizontal', fraction=0.046, pad=0.1)
                # colorbar_ad
                f.colorbar(a_diff, ax=axs[4], orientation='horizontal', fraction=0.046, pad=0.1)
                # colorbar_gm
                f.colorbar(g_mod, ax=axs[1], orientation='horizontal', fraction=0.046, pad=0.1)
                # colorbar_go
                f.colorbar(g_obs, ax=axs[3], orientation='horizontal', fraction=0.046, pad=0.1)
                # colorbar_gd
                f.colorbar(g_diff, ax=axs[5], orientation='horizontal', fraction=0.046, pad=0.1)

                manage_output(figname, output_path)

            for var in ['Norm']:
                ampl = 'norm'
                diff_norm = model[ampl] - observation[ampl]

                # Get the min and max values
                vmin = 0
                vmax = model[ampl].max()
                vmin_diff = -np.nanmax(np.abs(model['u_a']))
                vmax_diff = -vmin_diff

                # Plot the amplitudes and phases
                f, axs = figure_3_maps(model, 'harm')

                a_mod = axs[0].pcolormesh(model.lon, model.lat, model[ampl], vmin=vmin, vmax=vmax,
                                          cmap='jet', transform=ccrs.PlateCarree())
                a_obs = axs[1].pcolormesh(observation.lon, observation.lat, observation[ampl],
                                          vmin=vmin, vmax=vmax, cmap='jet',
                                          transform=ccrs.PlateCarree())
                a_diff = axs[2].pcolormesh(diff_norm.lon, diff_norm.lat, diff_norm, vmin=vmin_diff,
                                           vmax=vmax_diff, cmap=cmocean.cm.balance,
                                           transform=ccrs.PlateCarree())

                # Add the colorbar, titles etc.
                title, figname = get_title_figname(f'{wave} tidal wave', observation,
                                                   model.attrs['name'], observation.attrs['name'])
                f.suptitle(title, fontsize=15, fontweight='bold')

                # colorbar_am
                f.colorbar(a_mod, ax=axs[0], orientation='horizontal', fraction=0.046, pad=0.1)
                # colorbar_ao
                f.colorbar(a_obs, ax=axs[1], orientation='horizontal', fraction=0.046, pad=0.1)
                # colorbar_ad
                f.colorbar(a_diff, ax=axs[2], orientation='horizontal', fraction=0.046, pad=0.05)

                manage_output(figname, output_path)


def plot_ellipses_tide_current(models, observations, scales, output_path=None):
    """
    Plot the map with the tidal current ellipses.
    Parameters
    ----------
    models: xarray.dataset
        Model harmonic datasets.
    observations : xarray.dataset
        Observation harmonic dataset.
    scales : list of float
        Scales to adapt the size of the ellipses, one per constituent.
    output_path : str
        Path where to save the figures.

    """
    logger.info('Map with the tidal current ellipses.')
    # One plot per tidal wave
    for i_wave, wave in enumerate(observations.wave.data):
        freq = observations.isel(wave=i_wave).freq.data
        # Define scale
        if scales is not None:
            scale = scales[i_wave]
        else:
            scale = scales

        if freq > 0:
            # If vertical immersions : on plot per immersion (depth)
            if 'depth' in observations.dims:
                for i_depth, _ in enumerate(observations.depth):
                    plot_ellipses_tide_current_generic(observations, models, wave, scale,
                                                       output_path, i_depth=i_depth)

            # If vertical immersions : on plot per immersion (density)
            elif 'dens' in observations.dims:
                for i_dens, _ in enumerate(observations.dens):
                    plot_ellipses_tide_current_generic(observations, models, wave, scale,
                                                       output_path, i_dens=i_dens)
            # If vertical slices : one plot per slice
            elif 'slice' in observations.dims:
                for i_slice, _ in enumerate(observations.slice):
                    plot_ellipses_tide_current_generic(observations, models, wave, scale,
                                                       output_path, i_slice=i_slice)
            else:
                # Get the variables of interest
                plot_ellipses_tide_current_generic(observations, models, wave, scale, output_path)


def plot_ellipses_tide_current_generic(observation, models, wave_name, scale, output_path,
                                       i_dens=None, i_depth=None, i_slice=None):
    freq = observation.sel(wave=wave_name).freq.data
    observation = observation.sel(wave=wave_name)
    models = [mod.sel(wave=wave_name) for mod in models if wave_name in mod.wave.data]
    if i_dens is not None:
        observation = observation.isel(dens=i_dens)
        models = [mod.isel(dens=i_dens) for mod in models]
    elif i_depth is not None:
        observation = observation.isel(depth=i_depth)
        models = [mod.isel(depth=i_depth) for mod in models]
    elif i_slice is not None:
        observation = observation.isel(slice=i_slice)
        models = [mod.isel(slice=i_slice) for mod in models]
    observation = observation.squeeze()

    # Get ellipses scale
    if scale is None:
        scale = get_tide_scale(observation)

    f, ax = figure_1_map(observation)

    if np.size(observation.lon) > 1:
        for i_lon, _ in enumerate(observation.lon):
            obs = observation.isel(lon=[i_lon], lat=[i_lon])
            ax = plot_ellipses_tide_current_figure(freq, ax, obs, 'k', scale)
            for i_mod, mod in enumerate(models):
                mod = mod.isel(lon=[i_lon], lat=[i_lon])
                ax = plot_ellipses_tide_current_figure(freq, ax, mod, COLORS[i_mod], scale)
    else:
        ax = plot_ellipses_tide_current_figure(freq, ax, observation, 'k', scale)
        for i_mod, mod in enumerate(models):
            ax = plot_ellipses_tide_current_figure(freq, ax, mod, COLORS[i_mod], scale)

    # Add legend, show and save figure
    add_scale(ax, scale)
    handles, labels = plt.gca().get_legend_handles_labels()
    by_label = dict(zip(labels, handles))
    plt.legend(by_label.values(), by_label.keys())

    title, figname = get_title_figname(f'Tidal current ellipses {wave_name}', observation,
                                       [mod.attrs['name'] for mod in models],
                                       observation.attrs['name'])

    f.suptitle(title, fontsize=15, fontweight='bold')
    f.subplots_adjust(top=0.85)
    manage_output(figname, output_path)


def get_tide_scale(obs):
    """

    Parameters
    ----------
    obs : xarray.dataset
        Observation tidal current.

    Returns
    -------
    scale : float
        scale factor adapting the ellipses size to the window.
    """
    norm = np.sqrt(obs.u_a ** 2 + obs.v_a ** 2)
    norm = norm.mean()

    indice = 0.15

    scale = float(indice / norm)
    return scale


def plot_ellipses_tide_current_figure(freq, ax, ds, color, scale):
    """
    Plot the figure of the tidal current ellipsis.
    Parameters
    ----------
    freq : float
        frequency of the tidal harmonic.
    ax : figure ax
        ax where to plot the ellipsis.
    ds : xarray.dataset
        dataset from which to plot the ellipsis.
    color :
        color of the ellipsis.
    scale : int
        scale of the ellipsis.

    Returns
    -------
    ax : figure ax
        ax of the figure
    """
    logger.info('Figure of the tidal current ellipsis.')
    # Retrieve the variables
    ds_name = ds.name
    u_a, u_g = ds.u_a.values, ds.u_g.values * np.pi / 180
    v_a, v_g = ds.v_a.values, ds.v_g.values * np.pi / 180

    if np.size(ds.u_a.values) > 1:
        u_a, u_g = u_a[0], u_g[0]
        v_a, v_g = v_a[0], v_g[0]

    if np.size(ds.lon.values) > 1:
        lon, lat = float(ds.lon.values[0]), float(ds.lat.values[0])
    else:
        lon, lat = float(ds.lon.values), float(ds.lat.values)

    # Get the constants for the calculations
    omega = 2 * np.pi / freq

    # Create the arrays to plot the ellipse and display the hours
    time_1 = np.linspace(0, freq, 100)

    u_1 = lon + u_a * np.cos(omega * time_1 + u_g) * scale
    v_1 = lat + v_a * np.cos(omega * time_1 + v_g) * scale

    if not isinstance(u_1[0], np.float64):
        u_1 = u_1[0]
        v_1 = v_1[0]
    # Create the figure
    ax.plot(u_1, v_1, color, transform=ccrs.PlateCarree(), label=f'{ds_name}')
    ax.plot([lon, u_1[0]], [lat, v_1[0]], 'grey', linewidth=0.8, transform=ccrs.PlateCarree())

    return ax


def plot_map_metr_current(flag_interval, flag_slice, models, observation, i_mod, metric, attribute,
                          cmap=cmocean.cm.thermal, vmin=None, vmax=None, dvmin=None, dvmax=None,
                          output_path=None):
    """
    Plot the maps of the current with the comparison metric.
    Parameters
    ----------
    flag_interval : bool
        Indicates if the figures must be plot by intervals or not.
    flag_slice : bool
        Indicates if the figures must be plot by slices or not.
    mod_meta : xarray.DataArray
        Variable from model product, subset along the meta-zone.
    mod_coloc : xarray.DataArray
        Variable from model product, colocated with the observation.
    obs_meta : xarray.DataArray
        Variable from observation product, subset along the meta-zone.
    obs_coloc : xarray.DataArray
        Variable from observation product, colocated with the model.
    metric : str
        Comparison to plot.
    cmap : str
        cmocean colour map for the variable.
    vmin : float
       min colour value of variable to plot.
    vmax : float
       max colour value of variable to plot.
    dvmin : float
       min comparison value of variable to plot.
    dvmax : float
       max comparison value of variable to plot.
    output_path :
        Path where to save the figures.
    """
    logger.info('Maps of the current with the comparison metric.')

    # Get the model and observation variables
    obs_meta = observation['xarray_meta']
    obs_coloc = observation['xarray_meta_coloc'][i_mod]
    mod_meta = models[i_mod]['xarray_meta']
    mod_coloc = models[i_mod]['xarray_meta_coloc']

    if attribute == "current":
        var_norm = 'norm'
    elif attribute == "current_res":
        var_norm = 'norm_res'

    # Get the dimensions on which the stats are calculated
    list_dims_mean = []
    if 'idx_time' in mod_coloc.dims:
        list_dims_mean.append('idx_time')
    # Calculate the variables to plot
    if metric == "difference":
        if flag_interval is True:
            raise Exception(
                "Oops, pour utiliser cette carte de métrique, vous ne devriez pas fournir "
                "une spécification d'intervalles successifs dans votre meta-zone")

        comparison = mod_coloc - obs_coloc

    elif metric == "bias":
        if flag_interval is False and flag_slice is False:
            raise Exception("Oops, pour utiliser cette carte de métrique, vous devriez fournir "
                            "une spécification d'intervalles temporels "
                            "ou de tranches verticales dans votre meta-zone")

        obs_coloc = obs_coloc.mean(list_dims_mean)
        obs_meta = obs_meta.mean(list_dims_mean)
        mod_coloc = mod_coloc.mean(list_dims_mean)
        mod_meta = mod_meta.mean(list_dims_mean)
        comparison = mod_coloc - obs_coloc

    elif metric == "RMSE":
        if flag_interval is False and flag_slice is False:
            raise Exception("Oops, pour utiliser cette carte de métrique, vous devriez fournir"
                            " une spécification d'intervalles "
                            "temporels ou de tranches verticales dans votre meta-zone")
        comparison = calculation.rmse_generic(obs_coloc[var_norm], mod_coloc[var_norm],
                                              list_dims_mean)
        obs_coloc = obs_coloc.std(list_dims_mean)
        obs_meta = obs_meta.std(list_dims_mean)
        mod_coloc = mod_coloc.std(list_dims_mean)
        mod_meta = mod_meta.std(list_dims_mean)

    elif metric == "RMSEc":
        if flag_interval is False and flag_slice is False:
            raise Exception("Oops, pour utiliser cette carte de métrique, vous devriez fournir "
                            "une spécification d'intervalles "
                            "temporels ou de tranches verticales dans votre meta-zone")
        comparison = calculation.rmse_center_generic(obs_coloc[var_norm], mod_coloc[var_norm],
                                                     list_dims_mean)
        obs_coloc = obs_coloc.std(list_dims_mean)
        obs_meta = obs_meta.std(list_dims_mean)
        mod_coloc = mod_coloc.std(list_dims_mean)
        mod_meta = mod_meta.std(list_dims_mean)

    # Plot the values
    if metric == "difference":
        if len(mod_coloc.time) == 1:
            # Get the title
            title, figname = get_title_figname(f'Map {metric}', obs_coloc[var_norm],
                                               mod_coloc.attrs['name'], obs_coloc.attrs['name'])
            # Plot, save and display
            _, axs = plot_map_metr_figure(obs_meta[var_norm], mod_meta[var_norm],
                                          obs_coloc[var_norm], mod_coloc[var_norm],
                                          comparison[var_norm], vmin, vmax, cmap, title, metric,
                                          dvmin=dvmin, dvmax=dvmax)
            add_current_arrows(axs, obs_meta, obs_coloc, mod_meta, mod_coloc, attribute)

            manage_output(figname, output_path)

        else:
            for i_time, time in enumerate(mod_coloc.time):
                # Get the title
                title, figname = get_title_figname(f'Map {metric}',
                                                   obs_coloc[var_norm].isel(time=i_time),
                                                   mod_coloc.attrs['name'], obs_coloc.attrs['name'])

                # Plot
                f, axs = plot_map_metr_figure(obs_meta[var_norm].sel(time=time, method='nearest'),
                                              mod_meta[var_norm].sel(time=time, method='nearest'),
                                              obs_coloc[var_norm].isel(time=i_time),
                                              mod_coloc[var_norm].isel(time=i_time),
                                              comparison[var_norm].isel(time=i_time), vmin, vmax,
                                              cmap, title, metric, dvmin=dvmin, dvmax=dvmax)
                add_current_arrows(axs, obs_meta.sel(time=time, method='nearest'),
                                   obs_coloc.isel(time=i_time),
                                   mod_meta.sel(time=time, method='nearest'),
                                   mod_coloc.isel(time=i_time), attribute)

                manage_output(figname, output_path)

    else:
        if flag_interval:
            for i_inter, _ in enumerate(mod_coloc.interval):
                # Plot
                if metric in ['RMSE', 'RMSEc']:
                    i_inter_obs, i_inter_mod = get_index_interval(i_inter, obs_meta, mod_meta)
                    title, figname = get_title_figname(f'Map {metric}', obs_meta[var_norm].isel(
                        interval=i_inter_obs), mod_coloc.attrs['name'], obs_coloc.attrs['name'])
                    f, axs = plot_map_metr_figure(obs_meta[var_norm].isel(interval=i_inter_obs),
                                                  mod_meta[var_norm].isel(interval=i_inter_mod),
                                                  obs_coloc[var_norm].isel(interval=i_inter),
                                                  mod_coloc[var_norm].isel(interval=i_inter),
                                                  comparison.isel(interval=i_inter), vmin, vmax,
                                                  cmap, title, metric, dvmin=dvmin, dvmax=dvmax)
                else:
                    i_inter_obs, i_inter_mod = get_index_interval(i_inter, obs_meta, mod_meta)
                    title, figname = get_title_figname(f'Map {metric}', obs_meta[var_norm].isel(
                        interval=i_inter_obs), mod_coloc.attrs['name'], obs_coloc.attrs['name'])
                    f, axs = plot_map_metr_figure(obs_meta[var_norm].isel(interval=i_inter_obs),
                                                  mod_meta[var_norm].isel(interval=i_inter_mod),
                                                  obs_coloc[var_norm].isel(interval=i_inter),
                                                  mod_coloc[var_norm].isel(interval=i_inter),
                                                  comparison[var_norm].isel(interval=i_inter), vmin,
                                                  vmax, cmap, title, metric, dvmin=dvmin,
                                                  dvmax=dvmax)
                if metric == 'bias':
                    i_inter_obs, i_inter_mod = get_index_interval(i_inter, obs_meta, mod_meta)
                    title, figname = get_title_figname(f'Map {metric}', obs_meta[var_norm].isel(
                        interval=i_inter_obs), mod_coloc.attrs['name'], obs_coloc.attrs['name'])
                    add_current_arrows(axs, obs_meta.isel(interval=i_inter_obs),
                                       obs_coloc.isel(interval=i_inter),
                                       mod_meta.isel(interval=i_inter_mod),
                                       mod_coloc.isel(interval=i_inter), attribute)

                manage_output(figname, output_path)
        # no interval
        else:
            title, figname = get_title_figname(f'Map {metric}', obs_meta[var_norm],
                                               mod_coloc.attrs['name'], obs_coloc.attrs['name'])
            # Plot
            f, axs = plot_map_metr_figure(obs_meta[var_norm], mod_meta[var_norm],
                                          obs_coloc[var_norm], mod_coloc[var_norm],
                                          comparison[var_norm], vmin, vmax, cmap, title, metric,
                                          dvmin=dvmin, dvmax=dvmax)
            if metric == 'bias':
                add_current_arrows(axs, obs_meta, obs_coloc, mod_meta, mod_coloc, attribute)
            # Save and display
            manage_output(figname, output_path)


def add_current_arrows(axs, obs_meta, obs_coloc, mod_meta, mod_coloc, attribute, nb_vect=50):
    """
    Add the current vectors to the plot.
    Parameters
    ----------
    axs : list
        list of the axes where to add the vectors.
    obs_meta : xarray.DataArray
        Variable from observation product, subset along the meta-zone.
    obs_coloc : xarray.DataArray
        Variable from observation product, colocated with the model.
    mod_meta : xarray.DataArray
        Variable from model product, subset along the meta-zone.
    mod_coloc : xarray.DataArray
        Variable from model product, colocated with the observation.
    nb_vect : int
        Number of arrow vectors to plot.
    Returns
    -------
    axs : list
        list of the axes where the vectors were added.

    """
    logger.info('Current vectors')
    if attribute == "current":
        var_u, var_v = 'u', 'v'
    elif attribute == "current_res":
        var_u, var_v = 'u_res', 'v_res'

    # Squeeze
    obs_meta, obs_coloc = clean_dim_order(obs_meta), clean_dim_order(obs_coloc)
    mod_meta, mod_coloc = clean_dim_order(mod_meta), clean_dim_order(mod_coloc)

    for i_ds, ds in enumerate([obs_meta, obs_coloc, mod_meta, mod_coloc]):
        if 'lon' in ds.dims:
            dens = int(len(ds.lon.values) / nb_vect)
            dens = max(dens, 1)

            indexes_dens_lon = np.arange(0, len(ds.lon), dens)
            indexes_dens_lat = np.arange(0, len(ds.lat), dens)
            ds_dens = ds.isel(lon=indexes_dens_lon, lat=indexes_dens_lat)
            axs[i_ds].quiver(ds_dens.lon.values, ds_dens.lat.values, ds_dens[var_u].values,
                             ds_dens[var_v].values, transform=ccrs.PlateCarree())
        elif 'x' in ds.dims:
            dens = int(len(ds.x.values) / nb_vect)
            dens = max(dens, 1)
            indexes_dens_x = np.arange(0, len(ds.x), dens)
            indexes_dens_y = np.arange(0, len(ds.y), dens)
            ds_dens = ds.isel(x=indexes_dens_x, y=indexes_dens_y)
            axs[i_ds].quiver(ds_dens.lon.values, ds_dens.lat.values, ds_dens[var_u].values,
                             ds_dens[var_v].values, transform=ccrs.PlateCarree())

    return axs


def plot_ts_metr_point(models, observation, flag_interval, flag_slice, output_path=None):
    """
    Plot punctual time series of model and observation and the associated metric.
    Parameters
    ----------
    models : dict
        Dictionary with the model dataarrays.
    observation : dict
        Dictionary with the observations dataarrays.
    metric
    flag_interval : bool
        Indicates if the figures must be plot by intervals or not.
    flag_slice : bool
        Indicates if the figures must be plot by slices or not.
    output_path : str
        path where to save the figure.

    """
    logger.info('Punctual time series of model and observation and the associated metric.')
    obs_meta = observation["xarray_meta"]

    # all data are going to be colocated on the same bases, we can select lon lat on the first one
    obs_coloc_base = observation["xarray_meta_coloc"][0]
    longitudes, latitudes = obs_coloc_base.lon, obs_coloc_base.lat

    list_dims_mean = []

    if flag_interval:
        list_dims_mean.append('idx_time')
    if flag_slice:
        if 'depth' in obs_coloc_base.dims:
            list_dims_mean.append('idx_depth')
        elif 'dens' in obs_coloc_base.dims:
            list_dims_mean.append('idx_dens')
    if 'depth' in obs_coloc_base.dims and len(obs_coloc_base.depth) > 1:
        list_dims_mean.append('depth')
    elif 'dens' in obs_coloc_base.dims and len(obs_coloc_base.dens) > 1:
        list_dims_mean.append('dens')
    logging.info(f'The statistics are calculated on the following dimensions: {list_dims_mean}')

    # Get variable name and unit
    _, var_unit = find_var_title(obs_meta)

    for index_lon, longitude in enumerate(longitudes):
        latitude = latitudes[index_lon]
        if flag_interval:
            f, axs = figure_5lin_ts()

            obs_mean = obs_coloc_base.isel(lat=index_lon, lon=index_lon).mean(
                list_dims_mean).squeeze()
            obs_std = obs_coloc_base.isel(lat=index_lon, lon=index_lon).std(
                list_dims_mean).squeeze()
            time_coloc = obs_mean.interval

            axs[0].plot(time_coloc, obs_mean, 'k-o', label=f'{observation["name"]} ')
            f.autofmt_xdate(rotation=5)
            axs[2].plot(time_coloc, obs_std, 'k-o', label=f'{observation["name"]} ')

            for i, mod in enumerate(models):
                mod_coloc = mod["xarray_meta_coloc"].isel(lat=index_lon, lon=index_lon).squeeze()
                obs_coloc = observation["xarray_meta_coloc"][i].isel(lat=index_lon,
                                                                     lon=index_lon).squeeze()
                # MOYENNES
                mod_mean = mod_coloc.mean(list_dims_mean)
                axs[0].plot(time_coloc, mod_mean, '-o', label=f'{mod["name"]}')

                # BIAIS
                biais = mod_mean - obs_mean
                axs[1].plot(time_coloc, biais, '-o', label=f'{mod["name"]}')

                # ECART-TYPE
                mod_std = mod_coloc.std(list_dims_mean)
                axs[2].plot(time_coloc, mod_std, '-o', label=f'{mod["name"]}')

                # RMSE
                rmse = calculation.rmse_generic(obs_coloc, mod_coloc, list_dims_mean)
                axs[3].plot(time_coloc, rmse, '-o', label=f'{mod["name"]}')

                # RMSE CENTREE
                rmse_centree = calculation.rmse_center_generic(obs_coloc, mod_coloc, list_dims_mean)
                axs[4].plot(time_coloc, rmse_centree, '-o',
                            label=f'Centered RMSE : {observation["name"]}  {mod["name"]} ')
                axs[0].legend(loc=0)  # Demande de Mogan
            # Set labels and titles
            for ax in axs:
                ax.set_ylabel(f'{var_unit}')

            mod_names = [mod['name'] for mod in models]
            title, figname = get_title_figname('Metric statistics', obs_coloc, mod_names,
                                               observation['name'])

            f.suptitle(title, x=0.4, fontsize=15, fontweight='bold')

            # Rotate x labels
            for label in ax.get_xticklabels():
                label.set_rotation(25)

            # Change x interval labels
            modify_interval_label(axs[4])

        else:  # No flag interval : difference only

            f, axs = figure_2lin_ts()

            obs_0 = observation["xarray_meta_coloc"][0].isel(lat=index_lon, lon=index_lon).squeeze()
            time_coloc = obs_0.time
            axs[0].plot(time_coloc, obs_0, 'k', label=f'{observation["name"]}')
            f.autofmt_xdate(rotation=5)

            for i, mod in enumerate(models):
                mod_coloc = mod["xarray_meta_coloc"].isel(lat=index_lon, lon=index_lon).squeeze()
                obs_coloc = observation["xarray_meta_coloc"][i].isel(lat=index_lon,
                                                                     lon=index_lon).squeeze()

                # DIFFERENCE
                comparison = mod_coloc.data - obs_coloc.data
                axs[0].plot(time_coloc, mod_coloc, label=f'{mod["name"]} ')
                axs[1].plot(time_coloc, comparison, label=f'{mod["name"]} ')

                # Set title and legend
                axs[0].legend(loc=0)
                mod_names = [mod['name'] for mod in models]
                title, figname = get_title_figname('Metric difference', obs_coloc, mod_names,
                                                   observation['name'])

                f.suptitle(title, x=0.25, fontsize=14, fontweight='bold')

        # MINI-MAP
        ax_mini_map = add_mini_map(f, obs_coloc_base)
        ax_mini_map.scatter(longitudes, latitudes, 30, 'k', transform=ccrs.PlateCarree())
        ax_mini_map.scatter(longitude, latitude, 90, marker='*', c='yellow', edgecolors='black',
                            transform=ccrs.PlateCarree())

        manage_output(figname, output_path)


def plot_variable_3d(models, observation, cmap=cmocean.cm.thermal, vmin=None, vmax=None, dvmin=None,
                     dvmax=None, output_path=None):
    """
    Plot 3D variable section difference between observation and model.
    Parameters
    ----------
    models : dict of DataArray
        variables from model products.
    observation : dict of DataArray
        variables from observation products.
    cmap : str
        cmocean colour map for the variable.
    vmin : float
       min colour value of variable to plot.
    vmax : float
       max colour value of variable to plot.
    dvmin : float
        Minimum value of the comparison colorbar.
    dvmax : float
        Maximum value of the comparison colorbar.
    output_path :
        Path where to save the figures.
    """
    logger.info('3D variable section difference between observation and model.')
    if isinstance(observation["xarray_meta_coloc"][0], xr.DataArray):
        for i_mod, mod in enumerate(models):
            obs_meta_coloc = observation["xarray_meta_coloc"][i_mod].assign_attrs(
                {'name': observation['name']})
            mod_meta_coloc = mod["xarray_meta_coloc"].assign_attrs({'name': mod['name']})
            plot_variable_3d_figure(obs_meta_coloc, mod_meta_coloc, vmin, vmax, dvmin, dvmax, cmap,
                                    output_path)
    else:
        for var in list(observation["xarray_meta"].keys()):
            var_mod = var
            for i_mod, mod in enumerate(models):
                obs_meta_coloc = observation["xarray_meta_coloc"][i_mod][var].assign_attrs(
                    {'name': observation['name']})
                mod_meta_coloc = mod["xarray_meta_coloc"][var_mod].assign_attrs(
                    {'name': mod['name']})
                plot_variable_3d_figure(obs_meta_coloc, mod_meta_coloc, vmin, vmax, dvmin, dvmax,
                                        cmap, output_path)


def plot_variable_3d_figure(obs_meta_coloc, mod_meta_coloc, vmin=None, vmax=None, dvmin=None,
                            dvmax=None, cmap=cmocean.cm.thermal, output_path=None):
    """
    Plot the figure of 3D variable section difference between observation and model.
    Parameters
    ----------
    obs_meta_coloc : xarray.dataset
        Observation dataset colocated.
    mod_meta_coloc : xarray.dataset
        Model dataset colocated.
    cmap : str
        cmocean colour map for the variable.
    vmin : float
       min colour value of variable to plot.
    vmax : float
       max colour value of variable to plot.
    dvmin : float
        Minimum value of the comparison colorbar.
    dvmax : float
        Maximum value of the comparison colorbar.
    output_path :
        Path where to save the figures.

    """
    logger.info('Figure of 3D variable section difference between observation and model.')
    f, axs = figure_3lin_ts()

    # Squeeze
    mod_meta_coloc, obs_meta_coloc = mod_meta_coloc.squeeze(), obs_meta_coloc.squeeze()
    mod_meta_coloc = mod_meta_coloc.transpose('time', 'depth')
    obs_meta_coloc = obs_meta_coloc.transpose('time', 'depth')

    # Select the variables to plot
    diff = mod_meta_coloc.transpose() - obs_meta_coloc.transpose()

    # Drop nans if not all nans
    if not np.isnan(obs_meta_coloc.min(skipna=True).data):
        mod_meta_coloc = mod_meta_coloc.dropna('time', 'all')
        obs_meta_coloc = obs_meta_coloc.dropna('time', 'all')
        diff = diff.dropna('time', 'all')

    # Get min/max colobar values
    vmin, vmax, dvmin, dvmax, cmap, _ = get_min_max_values(vmin, vmax, obs_meta_coloc, diff,
                                                           'difference', dvmin, dvmax, cmap)

    # Plot the graphs
    im_obs = axs[0].pcolormesh(obs_meta_coloc.time, obs_meta_coloc.depth,
                               obs_meta_coloc.transpose().values, vmin=vmin, vmax=vmax, cmap=cmap)
    im_mod = axs[1].pcolormesh(mod_meta_coloc.time, mod_meta_coloc.depth,
                               mod_meta_coloc.transpose().values, vmin=vmin, vmax=vmax, cmap=cmap)
    im_diff = axs[2].pcolormesh(mod_meta_coloc.time, mod_meta_coloc.depth, diff, vmin=dvmin,
                                vmax=dvmax, cmap=cmocean.cm.balance)

    # Reverse y axes
    for ax in axs:
        ax.invert_yaxis()

    # Add the colorbar, titles etc.
    title, figname = get_title_figname('3D variable', obs_meta_coloc, mod_meta_coloc.attrs['name'],
                                       obs_meta_coloc.attrs['name'])
    _, var_unit = find_var_title(obs_meta_coloc)

    f.suptitle(title, x=0.3, fontsize=17, fontweight='bold')

    colorbar_model = f.colorbar(im_obs, ax=axs[0], fraction=0.046, pad=0.04)
    colorbar_obs = f.colorbar(im_mod, ax=axs[1], fraction=0.046, pad=0.04)
    colorbar_diff = f.colorbar(im_diff, ax=axs[2], fraction=0.046, pad=0.04)

    colorbar_model.set_label(f'{var_unit}', rotation=270, labelpad=10)
    colorbar_obs.set_label(f'{var_unit}', rotation=270, labelpad=10)
    colorbar_diff.set_label(f'{var_unit}', rotation=270, labelpad=10)

    # Add minimap
    ax_mini_map = add_mini_map(f, obs_meta_coloc)
    ax_mini_map.scatter(obs_meta_coloc.lon.values, obs_meta_coloc.lat.values, 30,
                        transform=ccrs.PlateCarree())

    # Add second x axis
    if len(np.unique(obs_meta_coloc.lon.values)) > 1:
        add_second_x_axis(f, axs[2], mod_meta_coloc)

    manage_output(figname, output_path)


def plot_variable_2d(models, observation, output_path=None):
    """
    Plot 2D variable section difference between observation and model

    Parameters
    ----------
    models : dict of DataArray
        variables from model products.
    observation : DataArray
        variables from observations.
    output_path :
        Path where to save the figures.

    """
    logger.info('2D variable section difference between observation and model.')

    if isinstance(observation["xarray_meta_coloc"][0], xr.DataArray):
        for i_mod, mod in enumerate(models):
            obs_meta_coloc = observation["xarray_meta_coloc"][i_mod]
            mod_meta_coloc = mod["xarray_meta_coloc"]
            plot_variable_2d_figure(obs_meta_coloc, mod_meta_coloc, output_path)

    else:
        for var in list(observation["xarray_meta"].keys()):
            for i_mod, mod in enumerate(models):
                obs_meta_coloc = observation["xarray_meta_coloc"][i_mod][var].assign_attrs(
                    {'name': observation['name']})
                mod_meta_coloc = mod["xarray_meta_coloc"][var].assign_attrs({'name': mod['name']})

                plot_variable_2d_figure(obs_meta_coloc, mod_meta_coloc, output_path)


def plot_variable_2d_figure(obs_meta_coloc, mod_meta_coloc, output_path=None):
    """
    Plot 2d figure.
    Parameters
    ----------
    obs_meta_coloc : xarray.dataset
        Observation dataset.
    mod_meta_coloc : xarray.dataset
        Observation dataset.
    var : str
        variable to plot.
    output_path : str
        Path where to save the figures.

    """
    logger.info('2D figure, time series')
    # Squeeze
    mod_meta_coloc, obs_meta_coloc = mod_meta_coloc.squeeze(), obs_meta_coloc.squeeze()

    # Create the plot
    f, axs = figure_2lin_ts()
    diff = mod_meta_coloc.transpose().values - obs_meta_coloc.transpose().values

    # Plot the graphs
    # Obs
    axs[0].plot(obs_meta_coloc.time, obs_meta_coloc.transpose().values, label='Observation')
    # Mod
    axs[0].plot(mod_meta_coloc.time, mod_meta_coloc.transpose().values, label='Model')
    # Diff
    axs[1].plot(mod_meta_coloc.time, diff)

    # Add the colorbar, titles etc.
    title, figname = get_title_figname("2D variable", obs_meta_coloc, mod_meta_coloc.attrs['name'],
                                       obs_meta_coloc.attrs['name'])
    f.suptitle(title, x=0.3, fontsize=17, fontweight='bold')

    # Add minimap
    ax_mini_map = add_mini_map(f, obs_meta_coloc)
    ax_mini_map.scatter(obs_meta_coloc.lon, obs_meta_coloc.lat, 30, transform=ccrs.PlateCarree())

    # Add legend
    axs[0].legend(loc=5)

    # Add second x axis
    if len(np.unique(obs_meta_coloc.lon.values)) > 1:
        add_second_x_axis(f, axs[1], mod_meta_coloc)

    manage_output(figname, output_path)


def create_harmonic_table(models, observations, output_path):
    """
    Create a table per tidal wave and per current constituent(u & v) with,
    for each depth, the amplitude and phase of
    the observation and the model and their differences
    Parameters
    ----------
    models : xarray.dataset
        Model dataset.
    observations : xarray.dataset
        Observation dataset.
    output_path : str
        Path where to save the figures.

    """
    logger.info('Create a table per tidal wave and per current constituent(u & v) with, for each ')
    logger.info(
        'depth, the amplitude and phase of the observation and the model and their differences')
    tide_tool = observations.attrs['tide_tool']
    for i_wave, wave_name in enumerate(observations.wave):
        wave_name = wave_name.data
        if wave_name in list(models.wave):
            # Get the variables of interest
            obs = observations.sel(wave=wave_name)
            mod = models.sel(wave=wave_name)
            diff = mod - obs

            # Plot current constituents
            for var in ['U', 'V']:
                if var == 'U':
                    ampl, phase = 'u_a', 'u_g'
                elif var == 'V':
                    ampl, phase = 'v_a', 'v_g'
                filename = f'{wave_name}_{var}_harm_table_{tide_tool}_{obs.lon.data[0]}_{obs.lat.data[0]}.csv'
                logger.info('Saving :: %s', filename)
                harmonic_table_file = open(os.path.join(output_path, filename), 'a')
                harmonic_table_file.write(
                    f'{wave_name} tidal wave - {var} current constituent - {tide_tool} librairy\n')
                harmonic_table_file.write(
                    f'Model : {mod.name} ; Analysis period : {mod.analysis_period}\n')
                harmonic_table_file.write(f'Observation : {obs.name} ; '
                                          f'Analysis period : {obs.analysis_period}\n')

                if 'depth' in obs.dims:
                    harmonic_table_file.write(f'Depth ; Ampl. obs ; Ampl. mod ; Ampl. diff. ; '
                                              f'Phase obs ; Phase mod ; Phase diff \n')
                    for i_depth, depth in enumerate(obs.depth):
                        obs_depth = obs.sel(depth=depth, method='nearest')
                        mod_depth = mod.sel(depth=depth, method='nearest')
                        diff_depth = diff.sel(depth=depth, method='nearest')
                        harmonic_table_file.write(f'{depth.values}m ;'
                                                  f'{obs_depth[ampl].values} ;'
                                                  f'{mod_depth[ampl].values} ;'
                                                  f'{diff_depth[ampl].values} ;'
                                                  f'{obs_depth[phase].values} ;'
                                                  f'{mod_depth[phase].values} ; '
                                                  f'{diff_depth[phase].values} \n')
                elif 'slice' in obs.dims:
                    harmonic_table_file.write(f'Slice ; Ampl. obs ; Ampl. mod ; Ampl. diff. ; '
                                              f'Phase obs ; Phase mod ; Phase diff \n')
                    for i_slice, slice in enumerate(obs.slice):
                        harmonic_table_file.write(
                            f'{slice.values}m ; {obs[ampl][i_slice].values} ; '
                            f'{mod[ampl][i_slice].values} ;'
                            f'{diff[ampl][i_slice].values} ; {obs[phase][i_slice].values} ; '
                            f'{mod[phase][i_slice].values} ; {diff[phase][i_slice].values} \n')


def plot_ts_metr_stats(models, observation, flag_interval, flag_slice, output_path=None, plg=None):
    """
    Plot statistical time series of model and observation.

    Parameters
    ----------
    models : dict of DataArray
        Variable from model products
    observation : dict of DataArray
        Variable from observation products
    flag_interval : bool
        Indicates if the figures must be plot by intervals or not.
    flag_slice : bool
        Indicates if the figures must be plot by slices or not.
    output_path : str
        path where to save the figure.
    figname : str
        Figure name.
    plg : list
        Polygon coordinates list to display on the minimap.
    """
    logger.info('Statistical time series of model and observation.')

    obs_coloc_base = observation["xarray_meta_coloc"][0]
    list_dims_mean = []

    # Get the dimensions on which to calculate the statistics
    if flag_interval:
        list_dims_mean.append('idx_time')
    if flag_slice:
        list_dims_mean.append('idx_depth')
    if 'lon' in observation["xarray_meta_coloc"][0].dims:
        list_dims_mean.append('lon')
        list_dims_mean.append('lat')
    if 'instr' in observation["xarray_meta_coloc"][0].dims:
        list_dims_mean.append('instr')
    if 'depth' in obs_coloc_base.dims and len(obs_coloc_base.depth) > 1:
        list_dims_mean.append('depth')
    elif 'dens' in obs_coloc_base.dims and len(obs_coloc_base.dens) > 1:
        list_dims_mean.append('dens')
    elif 'z' in obs_coloc_base.dims and len(obs_coloc_base.z) > 1:
        list_dims_mean.append('z')

    logger.info('The statistics are calculated on the following dimensions:')
    logger.info(f'{list_dims_mean}')

    # Case vertical slices
    if flag_slice:
        for idx_slice, _ in enumerate(observation["xarray_meta_coloc"][0].slice):
            # Plot mean and std for observation (plotted only once)
            obs_mean = obs_coloc_base.isel(slice=idx_slice).mean(list_dims_mean,
                                                                 skipna=True).squeeze()
            obs_std = obs_coloc_base.isel(slice=idx_slice).std(list_dims_mean,
                                                               skipna=True).squeeze()

            f, axs = figure_5lin_ts()
            f.autofmt_xdate(rotation=5)
            if flag_interval:
                time_coloc = obs_mean.interval.values
            else:
                time_coloc = obs_mean.time.values

            axs[0].plot(time_coloc, obs_mean, '-o', c='k', ms=0.2, label=f'{observation["name"]} ')
            axs[2].plot(time_coloc, obs_std, '-o', c='k', ms=0.2, label=f'{observation["name"]} ')
            for i, mod in enumerate(models):
                mod_coloc = mod["xarray_meta_coloc"].isel(slice=[idx_slice]).assign_attrs(
                    {'name': mod['name']})
                obs_coloc = observation["xarray_meta_coloc"][i].isel(
                    slice=[idx_slice]).assign_attrs({'name': observation['name']})

                plot_ts_metr_stats_figure(f, axs, time_coloc, mod_coloc, obs_coloc, list_dims_mean,
                                          plg)
            # Change x interval labels
            if flag_interval:
                modify_interval_label(axs[4])

            # Set title and save
            mod_name = [mod['name'] for mod in models]
            title, figname = get_title_figname(
                f'Time series metrics on {list_dims_mean} dimensions', obs_coloc, mod_name,
                observation['name'])
            f.suptitle(title, x=0.4, fontsize=15, fontweight='bold')
            manage_output(figname, output_path)

    # Case no vertical slices
    else:
        # Plot mean and std for observation (plotted only once)
        obs_mean = obs_coloc_base.mean(list_dims_mean, skipna=True).squeeze()
        obs_std = obs_coloc_base.std(list_dims_mean, skipna=True).squeeze()
        if flag_interval:
            time_coloc = obs_mean.interval.values
        else:
            time_coloc = obs_mean.time.values

        f, axs = figure_5lin_ts()
        f.autofmt_xdate(rotation=5)

        axs[0].plot(time_coloc, obs_mean, '-o', c='k', ms=0.2, label=f'{observation["name"]} ')
        axs[2].plot(time_coloc, obs_std, '-o', c='k', ms=0.2, label=f'{observation["name"]} ')

        for i, mod in enumerate(models):
            mod_coloc = mod["xarray_meta_coloc"].assign_attrs({'name': mod['name']})
            obs_coloc = observation["xarray_meta_coloc"][i].assign_attrs(
                {'name': observation['name']})
            plot_ts_metr_stats_figure(f, axs, time_coloc, mod_coloc, obs_coloc, list_dims_mean, plg)

        # Change x interval labels
        if flag_interval:
            modify_interval_label(axs[4])

        # Add title and save fig
        mod_name = [mod['name'] for mod in models]
        title, figname = get_title_figname(f'Time series metrics on {list_dims_mean} dimensions',
                                           obs_coloc, mod_name, observation['name'])
        f.suptitle(title, x=0.4, fontsize=15, fontweight='bold')
        manage_output(figname, output_path)


def plot_ts_metr_stats_figure(f, axs, time_coloc, mod_coloc, obs_coloc, list_dims_mean, plg):
    """
    Plot the statistical time series figure.
    Parameters
    ----------
    f : figure
        Figure where to plot the times series.
    axs : list af ax
        Axs where to plot the times series.
    time_coloc : array
        Time values.
    mod_coloc : xarray.dataset
        Values of the model.
    obs_coloc : xarray.dataset
        Values of the observation.
    list_dims_mean : list of str
        list of the dimensions on which to calculate the statistics
    plg : list
        Polygon coordinates list to display on the minimap.

    """
    logger.info('Statistical time series figure.')

    # Get product names
    mod_name = mod_coloc.attrs['name']

    # MOYENNES
    mod_mean = mod_coloc.mean(list_dims_mean, skipna=True).squeeze()
    obs_mean = obs_coloc.mean(list_dims_mean, skipna=True).squeeze()
    axs[0].plot(time_coloc, mod_mean, '-o', ms=0.2, label=f'{mod_name}')

    # BIAIS
    biais = (mod_mean - obs_mean).squeeze()
    axs[1].plot(time_coloc, biais, '-o', ms=0.2, label=f'{mod_name}')

    # ECART-TYPE
    mod_std = mod_coloc.std(list_dims_mean, skipna=True).squeeze()
    axs[2].plot(time_coloc, mod_std, '-o', ms=0.2, label=f'{mod_name}')

    # RMSE
    rmse = calculation.rmse_generic(obs_coloc, mod_coloc, list_dims_mean).squeeze()
    axs[3].plot(time_coloc, rmse, '-o', ms=0.2, label=f'{mod_name}')

    # RMSE CENTREE
    rmse_centree = calculation.rmse_center_generic(obs_coloc, mod_coloc, list_dims_mean).squeeze()
    axs[4].plot(time_coloc, rmse_centree, '-o', ms=0.2, label=f'{mod_name}')

    axs[0].legend(loc=0)  # Demande de Morgan
    for ax in axs:
        # ax.legend(loc=0)
        _, var_unit = find_var_title(obs_coloc)
        ax.set_ylabel(f'{var_unit}')

    # add minimap
    ax_mini_map = add_mini_map(f, obs_coloc)
    if 'lon' in list_dims_mean:
        add_plg_minimap(ax_mini_map, obs_coloc, plg)
    else:
        ax_mini_map.scatter(obs_coloc.lon.values, obs_coloc.lat.values, 30,
                            transform=ccrs.PlateCarree())

    # Rotate x labels
    for label in ax.get_xticklabels():
        label.set_rotation(25)


def plot_profile_unique(models, observation, radius, output_path=None):
    """
    Create the unique vertical profiles figures of a variable for feature 2
    Parameters
    ----------
    models : list of dict of xarray.dataset
        Values of the model.
    observation : xarray.dataset
        Values of the observation.
    radius : float
        Radius in which to include the selected observations.
    output_path : str
        Path where to save the figures.

    """
    logger.info('Unique vertical profiles')
    for _, time in enumerate(observation.time):
        # Select the profile
        obs = observation.sel(time=time).squeeze()
        if np.isnan(obs.max(skipna=True)):
            continue

        # Plot the observation profile
        f, ax = figure_1_profile()
        ax.plot(obs.values, -1 * obs.depth.values, '-ok', label=f'{obs.attrs["name"]}')
        for _, mod in enumerate(models):
            # Plot the model profiles
            mod_nearest = mod["xarray_meta"].sel(lon=obs.lon, lat=obs.lat, time=time,
                                                 method='nearest').squeeze()
            ax.plot(mod_nearest.values, -1 * mod_nearest.depth.values, '-^', label=f'{mod["name"]}')

            # Plot the standard deviation
            points = [obs.lon.data], [obs.lat.data]
            time_i = time.values
            mod_buffer = mod["xarray_meta"].sel(time=time_i, method='nearest')
            mod_buffer_std = mod_buffer.meta.horizontal_selection_cloud_dots(points, radius).std(
                'idx_point')
            ax.plot(mod_nearest + mod_buffer_std, -1 * mod_nearest.depth, linewidth=0.01)
            ax.plot(mod_nearest - mod_buffer_std, -1 * mod_nearest.depth, linewidth=0.01)
            ax.fill_betweenx(-1 * mod_nearest.depth.values,
                             (mod_nearest - mod_buffer_std).squeeze(),
                             (mod_nearest + mod_buffer_std).squeeze(), alpha=0.2,
                             label=f'{mod["name"]} +/- std')

        # Add the plot features
        plt.legend()
        var_name, var_unit = find_var_title(obs)
        var_title = f"{var_name} [{var_unit}]"
        ax.set_ylabel('Depth [m]', fontsize=12)
        ax.set_xlabel(var_title, fontsize=12)

        title, figname = get_title_figname(f"Unique profile", obs,
                                           [mod["name"] for mod in models], obs.attrs['name'])
        f.suptitle(title, fontsize=17, fontweight='bold', x=0.35)

        # Add the mini-map
        ax_mini_map = add_mini_map(f, obs)
        ax_mini_map.scatter(obs.lon, obs.lat, 30, 'navy', transform=ccrs.PlateCarree())

        manage_output(figname, output_path)


def plot_profile_multi(models, observation, radius, output_path=None):
    """
    Create the multi vertical profiles figures of a variable for feature 2
    Parameters
    ----------
    models : list of dict of xarray.dataset
        Values of the model.
    observation : xarray.dataset
        Values of the observation.
    radius : float
        Radius of the cricle used to buffer the model around the profile.
    output_path : str
        Path where to save the figures.

    """
    logger.info('Multi vertical profiles')

    for mod in models:
        # Whole period
        linewidth = 0.3
        plot_profile_multi_figure(mod, observation, radius, linewidth, output_path)

        # Each interval
        for i_inter, _ in enumerate(observation.interval):
            obs = observation.isel(interval=[i_inter])
            linewidth = 0.6
            plot_profile_multi_figure(mod, obs, radius, linewidth, output_path)


def plot_profile_multi_figure(mod, observation, radius, linewidth, output_path=None):
    """
    Create the multi vertical profiles figures of a variable for feature 2
    Parameters
    ----------
    models : list of dict of xarray.dataset
        Values of the model.
    observation : xarray.dataset
        Values of the observation.
    radius : float
        Radius of the circle used to buffer the model around the profile.
    linewidth : float
        Linewidth to plot.
    output_path : str
        Path where to save the figures.
    """
    logger.info('Multi vertical profiles')

    # Plot the profiles
    f, ax = figure_1_profile()

    mod_buffer_all_points = []
    #  "en traits fins, tous les profils observés"
    # Flatten data to cover cases with instr or not
    dims = list(observation.dims)
    for dim in ['z', 'depth', 'dens']:
        if dim in dims:
            dims.remove(dim)

    observation = observation.stack(idx_point=dims)

    for i_pt, _ in enumerate(observation.idx_point):
        obs = observation.isel(idx_point=i_pt).squeeze()
        ax.plot(obs.values, -1 * obs.depth, c="k", linewidth=linewidth,
                label=f'{obs.attrs["name"]}')

        # "en traits fins les profils modèles des disques définis
        # et temporellement les plus proches"
        points = [obs.lon.data], [obs.lat.data]
        var = mod["xarray_meta"].name
        time = obs.time.values

        mod_sel = mod["xarray"].sel_var.selection([var]).sel(time=time, method='nearest')[var]

        mod_buffer = mod_sel.meta.horizontal_selection_cloud_dots(points, radius)
        if len(mod_buffer.idx_point) > 0:
            mod_buffer_all_points.append(mod_buffer)
        for i_idx_point, _ in enumerate(mod_buffer.idx_point):
            mod_buffer_idx = mod_buffer.isel(idx_point=[i_idx_point]).squeeze()
            ax.plot(mod_buffer_idx.values, -1 * mod_buffer_idx.depth.values, c="tab:blue",
                    linewidth=linewidth, label=f'{mod["name"]}')

    if 'idx_point' in observation.depth.dims:
        depth = observation.depth.mean('idx_point')
    else:
        depth = observation.depth
    # "en trait épais le profil moyen des observations" + "zone grisée observation"
    add_std_profile(ax, observation, depth, '.3', f'{observation.attrs["name"]} - mean')

    # "en trait épais, le profil moyen modèle (moyenne sur les disques)" + "zone grisée modele"
    # (rapport v4, stephanie demande le plus proche)
    mod_buffer_all_points = xr.concat(mod_buffer_all_points, 'idx_point', combine_attrs="drop")
    add_std_profile(ax, mod_buffer_all_points, mod_buffer_all_points.depth, 'tab:blue',
                    f'{mod["name"]} - nearest')

    #  Add the legend and show figure
    handles, labels = plt.gca().get_legend_handles_labels()
    by_label = dict(zip(labels, handles))
    plt.legend(by_label.values(), by_label.keys())

    var_name, var_unit = find_var_title(observation)
    var_title = f"{var_name} [{var_unit}]"

    ax.set_ylabel('Depth [m]')
    ax.set_xlabel(var_title)

    title, figname = get_title_figname(f'Multi profile', observation, mod['name'],
                                       obs.attrs['name'])
    f.suptitle(title, fontsize=17, fontweight='bold', x=0.35)

    # Add the mini-map
    ax_mini_map = add_mini_map(f, observation)
    ax_mini_map.scatter(mod_buffer_all_points.lon, mod_buffer_all_points.lat, 30, c='tab:blue',
                        transform=ccrs.PlateCarree())
    ax_mini_map.scatter(observation.lon, observation.lat, 30, c="k", transform=ccrs.PlateCarree())

    manage_output(figname, output_path)


def add_std_profile(ax, data, depth, color, name):
    """
    Calculate and plot the mean values and the standard deviation contour
    for the vertival profiles in feature 2
    Parameters
    ----------
    ax : ax
        ax where to plot the standard deviation.
    data : array
        Data on which to calculate the standard deviation.
    depth : array
        Depth values.
    color : str
        Color of the profile to plot.
    name : str
        Name of the model/observation for the title.

    """
    if len(data) > 0:
        mean = data.mean('idx_point').squeeze()
        std = data.std('idx_point').squeeze()

        ax.plot(mean, -1 * depth, c=color, marker='o', linewidth=1.5, label=name)
        ax.fill_betweenx(-1 * depth, mean - std, mean + std, color=color, alpha=0.3, linewidth=0.01,
                         label=f"{name} +/- std")


def plot_diag_ts_multi(models, observation, radius, output_path=None):
    """
    Plot theta - S diagram with several profiles

    Parameters
    ----------
    models : list of dict of DataArray
        Variables from model products.
    observation : DataArray
        Variables profile from the observation.
    radius : float
        Radius of the circle used to buffer the model around the profile.
    output_path : str
        Path where to save the figure
    """
    logger.info('theta - S diagram with several profiles')
    for _, mod in enumerate(models):
        # Plot for the whole period
        vmin, vmax = observation.depth.min(skipna=True).data, observation.depth.max(
            skipna=True).data
        plot_diag_ts_multi_figure(observation, mod, radius, vmin, vmax, output_path)

        # Plot for each interval
        for i_inter, _ in enumerate(observation.interval):
            observation_inter = observation.isel(interval=[i_inter])
            vmin, vmax = observation_inter.depth.min(skipna=True).data, observation_inter.depth.max(
                skipna=True).data
            plot_diag_ts_multi_figure(observation_inter, mod, radius, vmin, vmax, output_path)


def plot_diag_ts_multi_figure(observation, mod, radius, vmin, vmax, output_path):
    """
    Plot the figure of the theta - S diagram with several profiles
    Parameters
    ----------
    mod : DataArray
        Variables from model product.
    observation : DataArray
        Variables profile from the observation.
    radius : float
        Radius of the circle used to buffer the model around the profile.
    vmin : float
       min colour value of variable to plot.
    vmax : float
       max colour value of variable to plot.
    output_path : str
        Path where to save the figure
    """
    logger.info('Theta - S diagram with several profiles')

    f, ax = figure_1_profile()

    # "en traits fins, tous les profils observés"
    sals_mod, ptemps_mod, depths_mod = [], [], []
    for i_inter, _ in enumerate(observation.interval):
        if "idx_time" in observation.dims:
            for i_idx_time, _ in enumerate(observation.idx_time):
                obs = observation.isel(idx_time=[i_idx_time], interval=[i_inter])
                if not np.isnan(obs.sal.max(skipna=True).values):
                    im_obs = ax.scatter(obs.sal.values, obs.ptemp.values, 30, obs.depth.values,
                                        vmin=vmin, vmax=vmax, marker="^", zorder=2,
                                        label=f'{obs.attrs["name"]}', alpha=0.3, cmap='autumn')

                # "en traits fin les profils modèles des disques définis
                # et temporellement les plus proches"
                if 'instr' in obs.dims:
                    for i_instr, _ in enumerate(obs.instr):
                        obs_instr = obs.isel(instr=i_instr)
                        sals_mod, ptemps_mod, depths_mod = get_sals_temps_depths(obs_instr, mod,
                                                                                 radius, sals_mod,
                                                                                 ptemps_mod,
                                                                                 depths_mod)
                else:
                    sals_mod, ptemps_mod, depths_mod = get_sals_temps_depths(obs, mod, radius,
                                                                             sals_mod, ptemps_mod,
                                                                             depths_mod)
        else:
            obs = observation.isel(interval=[i_inter])
            im_obs = ax.scatter(obs.sal.values, obs.ptemp.values, 30, obs.depth.values, vmin=vmin,
                                vmax=vmax, marker="^", zorder=2, label=f'{obs.attrs["name"]}',
                                alpha=0.3, cmap='autumn')

            # "en traits fin les profils modèles des disques définis
            # et temporellement les plus proches"
            if 'instr' in obs.dims:
                for i_instr, _ in enumerate(obs.instr):
                    obs_instr = obs.isel(instr=i_instr)
                    sals_mod, ptemps_mod, depths_mod = get_sals_temps_depths(obs_instr, mod, radius,
                                                                             sals_mod, ptemps_mod,
                                                                             depths_mod)
            else:
                sals_mod, ptemps_mod, depths_mod = get_sals_temps_depths(obs, mod, radius, sals_mod,
                                                                         ptemps_mod, depths_mod)
    im_mod = ax.scatter(sals_mod, ptemps_mod, 25, depths_mod, vmin=vmin, vmax=vmax, marker="o",
                        zorder=1, label=f'{mod["name"]}', alpha=0.4, cmap='summer')

    # "en trait épais, le profil moyen modèle(moyenne sur les disques)"
    sals_mod = np.nanmean(np.array(sals_mod), 0)
    ptemps_mod = np.nanmean(np.array(ptemps_mod), 0)

    im_mod_mean = ax.scatter(sals_mod, ptemps_mod, 50, depths_mod[0], vmin=vmin, vmax=vmax,
                             marker="o", zorder=3, edgecolors="black", linewidth=0.8,
                             label=f'Mean {mod["name"]}', cmap='summer')

    # "en trait épais le profil moyen des observations"
    if 'depth' in observation.coords and 'depth' not in list(
            observation.keys()) and 'depth' not in observation.dims:
        observation = observation.reset_coords('depth', drop=False)
    if "idx_time" in observation.dims:
        obs_mean = observation.mean(["idx_time", 'interval'])
    else:
        obs_mean = observation.mean(['interval'])
    im_obs_mean = ax.scatter(obs_mean.sal.values, obs_mean.ptemp.values, 40, obs_mean.depth.values,
                             vmin=vmin, vmax=vmax, marker="^", zorder=4, edgecolors="black",
                             linewidth=0.6, label=f'Mean {observation.attrs["name"]}',
                             cmap='autumn')

    # Add the plot features
    plt.legend(handles=[im_obs, im_obs_mean, im_mod, im_mod_mean])
    diag_ts_plot_features(f, ax, im_mod_mean, im_obs_mean, mod, observation, output_path)


def get_sals_temps_depths(obs, mod, radius, sals_mod, ptemps_mod, depths_mod):
    points = [obs.lon.data], [obs.lat.data]
    time = obs.time.values[0]
    mod_buffer = mod["xarray"].sel(time=time, method='nearest')
    mod_buffer = mod_buffer.meta.horizontal_selection_cloud_dots(points, radius)
    for i_idx_point, _ in enumerate(mod_buffer.idx_point):
        mod_buffer_idx = mod_buffer.isel(idx_point=[i_idx_point]).squeeze()
        sals_mod.append(mod_buffer_idx.sal.values)
        ptemps_mod.append(mod_buffer_idx.ptemp.values)
        depths_mod.append(mod_buffer_idx.depth.values)
    return sals_mod, ptemps_mod, depths_mod


def plot_diag_ts_unique(models, observation, output_path=None):
    """
    Plot theta - S diagram with unique profiles

    Parameters
    ----------
    models : list of dict of DataArray
        Variables from model products.
    observation : DataArray
        Variables profile from the observation.
    output_path : str
        Path where to save the figure
    """
    logger.info('Theta - S diagram with unique profiles')
    for _, time in enumerate(observation.time):
        obs = observation.sel(time=time).squeeze()
        for _, mod in enumerate(models):
            # Get min/max depth values
            vmin, vmax = obs.depth.min(skipna=True).data, obs.depth.max(skipna=True).data

            # Plot the profile
            f, ax = figure_1_profile()
            im_obs = ax.scatter(obs.sal, obs.ptemp, 30, obs.depth, marker="^", edgecolors="black",
                                linewidth=0.1, label=f'{obs.attrs["name"]}', cmap='autumn',
                                vmin=vmin, vmax=vmax)
            if 'depth' in mod["xarray_meta"].dims:
                mod_nearest = mod["xarray_meta"].sel(lon=obs.lon, lat=obs.lat, depth=obs.depth,
                                                     time=time, method='nearest').squeeze()
            elif 'z' in mod["xarray_meta"].dims:
                mod_nearest = mod["xarray_meta"].sel(lon=obs.lon, lat=obs.lat, z=obs.z, time=time,
                                                     method='nearest').squeeze()
            im_mod = ax.scatter(mod_nearest.sal, mod_nearest.ptemp, 30, mod_nearest.depth,
                                edgecolors="black", linewidth=0.1, label=f'{mod["name"]}',
                                cmap='summer', vmin=vmin, vmax=vmax)

            # Add the plot features
            plt.legend(handles=[im_obs, im_mod])
            diag_ts_plot_features(f, ax, im_mod, im_obs, mod, obs, output_path)


def diag_ts_plot_features(f, ax, im_mod, im_obs, mod, obs, output_path=None):
    """
    Add the plot features to the TS diagrams
    Parameters
    ----------
    f : figure
        figure of the theta-s diagram
    ax : ax
        ax where to add the TS diagramm features
    im_mod : image
        image of the model data
    im_obs : image
        image of the observation data
    mod : xarra.dataset
        model dataset
    obs : xarra.dataset
        observation dataset.
    output_path : str
        Path where to save the figures.

    """
    # Add the colorbar, titles etc.
    title, figname = get_title_figname('Theta-S diagram', obs, mod['name'], obs.attrs['name'])
    f.suptitle(title, x=0.35, fontsize=17, fontweight='bold')

    ax.set_ylabel('Potential temperature [°C]')
    ax.set_xlabel('Salinity [g/kg]')
    colorbar_model = ax.figure.colorbar(im_mod)
    colorbar_obs = ax.figure.colorbar(im_obs)
    colorbar_model.set_label(f'Depth {mod["name"]}(m)', rotation=270, labelpad=10)
    colorbar_obs.set_label(f'Depth {obs.attrs["name"]}(m)', rotation=270, labelpad=10)

    # Density contours from xoa.plot.plot_ts
    (smin, tmin), (smax, tmax) = ax.viewLim.get_points()
    tt = np.linspace(tmin, tmax, 100)
    ss = np.linspace(smin, smax, 100)
    ss, tt = np.meshgrid(ss, tt)
    dd = gsw.sigma0(ss, tt)

    contour = ax.contour(ss, tt, dd, colors='.3', zorder=0)
    ax.clabel(contour)

    # Add the mini-map
    ax_mini_map = add_mini_map(f, obs)
    ax_mini_map.scatter(obs.lon, obs.lat, 30, c='navy', transform=ccrs.PlateCarree())

    manage_output(figname, output_path)


def plot_stick_plots(models, observation, output_path=None):
    """
    Plot stick plots for current data.
    Parameters
    ----------
    models : list of dict of xarray.dataset
        List of the models data.
    observation : xarray.dataset
        Observation current data.
    output_path : str
        Path where to save the figures.

    """
    logger.info('Stick plots for current data')

    obs_base = observation['xarray_meta_coloc'][0]

    # Retrieve current to plot
    if 'u_bc' in obs_base:
        var_u = 'u_bc'
        var_v = 'v_bc'
        var_norm = 'norm_bc'
    elif 'u' in obs_base:
        var_u = 'u'
        var_v = 'v'
        var_norm = 'norm'

    if "depth" not in obs_base.dims and "dens" not in obs_base.dims:
        f, ax = figure_1_stickplot()
        obs = observation['xarray_meta_coloc'][0]
        ax.quiver(obs.time, [[0] * len(obs.time)], obs[var_u], obs[var_v], angles='uv', width=0.001,
                  headwidth=0.001, headlength=0.001, headaxislength=0.001, color='k',
                  label=observation['name'])
        for i_mod, mod in enumerate(models):
            mod = mod['xarray_meta_coloc'].squeeze()
            ax.quiver(mod.time, [[0] * len(mod.time)], mod[var_u], mod[var_v], angles='uv',
                      width=0.001, headwidth=0.001, headlength=0.001, headaxislength=0.001,
                      color=COLORS[i_mod], label=f'{mod.attrs["name"]}')
        # Add legend
        ax.set_ylabel('Current(m/s)')
        handles, labels = plt.gca().get_legend_handles_labels()
        by_label = dict(zip(labels, handles))
        plt.legend(by_label.values(), by_label.keys())

        # Add mini-map
        ax_mini_map = add_mini_map(f, obs)
        ax_mini_map.scatter(obs.lon, obs.lat, 15, c='navy', transform=ccrs.PlateCarree())

        # Add second x axis
        add_second_x_axis(f, ax, obs)

        # Set title
        title, figname = get_title_figname('Stick plot', obs[var_norm],
                                           [mod['name'] for mod in models], observation['name'])

        f.suptitle(title, x=0.3, fontsize=12, fontweight='bold')
        # Save figure
        manage_output(figname, output_path)
    else:
        if 'depth' in observation['xarray_meta_coloc'][0].dims:
            for i_depth, _ in enumerate(observation['xarray_meta_coloc'][0].depth):
                f, ax = figure_1_stickplot()
                obs = observation['xarray_meta_coloc'][0].isel(depth=i_depth)
                ax.quiver(obs.time, [[0] * len(obs.time)], obs[var_u], obs[var_v], angles='uv',
                          width=0.001, headwidth=0.001, headlength=0.001, headaxislength=0.001,
                          color='k', label=observation['name'])
                for i_mod, mod in enumerate(models):
                    mod = mod['xarray_meta_coloc'].isel(depth=i_depth).squeeze()
                    ax.quiver(mod.time, [[0] * len(mod.time)], mod[var_u], mod[var_v], angles='uv',
                              width=0.001, headwidth=0.001, headlength=0.001, headaxislength=0.001,
                              color=COLORS[i_mod], label=f'{mod.attrs["name"]}')
                # Add legend
                ax.set_ylabel('Current(m/s)')
                handles, labels = plt.gca().get_legend_handles_labels()
                by_label = dict(zip(labels, handles))
                plt.legend(by_label.values(), by_label.keys())

                # Add mini-map
                ax_mini_map = add_mini_map(f, obs)
                ax_mini_map.scatter(obs.lon, obs.lat, 15, c='navy', transform=ccrs.PlateCarree())

                # Add second x axis
                add_second_x_axis(f, ax, obs)

                # Set title
                title, figname = get_title_figname('Stick plot', obs,
                                                   [mod['name'] for mod in models],
                                                   observation['name'])

                f.suptitle(title, fontsize=12, fontweight='bold')
                # Save figure
                manage_output(figname, output_path)

        elif 'dens' in observation['xarray_meta_coloc'][0].dims:
            for i_dens, _ in enumerate(observation['xarray_meta_coloc'][0].dens):
                f, ax = figure_1_stickplot()
                obs = observation['xarray_meta_coloc'][0].isel(dens=i_dens)
                ax.quiver(obs.time, [[0] * len(obs.time)], obs[var_u], obs[var_v], angles='uv',
                          width=0.001, headwidth=0.001, headlength=0.001, headaxislength=0.001,
                          color='k', label=observation['name'])
                for i_mod, mod in enumerate(models):
                    mod_name = mod.name
                    mod = mod['xarray_meta_coloc'].isel(dens=i_dens).squeeze()
                    ax.quiver(mod.time, [[0] * len(mod.time)], mod[var_u], mod[var_v], angles='uv',
                              width=0.001, headwidth=0.001, headlength=0.001, headaxislength=0.001,
                              color=COLORS[i_mod], label=f'{mod_name}')
                # Add legend
                ax.set_ylabel('Current(m/s)')
                handles, labels = plt.gca().get_legend_handles_labels()
                by_label = dict(zip(labels, handles))
                plt.legend(by_label.values(), by_label.keys())

                # Add mini-map
                ax_mini_map = add_mini_map(f, obs)
                ax_mini_map.scatter(obs.lon, obs.lat, 15, c='navy', transform=ccrs.PlateCarree())

                # Add second x axis
                add_second_x_axis(f, ax, obs)

                # Set title
                title, figname = get_title_figname('Stick plot', obs,
                                                   [mod['name'] for mod in models],
                                                   observation['name'])

                f.suptitle(title, fontsize=12, fontweight='bold')
                # Save figure
                manage_output(figname, output_path)


# Useful functions

def find_var_title(da):
    """
    return the string of the variable corresponding to the variable name in the DaraArray
    Parameters
    ----------
    da : xr.DataArray
        Data array in which the units may be stored

    Returns
    -------
    title : str
        Title of the variable with units.
    """
    # Title
    if 'variable' in da.coords:
        var_name = da.coords['variable'].data
    else:
        var_name = da.name

    if "salinity" in var_name or 'Salinity' in var_name:
        var_name = 'Salinity'
    if "temperature" in var_name or 'Temperature' in var_name:
        var_name = 'Temperature'
    if 'sst' in var_name:
        var_name = 'SST'
    if 'res' in var_name:
        var_name = f"Residual current {var_name.split('_')[0]}"
    if 'bc' in var_name:
        var_name = f"Baroclinic current {var_name.split('_')[0]}"
    if 'geo' in var_name:
        var_name = "Geostrophic current"

    if "units" in da.attrs:
        var_unit = da.attrs['units']
    elif var_name in ['u', 'v', 'norm', "Geostrophic current"]:
        var_unit = 'm/s'
    elif 'dir' in var_name:
        var_unit = '°'
    else:
        var_unit = "N/A"

    return var_name, var_unit


def interval_str_to_date(da_interval):
    """
    Change the string time stamps of the intervals to a list of date times
    Parameters
    ----------
    da_interval : xarray.dataset
        Dataset on which to convert the time stamps

    """
    # change interval names into datetimes
    list_dates_mean = []
    for i in range(len(da_interval.values)):
        name_interval = str(da_interval[i].data).split(' to ')
        name_interval = [np.datetime64(name_interval[0].rstrip(' ')),
                         np.datetime64(name_interval[1].rstrip(' '))]
        date_mean = np.array(name_interval, dtype='datetime64[s]').view('i8').mean().astype(
            'datetime64[s]')
        list_dates_mean.append(date_mean)
        da = xr.DataArray(list_dates_mean, dims='interval')
    return da


def add_second_x_axis(f, ax, mod):
    """
    Add a second x axis to display the longitudes and latitudes.
    Parameters
    ----------
    f
    ax
    mod
    """
    ax2 = ax.twiny()

    # Add some extra space for the second axis at the bottom
    f.subplots_adjust(bottom=0.25)

    nbticks = 6
    new_tick_locations = np.array([i * 1 / nbticks for i in range(nbticks + 1)])

    def tick_function(mod, nbticks=nbticks):
        lons = mod.lon.values
        lats = mod.lat.values

        ticks = [i * math.floor(len(lons) / nbticks) for i in range(nbticks + 1)]
        ticks[-1] = len(lons) - 1
        return [f'{lons[tick]:.3f}E,{lats[tick]:.3f}N' for tick in ticks]

    # Move twinned axis ticks and label from top to bottom
    ax2.xaxis.set_ticks_position("bottom")
    ax2.xaxis.set_label_position("bottom")

    # Offset the twin axis below the host
    ax2.spines["bottom"].set_position(("axes", -0.2))

    # Turn on the frame for the twin axis, but then hide all
    # but the bottom spine
    ax2.set_frame_on(True)
    ax2.patch.set_visible(False)

    ax2.spines["bottom"].set_visible(True)

    ax2.set_xticks(new_tick_locations)
    ax2.set_xticklabels(tick_function(mod))
    ax2.set_xlabel('Lon, Lat')


def get_min_max_values(vmin, vmax, ds, comparison=None, metric=None, dvmin=None, dvmax=None,
                       cmap=None):
    """
    Give the appropriate values for the colorbar.
    Parameters
    ----------
    vmin : float
        Minimum value of the colorbar.
    vmax : float
        Maximum value of the colorbar.
    ds : xarray.dataArray
        Datarray to be displayed.
    comparison :
        Comparison datarray to be displayed.
    metric : str
        Name of the metric.
    dvmin : float
        Minimum value of the comparison colorbar.
    dvmax : float
        Maximum value of the comparison colorbar.

    Returns
    -------
    vmin : float
        Minimum value of the colorbar.
    vmax : float
        Maximum value of the colorbar.
    comparison_vmin : float
        Minimum value of the comparison colorbar.
    comparison_vmax : float
        Maximum value of the comparison colorbar.
    comparison_cmap : float
        Colormap to use for the comparison
    """
    # vmin / vmax
    if vmin is None:
        vmin = ds.min(skipna=True).values
    if vmax is None:
        vmax = ds.max(skipna=True).values

    # dvmin / dvmax / cmap
    if metric in ["difference", "bias"]:
        if dvmin is None:
            dvmin = -abs(np.nanmax(comparison))
        if dvmax is None:
            dvmax = abs(np.nanmax(comparison))
        dcmap = cmocean.cm.balance
    elif metric in ['RMSE', 'RMSEc']:
        if dvmin is None:
            dvmin = 0
        if dvmax is None:
            dvmax = np.nanmax(comparison)
        dcmap = cmocean.cm.amp
    else:
        dvmin = None
        dvmax = None
        dcmap = None

    if 'dir' in ds.name:
        cmap = cmocean.cm.phase

    return vmin, vmax, dvmin, dvmax, cmap, dcmap


def add_scale(ax, scale):
    """
    Add the vector scale to the figure.
    Parameters
    ----------
    ax
    scale

    """
    extent = ax.get_extent(crs=ccrs.PlateCarree())
    lon = extent[0] + (extent[1] - extent[0]) / 10
    lat = extent[2] + (extent[3] - extent[2]) / 15
    lat_txt = extent[2] + (extent[3] - extent[2]) / 25
    ax.plot([lon, lon + 0.1 * scale], [lat, lat], c='k', transform=ccrs.PlateCarree())
    ax.text(lon, lat_txt, '0.1 m.s-1', transform=ccrs.PlateCarree())
    ax.set_extent(extent)
    return ax


def get_index_interval(i_inter, obs_meta, mod_meta):
    """
    Get the index of the interval in the model and observation
    Parameters
    ----------
    i_inter
    obs_meta
    mod_meta

    """
    if i_inter >= len(obs_meta.interval):
        i_inter_obs = len(obs_meta.interval) - 1
    else:
        i_inter_obs = i_inter

    if i_inter >= len(mod_meta.interval):
        i_inter_mod = len(mod_meta.interval) - 1
    else:
        i_inter_mod = i_inter

    return i_inter_obs, i_inter_mod


def modify_interval_label(ax):
    """
    Modifies the labels of the intervals on the figure.
    Parameters
    ----------
    ax
    """
    labels_ini = [label.get_text() for label in ax.get_xticklabels()]
    labels_modif = []
    for lab in labels_ini:
        date_first, date_last = lab.split(' to ')[0], lab.split(' to ')[1]
        if date_first[0:1] == ' ':
            date_first = date_first[1:]
        if date_first[-1:] == ' ':
            date_first = date_first[:-1]
        if date_last[0:1] == ' ':
            date_last = date_last[1:]
        if date_last[-1:] == ' ':
            date_last = date_last[:-1]
        date_first, date_last = np.datetime64(date_first), np.datetime64(date_last)
        date_center = date_first + (date_last - date_first) / 2
        labels_modif.append(np.datetime_as_string(date_center))

    pas = max(1, len(labels_modif) // 15)
    updated_labels = [""] * len(labels_modif)
    updated_labels[::pas] = labels_modif[::pas]
    ax = ax.set_xticklabels(updated_labels)
    return ax
