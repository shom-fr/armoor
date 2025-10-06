"""Command-line interface for armoor-interp-*.

This module provides command-line interfaces for applying various types of interpolation
(temporal, horizontal, vertical) to oceanographic and meteorological data files.
The interpolation operations are optimized for large datasets using Dask distributed computing.
"""
import logging
from argparse import ArgumentParser
from dask.distributed import Client, LocalCluster

from armoor.base.io import ArmoorArgumentHelpFormatter, setup_dask_client
from armoor.base.misc import parse_date, is_dict_empty, parse_coords
from armoor.cli.io import (
    add_input_parser_arguments,
    add_input_fmt_parser_arguments,
    add_output_parser_arguments,
    add_output_fmt_parser_arguments,
    add_dask_parser_arguments,
    save_output
)        
from armoor.cli.log import add_logging_parser_arguments, main_setup_logging
from armoor.comp.coloc import (
    process_time_colocation,
    process_horizontal_colocation,
    process_vertical_colocation
    )
from armoor.data.open_decode import open_decode


logger = logging.getLogger(__name__)

logging.getLogger('distributed').setLevel(logging.ERROR)


class ColocError(Exception):
    """Exception raised for errors in the interpolation module.
    
    This exception is raised when there are issues with interpolation configuration
    or execution, such as incompatible parameters, missing required arguments,
    or invalid interpolation specifications.
    """
    pass


def add_refinput_parser_arguments(parser):
    """Add reference input file pattern argument to argument parser.
    """
    parser.add_argument(
        "ref_fins",
        type=str,
        help="Pattern of reference input file. Ex: croco_*.zarr",
    )
    
def add_refinput_fmt_parser_arguments(parser):
    """Add reference input file format argument to argument parser.
    """
    parser.add_argument(
        "--ref-ifmt",
        type=str,
        choices=("hycom", "cmems_model", "croco", "armoor"),
        help="Format of the input files",
    )
    
def add_coloc_io_parser_arguments(parser):
    """Add all input/output related arguments to argument colocation parser.
    """
    add_refinput_parser_arguments(parser)
    add_refinput_fmt_parser_arguments(parser)
    add_input_parser_arguments(parser)
    add_input_fmt_parser_arguments(parser)
    add_output_parser_arguments(parser)
    add_output_fmt_parser_arguments(parser)

def get_parser_coloc_time():
    """Create argument parser for temporal colocation operations.
    """
    parser = ArgumentParser(
        description="Apply time colocation over a list of input files.",
        formatter_class=ArmoorArgumentHelpFormatter,
        )
    add_logging_parser_arguments(parser)
    add_dask_parser_arguments(parser)
    add_coloc_io_parser_arguments(parser)

    return parser

def main_coloc_time():
    """Apply temporal colocation to input files via command line interface.
    """
    # Get parser
    parser = get_parser_coloc_time()

    # Parse
    args = parser.parse_args()
    
    # Setup logging
    main_setup_logging(args)
    
    with LocalCluster(**setup_dask_client(args.dask_nworkers, args.dask_processes, args.dask_memorylimit)) as cluster:
        with Client(cluster):
            dsref = open_decode(args.ref_fins, args.ref_ifmt)
            dsprod = open_decode(args.fins, args.ifmt)
            tbound = (dsref.time.min(), dsref.time.max())
            param = ("trange_seq", (None, "reference"))
            _, dsout = process_time_colocation(dsref, dsprod, param, tbound)
            del dsref
            del dsprod
            save_output(dsout, args.fout, args.ofmt)
