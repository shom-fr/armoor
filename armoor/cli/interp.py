"""Command-line interface for armoor-interp-*.

This module provides command-line interfaces for applying various types of interpolation
(temporal, horizontal, vertical) to oceanographic and meteorological data files.
The interpolation operations are optimized for large datasets using Dask distributed computing.
"""
import logging, shutil
from argparse import ArgumentParser
from dask.distributed import Client, LocalCluster
import xarray as xr

from armoor.base.io import ArmoorArgumentHelpFormatter, setup_dask_client
from armoor.base.misc import parse_date, is_dict_empty, parse_coords
from armoor.cli.io import (
    add_io_parser_arguments,
    add_dask_parser_arguments,
    get_dask_args,
    save_output
)        
from armoor.cli.log import add_logging_parser_arguments, main_setup_logging
from armoor.data.interp import (
    process_time_interpolation,
    process_horizontal_interpolation,
    process_vertical_interpolation
    )
from armoor.data.open_decode import open_decode, register_cf


logger = logging.getLogger(__name__)

logging.getLogger('distributed').setLevel(logging.ERROR)


class InterpError(Exception):
    """Exception raised for errors in the interpolation module.
    
    This exception is raised when there are issues with interpolation configuration
    or execution, such as incompatible parameters, missing required arguments,
    or invalid interpolation specifications.
    """
    pass
    

def get_parser_interp_time():
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
        help="Time frequency for interpolation (pandas frequency string). Ex: 1H, 6H, 1D"
        )

    return parser


def main_interp_time():
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
    
    # Setup logging
    main_setup_logging(args)
    
    register_cf()
    
    kw_dask = get_dask_args(args)
    
    with LocalCluster(**setup_dask_client(*kw_dask)) as cluster:
        with Client(cluster):
            ds = open_decode(args.fins, args.ifmt)
            if args.ifmt != 'armoor':
                save_output(ds, "tmp.zarr", ofmt="zarr", scheduler="threads")
                del ds
                ds = xr.open_dataset("tmp.zarr")
            if ("depth" in ds.coords) and ("time" in ds["depth"].dims):
                ds = ds.reset_coords("depth")
            ds = process_time_interpolation(
                ds,
                ("tfreq", args.tfreq),
                [ds.time.min().values, ds.time.max().values]
                )
            save_output(ds, args.fout, ofmt=args.ofmt, scheduler="processes")
            if args.ifmt != 'armoor':
                shutil.rmtree("tmp.zarr")
                

def get_parser_interp_horizontal():
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
        help="String of comma-separated coordinates (lat,lon) tuples. Ex: '(45.0,2.0),(46.0,3.0),(44.0,4.0)'"
        )
    parser.add_argument(
        '--section',
        nargs="*",
        type=float,
        help="Linear section definition: lat0 lon0 lat1 lon1 .... step_km"
        )
    parser.add_argument(
        '--lon-grid',
        nargs=3,
        type=float,
        help="Longitude grid specification: lon_min lon_max lon_step"
        )
    parser.add_argument(
        '--lat-grid',
        nargs=3,
        type=float,
        help="Latitude grid specification: lat_min lat_max lat_step"
        )
    parser.add_argument(
        '--ncgrid',
        type=str,
        help="NetCDF file containing target grid lat/lon coordinates."
        )
    
    return parser


def main_interp_horizontal():
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
        Regular longitude grid: minimum, maximum, and step size in degrees.
    --lat-grid : float, float, float  
        Regular latitude grid: minimum, maximum, and step size in degrees.
        Required when --lon-grid is specified.
    --ncgrid : str
        Path to NetCDF file containing target grid coordinates.
    
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
    
    Notes
    -----
    - Only one interpolation method can be specified per execution
    - Regular grid interpolation requires both longitude and latitude specifications
    - Section interpolation creates points along a great circle path
    - Cloud point interpolation supports irregular scattered point distributions
    """
    # Get parser
    parser = get_parser_interp_horizontal()

    # Parse
    args = parser.parse_args()
    
    # Setup logging
    main_setup_logging(args)
    
    cloud = args.cloud
    section = args.section
    lon_grid = args.lon_grid
    lat_grid = args.lat_grid
    ncgrid = args.ncgrid
    
    if lon_grid and not lat_grid:
        raise InterpError(
            "--lat-grid is mandatory since --lon-grid is specified."
            )
    if lat_grid and not lon_grid:
        raise InterpError(
            "--lon-grid is mandatory since --lat-grid is specified."
            )
    if section:
        if len(section) %2 == 0:
            raise InterpError(
                "--section expects a odd length of arguments"
                )
            
    check = sum(1 for x in (cloud, section, lon_grid, ncgrid) if x is not None)
    if check > 1:
        raise InterpError(
            "--cloud, --section, --lon-grid and --ncgrid are not compatible."
            )
    elif check == 0:
        raise InterpError("No horizontal interpolation to be performed.")
        
    if cloud:
        params = ("cloud", cloud)
    elif section:
        it = iter(section[:-1])
        coords_pairs = list(zip(it, it))
        dx = section[-1]
        params = ("section", coords_pairs, dx)
    elif lon_grid:
        params = (
            "regrid_from_latlon", lon_grid, lat_grid
            )
    elif ncgrid:
        params = (
            "regrid_from_nc", ncgrid
            )
    
    register_cf()
    
    kw_dask = get_dask_args(args)
    
    with LocalCluster(**setup_dask_client(*kw_dask)) as cluster:
        with Client(cluster):
            ds = open_decode(args.fins, args.ifmt)
            if args.ifmt != 'armoor':
                save_output(ds, "tmp.zarr", ofmt="zarr", scheduler="threads")
                del ds
                ds = xr.open_dataset("tmp.zarr")
            if ("depth" in ds.coords) and ("time" in ds["depth"].dims):
                ds = ds.reset_coords("depth")
            ds = process_horizontal_interpolation(ds, params)
            save_output(ds, args.fout, ofmt=args.ofmt, scheduler="processes")
            if args.ifmt != 'armoor':
                shutil.rmtree("tmp.zarr")
        

def get_parser_interp_vertical():
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
        help="List of specific vertical levels for interpolation."
        )
    parser.add_argument(
        '--vfreq',
        type=float,
        help="Vertical spacing for regular level interpolation."
        )
    parser.add_argument(
        '--vname',
        default="depth",
        type=str,
        help="Name of vertical coordinate variable in input data."
        )
    return parser


def main_interp_vertical():
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
    
    # Setup logging
    main_setup_logging(args)
    
    register_cf()
    
    vlevel = args.vlevel
    vfreq = args.vfreq
    vname = args.vname
    
    check = sum(1 for x in (vlevel, vfreq) if x is not None)
    if check > 1:
        raise InterpError(
            "--vlevel and --vfreq are not compatible."
            )
    elif check == 0:
        raise InterpError("No vertical interpolation to be performed.")

    if vlevel:
        params = ("vlevel", (vname, vlevel))
    elif vfreq:
        params = ("vfreq", (vname, vfreq))
    
    kw_dask = get_dask_args(args)
    
    with LocalCluster(**setup_dask_client(*kw_dask)) as cluster:
        with Client(cluster):
            ds = open_decode(args.fins, args.ifmt)
            if args.ifmt != 'armoor':
                save_output(ds, "tmp.zarr", ofmt="zarr", scheduler="threads")
                del ds
                ds = xr.open_dataset("tmp.zarr")
            if ("depth" in ds.coords) and ("time" in ds["depth"].dims):
                ds = ds.reset_coords("depth")
            ds = process_vertical_interpolation(ds.chunk(dict(z=-1)), params)
            save_output(ds, args.fout, ofmt=args.ofmt, scheduler="processes")
            if args.ifmt != 'armoor':
                shutil.rmtree("tmp.zarr")
            