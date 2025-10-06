"""Command-line interface for armoor-coloc-*.

This module provides command-line interfaces for applying various types of interpolation
(temporal, horizontal, vertical) to oceanographic and meteorological data files.
The interpolation operations are optimized for large datasets using Dask distributed computing.
"""
import logging
from argparse import ArgumentParser
from dask.distributed import Client, LocalCluster

from armoor import ArmoorError

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

def get_parser_coloc():
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
 
    This function processes temporal colocation between reference and product datasets
    by matching their time coordinates. It uses Dask distributed computing for efficient
    processing of large datasets.
    
    The function performs the following steps:
    1. Parses command-line arguments for input/output specifications
    2. Sets up logging configuration
    3. Creates a Dask distributed cluster for parallel processing
    4. Opens and decodes reference and product datasets
    5. Extracts time boundaries from the reference dataset
    6. Applies temporal colocation using the specified parameters
    7. Saves the colocated output to the specified file format
    
    Command-line Arguments
    ----------------------
    ref_fins : str
        Pattern for reference input files (e.g., 'croco_*.zarr')
    --ref-ifmt : str
        Format of reference input files (choices: 'hycom', 'cmems_model', 'croco', 'armoor')
    fins : str
        Pattern for product input files
    --ifmt : str
        Format of product input files
    fout : str
        Output file path
    --ofmt : str
        Output file format
    --dask-nworkers : int, optional
        Number of Dask workers
    --dask-processes : bool, optional
        Use processes instead of threads for Dask workers
    --dask-memorylimit : str, optional
        Memory limit per Dask worker
    
    Notes
    -----
    - The function uses a LocalCluster for Dask distributed computing
    - Time boundaries are extracted from the reference dataset's time coordinate
    - The colocation parameter is set to ('trange_seq', (None, 'reference'))
    - Both input datasets are deleted after processing to free memory
    - All distributed computing logs are set to ERROR level to reduce verbosity
    
    See Also
    --------
    process_time_colocation : Core function that performs temporal colocation
    open_decode : Function to open and decode datasets
    save_output : Function to save processed datasets
    
    Examples
    --------
    Command-line usage:
    
    >>> armoor-coloc-time croco_ref_*.zarr input_*.nc output.zarr \\
    ...     --ref-ifmt croco --ifmt armoor --ofmt zarr \\
    ...     --dask-nworkers 4
    """
    # Get parser
    parser = get_parser_coloc()

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

def main_coloc_horizontal():
    """Apply horizontal colocation to input files via command line interface.
 
    This function processes horizontal colocation between reference and product datasets
    by matching their lon/lat coordinates. It uses Dask distributed computing for efficient
    processing of large datasets.
    
    The function performs the following steps:
    1. Parses command-line arguments for input/output specifications
    2. Sets up logging configuration
    3. Creates a Dask distributed cluster for parallel processing
    4. Opens and decodes reference and product datasets
    5. Applies horizontal colocation using the specified parameters
    6. Saves the colocated output to the specified file format
    
    Command-line Arguments
    ----------------------
    ref_fins : str
        Pattern for reference input files (e.g., 'croco_*.zarr')
    --ref-ifmt : str
        Format of reference input files (choices: 'hycom', 'cmems_model', 'croco', 'armoor')
    fins : str
        Pattern for product input files
    --ifmt : str
        Format of product input files
    fout : str
        Output file path
    --ofmt : str
        Output file format
    --dask-nworkers : int, optional
        Number of Dask workers
    --dask-processes : bool, optional
        Use processes instead of threads for Dask workers
    --dask-memorylimit : str, optional
        Memory limit per Dask worker
    
    Notes
    -----
    - The function uses a LocalCluster for Dask distributed computing
    - Both input datasets are deleted after processing to free memory
    - All distributed computing logs are set to ERROR level to reduce verbosity
    
    See Also
    --------
    process_horizontal_colocation : Core function that performs horizontal colocation
    open_decode : Function to open and decode datasets
    save_output : Function to save processed datasets
    
    Examples
    --------
    Command-line usage:
    
    >>> armoor-coloc-horizontal croco_ref_*.zarr input_*.nc output.zarr \\
    ...     --ref-ifmt croco --ifmt armoor --ofmt zarr \\
    ...     --dask-nworkers 4
    """
    # Get parser
    parser = get_parser_coloc()

    # Parse
    args = parser.parse_args()
    
    # Setup logging
    main_setup_logging(args)
    
    with LocalCluster(**setup_dask_client(args.dask_nworkers, args.dask_processes, args.dask_memorylimit)) as cluster:
        with Client(cluster):
            dsref = open_decode(args.ref_fins, args.ref_ifmt)
            dsprod = open_decode(args.fins, args.ifmt)
            if set(("x", "y")).issubset(dsref.lon.dims):
                param = ("href", "reference")
            elif (dsref.lon.dims == ("npts",)) or (dsref.lon.dims == ("time",)):
                param = ("cloud", list(zip(dsref.lat.values, dsref.lon.values)))
            else:
                raise ArmoorError(
                    "No horizontal colocation detected."
                    )
            _, dsout = process_horizontal_colocation(dsref, dsprod, param)
            del dsref
            del dsprod
            save_output(dsout, args.fout, args.ofmt)
            
def main_coloc_vertical():
    """Apply vertical colocation to input files via command line interface.
 
    This function processes vertical colocation between reference and product datasets
    by matching their vertical coordinates. It uses Dask distributed computing for efficient
    processing of large datasets.
    
    The function performs the following steps:
    1. Parses command-line arguments for input/output specifications
    2. Sets up logging configuration
    3. Creates a Dask distributed cluster for parallel processing
    4. Opens and decodes reference and product datasets
    5. Applies vertical colocation using the specified parameters
    6. Saves the colocated output to the specified file format
    
    Command-line Arguments
    ----------------------
    ref_fins : str
        Pattern for reference input files (e.g., 'croco_*.zarr')
    --ref-ifmt : str
        Format of reference input files (choices: 'hycom', 'cmems_model', 'croco', 'armoor')
    fins : str
        Pattern for product input files
    --ifmt : str
        Format of product input files
    fout : str
        Output file path
    --ofmt : str
        Output file format
    --dask-nworkers : int, optional
        Number of Dask workers
    --dask-processes : bool, optional
        Use processes instead of threads for Dask workers
    --dask-memorylimit : str, optional
        Memory limit per Dask worker
    
    Notes
    -----
    - The function uses a LocalCluster for Dask distributed computing
    - Both input datasets are deleted after processing to free memory
    - All distributed computing logs are set to ERROR level to reduce verbosity
    
    See Also
    --------
    process_vertical_colocation : Core function that performs vertical colocation
    open_decode : Function to open and decode datasets
    save_output : Function to save processed datasets
    
    Examples
    --------
    Command-line usage:
    
    >>> armoor-coloc-vertical croco_ref_*.zarr input_*.nc output.zarr \\
    ...     --ref-ifmt croco --ifmt armoor --ofmt zarr \\
    ...     --dask-nworkers 4
    """
    # Get parser
    parser = get_parser_coloc()

    # Parse
    args = parser.parse_args()
    
    # Setup logging
    main_setup_logging(args)
    
    with LocalCluster(**setup_dask_client(args.dask_nworkers, args.dask_processes, args.dask_memorylimit)) as cluster:
        with Client(cluster):
            dsref = open_decode(args.ref_fins, args.ref_ifmt)
            dsprod = open_decode(args.fins, args.ifmt)
            if ("depth" in dsref) and ("depth"  in dsprod):
                vname = "depth"
            elif ("pdens" in dsref) and ("pdens"  in dsprod):
                vname = "pdens"
            else:
                raise ArmoorError("No vertical coordinate found.")
            logger.info(f"Vertical coordinate is: {vname}")
            vcoord_original = dsref[vname]
            if len(vcoord_original.dims) > 1:
                if set(("x", "y")).issubset(vcoord_original.lon.dims):
                    if (vcoord_original == vcoord_original.isel(time=0, y=0, x=0)).all():
                        vcoord = vcoord_original.isel(time=0, y=0, x=0)
                    elif (dsref.lon == dsprod.lon).all() and (dsref.lat == dsprod.lat).all() and (dsref.time == dsprod.time).all():
                        vcoord = vcoord_original
                elif set(("npts",)).issubset(vcoord_original.lon.dims):
                    if "time" in vcoord_original.lon.dims:
                        dict2sel = {"time": 0, "npts": 0}
                    else:
                        dict2sel = {"npts": 0}
                    if (vcoord_original == vcoord_original.isel(dict2sel)).all():
                        vcoord = vcoord_original.isel(time=0, npts=0)
                    elif (dsref.lon == dsprod.lon).all() and (dsref.lat == dsprod.lat).all() and (dsref.time == dsprod.time).all():
                        vcoord = vcoord_original
            else:
                vcoord = vcoord_original
            if vcoord is not None:
                param = ("vrange", ("reference", vname, None))
            else:
                raise ArmoorError(f"Vertical coordinate {vname} varying in time, y, x")
            dsref["depth"] = vcoord
            _, dsout = process_vertical_colocation(dsref, dsprod, param)
            del dsref
            del dsprod
            save_output(dsout, args.fout, args.ofmt)
