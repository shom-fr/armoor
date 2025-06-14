import logging

logger = logging.getLogger(__name__)

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

def optimize_for_low_swap(dataset, target_chunk_mb=16):
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
    
    logger.info(f"Anti-swap chunks: {chunks}")
    logger.info(f"Estimated chunk size: {(elements_per_dim**n_dims * element_size) / 1024**2:.1f} MB per chunk")
    
    return dataset.chunk(chunks)