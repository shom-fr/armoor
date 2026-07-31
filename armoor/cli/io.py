"""Input/Output utility functions for command-line argument parsing and data saving.

This module provides utility functions for adding standardized command-line arguments
related to input/output operations and saving xarray datasets in various formats.

Heavy imports (dask, armoor.base.io) are deferred to the functions that need them
so that importing this module for argument-parser setup is fast.
"""
import logging
from contextlib import contextmanager
from pathlib import Path

from armoor import ArmoorError
from armoor.base.misc import comma_separated, str2bool
from armoor.cli.log import main_setup_logging

logger = logging.getLogger(__name__)


def add_comp_parser_arguments(parser, default_level="info", has_coloc=True,
                               default_jsonfile='ncs_{func_comp}.json'):
    parser.add_argument(
        'metazones',
        type=comma_separated,
        help="List of metazone to be processed."
        )
    parser.add_argument(
        'cfgfile',
        type=Path,
        help="Path of the configuration file."
        )
    parser.add_argument(
        '-m', '--metazonesfile',
        type=Path,
        help="Path of the configuration file dedicated to the description of metazones.",
        default="metazones.cfg"
        )
    add_tbound_parser_arguments(parser)
    parser.add_argument(
        '--jsonfile',
        type=Path,
        help="Path of the output json file.",
        default=default_jsonfile
        )
    parser.add_argument(
        '--filters-only',
        action='store_true',
        help="Use for exiting after filters processes.",
        )
    if has_coloc:
        parser.add_argument(
            '--coloc-only',
            action='store_true',
            help="Use for exiting after colocation processes.",
            )
    stages = "filter+colocation+output" if has_coloc else "filter+output"
    parser.add_argument(
        '--no-plot',
        action='store_true',
        help=f"Run {stages} but skip the plot stage.",
        )
    parser.add_argument(
        '--plot-only',
        type=str,
        default=None,
        metavar='OTYPE',
        help="Run only plots for this output type (requires --input-json).",
        )
    parser.add_argument(
        '--input-json',
        type=Path,
        default=None,
        help="JSON file listing pre-computed output zarr paths (used with --plot-only).",
        )
    parser.add_argument(
        '--hosts-cfg',
        type=Path,
        default=None,
        metavar='PATH',
        help="Path to a woom hosts.cfg file for HPC scheduler detection. "
             "If absent, armoor runs in background mode.",
    )
    parser.add_argument(
        '--load-only',
        type=str,
        default=None,
        metavar='DATASET_KEY',
        help="Load-only mode: load a single dataset key for all metazones "
             "and write zarr paths to --jsonfile as {mz: [paths]}. "
             "Used internally by HPC Wave 0 jobs.",
    )
    parser.add_argument(
        '--input-zarrs',
        type=comma_separated,
        default=None,
        metavar='JSON,...',
        help="Comma-separated list of zarr-paths JSON files produced by Wave 0 load jobs. "
             "When provided, load_datasets() is skipped.",
    )

def add_tbound_parser_arguments(parser):
    """Add tbound argument to argument parser.
    
    Adds a optional argument 'tbound' for specifying time bounds
    
    Parameters
    ----------
    parser : argparse.ArgumentParser
        The argument parser to which the input file argument will be added.
    """
    parser.add_argument(
        "--tbound",
        type=str,
        nargs=2,
        help="Time bounds: begin_date end_date",
    )

def add_input_parser_arguments(parser):
    """Add input file pattern argument to argument parser.
    
    Adds a positional argument 'fins' for specifying input file patterns,
    supporting glob patterns for multiple file selection.
    
    Parameters
    ----------
    parser : argparse.ArgumentParser
        The argument parser to which the input file argument will be added.
    
    Examples
    --------
    >>> from argparse import ArgumentParser
    >>> parser = ArgumentParser()
    >>> add_input_parser_arguments(parser)
    >>> args = parser.parse_args(['croco_*.zarr'])
    >>> print(args.fins)
    'croco_*.zarr'
    
    Notes
    -----
    The input file pattern supports standard glob patterns such as:
    - '*' for matching any characters
    - '?' for matching single characters  
    - '[seq]' for matching any character in seq
    """
    parser.add_argument(
        "fins",
        type=str,
        help="Pattern of input file. Ex: croco_*.zarr",
    )


def add_output_parser_arguments(parser):
    """Add output file name argument to argument parser.
    
    Adds a positional argument 'fout' for specifying the output file path.
    
    Parameters
    ----------
    parser : argparse.ArgumentParser
        The argument parser to which the output file argument will be added.
    
    Examples
    --------
    >>> from argparse import ArgumentParser
    >>> parser = ArgumentParser()
    >>> add_output_parser_arguments(parser)
    >>> args = parser.parse_args(['output.zarr'])
    >>> print(args.fout)
    'output.zarr'
    """
    parser.add_argument(
        "fout",
        type=str,
        help="Name of the output file",
    )


def add_input_fmt_parser_arguments(parser):
    """Add input file format argument to argument parser.
    
    Adds an optional argument '--ifmt' for specifying the format of input files.
    This helps the system understand how to properly parse different model outputs.
    
    Parameters
    ----------
    parser : argparse.ArgumentParser
        The argument parser to which the input format argument will be added.
    
    Notes
    -----
    Supported input formats:
    
    - 'hycom' : HYCOM (HYbrid Coordinate Ocean Model) output format
    - 'cmems_model' : Copernicus Marine Environment Monitoring Service model format
    - 'croco' : CROCO (Coastal and Regional Ocean COmmunity model) output format  
    - 'armoor' : ARMOOR internal/native format
    
    Examples
    --------
    >>> from argparse import ArgumentParser
    >>> parser = ArgumentParser()
    >>> add_input_fmt_parser_arguments(parser)
    >>> args = parser.parse_args(['--ifmt', 'croco'])
    >>> print(args.ifmt)
    'croco'
    """
    parser.add_argument(
        "--ifmt",
        type=str,
        default="sloop",
        choices=(
            "hycom", "cmems_model", "croco", "armoor",
            "cmems_insitu", "cora_insitu",
            "cmems_sst_l3", "cersat_sst_l3", "cmems_sst_l4",
            "sloop",
            "eddy_pet", "eddy_sacso", "eddy_shoot",
            ),
        help="Format of the input files (default: sloop)",
    )
    parser.add_argument(
        "--platform",
        type=str,
        choices=("argo", "drifter", "glider", "mooring"),
        default=None,
        help="Type of platform in case of in situ observation",
    )


def add_output_fmt_parser_arguments(parser):
    """Add output file format argument to argument parser.
    
    Adds an optional argument '--ofmt' for specifying the format of output files.
    Defaults to 'zarr' format for optimal performance with large datasets.
    
    Parameters
    ----------
    parser : argparse.ArgumentParser
        The argument parser to which the output format argument will be added.
    
    Notes
    -----
    Supported output formats:
    
    - 'zarr' : Zarr chunked array storage format (default)
        - Optimized for cloud storage and parallel I/O
        - Better compression and performance for large datasets
    - 'netcdf' : Network Common Data Form format
        - Traditional format, widely supported
        - Good for smaller datasets and legacy compatibility
    
    Examples
    --------
    >>> from argparse import ArgumentParser
    >>> parser = ArgumentParser()
    >>> add_output_fmt_parser_arguments(parser)
    >>> args = parser.parse_args(['--ofmt', 'netcdf'])
    >>> print(args.ofmt)
    'netcdf'
    >>> 
    >>> # Default behavior
    >>> args = parser.parse_args([])
    >>> print(args.ofmt)
    'zarr'
    """
    parser.add_argument(
        "--ofmt",
        type=str,
        default="zarr",
        choices=("netcdf", "zarr"),
        help="Format of the output files",
    )


def add_io_parser_arguments(parser):
    """Add all input/output related arguments to argument parser.
    
    This is a convenience function that adds input file pattern, input format,
    output file name, and output format arguments to the parser in a single call.
    Ensures consistent I/O argument handling across different CLI commands.
    
    Parameters
    ----------
    parser : argparse.ArgumentParser
        The argument parser to which all I/O arguments will be added.
    
    Examples
    --------
    >>> from argparse import ArgumentParser
    >>> parser = ArgumentParser(description="Process oceanographic data")
    >>> add_io_parser_arguments(parser)
    >>> args = parser.parse_args([
    ...     'input_*.nc',           # fins (positional)
    ...     '--ifmt', 'croco',      # input format
    ...     'output.zarr',          # fout (positional)  
    ...     '--ofmt', 'zarr'        # output format
    ... ])
    >>> print(f"Input: {args.fins}, Format: {args.ifmt}")
    Input: input_*.nc, Format: croco
    >>> print(f"Output: {args.fout}, Format: {args.ofmt}")
    Output: output.zarr, Format: zarr
    
    Notes
    -----
    The order of arguments added is:
    1. Input file pattern (positional)
    2. Input format (optional)
    3. Output file name (positional) 
    4. Output format (optional, defaults to 'zarr')
    """
    add_input_parser_arguments(parser)
    add_input_fmt_parser_arguments(parser)
    add_output_parser_arguments(parser)
    add_output_fmt_parser_arguments(parser)

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
        choices=(
            "hycom", "cmems_model", "croco", "armoor", 
            "cmems_insitu", "cora_insitu",
            "cmems_sst_l3", "cersat_sst_l3", "cmems_sst_l4"
            ),
        help="Format of the input files",
    )
    parser.add_argument(
        "--ref-platform",
        type=str,
        choices=("argo", "drifter", "glider", "mooring"),
        default=None,
        help="Type of platform in case of in situ observation",
    )
    
def add_comp_io_parser_arguments(parser):
    """Add all input/output related arguments to argument colocation/comparison parser.
    """
    add_refinput_parser_arguments(parser)
    add_refinput_fmt_parser_arguments(parser)
    add_input_parser_arguments(parser)
    add_input_fmt_parser_arguments(parser)
    add_output_parser_arguments(parser)
    add_output_fmt_parser_arguments(parser)

def add_dask_nworkers_parser_arguments(parser):
    """Add dask argument to argument parser.
    
    Adds an optional argument '--dask-nworkers' for specifying n_workers dask.
    
    Parameters
    ----------
    parser : argparse.ArgumentParser
        The argument parser to which the output format argument will be added.
    """
    parser.add_argument(
        "--dask-nworkers",
        type=int,
        default=4,
        help="Number of workers of a Dask LocalCluster",
        )
    
def add_dask_processes_parser_arguments(parser):
    """Add dask argument to argument parser.
    
    Adds an optional argument '--dask-processes' for specifying n_workers dask.
    
    Parameters
    ----------
    parser : argparse.ArgumentParser
        The argument parser to which the output format argument will be added.
    """
    parser.add_argument(
        "--dask-processes",
        type=str2bool,
        default=False,
        help="Use dask processes: True/False",
        )
    
def add_dask_memorylimit_parser_arguments(parser):
    """Add dask argument to argument parser.
    
    Adds an optional argument '--dask-memorylimit' for specifying n_workers dask.
    
    Parameters
    ----------
    parser : argparse.ArgumentParser
        The argument parser to which the output format argument will be added.
    """
    parser.add_argument(
        "--dask-memorylimit",
        type=str,
        default=None,
        help="Memory_limit per worker of a Dask LocalCluster",
        )

def add_dask_dashboardaddress_parser_arguments(parser):
    """Add dask argument to argument parser.
    
    Adds an optional argument '--dask-dashboardaddress' for specifying n_workers dask.
    
    Parameters
    ----------
    parser : argparse.ArgumentParser
        The argument parser to which the output format argument will be added.
    """
    parser.add_argument(
        "--dask-dashboardaddress",
        type=str,
        default=":8787",
        help="Dashboard adress of a Dask LocalCluster",
        )
    
def add_dask_localdirectory_parser_arguments(parser):
    """Add dask argument to argument parser.
    
    Adds an optional argument '--dask-localdirectory' for specifying tempory dask directory.
    
    Parameters
    ----------
    parser : argparse.ArgumentParser
        The argument parser to which the output format argument will be added.
    """
    parser.add_argument(
        "--dask-localdirectory",
        type=str,
        default="/tmp",
        help="Path of the temporary dask directory.",
        )

def add_dask_parser_arguments(parser):
    """Add all dask related arguments to argument parser.
    """
    add_dask_nworkers_parser_arguments(parser)
    add_dask_processes_parser_arguments(parser)
    add_dask_memorylimit_parser_arguments(parser)
    add_dask_dashboardaddress_parser_arguments(parser)
    add_dask_localdirectory_parser_arguments(parser)

def save_output(ds, fout, ofmt="zarr", scheduler=None):
    """Save xarray Dataset to file in specified format.
    
    Saves the provided xarray Dataset to the specified output path using
    the requested format. Supports both NetCDF and Zarr formats with
    format-specific optimizations.
    
    Parameters
    ----------
    ds : xarray.Dataset
        The dataset to be saved to disk.
    fout : str
        Output file path. Should include appropriate extension for the format.
    ofmt : {'zarr', 'netcdf'}, default 'zarr'
        Output file format. Zarr is recommended for large datasets due to
        better compression and chunking capabilities.
    
    Raises
    ------
    ValueError
        If ofmt is not one of the supported formats ('zarr', 'netcdf').
    IOError
        If there are issues writing to the specified output path.
    
    Examples
    --------
    >>> import xarray as xr
    >>> import numpy as np
    >>> 
    >>> # Create sample dataset
    >>> data = np.random.rand(100, 50, 25)
    >>> ds = xr.Dataset({
    ...     'temperature': (['time', 'lat', 'lon'], data),
    ...     'coords': {
    ...         'time': range(100),
    ...         'lat': np.linspace(-90, 90, 50),
    ...         'lon': np.linspace(-180, 180, 25)
    ...     }
    ... })
    >>> 
    >>> # Save as zarr (default)
    >>> save_output(ds, 'output.zarr')
    >>> 
    >>> # Save as netcdf
    >>> save_output(ds, 'output.nc', ofmt='netcdf')
    
    Notes
    -----
    - For zarr format, uses optimized variable-by-variable saving via `to_zarr()`
    - For netcdf format, uses standard xarray `to_netcdf()` method
    - Zarr format is preferred for large datasets due to better performance
    """
    import dask
    from dask.diagnostics import ProgressBar
    from armoor.base.io import write_dataset_to_zarr, write_dataset_to_netcdf

    logger.info(f"Saving {fout}")
    if ofmt == "zarr":
        write_job = write_dataset_to_zarr(
            ds,
            fout,
            mode="w",
            consolidated=True,
            compute=False,
            )
    elif ofmt == "netcdf":
        write_job = write_dataset_to_netcdf(ds, fout, compute=False)
    else:
        raise ValueError(f"Unsupported output format: {ofmt}. Use 'zarr' or 'netcdf'.")
    # Use dask.config.set so the scheduler override propagates into
    # write_job.compute() → dask.compute() without needing to thread
    # kwargs through _BundledZarrWrite / _BundledNetcdfWrite.
    cfg = {"scheduler": scheduler} if scheduler else {}
    with dask.config.set(cfg):
        with ProgressBar():
            write_job.compute()


@contextmanager
def open_decode_materialized(fins, ifmt, platform=None):
    """Open+decode input files, materializing non-'armoor' formats first.

    Some downstream operations (interpolation, filtering) need dask-backed,
    chunked arrays; `open_decode` output for non-'armoor' formats isn't
    guaranteed to be, so it's round-tripped through a temporary zarr store
    to force materialization. The temporary store is removed on exit.
    """
    import shutil
    import xarray as xr
    from armoor.data.open_decode import open_decode

    ds = open_decode(fins, ifmt, platform=platform)
    if ifmt != 'armoor':
        save_output(ds, "tmp.zarr", ofmt="zarr", scheduler="threads")
        ds.close()
        ds = xr.open_dataset("tmp.zarr")
    try:
        yield ds
    finally:
        if ifmt != 'armoor':
            shutil.rmtree("tmp.zarr", ignore_errors=True)


def to_zarr(ds, fout):
    """Save xarray Dataset to zarr format with optimized memory usage.
    
    Saves each data variable separately to zarr format with automatic chunking,
    which optimizes memory usage for large datasets. Variables are written
    incrementally to avoid loading the entire dataset into memory.
    
    Parameters
    ----------
    ds : xarray.Dataset
        The dataset to be saved to zarr format.
    fout : str
        Output zarr store path (directory path, not file).
    
    Examples
    --------
    >>> import xarray as xr
    >>> import numpy as np
    >>> 
    >>> # Create large dataset
    >>> temp_data = np.random.rand(365, 180, 360)
    >>> salt_data = np.random.rand(365, 180, 360) * 35
    >>> 
    >>> ds = xr.Dataset({
    ...     'temperature': (['time', 'lat', 'lon'], temp_data),
    ...     'salinity': (['time', 'lat', 'lon'], salt_data)
    ... })
    >>> 
    >>> to_zarr(ds, 'ocean_data.zarr')
    
    Notes
    -----
    Memory optimization strategy:
    
    - Each variable is processed individually to minimize memory footprint
    - Automatic chunking is applied for optimal I/O performance  
    - First variable uses write mode ('w'), subsequent use append mode ('a')
    - Variable datasets are explicitly deleted after writing to free memory
    - Zarr encoding is obtained via `get_zarr_encoding()` for optimal storage
    
    The function logs progress for each variable being written, which is useful
    for monitoring the processing of large datasets.
    
    See Also
    --------
    get_zarr_encoding : Function to get optimal zarr encoding parameters
    save_output : Higher-level function that calls this for zarr format
    """
    ds = ds.chunk(chunks="auto")
    for ivar, var_name in enumerate(ds.data_vars):
        logger.info(f"Writing variable '{var_name}' to {fout}")
        
        # Select single variable to minimize memory usage
        var_ds = ds[var_name]
        # var_ds = var_ds.chunk('auto')
        
        # First variable overwrites, subsequent append
        mode = "w" if ivar == 0 else "a"
        
        var_ds.to_zarr(
            store=fout,
            mode=mode,
            # encoding=encoding[var_name]
            compute=False
        )
        # Explicit cleanup to free memory
        del var_ds

def get_dask_args(args):

    dask_dashboardaddress = args.dask_dashboardaddress
    if dask_dashboardaddress == "None":
        dask_dashboardaddress = None
    return (
        args.dask_nworkers,
        args.dask_processes,
        args.dask_memorylimit,
        dask_dashboardaddress,
        args.dask_localdirectory
        )


def configure_dask_scheduler(kw_dask):
    """Configure dask's local (non-distributed) scheduler from parsed
    --dask-* CLI args -- shared by armoor-data and armoor-comp-* so both
    stay in sync.

    "processes" gives each worker its own independent process (and its
    own independent numba/OpenMP runtime instance, with nothing shared to
    race on); "threads" runs every worker in this one process, sharing a
    single numba threading-layer instance across them.
    """
    import dask
    dask.config.set({
        'scheduler': 'processes' if kw_dask[1] else 'threads',
        'num_workers': kw_dask[0],
        'array.slicing.split_large_chunks': True,
        'optimization.fuse.active': True,
    })


def check_insitu_platform(fmt, platform):
    if (fmt == "cmems_insitu") and not platform:
        raise ArmoorError("`--platform` option is mandatory is case of specifying `cmems_insitu` format.")


@contextmanager
def armoor_cli_session(args, *ifmt_platform_pairs):
    """Standard setup/teardown shared by every armoor-* CLI entry point.

    Configures logging, registers CF conventions, validates each
    (ifmt, platform) pair via `check_insitu_platform`, then yields inside
    a Dask `LocalCluster` + `Client` context sized from `args`.

    Parameters
    ----------
    args : argparse.Namespace
        Parsed CLI arguments (must carry the `--dask-*` options).
    *ifmt_platform_pairs : tuple of (str, str or None)
        One pair per input dataset needing validation, e.g.
        `(args.ifmt, args.platform)` or, for ref/prod pipelines,
        `(args.ref_ifmt, args.ref_platform), (args.ifmt, args.platform)`.
    """
    from dask.distributed import Client, LocalCluster
    from armoor.base.io import setup_dask_client
    from armoor.data.open_decode import register_cf

    main_setup_logging(args)
    register_cf()
    for ifmt, platform in ifmt_platform_pairs:
        check_insitu_platform(ifmt, platform)

    kw_dask = get_dask_args(args)
    with LocalCluster(**setup_dask_client(*kw_dask)) as cluster:
        with Client(cluster):
            yield
