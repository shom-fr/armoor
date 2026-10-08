import logging
from typing import Any, Dict, List, Optional, Tuple, Union
from datetime import datetime
from argparse import ArgumentTypeError
from armoor.__init__ import ArmoorError

logger = logging.getLogger(__name__)

def is_dict_empty(dictionary: Optional[Dict[Any, Any]]) -> bool:
    """
    Check if a dictionary is empty.

    Parameters
    ----------
    dictionary
        The dictionary to check. Can be None.

    Returns
    -------
    bool
        True if the dictionary is empty or None, False otherwise.

    Raises
    ------
    TypeError
        If the input is not a dictionary or None.
    """
    if dictionary is None:
        return True
    
    if not isinstance(dictionary, dict):
        raise TypeError("Input must be a dictionary or None")
    
    return not dictionary

def parse_qc_tuple(value):
    """Parse a ``"varname,flag,replacement"`` CLI argument into a tuple.

    Parameters
    ----------
    value : str
        A comma-separated ``"varname,flag,replacement"`` string.

    Returns
    -------
    tuple of (str, int, int)
        ``(varname, flag, replacement)``.
    """
    parts = value.split(',')
    return (parts[0].strip(), int(parts[1].strip()), int(parts[2].strip()))

def validate_metazone_params(metazones, params, label="colocation"):
    """Validate that only one of each pair of parameters is defined for each metazone.

    This function checks, for each metazone and each two-element candidate
    pair in `params`, that either param1 or param2 is defined, but not both.
    Shared between armoor.comp (colocation) and armoor.data (interpolation),
    which pick different candidate-parameter dicts but apply the identical
    validation rule.

    Parameters
    ----------
    metazones : dict
        A dictionary of metazones with their parameters.
    params : dict
        A dictionary where keys are parameter categories and values are lists
        of parameter candidates to validate -- either a single candidate
        (e.g. ``("cloud",)``) or a mutually-exclusive pair (e.g.
        ``("vlevel", "vfreq")``).
    label : str
        Word used in log/error messages to name the kind of choice being
        validated (e.g. "colocation", "interpolation").

    Returns
    -------
    dict
        A new dict (metazones is not mutated) mapping each metazone to its
        original params, or to None where *no* candidate in any category is
        defined. A metazone missing just one optional pair (e.g. no
        vlevel/vfreq) while another category *is* set (e.g. cloud) keeps its
        original params -- only a category with neither candidate of a pair
        set is itself left unselected; it doesn't null out categories that
        are configured. Returning a copy matters: callers of this function
        (e.g. armoor.data.output.OutputProcessor) go on to look up the
        *original* metazone config again later for unrelated processing
        (time/vertical ranges, filters) -- mutating the caller's own dict in
        place would silently replace that config with None.

    Raises
    ------
    ArmoorError
        If both parameters of a pair are defined for the same metazone.
    """
    if not params:
        # No candidate categories at all to validate (e.g. CompDrifter's
        # colocation_params_user is {} -- it relies entirely on
        # colocation_params_default, never on a user-configured choice)
        # -- nothing to null out, pass every metazone through unchanged.
        return dict(metazones)
    result = dict(metazones)
    for mz_name, mz_param in metazones.items():
        any_set = False
        for k, v in params.items():
            if len(v) == 2:
                param1, param2 = v[0], v[1]
                val1 = mz_param.get(param1)
                val2 = mz_param.get(param2)
                if val1 is not None and val2 is not None:
                    raise ArmoorError(
                        f"Both '{param1}' and '{param2}' are defined for {mz_name}. "
                        f"Please choose either '{param1}' or '{param2}' {label}."
                    )
                if val1 is None and val2 is None:
                    logger.info(
                        f"Neither '{param1}' nor '{param2}' is defined for {mz_name}. "
                        f"Please choose either '{param1}' or '{param2}' {label}."
                    )
                else:
                    any_set = True
            elif any(mz_param.get(candidate) is not None for candidate in v):
                any_set = True
        if not any_set:
            result[mz_name] = None
    return result

def parse_coords(s):
    """
    Parse a string into latitude and longitude coordinates.
    
    Parameters
    ----------
    s: str
        A string representing the coordinates in the format "lat,lon".
    
    Returns
    -------
    tuple: A tuple containing the latitude and longitude as floats.
    
    Raises
    ------
    ArmoorError: If the string is not in the correct format.
    """
    try:
        if not isinstance(s, str):
            s = ",".join(s)
        return string_to_tuples_float(s)
    except:
        raise ArmoorError("Coordinates must be a list of tuples (lat,lon)")

def comma_separated(sarg):
    """Parse a string of comma-separated list."""
    return [a.strip() for a in sarg.split(",")]

def str2bool(sarg):
    """Parse an argparse `--flag True/False`-style boolean argument.

    `type=bool` is a common argparse footgun: `bool("False")` is `True`
    (any non-empty string is truthy), so a plain `type=bool` argument
    silently ignores the actual value typed on the command line.
    """
    if isinstance(sarg, bool):
        return sarg
    if sarg.strip().lower() in ("true", "1", "yes"):
        return True
    if sarg.strip().lower() in ("false", "0", "no"):
        return False
    # argparse's type= callables must raise ValueError/TypeError (not
    # ArmoorError) for its own "invalid X value" CLI error message to fire.
    raise ValueError(f"Expected True/False, got {sarg!r}")

def blanck_separated(sarg):
    """Parse a string of blanck-separated list."""
    return [a.strip() for a in sarg.split(" ")]

def various_separated(sarg):
    """Parse a string/list of various-separated list."""
    print(type(sarg))
    if "," in sarg:
        return comma_separated(sarg)
    else:
        return blanck_separated(sarg)

def parse_date(date_string):
    """Parse a date string in one of several accepted formats.

    Parameters
    ----------
    date_string : str
        A date in ``YYYY-MM-DD``, ``MM/DD/YYYY`` or ``DD-MM-YYYY`` format.

    Returns
    -------
    datetime.date

    Raises
    ------
    argparse.ArgumentTypeError
        If `date_string` matches none of the accepted formats.
    """
    formats = ['%Y-%m-%d', '%m/%d/%Y', '%d-%m-%Y']
    for fmt in formats:
        try:
            return datetime.strptime(date_string, fmt).date()
        except ValueError:
            continue
    raise ArgumentTypeError(
        f"Invalid date format: {date_string}. Use YYYY-MM-DD, MM/DD/YYYY, or DD-MM-YYYY"
    )
    
def parse_hours(hours_string):
    """Parse a time-of-day string in one of several accepted formats.

    Parameters
    ----------
    hours_string : str
        A time in ``hh:mm:ss`` or ``hhmmss`` format.

    Returns
    -------
    datetime.time

    Raises
    ------
    argparse.ArgumentTypeError
        If `hours_string` matches none of the accepted formats.
    """
    formats = ['%H:%M:%S', '%H%M%S']
    for fmt in formats:
        try:
            return datetime.strptime(hours_string, fmt).time()
        except ValueError:
            continue
    raise ArgumentTypeError(
        f"Invalid date format: {hours_string}. Use hh:mm:ss or hhmmss"
    )

def geo_vars(ds):
    """List data variables that have both an "x" and a "y" dimension.

    Parameters
    ----------
    ds : xr.Dataset

    Returns
    -------
    list of str
    """
    geo_vars = [
        var
        for var in ds.data_vars
        if ("x" in ds[var].dims) and ("y" in ds[var].dims)
    ]

    return geo_vars


def nongeo_vars(ds):
    """List data variables that have neither an "x" nor a "y" dimension.

    Parameters
    ----------
    ds : xr.Dataset

    Returns
    -------
    list of str
    """
    nongeo_vars = [
        var
        for var in ds.data_vars
        if ("x" not in ds[var].dims) and ("y" not in ds[var].dims)
    ]

    return nongeo_vars

def string_to_tuples_float(s):
    """
    Convert a string of tuples into a list of tuples.

    Parameters
    ----------
    s: str
        A string representing tuples, e.g., "(elm1, elm2), (elm3, elm4)".

    Returns
    -------
    list: A list of tuples.
    """
    s = s.replace(" ", "")
    tuples_str = s.split("),(")
    tuples = []
    for tuple_str in tuples_str:
        tuple_str = tuple_str.strip("()")
        elements = tuple_str.split(",")
        for iel, el in enumerate(elements):
            elements[iel] = float(el)
        tuples.append(tuple(elements))

    return tuples

def get_last_keys_generator(d):
    """Generator version that yields last keys one by one."""
    for key, value in d.items():
        if isinstance(value, dict) and value:
            yield from get_last_keys_generator(value)
        else:
            yield value

def dict_to_list(d):
    """
    Convert a nested dictionary to a flattened list.

    This function processes a nested dictionary structure and returns a flat list
    containing all values from the deepest level of nesting. It uses the
    get_last_keys_generator() function to traverse the dictionary and extract
    the final key-value pairs or leaf values.

    Parameters
    ----------
    d : dict
        A dictionary that may contain nested dictionaries or other values.

    Returns
    -------
    list
        A flattened list containing items from the deepest level of the
        dictionary structure. The exact content depends on what
        get_last_keys_generator() yields.

    Examples
    --------
    >>> nested_dict = {'a': {'b': [1, 2]}, 'c': {'d': [3, 4]}}
    >>> dict_to_list(nested_dict)
    [1, 2, 3, 4]  # Assuming get_last_keys_generator yields the leaf values

    Notes
    -----
    This function depends on get_last_keys_generator(d) which should yield
    iterable objects that will be flattened into the final list.
    """
    return [
        item for sublist in get_last_keys_generator(d) for item in sublist
        ]  

def optimize_for_low_swap(dataset, target_chunk_mb=256):
    """
    Optimize dataset chunks to reduce swap usage.
    
    This function calculates optimal chunk sizes for xarray datasets to minimize 
    memory usage and prevent excessive swap utilization during processing.
    
    Parameters
    ----------
    dataset : xarray.Dataset or xarray.DataArray
        The dataset to optimize chunking for
    target_chunk_mb : int, optional
        Target chunk size in megabytes (default: 16)
        Smaller values reduce memory usage but may increase overhead
    
    Returns
    -------
    xarray.Dataset or xarray.DataArray
        Dataset with optimized chunk sizes
    
    Notes
    -----
    - Assumes float64 data type (8 bytes per element)
    - Distributes chunk size evenly across all dimensions
    - Chunk size per dimension = (total_elements_per_chunk)^(1/n_dimensions)
    - Ensures chunk size doesn't exceed dimension size
    
    Examples
    --------
    >>> import xarray as xr
    >>> ds = xr.open_zarr('large_dataset.zarr')
    >>> ds_optimized = optimize_for_low_swap(ds, target_chunk_mb=8)
    >>> print(ds_optimized.chunks)
    
    >>> # For very memory-constrained environments
    >>> ds_minimal = optimize_for_low_swap(ds, target_chunk_mb=4)
    """
    # Calculate optimal chunk size
    element_size = 8  # float64 bytes per element
    elements_per_chunk = (target_chunk_mb * 1024**2) // element_size
    
    # Distribute across dimensions
    n_dims = len(dataset.dims)
    elements_per_dim = int(elements_per_chunk ** (1/n_dims))
    
    chunks = {}
    for dim in dataset.dims:
        # Ensure chunk size doesn't exceed dimension size
        chunks[dim] = min(dataset.sizes[dim], elements_per_dim)
    
    # z_dim = chunks.get("z")
    # if z_dim:
    #     chunks.update({"z": -1})
    # z_dim = chunks.get("lev")
    # if z_dim:
    #     chunks.update({"lev": -1})
    # z_dim = chunks.get("time")
    # if z_dim:
    #     chunks.update({"time": -1}) 
    logger.info(f"Anti-swap chunks: {chunks}")
    logger.info(f"Estimated chunk size: {(elements_per_dim**n_dims * element_size) / 1024**2:.1f} MB per chunk")
    
    return dataset.chunk(chunks).unify_chunks()

