import xarray as xr
import pandas
import os

from matplotlib import pyplot as plt
from matplotlib import colors
import cartopy.crs as ccrs
import cartopy.feature as cfeature
import cmocean

DELTA_BEFORE = 3  # T0 + the last 10 days
DELTA_AFTER = 0  # 5 + 1  # T0 + the next 5 days (+1 to get all fifth day)
BASE_PATH = "/gpfs/PROJETS/1144-FE_Shom_Outils_validation_et_bulletins/REALISATION/Technique/shared_data/Poste3"

SELECTED_TIME = '2022-03-10'


def get_path_day(day, folders, file) -> str:
    """
    generate the path for a specific day
    Parameters
    ----------
    file : file name
    folders : folders
    day : day of the path to create

    Returns
    -------
    path of the chosen day to create
    """
    path = ''
    for folder in folders:
        date = day.strftime(folder)
        path += f"{date}/"
    if file is not None:
        path += day.strftime(file)

    return path


def is_path_unique(path: str, paths: list) -> bool:
    """
    Check if the path is not already in the list of paths
    Parameters
    ----------
    path : path to check
    paths : list of path to check with

    Returns
    -------
    True if the path is unique False otherwise
    """
    return path not in paths if paths else True


def smart_append(path: str, paths: list) -> list:
    """
    Add path if the path is not already in the list and if the path exist
    Parameters
    ----------
    path : path to append
    paths : already added paths

    Returns
    -------
    new list of path
    """
    if is_path_unique(path, paths) and does_the_path_exist(path):
        paths.append(path)

    return paths


def does_the_path_exist(path: str) -> bool:
    """
    Check if the path exist
    Parameters
    ----------
    path : path to check

    Returns
    -------
    True if path exist False otherwise
    """
    return os.path.isfile(path) or os.path.isdir(path)


def get_rivers_paths(t0) -> list:

    list_of_folder = [BASE_PATH, "rivers", "%Y%m%d"]

    paths = list()
    for time in range(-DELTA_AFTER, DELTA_BEFORE):
        path = get_path_day(t0 - pandas.offsets.Day(time), list_of_folder, None)
        paths = smart_append(path, paths)

    final_paths = list()
    for path in paths:
        file_list = os.listdir(path)
        for file in file_list:
            if not file.__contains__('GL_TS_RF_IF'):
                final_paths = smart_append(f'{path}{file}', final_paths)

    # print(f'get_rivers_paths folders   {paths = }')
    #
    # print(f'get_rivers_paths files     {final_path = }')
    # for final_path in final_paths:
    #     print('#@'*200)
    #     print(f'{final_path = }')
    #
    #     print(f'{ xr.open_mfdataset(final_path) = }')
    #     print('@#' * 200)

    final_paths.sort()
    return final_paths

def open_file(path_files) -> xr.Dataset:
    func = "SCHAPI_CMEMS"
    drop_variables_true = {'SCHAPI_CMEMS': ('POSITION_QC', 'TIME_QC', 'DC_REFERENCE')}
    drop_variables = drop_variables_true[func],
    return xr.open_mfdataset(path_files, drop_variables=drop_variables, combine='nested', concat_dim='time')


def visu_runoff(ds):
    """
    Parameters
    ----------
    ds : dataset containing runoff

    Returns
    the path to the png image saved
    -------
    """
    print(f"{ds =}")
    # ds to da # #TODO is it always eastward_wind and northward_wind ?
    da = ds.ro.squeeze()
    # var name
    var_name = "River runoff"
    var_unit = "(m)"

    # plot #
    fig = plt.figure(figsize=(10, 20))
    ax = plt.axes(projection=ccrs.PlateCarree())  # \
    ax.coastlines()
    im0 = ax.pcolor(da.xoa.lon, da.xoa.lat, da, norm=colors.Normalize(), cmap=cmocean.cm.dense,
                    transform=ccrs.PlateCarree())
    cbar = fig.colorbar(im0, ax=ax, fraction=0.046, pad=0.04)  # , fraction=0.046, pad=0.04)
    cbar.set_label(f' {var_name} {var_unit}', rotation=270, labelpad=15)
    ax.set_title(f'{var_name} {var_unit}', fontsize=16, fontweight='bold')

    gl = ax.gridlines(crs=ccrs.PlateCarree(), draw_labels=False,
                      linewidth=1, color='gray', alpha=0.2, linestyle='--')
    gl.left_labels = True
    gl.bottom_labels = True
    ax.add_feature(cfeature.LAND, zorder=1, edgecolor='k')

    plt.show()
    # savefig
    # plt.savefig(f"../../../../shared_output_data/{var_name}.png")

    return None


def main():
    print(f'start')
    paths = get_rivers_paths(pandas.to_datetime('2022-03-10'))
    print(f'{paths}')
    data = open_file(paths)
    data.read.decode()

    print(data)
    # disk_path = BASE_PATH + "/grib_out/rivers.nc"
    # data.to_netcdf(disk_path)
    # ou ? data.sel(time=pandas.to_datetime(SELECTED_TIME), method="nearest")

    data.sel(time=SELECTED_TIME, method="nearest")
    visu_runoff(data)


if __name__ == "__main__":
    main()
