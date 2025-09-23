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
from armoor.data.open_decode import open_decode


logger = logging.getLogger(__name__)

logging.getLogger('distributed').setLevel(logging.ERROR)

class FiltersError(Exception):
    pass


def process_filters(fins, ifmt, fout, ofmt, filters_config):
    
    if is_dict_empty(filters_config):
        raise FiltersError("No filters to be applied.")

    with Client(**setup_dask_client()):
        ds = open_decode(
            fins, ifmt
            ).armoorfilters.apply_combined_filters(
            filters_config
            )
        save_output(ds, fout, ofmt)

def get_parser_filters_time():
    """Get parser for applying time filters."""
    parser = ArgumentParser(
        description="Apply time filters over a list of input files.",
        formatter_class=ArmoorArgumentHelpFormatter,
        )
    add_logging_parser_arguments(parser)
    add_io_parser_arguments(parser)
    parser.add_argument(
        '--date-range',
        nargs=2,
        type=parse_date,
        help="Start and end dates"
        )
    parser.add_argument(
        '--tides',
        type=str,
        choices=("mean", "godin", "demerliac"),
        help="Name of tidal filter: mean, godin or demerliac."
        )

    return parser

def main_filters_time():
    """Apply time filters over input files."""
    # Get parser
    parser = get_parser_filters_time()

    # Parse
    args = parser.parse_args()
    
    # Setup logging
    main_setup_logging(args)
    
    filters_config = {}
    
    #date range
    date_range = args.date_range
    if date_range:
        filters_config.update({
            'time_selection': {
                'minimum': date_range[0],
                'maximum': date_range[1]
                }
            })

    #tidal filter
    tides = args.tides
    if tides:
        filters_config.update({
            'tide': tides
            })
    
    process_filters(
        args.fins, args.ifmt, args.fout, args.ofmt, filters_config
        )

def get_parser_filters_horizontal():
    """Get parser for applying horizontal filters."""
    parser = ArgumentParser(
        description="Apply horizontal filters over a list of input files.",
        formatter_class=ArmoorArgumentHelpFormatter,
        )
    add_logging_parser_arguments(parser)
    add_io_parser_arguments(parser)
    parser.add_argument(
        '--polygon-dilat',
        type=bool,
        default=False,
        help="Extent polygon, usefull for regridding : True or False"
        )
    parser.add_argument(
        '--polygon-coords',
        type=parse_coords,
        help="list of tuple (lat, lon)"
        )
    parser.add_argument(
        '--bathy-file',
        type=str,
        help="NetCDF file containing bathy to use."
        )
    parser.add_argument(
        '--bathy-fmt',
        type=str,
        choices=("croco", "hycom", "armoor"),
        help="Format of the netcdf file."
        )
    parser.add_argument(
        '--bathy-thr',
        type=float,
        nargs=2,
        help="Bathy thresholds: min max"
        )
    return parser

def main_filters_horizontal():
    """Apply horizontal filters over input files."""
    # Get parser
    parser = get_parser_filters_horizontal()

    # Parse
    args = parser.parse_args()
    
    # Setup logging
    main_setup_logging(args)
    
    filters_config = {}
    
    coords = args.polygon_coords
    if coords:
        if len(coords) > 3:
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
        bathy_thr = args.bathy_thr
        if not bathy_fmt:
            raise FiltersError(
                "--bathy-fmt is mandatory since --bathy-file is specified."
                )
        if not bathy_thr:
            raise FiltersError(
                "--bathy-thr is mandatory since --bathy-file is specified."
                )
        filters_config.update({
            "bathy":{
                "path": bathy_file,
                "fmt": bathy_fmt,
                "min": bathy_thr[0],
                "max": bathy_thr[1]
                }
            })
    process_filters(
        args.fins, args.ifmt, args.fout, args.ofmt, filters_config
        )

def get_parser_filters_quality():
    """Get parser for applying quality filters."""
    parser = ArgumentParser(
        description="Apply quality filters over a list of input files.",
        formatter_class=ArmoorArgumentHelpFormatter,
        )
    add_logging_parser_arguments(parser)
    add_io_parser_arguments(parser)
    parser.add_argument(
        'qc-name',
        type=str,
        help="Quality control variable name"
        )
    parser.add_argument(
        'qc-thr',
        type=float,
        nargs=2,
        help="Quality control thresholds: min max"
        )
    return parser

def main_filters_quality():
    """Apply quality filters over input files."""
    # Get parser
    parser = get_parser_filters_quality()

    # Parse
    args = parser.parse_args()
    
    # Setup logging
    main_setup_logging(args)
    
    filters_config = {}
   
    filters_config = {
        "quality":{
            "qname": args.qc_var,
            "qmin": args.qc_thr[0],
            "qmax": args.qc_thr[1]
            }
        }  
    process_filters(
        args.fins, args.ifmt, args.fout, args.ofmt, filters_config
        )
    