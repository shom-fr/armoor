"""Input/Output utility functions for command-line argument parsing and data saving.

This module provides utility functions for adding standardized command-line arguments
related to input/output operations and saving xarray datasets in various formats.
"""
import logging

from armoor.base.io import get_zarr_encoding

logger = logging.getLogger(__name__)


def add_input_parser_arguments(parser):
    """Add input file pattern argument to argument parser.
    
    Adds a positional argument 'fins' for specifying input file patterns,
    supporting glob patterns for multiple file selection.
    
    Parameters
    ----------
    parser : argparse.ArgumentParser
        The argument parser to which the input file argument will be added.
    
    Examples
    --------
    >>> from argparse import ArgumentParser
    >>> parser = ArgumentParser()
    >>> add_input_parser_arguments(parser)
    >>> args = parser.parse_args(['croco_*.zarr'])
    >>> print(args.fins)
    'croco_*.zarr'
    
    Notes
    -----
    The input file pattern supports standard glob patterns such as:
    - '*' for matching any characters
    - '?' for matching single characters  
    - '[seq]' for matching any character in seq
    """
    parser.add_argument(
        "fins",
        type=str,
        help="Pattern of input file. Ex: croco_*.zarr",
    )


def add_output_parser_arguments(parser):
    """Add output file name argument to argument parser.
    
    Adds a positional argument 'fout' for specifying the output file path.
    
    Parameters
    ----------
    parser : argparse.ArgumentParser
        The argument parser to which the output file argument will be added.
    
    Examples
    --------
    >>> from argparse import ArgumentParser
    >>> parser = ArgumentParser()
    >>> add_output_parser_arguments(parser)
    >>> args = parser.parse_args(['output.zarr'])
    >>> print(args.fout)
    'output.zarr'
    """
    parser.add_argument(
        "fout",
        type=str,
        help="Name of the output file",
    )


def add_input_fmt_parser_arguments(parser):
    """Add input file format argument to argument parser.
    
    Adds an optional argument '--ifmt' for specifying the format of input files.
    This helps the system understand how to properly parse different model outputs.
    
    Parameters
    ----------
    parser : argparse.ArgumentParser
        The argument parser to which the input format argument will be added.
    
    Notes
    -----
    Supported input formats:
    
    - 'hycom' : HYCOM (HYbrid Coordinate Ocean Model) output format
    - 'cmems_model' : Copernicus Marine Environment Monitoring Service model format
    - 'croco' : CROCO (Coastal and Regional Ocean COmmunity model) output format  
    - 'armoor' : ARMOOR internal/native format
    
    Examples
    --------
    >>> from argparse import ArgumentParser
    >>> parser = ArgumentParser()
    >>> add_input_fmt_parser_arguments(parser)
    >>> args = parser.parse_args(['--ifmt', 'croco'])
    >>> print(args.ifmt)
    'croco'
    """
    parser.add_argument(
        "--ifmt",
        type=str,
        choices=("hycom", "cmems_model", "croco", "armoor"),
        help="Format of the input files",
    )


def add_output_fmt_parser_arguments(parser):
    """Add output file format argument to argument parser.
    
    Adds an optional argument '--ofmt' for specifying the format of output files.
    Defaults to 'zarr' format for optimal performance with large datasets.
    
    Parameters
    ----------
    parser : argparse.ArgumentParser
        The argument parser to which the output format argument will be added.
    
    Notes
    -----
    Supported output formats:
    
    - 'zarr' : Zarr chunked array storage format (default)
        - Optimized for cloud storage and parallel I/O
        - Better compression and performance for large datasets
    - 'netcdf' : Network Common Data Form format
        - Traditional format, widely supported
        - Good for smaller datasets and legacy compatibility
    
    Examples
    --------
    >>> from argparse import ArgumentParser
    >>> parser = ArgumentParser()
    >>> add_output_fmt_parser_arguments(parser)
    >>> args = parser.parse_args(['--ofmt', 'netcdf'])
    >>> print(args.ofmt)
    'netcdf'
    >>> 
    >>> # Default behavior
    >>> args = parser.parse_args([])
    >>> print(args.ofmt)
    'zarr'
    """
    parser.add_argument(
        "--ofmt",
        type=str,
        default="zarr",
        choices=("netcdf", "zarr"),
        help="Format of the output files",
    )


def add_io_parser_arguments(parser):
    """Add all input/output related arguments to argument parser.
    
    This is a convenience function that adds input file pattern, input format,
    output file name, and output format arguments to the parser in a single call.
    Ensures consistent I/O argument handling across different CLI commands.
    
    Parameters
    ----------
    parser : argparse.ArgumentParser
        The argument parser to which all I/O arguments will be added.
    
    Examples
    --------
    >>> from argparse import ArgumentParser
    >>> parser = ArgumentParser(description="Process oceanographic data")
    >>> add_io_parser_arguments(parser)
    >>> args = parser.parse_args([
    ...     'input_*.nc',           # fins (positional)
    ...     '--ifmt', 'croco',      # input format
    ...     'output.zarr',          # fout (positional)  
    ...     '--ofmt', 'zarr'        # output format
    ... ])
    >>> print(f"Input: {args.fins}, Format: {args.ifmt}")
    Input: input_*.nc, Format: croco
    >>> print(f"Output: {args.fout}, Format: {args.ofmt}")
    Output: output.zarr, Format: zarr
    
    Notes
    -----
    The order of arguments added is:
    1. Input file pattern (positional)
    2. Input format (optional)
    3. Output file name (positional) 
    4. Output format (optional, defaults to 'zarr')
    """
    add_input_parser_arguments(parser)
    add_input_fmt_parser_arguments(parser)
    add_output_parser_arguments(parser)
    add_output_fmt_parser_arguments(parser)


def save_output(ds, fout, ofmt="zarr"):
    """Save xarray Dataset to file in specified format.
    
    Saves the provided xarray Dataset to the specified output path using
    the requested format. Supports both NetCDF and Zarr formats with
    format-specific optimizations.
    
    Parameters
    ----------
    ds : xarray.Dataset
        The dataset to be saved to disk.
    fout : str
        Output file path. Should include appropriate extension for the format.
    ofmt : {'zarr', 'netcdf'}, default 'zarr'
        Output file format. Zarr is recommended for large datasets due to
        better compression and chunking capabilities.
    
    Raises
    ------
    ValueError
        If ofmt is not one of the supported formats ('zarr', 'netcdf').
    IOError
        If there are issues writing to the specified output path.
    
    Examples
    --------
    >>> import xarray as xr
    >>> import numpy as np
    >>> 
    >>> # Create sample dataset
    >>> data = np.random.rand(100, 50, 25)
    >>> ds = xr.Dataset({
    ...     'temperature': (['time', 'lat', 'lon'], data),
    ...     'coords': {
    ...         'time': range(100),
    ...         'lat': np.linspace(-90, 90, 50),
    ...         'lon': np.linspace(-180, 180, 25)
    ...     }
    ... })
    >>> 
    >>> # Save as zarr (default)
    >>> save_output(ds, 'output.zarr')
    >>> 
    >>> # Save as netcdf
    >>> save_output(ds, 'output.nc', ofmt='netcdf')
    
    Notes
    -----
    - For zarr format, uses optimized variable-by-variable saving via `to_zarr()`
    - For netcdf format, uses standard xarray `to_netcdf()` method
    - Zarr format is preferred for large datasets due to better performance
    """
    logger.info(f"Saving {fout}")
    if ofmt == "zarr":
        to_zarr(ds, fout)
    elif ofmt == "netcdf":
        ds.to_netcdf(fout)
    else:
        raise ValueError(f"Unsupported output format: {ofmt}. Use 'zarr' or 'netcdf'.")


def to_zarr(ds, fout):
    """Save xarray Dataset to zarr format with optimized memory usage.
    
    Saves each data variable separately to zarr format with automatic chunking,
    which optimizes memory usage for large datasets. Variables are written
    incrementally to avoid loading the entire dataset into memory.
    
    Parameters
    ----------
    ds : xarray.Dataset
        The dataset to be saved to zarr format.
    fout : str
        Output zarr store path (directory path, not file).
    
    Examples
    --------
    >>> import xarray as xr
    >>> import numpy as np
    >>> 
    >>> # Create large dataset
    >>> temp_data = np.random.rand(365, 180, 360)
    >>> salt_data = np.random.rand(365, 180, 360) * 35
    >>> 
    >>> ds = xr.Dataset({
    ...     'temperature': (['time', 'lat', 'lon'], temp_data),
    ...     'salinity': (['time', 'lat', 'lon'], salt_data)
    ... })
    >>> 
    >>> to_zarr(ds, 'ocean_data.zarr')
    
    Notes
    -----
    Memory optimization strategy:
    
    - Each variable is processed individually to minimize memory footprint
    - Automatic chunking is applied for optimal I/O performance  
    - First variable uses write mode ('w'), subsequent use append mode ('a')
    - Variable datasets are explicitly deleted after writing to free memory
    - Zarr encoding is obtained via `get_zarr_encoding()` for optimal storage
    
    The function logs progress for each variable being written, which is useful
    for monitoring the processing of large datasets.
    
    See Also
    --------
    get_zarr_encoding : Function to get optimal zarr encoding parameters
    save_output : Higher-level function that calls this for zarr format
    """
    #encoding = get_zarr_encoding(ds)
    
    for ivar, var_name in enumerate(ds.data_vars):
        logger.info(f"Writing variable '{var_name}' to {fout}")
        
        # Select single variable to minimize memory usage
        var_ds = ds[[var_name]]
        var_ds = var_ds.chunk("auto")
        
        # First variable overwrites, subsequent append
        mode = "w" if ivar == 0 else "a"
        
        var_ds.to_zarr(
            store=fout,
            mode=mode,
            #encoding=encoding
        )
        
        # Explicit cleanup to free memory
        del var_ds
