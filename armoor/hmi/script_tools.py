"""
Tools for the script to run smoothly
"""
from pathlib import Path

import numpy as np
import xarray as xr

import xoa

import logging
logger = logging.getLogger(__name__)

def decumulate_data(data, cut_list):
    """

    Parameters
    ----------
    data : cumulated data
    cut_list : list of chunks

    Returns
    -------
    decumulated data
    """
    end_i = 0
    tmp_list = list()

    for i in cut_list:
        start_i = end_i
        end_i = start_i + i

        aux = data[start_i:end_i, :, :]
        diff = np.diff(aux, axis=0)
        conc = np.concatenate((data[start_i:start_i + 1], diff))

        tmp_list.append(conc)

    result = np.concatenate(tmp_list)

    return result



def from_nh_to_1h(data, cumul_time_in_h):
    """

    Parameters
    ----------
    data : data to process
    cumul_time_in_h : list of accumulation times in hour(s)

    Returns
    -------
    decumulated data 1h step
    """

    size_time, size_lat, size_lon = data.shape

    repeated_cumul_lat = np.repeat(np.array([cumul_time_in_h]), size_lat, axis=0)
    repeated_cumul_lat_t = np.transpose(repeated_cumul_lat)

    repeated_cumul_lon = np.repeat(np.array([repeated_cumul_lat_t]), size_lon, axis=0)
    repeated_cumul = np.transpose(repeated_cumul_lon, axes=[1, 2, 0])

    return np.divide(data, repeated_cumul)

def retrieve_raw_paths_names(path_files: list) ->list:
    """

    Parameters
    ----------
    path_files : raw list of paths

    Returns
    -------
    list of raw names looking like : _202203090000_0001 or 202203090000_0001_
    """
    return [path[-33:-15] for path in path_files]

def retrieve_clean_paths_names(raw_names: list) ->list:
    """

    Parameters
    ----------
    raw_names : raw list of names

    Returns
    -------
    clean list of names change from : _* or *_ to *
    """
    clean_name_list = list()

    for path in raw_names:
        if path[0] == '_':
            clean_name_list.append(path[1:])
        elif path[-1] == '_':
            clean_name_list.append(path[:-1])
        else:
            logger.error(f'Unrecognised name  : {path}')

    return sorted(clean_name_list)

def gathered_names(clean_name_list: list) -> dict:
    """

    Parameters
    ----------
    clean_name_list : list of names looking like "reseau_echeance"

    Returns
    -------
    dictionary sorted by "reseau"
    """
    dict_cumul = {}
    for name in clean_name_list:
        reseau, echeance = name.split('_')
        if reseau in dict_cumul:
            dict_cumul[reseau].append(int(echeance))
        else:
            dict_cumul.update({reseau: [int(echeance)]})

    return dict_cumul

def get_cumul_list_to_cut(dict_cumul: dict) -> list:
    """

    Parameters
    ----------
    dict_cumul : dictionary of "reseau" with corresponding "echeances"

    Returns
    -------
    list of size "reseau" fragments
    """
    return [len(dict_cumul[reseau]) for reseau in dict_cumul]

def get_cumul_time_in_h(dict_cumul: dict) -> list:
    """

    Parameters
    ----------
    dict_cumul

    Returns
    -------
    list of decumulated times in hours for each "echeance"
    """
    dict_decumul = dict()
    for key, value in dict_cumul.items():
        dict_decumul.update({key : np.insert(np.diff(value), 0, value[0])})

    return np.concatenate([value for value in dict_decumul.values()])

def get_cumul_info(path_files):
    """

    Parameters
    ----------
    path_files : raw list of paths

    Returns
    -------
    list of size "reseau" fragments
    list of decumulated times in hours for each "echeance"
    """
    name_list = retrieve_raw_paths_names(path_files)
    clean_name_list = retrieve_clean_paths_names(name_list)
    dict_cumul = gathered_names(clean_name_list)

    list_cut = get_cumul_list_to_cut(dict_cumul)
    cumul_time_in_h = get_cumul_time_in_h(dict_cumul)

    return list_cut, cumul_time_in_h

def convert_k_c(data: xr.Dataset) -> xr.Dataset:
    """
    Convert temperature units into Celcius degrees.

    Returns
    -------
    xarray.DataArray
        Data array containing SST in Celcius degrees.
    """
    if 'units' in data.attrs and data.attrs['units'] == 'kelvin':
        logger.info('Converting to Celsius degrees')
        return data - 273.15
    else:
        return data


def create_folder(path: str):
    """
    Create folder without error if folder already exists
    Parameters
    ----------
    path

    Returns
    -------
    None
    """
    Path(path).mkdir(parents=True, exist_ok=True)


def compute_mixed_layer(data: xr.Dataset) -> xr.Dataset:
    """
    Compute the mixed layer depth
    Parameters
    ----------
    data : data containing the attributes to compute the mixed layer depth

    Returns
    -------

    """
    logger.info('computing mixed layer depth')
    logger.warning('Cleanup code when xao is updated')
    # c.f. ...####START line
    # return xoa.thermdyn.mixed_layer_depth(data)
    return mixed_layer_depth(data)


def format_times(times: list) -> list:
    """
    Format time from a list to be able to create filenames with formatted times
    Parameters
    ----------
    times : list of times

    Returns
    -------
    list of times formatted
    """
    new_times = []
    for time in times:
        new_times.append(time.replace(':', 'h'))
    return new_times


def get_t0(times: list, today: str) -> str:
    """
    Get the model's first time step in the production day
    Parameters
    ----------
    times : all model time steps
    today : production day

    Returns
    -------
    first time step of the model in the production day
    """
    t0_forecaster_web_interface = ""
    for time in times:
        if today in time:
            t0_forecaster_web_interface = time
            break
    return t0_forecaster_web_interface


#############################################################################################START
# delete all to  ##..##END once mixed_layer_depth in xoa.thermdyn.mixed_layer_depth available
# i.e. delete : is_temp, is_dens, MLD_METHODS, mixed_layer_depth
def is_temp(da, potential=None):
    """Check if `da` is a temperature-like array.

    Parameters
    ----------
    da: xarray.DataArray
    potential: None, bool
        Consider the temperature to be potential or not.

    Return
    ------
    bool
    """
    cfspecs = xoa.cf.get_cf_specs(da)
    cf_names = []
    if potential is None or potential is False:
        cf_names.append("temp")
    if potential is None or potential is True:
        cf_names.append("ptemp")
    for cf_name in cf_names:
        if cfspecs.match_data_var(da, cf_name):
            return True
    return False


def is_dens(da, potential=None):
    """Check if `da` is a density-like array.

    Parameters
    ----------
    da: xarray.DataArray
    potential: None, bool
        Consider the density to be potential/neutral or not.

    Return
    ------
    bool
    """
    cfspecs = xoa.cf.get_cf_specs(da)
    cf_names = []
    if potential is None or potential is False:
        cf_names.extend(["dens", "sigmat"])
    if potential is None or potential is True:
        cf_names.append(
            ["pdens", "ndens", "sigmatheta", "sigma0", "sigma1", "sigma2", "sigma3", "sigma4"]
        )
    for cf_name in cf_names:
        if cfspecs.match_data_var(da, cf_name):
            return True
    return False


MLD_METHODS = xoa.misc.Choices(
    {
        "deltatemp": (
            "depth at which the potential temperature is `deltadtemp` "
            "lower than the surface temperature"
        ),
        "deltadens": (
            "depth at which the potential density is `deltadens` higher than the surface density"
        ),
        "kzmax": "depth at which the vertical diffusivity value reaches the `kzmax` value",
    },
    parameter="method",
    description="Method for computing the mixed layer depth",
)


def mixed_layer_depth(
        da,
        method=None,
        deltatemp=0.2,
        deltadens=0.3,
        kzmax=0.0005,
        zdim=None,
        dask="parallelized",
        **kwargs,
):
    """Compute the mixed layer depth with different methods.

    Parameters
    ----------
    da: xarray.DataArray
        A data array that contains either the potential temperature, the potential density or
        the vertical tracer diffisivity.
        Note that this array **must contain a depth coordinate**, which optimally contains
        the `positive` attribute.
    {method}
    kwargs: dict
        Extra keywords are passed to :func:`xoa.regrid.isoslice`.

    Raise
    -----
    XoaError:
        When `method` is `None` and cannot be inferred from `da`.

    Return
    ------
    xarray.DataArray
        Mixed layer depth

    See Also
    --------
    xoa.regrid.isoslice
    """
    # Vertical dimension
    if zdim is None:
        zdim = xoa.coords.get_zdim(da)
    else:
        assert zdim in da.dims
    assert zdim in da.dims

    # Depths
    depth = xoa.coords.get_depth(da)
    positive = xoa.coords.get_positive_attr(depth, zdim=zdim) or "up"

    # Method
    cfspecs = xoa.cf.get_cf_specs(da)
    if method is None:
        if is_temp(da):
            method = "deltatemp"
        elif cfspecs.match_data_var(da, 'kz'):
            method = "kzmax"
        elif is_dens(da):
            method = "deltadens"
        else:
            raise (
                "Cannot infer mixed layer depth computation method from data array. "
                "Please specify the `method` keyword."
            )
    else:
        method = MLD_METHODS[method]

    # Iso value
    if method == "kzmax":
        isoval = kzmax
    else:
        surf = da.isel({zdim: 0 if positive == "down" else -1})
        if method == "deltatemp":
            isoval = surf - deltatemp
        elif method == "deltadens":
            isoval = surf + deltadens

    # Slice
    mld = xoa.regrid.isoslice(depth, da, isoval, dim=zdim, dask=dask, **kwargs)
    mld = np.abs(mld)
    mld = mld.drop_vars(depth.name, errors="ignore")

    # Format
    mld.attrs = {}
    cfspecs.format_data_var(
        mld, "mld", format_coords=False, rename_dims=False, copy=False, replace_attrs=True
    )

    return mld

###############################################################################################END
