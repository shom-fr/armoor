import xarray as xr
import pandas
import os

DELTA_BEFORE = 3  # 10  # T0 + the last 10 days
DELTA_AFTER = 0  # 5 + 1  # T0 + the next 5 days (+1 to get all fifth day)
BASE_PATH = "/gpfs/PROJETS/1144-FE_Shom_Outils_validation_et_bulletins/REALISATION/Technique/shared_data/Poste3"


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


def get_arpege_path(t0, periode) -> list:
    """
    get the list of the path where the values of the DELTA (see on top of the file) last days are
    Returns
    -------

    """
    start = t0 - pandas.offsets.Day(DELTA_BEFORE)
    end = t0 + pandas.offsets.Day(DELTA_AFTER)

    paths = list()
    for time in range(-DELTA_AFTER, DELTA_BEFORE):
        for hour in ['00', '06', '12', '18']:
            list_of_folder = [BASE_PATH, "mf", "EURAT01", f'%Y%m%d{hour}']
            for number in ['0', '1', '2', '3', '4', '5', '6']:
                file_name = f'arpege_%Y%m%d{hour}00_000{number}_ana_{periode}.grib'
                path = get_path_day(t0 - pandas.offsets.Day(time), list_of_folder, file_name)
                paths = smart_append(path, paths)
    return paths


def open_file(path_files) -> xr.Dataset:
    return xr.open_mfdataset(path_files,
                             engine='cfgrib',
                             combine='nested',
                             concat_dim='time',
                             filter_by_keys={'typeOfLevel': 'heightAboveGround',
                                             'u': 'u-component_of_wind_height_above_ground',
                                             'v': 'v-component_of_wind_height_above_ground',
                                             'topLevel': 2})


def main():
    print(f'start')
    # paths = get_arpege_path(pandas.to_datetime('2022-03-10'), 'insta')
    # print(f'{paths}')
    print(f'')
    print(f'')
    print(f'')
    simple_path = BASE_PATH + '/mf/EURAT01/2022030618/' + 'arpege_202203061800_0005_ana_insta.grib'
    simple_data = xr.open_mfdataset(simple_path,
                                    engine='cfgrib',
                                    filter_by_keys={'typeOfLevel': 'heightAboveGround',
                                                    'topLevel': 10})
    print(f'{simple_data}')

    # print(f'')
    # print(f'')
    # print(f'')
    # data = open_file(paths)
    # print(data)
    # disk_path = BASE_PATH + "/grib_out/insta2.nc"
    # data.to_netcdf(disk_path)


if __name__ == "__main__":
    main()
