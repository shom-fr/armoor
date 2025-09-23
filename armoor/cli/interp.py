"""Command-line interface for armoor-*-filters."""
import logging
from argparse import ArgumentParser
from dask.distributed import Client

from armoor.base.io import ArmoorArgumentHelpFormatter, setup_dask_client
from armoor.base.misc import parse_date, is_dict_empty, parse_coords
from armoor.cli.io import (
    add_io_parser_arguments,
    save_output
)        
from armoor.cli.log import add_logging_parser_arguments, main_setup_logging
from armoor.data.interp import (
    process_time_interpolation,
    process_horizontal_interpolation,
    process_vertical_interpolation
    )
from armoor.data.open_decode import open_decode


logger = logging.getLogger(__name__)

logging.getLogger('distributed').setLevel(logging.ERROR)

class InterpError(Exception):
    pass
    

def get_parser_interp_time():
    """Get parser for applying time interpolation."""
    parser = ArgumentParser(
        description="Apply time interpolation over a list of input files.",
        formatter_class=ArmoorArgumentHelpFormatter,
        )
    add_logging_parser_arguments(parser)
    add_io_parser_arguments(parser)
    parser.add_argument(
        'tfreq',
        type=str,
        help="Time frequency. Ex: 1h"
        )

    return parser

def main_interp_time():
    """Apply time interpolation over input files."""
    # Get parser
    parser = get_parser_interp_time()

    # Parse
    args = parser.parse_args()
    
    # Setup logging
    main_setup_logging(args)
    
    with Client(**setup_dask_client()):
        ds = open_decode(args.fins, args.ifmt)
        ds = process_time_interpolation(
            ds,
            ("tfreq", args.tfreq),
            [ds.time.min().values, ds.time.max().values]
            )
        save_output(ds, args.fout, args.ofmt)
        
def get_parser_interp_horizontal():
    """Get parser for applying horizontal interpolation."""
    parser = ArgumentParser(
        description="Apply horizontal interpolation over a list of input files.",
        formatter_class=ArmoorArgumentHelpFormatter,
        )
    add_logging_parser_arguments(parser)
    add_io_parser_arguments(parser)
    parser.add_argument(
        '--cloud',
        type=parse_coords,
        help="Tuple of coordinates of cloud points (lat/lon)."
        )
    parser.add_argument(
        '--lon-grid',
        nargs=3,
        type=float,
        help="lon_min, lon_max, lon_step."
        )
    parser.add_argument(
        '--lat-grid',
        nargs=3,
        type=float,
        help="lat_min, lat_max, lat_step."
        )
    parser.add_argument(
        '--ncgrid',
        type=str,
        help="Netcdf file containing lat/lon coordinates of target grid."
        )
    return parser

def main_interp_horizontal():
    """Apply horizontal interpolation over input files."""
    # Get parser
    parser = get_parser_interp_horizontal()

    # Parse
    args = parser.parse_args()
    
    # Setup logging
    main_setup_logging(args)
    
    cloud = args.cloud
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
    check = sum(1 for x in (cloud, lon_grid, ncgrid) if x is not None)
    if check > 1:
        raise InterpError(
            "--cloud, --lon-grid and --ncgrid are not compatible."
            )
    elif check == 0:
        raise InterpError("No horizontal interpolation to be performed.")
        
    if cloud:
        params = ("cloud", cloud)
    elif lon_grid:
        params = (
            "regrid_from_latlon", lon_grid, lat_grid
            )
    elif ncgrid:
        params = (
            "regrid_from_nc", ncgrid
            )
        
    with Client(**setup_dask_client()):
        ds = open_decode(args.fins, args.ifmt)
        ds = process_horizontal_interpolation(ds, params)
        save_output(ds, args.fout, args.ofmt)
    
    
    
    
    
    
    
    
    
    
 