"""Command-line interface for armoor-interp-\*.

This module provides command-line interfaces for applying various types of interpolation
(temporal, horizontal, vertical) to oceanographic data files.
The interpolation operations are optimized for large datasets using Dask distributed computing.
"""

import logging
from argparse import ArgumentParser

from armoor.io import ArmoorArgumentHelpFormatter
from armoor.misc import parse_coords
from armoor.cli.io import (
    add_io_parser_arguments,
    add_dask_parser_arguments,
    save_output,
    armoor_cli_session,
    open_decode_materialized,
)
from armoor.cli.log import add_logging_parser_arguments
import armoor  # noqa: F401 — registers ds.interp accessor


logger = logging.getLogger(__name__)

logging.getLogger('distributed').setLevel(logging.ERROR)


class InterpError(Exception):
    """Exception raised for errors in the interpolation module.

    This exception is raised when there are issues with interpolation configuration
    or execution, such as incompatible parameters, missing required arguments,
    or invalid interpolation specifications.
    """

    pass


def get_parser_interp_time() -> ArgumentParser:
    """Create argument parser for temporal interpolation operations.

    Returns
    -------
    ArgumentParser
        Configured argument parser with temporal interpolation options including
        time frequency specification for resampling operations.

    Examples
    --------
    >>> parser = get_parser_interp_time()
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
        description="Apply time interpolation over a list of input files.",
        formatter_class=ArmoorArgumentHelpFormatter,
    )
    add_logging_parser_arguments(parser)
    add_io_parser_arguments(parser)
    add_dask_parser_arguments(parser)
    parser.add_argument(
        'tfreq',
        type=str,
        help="Time frequency for interpolation (pandas frequency string). Ex: 1H, 6H, 1D",
    )

    return parser


def main_interp_time() -> None:
    """Apply temporal interpolation to input files via command line interface.

    This function serves as the main entry point for temporal interpolation operations.
    It parses command line arguments, configures temporal interpolation parameters,
    and processes input files using Dask distributed computing for optimal performance.

    The interpolation is performed over the full time range present in the input data,
    resampling to the specified frequency using advanced interpolation methods.

    Positional Arguments
    --------------------
    tfreq : str
        Time frequency for interpolation using pandas frequency strings.
        Common values: '1H' (hourly), '6H' (6-hourly), '1D' (daily), '1M' (monthly).

    Examples
    --------
    Command line usage:

    .. code-block:: bash

        # Interpolate to hourly frequency
        armoor-interp-time input.nc output.nc 1H --ifmt croco

        # Interpolate to daily frequency
        armoor-interp-time input.nc output.nc 1D --ifmt croco

    Notes
    -----
    - Temporal interpolation preserves data quality while providing regular time sampling
    - Uses the full time range from input data (min to max timestamps)
    - Leverages Dask for memory-efficient processing of large datasets
    - Supports all input/output formats available in the ARMOOR ecosystem
    """
    # Get parser
    parser = get_parser_interp_time()

    # Parse
    args = parser.parse_args()

    with armoor_cli_session(args, (args.ifmt, args.platform)):
        with open_decode_materialized(args.fins, args.ifmt, platform=args.platform) as ds:
            if ("depth" in ds.coords) and ("time" in ds["depth"].dims):
                ds = ds.reset_coords("depth")
            ds = ds.interp.tfreq(args.tfreq)
            # "threads" deadlocks intermittently: xarray's netCDF4 write lock
            # is a CombinedLock over several process-global locks, and
            # multiple dask worker threads doing netCDF I/O concurrently can
            # block on each other acquiring them (confirmed via py-spy on
            # stuck armoor-interp-* processes; "synchronous" -- single
            # thread, no lock contention possible -- doesn't).
            save_output(ds, args.fout, ofmt=args.ofmt, scheduler="synchronous")


def get_parser_interp_horizontal() -> ArgumentParser:
    """Create argument parser for horizontal spatial interpolation operations.

    Returns
    -------
    ArgumentParser
        Configured argument parser with horizontal interpolation options including
        cloud points, sections, regular grids, and NetCDF grid specifications.

    Examples
    --------
    >>> parser = get_parser_interp_horizontal()
    >>> args = parser.parse_args(['--cloud', '45.0,2.0', '46.0,3.0', 'input.nc', 'output.zarr'])

    Notes
    -----
    Horizontal interpolation methods (mutually exclusive):

    - **Cloud points**: Irregular scattered points defined by lat/lon coordinates
    - **Section**: Linear transect between two geographic points with specified spacing
    - **Regular grid**: Rectangular lat/lon grid with uniform spacing
    - **NetCDF grid**: Grid coordinates read from existing NetCDF file
    - **Coarsen**: Block aggregation onto a coarser structured grid
    """
    parser = ArgumentParser(
        description="Apply horizontal interpolation over a list of input files.",
        formatter_class=ArmoorArgumentHelpFormatter,
    )
    add_logging_parser_arguments(parser)
    add_io_parser_arguments(parser)
    add_dask_parser_arguments(parser)
    parser.add_argument(
        '--cloud',
        type=parse_coords,
        help="String of comma-separated coordinates (lat,lon) tuples. Ex: '(45.0,2.0),(46.0,3.0),(44.0,4.0)'",
    )
    parser.add_argument(
        '--section',
        nargs="*",
        type=float,
        help="Linear section definition: lat0 lon0 lat1 lon1 .... step_km",
    )
    parser.add_argument(
        '--lon-grid',
        nargs=3,
        type=float,
        help="Longitude grid specification: lon_min lon_max lon_step",
    )
    parser.add_argument(
        '--lat-grid',
        nargs=3,
        type=float,
        help="Latitude grid specification: lat_min lat_max lat_step",
    )
    parser.add_argument(
        '--ncgrid',
        type=str,
        help="NetCDF file in armoor format containing target grid lat/lon coordinates.",
    )
    parser.add_argument(
        '--regrid-method',
        choices=["bilinear", "bicubic", "conservative"],
        default="bilinear",
        help="Regridding method of --lon-grid and --ncgrid.",
    )
    parser.add_argument(
        '--regrid-weights',
        metavar='FILE',
        help="NetCDF file where the regridding weights are loaded from if already there, "
        "and saved to otherwise, to be reused by later runs on the same grids.",
    )
    parser.add_argument(
        '--coarsen-factor',
        type=int,
        metavar='FACTOR',
        help="Coarsening factor applied to both x and y dimensions (e.g. 4 degrades a 1/12° grid to ~1/3°).",
    )
    parser.add_argument(
        '--coarsen-boundary',
        choices=["trim", "pad"],
        default="trim",
        help="How to handle sizes not divisible by the coarsening factor (default: trim).",
    )
    parser.add_argument(
        '--coarsen-method',
        choices=["mean", "median", "min", "max"],
        default="mean",
        help="Block aggregation method (default: mean).",
    )

    return parser


def main_interp_horizontal() -> None:
    """Apply horizontal spatial interpolation to input files via command line interface.

    This function serves as the main entry point for horizontal interpolation operations.
    It parses command line arguments, validates interpolation parameters, and processes
    input files using various spatial interpolation methods.

    Command Line Arguments
    ----------------------
    --cloud : list of tuples
        Scattered point coordinates as (lat,lon) pairs for irregular interpolation.
    --section : float, float, float, float, float
        Linear section from (lat0,lon0) to (lat1,lon1) with step size in kilometers.
    --lon-grid : float, float, float
        Regular longitude grid: minimum, maximum, and step size in km.
    --lat-grid : float, float, float
        Regular latitude grid: minimum, maximum, and step size in km.
        Required when --lon-grid is specified.
    --ncgrid : str
        Path to NetCDF file containing target grid coordinates.
    --regrid-method : {"bilinear", "bicubic", "conservative"}
        Regridding method of --lon-grid and --ncgrid (default: bilinear).
    --regrid-weights : str
        NetCDF file of the regridding weights, reused when already there.
    --coarsen-factor : int
        Coarsening factor applied to both x and y dimensions.
    --coarsen-boundary : {"trim", "pad"}
        How to handle sizes not divisible by the factor (default: trim).
    --coarsen-method : {"mean", "median", "min", "max"}
        Block aggregation method (default: mean).

    Raises
    ------
    InterpError
        If latitude grid is missing when longitude grid is specified, if longitude
        grid is missing when latitude grid is specified, if multiple incompatible
        interpolation methods are specified, or if no interpolation method is provided.

    Examples
    --------
    Command line usage:

    .. code-block:: bash

        # Interpolate to scattered cloud points
        armoor-interp-horizontal input.nc output.zarr \\
                                --cloud '(45.0,2.0),(46.0,3.0),(44.0,4.0)'

        # Create linear section with 5km spacing
        armoor-interp-horizontal input.nc output.zarr \\
                                --section 45.0 2.0 46.0 4.0 5.0

        # Regular grid interpolation
        armoor-interp-horizontal input.nc output.zarr \\
                            --lon-grid -5.0 10.0 0.1 \\
                            --lat-grid 40.0 50.0 0.1

        # Use existing grid from NetCDF file
        armoor-interp-horizontal input.nc output.zarr \\
                                --ncgrid target_grid.nc

        # Conservative regridding, with weights reused across runs
        armoor-interp-horizontal input.nc output.zarr \\
                                --ncgrid target_grid.nc --regrid-method conservative \\
                                --regrid-weights weights.nc

        # Coarsen by a factor of 4 (mean aggregation)
        armoor-interp-horizontal input.nc output.zarr \\
                                --coarsen-factor 4

        # Coarsen by a factor of 8 using median, pad incomplete blocks
        armoor-interp-horizontal input.nc output.zarr \\
                                --coarsen-factor 8 --coarsen-boundary pad --coarsen-method median

    Notes
    -----
    - Only one interpolation method can be specified per execution
    - Regular grid interpolation requires both longitude and latitude specifications
    - Section interpolation creates points along a great circle path
    - Cloud point interpolation supports irregular scattered point distributions
    - Coarsening works on structured grids only (x and y dimensions required)
    """
    # Get parser
    parser = get_parser_interp_horizontal()

    # Parse
    args = parser.parse_args()

    cloud = args.cloud
    section = args.section
    lon_grid = args.lon_grid
    lat_grid = args.lat_grid
    ncgrid = args.ncgrid
    coarsen_factor = args.coarsen_factor

    if lon_grid and not lat_grid:
        raise InterpError("--lat-grid is mandatory since --lon-grid is specified.")
    if lat_grid and not lon_grid:
        raise InterpError("--lon-grid is mandatory since --lat-grid is specified.")
    if section:
        if len(section) % 2 == 0:
            raise InterpError("--section expects a odd length of arguments")

    check = sum(1 for x in (cloud, section, lon_grid, ncgrid, coarsen_factor) if x is not None)
    if check > 1:
        raise InterpError(
            "--cloud, --section, --lon-grid, --ncgrid and --coarsen-factor are not compatible."
        )
    elif check == 0:
        raise InterpError("No horizontal interpolation to be performed.")

    with armoor_cli_session(args, (args.ifmt, args.platform)):
        with open_decode_materialized(args.fins, args.ifmt, platform=args.platform) as ds:
            if ("depth" in ds.coords) and ("time" in ds["depth"].dims):
                ds = ds.reset_coords("depth")
            if cloud:
                ds = ds.interp.grid2loc(cloud)
            elif section:
                it = iter(section[:-1])
                coords_pairs = list(zip(it, it))
                ds = ds.interp.grid2section(coords_pairs, dx=section[-1])
            elif lon_grid:
                ds = ds.interp.regrid_from_latlon(
                    lon_grid, lat_grid, method=args.regrid_method, weights_file=args.regrid_weights
                )
            elif ncgrid:
                ds = ds.interp.regrid_from_nc(
                    ncgrid, method=args.regrid_method, weights_file=args.regrid_weights
                )
            elif coarsen_factor:
                ds = ds.interp.coarsen(
                    coarsen_factor,
                    boundary=args.coarsen_boundary,
                    method=args.coarsen_method,
                )
            # "threads" deadlocks intermittently: xarray's netCDF4 write lock
            # is a CombinedLock over several process-global locks, and
            # multiple dask worker threads doing netCDF I/O concurrently can
            # block on each other acquiring them (confirmed via py-spy on
            # stuck armoor-interp-* processes; "synchronous" -- single
            # thread, no lock contention possible -- doesn't).
            save_output(ds, args.fout, ofmt=args.ofmt, scheduler="synchronous")


def get_parser_interp_vertical() -> ArgumentParser:
    """Create argument parser for vertical interpolation operations.

    Returns
    -------
    ArgumentParser
        Configured argument parser with vertical interpolation options including
        specific vertical levels and regular vertical spacing.

    Examples
    --------
    >>> parser = get_parser_interp_vertical()
    >>> args = parser.parse_args(['--vlevel', '0', '10', '20', '50', 'input.nc', 'output.zarr'])

    Notes
    -----
    Vertical interpolation methods (mutually exclusive):

    - **Specific levels**: Interpolate to user-defined depth/height levels
    - **Regular spacing**: Interpolate to regularly spaced vertical levels
    """
    parser = ArgumentParser(
        description="Apply vertical interpolation over a list of input files.",
        formatter_class=ArmoorArgumentHelpFormatter,
    )
    add_logging_parser_arguments(parser)
    add_io_parser_arguments(parser)
    add_dask_parser_arguments(parser)
    parser.add_argument(
        '--vlevel',
        nargs="*",
        type=float,
        help="List of specific vertical levels for interpolation.",
    )
    parser.add_argument(
        '--vfreq', type=float, help="Vertical spacing for regular level interpolation."
    )
    parser.add_argument(
        '--vname',
        default="depth",
        type=str,
        help="Name of vertical coordinate variable in input data.",
    )
    return parser


def main_interp_vertical() -> None:
    """Apply vertical interpolation to input files via command line interface.

    This function serves as the main entry point for vertical interpolation operations.
    It parses command line arguments, validates vertical interpolation parameters,
    and processes input files using depth/height-based interpolation methods.

    Command Line Arguments
    ----------------------
    --vlevel : list of float
        Specific vertical levels for interpolation. Units should match the
        vertical coordinate in the input data (typically meters for depth).
    --vfreq : float
        Regular vertical spacing for interpolation. Creates evenly spaced levels
        throughout the vertical range of the input data.
    --vname : str, default 'depth'
        Name of the vertical coordinate variable in input files.
        Common names: 'depth', 'height', 'level', 'z'.

    Raises
    ------
    InterpError
        If both --vlevel and --vfreq are specified (incompatible), or if neither
        is provided (no interpolation to perform).

    Examples
    --------
    Command line usage:

    .. code-block:: bash

        # Interpolate to specific depth levels
        armoor-interp-vertical input.nc output.zarr \\
                                --vlevel 0 10 20 50 100 200 500 \\
                                --vname depth


        # Regular 25-meter spacing interpolation
        armoor-interp-vertical input.nc output.zarr \\
                                --vfreq 25.0 --vname depth

    Notes
    -----
    - Vertical interpolation preserves horizontal structure while resampling vertically
    - Extrapolation beyond data bounds is handled according to interpolation method
    - Regular spacing (--vfreq) automatically determines levels within data range
    - Specific levels (--vlevel) allow targeting particular depths/heights of interest
    - Vertical coordinate name must match the variable name in input files
    """
    # Get parser
    parser = get_parser_interp_vertical()

    # Parse
    args = parser.parse_args()

    vlevel = args.vlevel
    vfreq = args.vfreq
    vname = args.vname

    check = sum(1 for x in (vlevel, vfreq) if x is not None)
    if check > 1:
        raise InterpError("--vlevel and --vfreq are not compatible.")
    elif check == 0:
        raise InterpError("No vertical interpolation to be performed.")

    with armoor_cli_session(args, (args.ifmt, args.platform)):
        with open_decode_materialized(args.fins, args.ifmt, platform=args.platform) as ds:
            if ("depth" in ds.coords) and ("time" in ds["depth"].dims):
                ds = ds.reset_coords("depth")
            ds_chunked = ds.chunk(dict(z=-1))
            if vlevel:
                ds = ds_chunked.interp.vertical(vname, vlevel)
            elif vfreq:
                ds = ds_chunked.interp.vfreq(vname, vfreq)
            # "threads" deadlocks intermittently: xarray's netCDF4 write lock
            # is a CombinedLock over several process-global locks, and
            # multiple dask worker threads doing netCDF I/O concurrently can
            # block on each other acquiring them (confirmed via py-spy on
            # stuck armoor-interp-* processes; "synchronous" -- single
            # thread, no lock contention possible -- doesn't).
            save_output(ds, args.fout, ofmt=args.ofmt, scheduler="synchronous")
