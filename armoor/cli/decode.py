"""Command-line interface for armoor-decode.

This module provides command-line interfaces for decoding various types of input.
"""
import logging, shutil
import asyncio
from argparse import ArgumentParser
from dask.distributed import Client, LocalCluster
import dask.config
import xarray as xr

from armoor.base.io import ArmoorArgumentHelpFormatter, setup_dask_client
from armoor.base.misc import parse_date, parse_hours, is_dict_empty, parse_coords
from armoor.cli.io import (
    add_io_parser_arguments,
    add_dask_parser_arguments,
    get_dask_args,
    save_output,
    check_insitu_platform
)        
from armoor.cli.log import add_logging_parser_arguments, main_setup_logging
from armoor.data.open_decode import open_decode, register_cf


logger = logging.getLogger(__name__)

logging.getLogger('distributed').setLevel(logging.ERROR)

# dask.config.set({"distributed.worker.profile.enabled": False})

class DecodeError(Exception):
    """Exception raised for errors in the decode module.
    
    This exception is raised when there are issues with decode configuration or application.
    """
    pass


def get_parser_decode():
    """Create argument parser for decoding operations.
    
    Returns
    -------
    ArgumentParser
        Configured argument parser with decoding options.
    
    Examples
    --------
    >>> parser = get_parser_decode()
    >>> args = parser.parse_args()
    """
    parser = ArgumentParser(
        description="Apply time filters over a list of input files.",
        formatter_class=ArmoorArgumentHelpFormatter,
        )
    add_logging_parser_arguments(parser)
    add_io_parser_arguments(parser)
    add_dask_parser_arguments(parser)

    return parser

def main_decode():
    """Apply decode to input files via command line interface.
    
    This function serves as the main entry point for decoding operations.
    It parses command line arguments, configures decode 
    and processes the input files accordingly.
    
    Examples
    --------
    Command line usage:
    
    .. code-block:: bash
    
        armoor-filters-time input.nc output.nc \\
                            --ifmt hycom --ofmt netcdf
    
    Notes
    -----
    - Leverages Dask for memory-efficient processing of large datasets
    - Supports all input/output formats available in the ARMOOR ecosystem
    """
    # Get parser
    parser = get_parser_decode()

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
            save_output(ds, args.fout, ofmt=args.ofmt, scheduler="threads")
