"""Command-line interface for armoor-decode.

This module provides command-line interfaces for decoding various types of input.
"""

import logging
from argparse import ArgumentParser

from armoor.io import ArmoorArgumentHelpFormatter
from armoor.cli.io import (
    add_io_parser_arguments,
    add_dask_parser_arguments,
    save_output,
    armoor_cli_session,
)
from armoor.cli.log import add_logging_parser_arguments
from armoor.data.open_decode import open_decode


logger = logging.getLogger(__name__)

logging.getLogger('distributed').setLevel(logging.ERROR)

# dask.config.set({"distributed.worker.profile.enabled": False})


class DecodeError(Exception):
    """Exception raised for errors in the decode module.

    This exception is raised when there are issues with decode configuration or application.
    """

    pass


def get_parser_decode() -> ArgumentParser:
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
        description="Apply decode over a list of input files.",
        formatter_class=ArmoorArgumentHelpFormatter,
    )
    add_logging_parser_arguments(parser)
    add_io_parser_arguments(parser)
    add_dask_parser_arguments(parser)

    return parser


def main_decode() -> None:
    """Apply decode to input files via command line interface.

    This function serves as the main entry point for decoding operations.
    It parses command line arguments, configures decode
    and processes the input files accordingly.

    Examples
    --------
    Command line usage:

    .. code-block:: bash

        armoor-decode --ifmt eddy_sacso --ofmt netcdf \\
                            "folder/files*.txt" output.nc

    Notes
    -----
    - Leverages Dask for memory-efficient processing of large datasets
    - Supports all input/output formats available in the ARMOOR ecosystem
    """
    # Get parser
    parser = get_parser_decode()

    # Parse
    args = parser.parse_args()

    with armoor_cli_session(args, (args.ifmt, args.platform)):
        ds = open_decode(args.fins, args.ifmt, platform=args.platform)
        # "threads" deadlocks intermittently: xarray's netCDF4 write lock is
        # a CombinedLock over several process-global locks, and multiple
        # dask worker threads doing netCDF I/O concurrently can block on
        # each other acquiring them (confirmed via py-spy on stuck
        # armoor-decode processes; "synchronous" -- single thread, no lock
        # contention possible -- doesn't).
        save_output(ds, args.fout, ofmt=args.ofmt, scheduler="synchronous")
