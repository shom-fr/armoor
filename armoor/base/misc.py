import ast
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
    parts = value.split(',')
    return (parts[0].strip(), int(parts[1].strip()), int(parts[2].strip()))

def parse_mixed_param(param_value: Union[str, List]) -> List:
    """
    Parse a ConfigObj parameter that contains strings and lists mixed together.
    Returns all elements in their original order.
    
    Handles formats like:
    - param1 = "toto", [10, 20, 100]
    - param1 = "tutu", "toto", [10, 20, 100]
    - param1 = [10, 20, 100], "toto"
    - param1 = ["toto", [10, 20, 100]]
    - param1 = "product","depth",[(0, 100), (400, 500)]
    
    Parameters
    ----------
    param_value : Union[str, List]
        ConfigObj parameter value (can be string or already parsed list)
        
    Returns
    -------
    List
        List containing all elements (strings and lists) in original order
        
    Raises
    ------
    ValueError
        If the parameter format is invalid
        
    Examples
    --------
    >>> parse_mixed_param('"toto", [10, 20, 100]')
    ['toto', [10, 20, 100]]
    
    >>> parse_mixed_param('"tutu", "toto", [10, 20, 100]')
    ['tutu', 'toto', [10, 20, 100]]
    
    >>> parse_mixed_param(['tutu', 'toto', [10, 20, 100]])
    ['tutu', 'toto', [10, 20, 100]]
    
    >>> parse_mixed_param('"product","depth",[(0, 100), (400, 500)]')
    ['product', 'depth', [(0, 100), (400, 500)]]
    """
    if isinstance(param_value, str):
        return _parse_string_format(param_value)
    elif isinstance(param_value, list):
        return _parse_list_format(param_value)
    else:
        raise ValueError(f"Unsupported parameter type: {type(param_value)}")


def _parse_string_format(param_str: str) -> List:
    """Parse string format and return all elements in order."""
    param_str = param_str.strip()
    
    result = []
    i = 0
    current_token = ""
    in_quotes = False
    quote_char = None
    
    while i < len(param_str):
        char = param_str[i]
        
        # Handle quotes
        if char in ['"', "'"] and (quote_char is None or char == quote_char):
            if not in_quotes:
                in_quotes = True
                quote_char = char
            elif char == quote_char:
                in_quotes = False
                quote_char = None
            current_token += char
        
        # Handle list start
        elif char == '[' and not in_quotes:
            # Save current token if it exists
            if current_token.strip():
                cleaned_token = _clean_string_value(current_token.strip().rstrip(','))
                if cleaned_token:
                    result.append(cleaned_token)
                current_token = ""
            
            # Find matching closing bracket
            bracket_count = 1
            list_start = i
            i += 1
            
            while i < len(param_str) and bracket_count > 0:
                if param_str[i] == '[':
                    bracket_count += 1
                elif param_str[i] == ']':
                    bracket_count -= 1
                i += 1
            
            if bracket_count > 0:
                raise ValueError(f"Unmatched opening bracket at position {list_start}")
            
            # Extract and parse the list
            list_str = param_str[list_start:i]
            try:
                list_value = ast.literal_eval(list_str)
                if isinstance(list_value, list):
                    result.append(list_value)
                else:
                    raise ValueError(f"Expected list, got {type(list_value)}")
            except (ValueError, SyntaxError) as e:
                raise ValueError(f"Invalid list format '{list_str}': {e}")
            
            # Skip any following comma and whitespace
            while i < len(param_str) and param_str[i] in ', \t':
                i += 1
            continue
        
        # Handle comma (separator)
        elif char == ',' and not in_quotes:
            if current_token.strip():
                cleaned_token = _clean_string_value(current_token.strip())
                if cleaned_token:
                    result.append(cleaned_token)
            current_token = ""
        
        # Regular character
        else:
            current_token += char
        
        i += 1
    
    # Handle last token
    if current_token.strip():
        cleaned_token = _clean_string_value(current_token.strip())
        if cleaned_token:
            result.append(cleaned_token)
    
    return result


def _parse_list_format(param_list: List) -> List:
    """Parse list format and return all elements as-is."""
    if len(param_list) < 1:
        raise ValueError(f"Parameter must contain at least 1 element, got {len(param_list)}")
    
    # Clean string elements but keep everything in order
    result = []
    for element in param_list:
        if isinstance(element, str):
            result.append(_clean_string_value(element))
        else:
            result.append(element)
    
    return result


def _clean_string_value(string_part: str) -> str:
    """Remove quotes and clean string value."""
    string_part = string_part.strip()
    
    # Remove outer quotes if present
    if ((string_part.startswith('"') and string_part.endswith('"')) or 
        (string_part.startswith("'") and string_part.endswith("'"))):
        string_part = string_part[1:-1]
    
    return string_part


def parse_multiple_params(config_dict: dict, param_names: List[str]) -> dict:
    """
    Parse multiple ConfigObj parameters that follow the mixed format.
    
    Parameters
    ----------
    config_dict : dict
        Dictionary containing configuration parameters
    param_names : List[str]
        Names of parameters to parse as mixed format
        
    Returns
    -------
    dict
        Dictionary with parsed parameters as lists
        
    Examples
    --------
    >>> config = {
    ...     'param1': '"toto", [10, 20, 100]',
    ...     'param2': '"tutu", "toto", [10, 20, 100]',
    ...     'vrange': '"product","depth",[(0, 100), (400, 500)]',
    ...     'other': 'normal_param'
    ... }
    >>> parse_multiple_params(config, ['param1', 'param2', 'vrange'])
    {'param1': ['toto', [10, 20, 100]], 'param2': ['tutu', 'toto', [10, 20, 100]], 'vrange': ['product', 'depth', [(0, 100), (400, 500)]]}
    """
    result = {}
    
    for param_name in param_names:
        if param_name in config_dict:
            try:
                result[param_name] = parse_mixed_param(config_dict[param_name])
            except ValueError as e:
                raise ValueError(f"Error parsing parameter '{param_name}': {e}")
        else:
            raise KeyError(f"Parameter '{param_name}' not found in configuration")
    
    return result


def validate_mixed_param_types(parsed_list: List, 
                             expected_string_count: Optional[int] = None,
                             expected_list_count: Optional[int] = None) -> bool:
    """
    Validate the types of parsed mixed parameter.
    
    Parameters
    ----------
    parsed_list : List
        Parsed list containing strings and lists
    expected_string_count : int, optional
        Expected number of string elements
    expected_list_count : int, optional
        Expected number of list elements
        
    Returns
    -------
    bool
        True if validation passes
        
    Raises
    ------
    TypeError
        If validation fails
    """
    if not isinstance(parsed_list, list):
        raise TypeError(f"Parsed parameter must be a list, got {type(parsed_list)}")
    
    string_count = sum(1 for item in parsed_list if isinstance(item, str))
    list_count = sum(1 for item in parsed_list if isinstance(item, list))
    
    if expected_string_count is not None and string_count != expected_string_count:
        raise TypeError(f"Expected {expected_string_count} strings, got {string_count}")
    
    if expected_list_count is not None and list_count != expected_list_count:
        raise TypeError(f"Expected {expected_list_count} lists, got {list_count}")

    return True

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
        of parameter pairs to validate.
    label : str
        Word used in log/error messages to name the kind of choice being
        validated (e.g. "colocation", "interpolation").

    Raises
    ------
    ArmoorError
        If both parameters are defined or neither is defined.
    """
    for mz_name, mz_param in metazones.items():
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
                    metazones[mz_name] = None
                    continue
    return metazones

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

    geo_vars = [
        var
        for var in ds.data_vars
        if ("x" in ds[var].dims) and ("y" in ds[var].dims)
    ]

    return geo_vars


def nongeo_vars(ds):

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

