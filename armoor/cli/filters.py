"""Command-line interface for armoor-filters-\*.

This module provides command-line interfaces for applying various types of filters
(time, horizontal, quality) to oceanographic data files.
"""
import logging
import asyncio
from argparse import ArgumentParser
import dask.config

import armoor  # noqa: F401 — registers ds.filters accessor
from armoor.base.io import ArmoorArgumentHelpFormatter
from armoor.base.misc import parse_date, parse_hours, is_dict_empty, parse_coords
from armoor.cli.io import (
    add_io_parser_arguments,
    add_dask_parser_arguments,
    save_output,
    armoor_cli_session,
    open_decode_materialized,
)
from armoor.cli.log import add_logging_parser_arguments


logger = logging.getLogger(__name__)

logging.getLogger('distributed').setLevel(logging.ERROR)

# dask.config.set({"distributed.worker.profile.enabled": False})

class FiltersError(Exception):
    """Exception raised for errors in the filters module.
    
    This exception is raised when there are issues with filter configuration
    or application, such as missing required parameters or invalid filter
    configurations.
    """
    pass


def process_filters(args, filters_config):
    """Process input files by applying specified filters and saving output.

    This function opens input files, applies the configured filters using
    Dask distributed computing, and saves the filtered results to the
    specified output format.

    Parameters
    ----------
    args : argparse.Namespace
        Parsed CLI arguments (fins, ifmt, platform, fout, ofmt, dask-\*).
    filters_config : dict
        Dictionary containing filter configurations. Each key represents
        a filter type with its corresponding parameters.

    Raises
    ------
    FiltersError
        If filters_config is empty or None.
    """
    if is_dict_empty(filters_config):
        raise FiltersError("No filters to be applied.")

    with armoor_cli_session(args, (args.ifmt, args.platform)):
        with open_decode_materialized(args.fins, args.ifmt, platform=args.platform) as ds:
            ds = ds.filters.combined(filters_config)
            # "threads" deadlocks intermittently: xarray's netCDF4 write lock
            # is a CombinedLock over several process-global locks, and
            # multiple dask worker threads doing netCDF I/O concurrently can
            # block on each other acquiring them (confirmed via py-spy on
            # stuck armoor-filters-* processes; "synchronous" -- single
            # thread, no lock contention possible -- doesn't).
            save_output(ds, args.fout, ofmt=args.ofmt, scheduler="synchronous")


def get_parser_filters_time():
    """Create argument parser for time-based filtering operations.
    
    Returns
    -------
    ArgumentParser
        Configured argument parser with time filtering options including
        date range selection and tidal filters.
    
    Examples
    --------
    >>> parser = get_parser_filters_time()
    >>> args = parser.parse_args(['--date-range', '2020-01-01', '2020-12-31'])
    """
    parser = ArgumentParser(
        description="Apply time filters over a list of input files.",
        formatter_class=ArmoorArgumentHelpFormatter,
        )
    add_logging_parser_arguments(parser)
    add_io_parser_arguments(parser)
    add_dask_parser_arguments(parser)
    parser.add_argument(
        '--date-range',
        nargs=2,
        type=parse_date,
        help="Start and end dates for time selection"
        )
    parser.add_argument(
        '--hours-range',
        nargs=2,
        type=parse_hours,
        help="Start and end hours for hours selection"
        )
    parser.add_argument(
        '--tides',
        type=str,
        choices=("mean", "godin", "demerliac"),
        help="Name of tidal filter: mean, godin or demerliac."
        )
    parser.add_argument(
        '--resample',
        type=str,
        help="Resample at a given frequency (see pandas offset alias)"
        )
    parser.add_argument(
        '--smooth',
        type=str,
        help="Smooth over a given period (see pandas offset alias)"
        )

    return parser


def main_filters_time():
    """Apply time-based filters to input files via command line interface.
    
    This function serves as the main entry point for time filtering operations.
    It parses command line arguments, configures time-based filters (date range
    and tidal filters), and processes the input files accordingly.
    
    Command Line Arguments
    ----------------------
    --date-range : str, str
        Start and end dates for time selection (format: YYYY-MM-DD).
    --tides : {'mean', 'godin', 'demerliac'}
        Type of tidal filter to apply.
    
    Examples
    --------
    Command line usage:
    
    .. code-block:: bash
    
        armoor-filters-time input.nc output.nc \\
                            --ifmt hycom --ofmt netcdf \\
                            --date-range 2020-01-01 2020-12-31 \\
                            --tides godin
    
    Notes
    -----
    - Leverages Dask for memory-efficient processing of large datasets
    - Supports all input/output formats available in the ARMOOR ecosystem
    """
    # Get parser
    parser = get_parser_filters_time()

    # Parse
    args = parser.parse_args()

    filters_config = {}

    # Date range
    date_range = args.date_range
    if date_range:
        filters_config.update({
            'time_selection': {
                'minimum': date_range[0],
                'maximum': date_range[1]
                }
            })

    # Date range
    hours_range = args.hours_range
    if hours_range:
        filters_config.update({
            'hours_selection': {
                'minimum': hours_range[0],
                'maximum': hours_range[1]
                }
            })

    # Tidal filter
    tides = args.tides
    if tides:
        filters_config.update({
            'tide': tides
            })
        
    # Resampling
    resample = args.resample
    if resample:
        filters_config.update({
            'tresample': resample
            })
        
    # Smoothing
    smooth = args.smooth
    if smooth:
        filters_config.update({
            'tsmooth': smooth
            })
    
    process_filters(args, filters_config)


def get_parser_filters_horizontal():
    """Create argument parser for horizontal spatial filtering operations.
    
    Returns
    -------
    ArgumentParser
        Configured argument parser with horizontal filtering options including
        polygon-based selection and bathymetry-based filtering.
    
    Examples
    --------
    >>> parser = get_parser_filters_horizontal()
    >>> args = parser.parse_args(['--polygon-coords', '45.0,2.0', '46.0,3.0', '44.0,4.0'])
    """
    parser = ArgumentParser(
        description="Apply horizontal filters over a list of input files.",
        formatter_class=ArmoorArgumentHelpFormatter,
        )
    add_logging_parser_arguments(parser)
    add_io_parser_arguments(parser)
    add_dask_parser_arguments(parser)
    parser.add_argument(
        '--polygon-dilat',
        type=bool,
        default=False,
        help="Extend polygon, useful for regridding: True or False"
        )
    parser.add_argument(
        '--polygon-coords',
        type=parse_coords,
        help="String of comma-separated coordinates (lat,lon) tuples \
              defining polygon vertices. Ex: '(45.0,2.0),(46.0,3.0),(44.0,4.0)'"
        )
    parser.add_argument(
        '--bathy-file',
        type=str,
        help="NetCDF file containing bathymetry data to use for filtering."
        )
    parser.add_argument(
        '--bathy-fmt',
        type=str,
        choices=("croco", "hycom", "armoor", "cmems_model"),
        help="Format of the bathymetry NetCDF file."
        )
    parser.add_argument(
        '--bathy-thr-min',
        type=float,
        help="Bathymetry depth minimum threshold (in meters)"
        )
    parser.add_argument(
        '--bathy-thr-max',
        type=float,
        help="Bathymetry depth maximum threshold (in meters)"
        )
    return parser


def main_filters_horizontal():
    """Apply horizontal spatial filters to input files via command line interface.
    
    This function serves as the main entry point for horizontal filtering operations.
    It parses command line arguments, configures spatial filters (polygon-based
    selection and bathymetry filtering), and processes the input files accordingly.
    
    Command Line Arguments
    ----------------------
    --polygon-coords : list of tuples
        Coordinates (lat, lon) defining polygon vertices for spatial selection.
        Requires at least 3 points to define a valid polygon.
    --polygon-dilat : bool, default False
        Whether to dilate/extend the polygon boundaries.
    --bathy-file : str
        Path to NetCDF file containing bathymetry data.
    --bathy-fmt : {'croco', 'hycom', 'armoor'}
        Format of the bathymetry file. Required if --bathy-file is specified.
    --bathy-thr : float, float
        Minimum and maximum depth thresholds for bathymetry filtering.
        Required if --bathy-file is specified.
    
    Raises
    ------
    FiltersError
        If polygon has less than 3 points, or if bathymetry file is specified
        without required format or threshold parameters.
    
    Examples
    --------
    Command line usage:
    
    .. code-block:: bash
    
        armoor-filters-horizontal input.nc output.nc \\
                            --ifmt hycom --ofmt netcdf \\
                            --polygon-coords "(45.0,2.0),(46.0,3.0),(44.0,4.0)" \\
                            --bathy-file bathy.nc --bathy-fmt croco \\
                            --bathy-thr -1000.0 0.0
    Notes
    -----
    - Leverages Dask for memory-efficient processing of large datasets
    - Supports all input/output formats available in the ARMOOR ecosystem
    """
    # Get parser
    parser = get_parser_filters_horizontal()

    # Parse
    args = parser.parse_args()

    filters_config = {}

    coords = args.polygon_coords
    if coords:
        if len(coords) >= 3:
            filters_config.update({
                "polygon":{
                    "coords": coords,
                    "dilate": args.polygon_dilat
                    }
                })
        elif len(coords) < 3:
            raise FiltersError(
                "A polygon has to be defined by 3 points at least."
                )

    bathy_file = args.bathy_file
    if bathy_file:
        bathy_fmt = args.bathy_fmt
        bathy_thr_min = args.bathy_thr_min
        bathy_thr_max = args.bathy_thr_max
        if not bathy_fmt:
            raise FiltersError(
                "--bathy-fmt is mandatory since --bathy-file is specified."
                )
        if (not bathy_thr_min) and (not bathy_thr_max):
            raise FiltersError(
                "--bathy-thr-min and/or --bathy-thr-max is mandatory since --bathy-file is specified."
                )
        filters_config.update({
            "bathy":{
                "path": bathy_file,
                "fmt": bathy_fmt,
                "min": bathy_thr_min,
                "max": bathy_thr_max
                }
            })
        
    process_filters(args, filters_config)

def get_parser_filters_quality():
    """Create argument parser for quality control filtering operations.
    
    Returns
    -------
    ArgumentParser
        Configured argument parser with quality control filtering options
        including quality variable name and threshold specifications.
    
    Examples
    --------
    >>> parser = get_parser_filters_quality()
    >>> args = parser.parse_args(['qc_flag', '0.0', '1.0'])
    """
    parser = ArgumentParser(
        description="Apply quality filters over a list of input files.",
        formatter_class=ArmoorArgumentHelpFormatter,
        )
    add_logging_parser_arguments(parser)
    add_io_parser_arguments(parser)
    add_dask_parser_arguments(parser)
    parser.add_argument(
        'vname',
        type=str,
        help="Name of the armoor variable from which the quality tresholds will be applied."
        )
    parser.add_argument(
        'qc_thr',
        type=float,
        nargs=2,
        help="Quality control thresholds: minimum maximum acceptable values"
        )
    return parser

def main_filters_quality():
    """Apply quality control filters to input files via command line interface.
    
    This function serves as the main entry point for quality filtering operations.
    It parses command line arguments, configures quality control filters based on
    specified variable names and thresholds, and processes the input files accordingly.
    
    Positional Arguments
    --------------------
    qc_name : str
        Name of the quality control variable in the input files.
    qc_thr : float, float
        Minimum and maximum acceptable quality control values.
        Data points outside this range will be filtered out.
    
    Examples
    --------
    Command line usage:
    
    .. code-block:: bash
    
        armoor-filters-quality input.nc output.nc qc_flag 0.0 1.0
    
    Notes
    -----
    - Quality control filtering removes data points where the specified quality
      control variable falls outside the acceptable threshold range. This is
      commonly used to remove poor quality observations from oceanographic datasets.
    - Leverages Dask for memory-efficient processing of large datasets
    - Supports all input/output formats available in the ARMOOR ecosystem
    
    """
    # Get parser
    parser = get_parser_filters_quality()

    # Parse
    args = parser.parse_args()

    filters_config = {
        "quality":{
            "qname": args.vname,
            "qmin": args.qc_thr[0],
            "qmax": args.qc_thr[1]
            }
        }

    process_filters(args, filters_config)

def get_parser_filters_oceanvars():
    """Create argument parser for ocean variables filtering operations.
    
    Returns
    -------
    ArgumentParser
        Configured argument parser with ocean variables filtering options.
    
    Examples
    --------
    >>> parser = get_parser_filters_oceanvars()
    >>> args = parser.parse_args(['ptemp', 'sal'])
    """
    parser = ArgumentParser(
        description="Apply ocean variables filters over a list of input files.",
        formatter_class=ArmoorArgumentHelpFormatter,
        )
    add_logging_parser_arguments(parser)
    add_io_parser_arguments(parser)
    add_dask_parser_arguments(parser)
    parser.add_argument(
        'vnames',
        type=str,
        nargs="*",
        help="List of ocean variables"
        )
    return parser

def main_filters_oceanvars():
    """Apply ocean variables filters to input files via command line interface.
    
    This function serves as the main entry point for ocean variables filtering operations.
    It parses command line arguments, configures ocean variables filters based on
    specified variable names, and processes the input files accordingly.
    
    Positional Arguments
    --------------------
    vnames : list
        Names of the ocean variable to keep.
    
    Examples
    --------
    Command line usage:
    
    .. code-block:: bash
    
        armoor-filters-oceanvars input.nc output.nc ptemp sal
    
    Notes
    -----
    - Leverages Dask for memory-efficient processing of large datasets
    - Supports all input/output formats available in the ARMOOR ecosystem
    """
    # Get parser
    parser = get_parser_filters_oceanvars()

    # Parse
    args = parser.parse_args()

    filters_config = {
        "oceanvars": args.vnames
        }

    process_filters(args, filters_config)