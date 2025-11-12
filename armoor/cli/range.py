"""Command-line interface for armoor-interp-*.

This module provides command-line interfaces for applying various types of interpolation
(temporal, horizontal, vertical) to oceanographic and meteorological data files.
The interpolation operations are optimized for large datasets using Dask distributed computing.
"""
import logging
from argparse import ArgumentParser
from dask.distributed import Client, LocalCluster
import pandas as pd

from armoor.base.io import ArmoorArgumentHelpFormatter, setup_dask_client
from armoor.base.misc import parse_date, is_dict_empty, parse_coords
from armoor.cli.io import (
    add_io_parser_arguments,
    add_dask_parser_arguments,
    get_dask_args,
    save_output,
    check_insitu_platform
)        
from armoor.cli.log import add_logging_parser_arguments, main_setup_logging
from armoor.data.range import (
    process_time_range,
    process_vertical_range
    )
from armoor.data.open_decode import open_decode, register_cf


logger = logging.getLogger(__name__)

logging.getLogger('distributed').setLevel(logging.ERROR)

class RangeError(Exception):
    """Exception raised for errors in the range module.
    
    This exception is raised when there are issues with range configuration
    or execution, such as incompatible parameters, missing required arguments,
    or invalid range specifications.
    """
    pass


def get_parser_range_time():
    """Create argument parser for temporal range operations.
    
    Returns
    -------
    ArgumentParser
        Configured argument parser with range options including
        time frequency specification.
    
    Examples
    --------
    >>> parser = get_parser_range_time()
    >>> args = parser.parse_args(['1H', 'input.nc', 'output.zarr'])
    >>> print(args.tfreq)
    '1H'
    
    Notes
    -----
    Time frequency follows pandas frequency strings format:
    - '1H' : hourly
    - '6H' : 6-hourly  
    - '1D' : daily
    - '1M' : monthly
    """
    parser = ArgumentParser(
        description="Apply time range over a list of input files.",
        formatter_class=ArmoorArgumentHelpFormatter,
        )
    add_logging_parser_arguments(parser)
    add_io_parser_arguments(parser)
    add_dask_parser_arguments(parser)
    parser.add_argument(
        'tfreq',
        type=str,
        help="Time frequency for ranging (pandas frequency string). Ex: 1H, 6H, 1D"
        )
    return parser


def main_range_time():
    """Apply time range to input files via command line interface.
    
    This function serves as the main entry point for time range operations.
    It parses command line arguments, configures range parameters,
    and processes input files using Dask distributed computing for optimal performance.
    
    Positional Arguments
    --------------------
    tfreq : str
        Time frequency for ranging using pandas frequency strings.
        Common values: '1H' (hourly), '6H' (6-hourly), '1D' (daily), '1M' (monthly).
        
    Examples
    --------
    Command line usage:
    
    .. code-block:: bash
    
        # Range to hourly frequency
        armoor-range input.nc output.nc --tfreq 1H --ifmt croco
        
        # Range to daily frequency  
        armoor-range-time input.nc output.nc 1D --ifmt croco
    
    Notes
    -----
    - Uses the full time range from input data (min to max timestamps)
    - Leverages Dask for memory-efficient processing of large datasets
    - Supports all input/output formats available in the ARMOOR ecosystem
    """
    # Get parser
    parser = get_parser_range_time()

    # Parse
    args = parser.parse_args()
    
    # Setup logging
    main_setup_logging(args)
    
    register_cf()
    
    check_insitu_platform(args.ifmt, args.platform)
    
    kw_dask = get_dask_args(args)
    
    with LocalCluster(**setup_dask_client(*kw_dask)) as cluster:
        with Client(cluster):
            ds = open_decode(args.fins, args.ifmt, platform=args.platform)
            ds = process_time_range(ds, args.tfreq)
            save_output(ds, args.fout, args.ofmt)
            
def get_parser_range_vertical():
    """Create argument parser for vertical range operations.
    
    Returns
    -------
    ArgumentParser
        Configured argument parser with range options including.
    """
    parser = ArgumentParser(
        description="Apply vertical range over a list of input files.",
        formatter_class=ArmoorArgumentHelpFormatter,
        )
    add_logging_parser_arguments(parser)
    add_io_parser_arguments(parser)
    add_dask_parser_arguments(parser)
    parser.add_argument(
        'vname',
        type=str,
        help="Name of the vertical coordinate."
        )
    parser.add_argument(
        'vmin',
        type=float,
        help="Minimum value a vertical range."
        )
    parser.add_argument(
        'vmax',
        type=float,
        help="Maximum value a vertical range."
        )
    return parser

def main_range_vertical():
    """Apply vertical range to input files via command line interface.
    
    This function serves as the main entry point for vertical range operations.
    It parses command line arguments, configures range parameters,
    and processes input files using Dask distributed computing for optimal performance.
    
    Positional Arguments
    --------------------
    vrange : float
        Bounds of a vertical range.
        
    Examples
    --------
    Command line usage:
    
    .. code-block:: bash
    
        armoor-range input.nc output.nc depth 100.0 200.0 --ifmt croco

    
    Notes
    -----
    - Leverages Dask for memory-efficient processing of large datasets
    - Supports all input/output formats available in the ARMOOR ecosystem
    """
    # Get parser
    parser = get_parser_range_vertical()

    # Parse
    args = parser.parse_args()
    
    # Setup logging
    main_setup_logging(args)
    
    register_cf()
    
    check_insitu_platform(args.ifmt, args.platform)
    
    kw_dask = get_dask_args(args)
    
    with LocalCluster(**setup_dask_client(*kw_dask)) as cluster:
        with Client(cluster):
            ds = open_decode(args.fins, args.ifmt, platform=args.platform)
            ds = process_vertical_range(ds, args.vname, [args.vmin, args.vmax])
            save_output(ds, args.fout, args.ofmt)