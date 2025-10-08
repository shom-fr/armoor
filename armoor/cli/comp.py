"""Command-line interface for armoor-comp.

This module provides command-line interfaces for applying various types of comparison
(temporal, horizontal, vertical) to oceanographic and meteorological data files.
The interpolation operations are optimized for large datasets using Dask distributed computing.
"""
import logging
from argparse import ArgumentParser
from dask.distributed import Client, LocalCluster
import pandas as pd
import xarray as xr
import numpy as np

from armoor.base.io import ArmoorArgumentHelpFormatter, setup_dask_client
from armoor.base.misc import parse_date, is_dict_empty, parse_coords
from armoor.cli.io import (
    add_comp_io_parser_arguments,
    add_dask_parser_arguments,
    save_output
)        
from armoor.cli.log import add_logging_parser_arguments, main_setup_logging
from armoor.data.range import (
    process_time_range,
    process_vertical_range
    )
from armoor.data.open_decode import open_decode


logger = logging.getLogger(__name__)

logging.getLogger('distributed').setLevel(logging.ERROR)

class CompError(Exception):
    """Exception raised for errors in the comp module.
    
    This exception is raised when there are issues with comp configuration
    or execution, such as incompatible parameters, missing required arguments,
    or invalid comp specifications.
    """
    pass


def drop_time_range(dsref, dsprod):
    """
    Drop the 'time_range' variable from reference and product datasets.
    
    Parameters
    ----------
    dsref : xarray.Dataset
        Reference dataset.
    dsprod : xarray.Dataset
        Product dataset.
    
    Returns
    -------
    dsref : xarray.Dataset
        Reference dataset without 'time_range' variable.
    dsprod : xarray.Dataset
        Product dataset without 'time_range' variable.
    """
    dsref = dsref.drop_vars("time_range")
    dsprod = dsprod.drop_vars("time_range")
    return dsref, dsprod


def rename_stat_var(ds, stat):
    """
    Rename all data variables in a dataset by adding a prefix.
    
    Parameters
    ----------
    ds : xarray.Dataset
        Input dataset.
    stat : str
        Prefix to add to all variable names.
    
    Returns
    -------
    xarray.Dataset
        Dataset with renamed variables in the format '{stat}_{var}'.
    """
    dico = {}
    for var in ds.data_vars:
        dico.update({
            var: f"{stat}_{var}"
        })
    return ds.rename_vars(dico)

    
def diff(dsref, dsprod):
    """
    Calculate the difference between reference and product datasets.
    
    Parameters
    ----------
    dsref : xarray.Dataset
        Reference dataset.
    dsprod : xarray.Dataset
        Product dataset.
    
    Returns
    -------
    xarray.Dataset
        Element-wise difference (dsref - dsprod).
    """
    return dsref - dsprod


def cdiff(dsref, dsprod, dim):
    """
    Calculate the centered difference between reference and product datasets.
    
    The centered difference removes the mean along the specified dimension
    from both datasets before computing the difference.
    
    Parameters
    ----------
    dsref : xarray.Dataset
        Reference dataset.
    dsprod : xarray.Dataset
        Product dataset.
    dim : str or list of str
        Dimension(s) along which to compute the mean.
    
    Returns
    -------
    xarray.Dataset
        Centered difference: (dsref - mean(dsref)) - (dsprod - mean(dsprod)).
    """
    return ((
        dsref - dsref.mean(dim=dim)
    ) - (
        dsprod - dsprod.mean(dim=dim)    
    ))


def mean(ds, dim):
    """
    Calculate the mean of a dataset along specified dimension(s).
    
    Parameters
    ----------
    ds : xarray.Dataset
        Input dataset.
    dim : str or list of str
        Dimension(s) along which to compute the mean.
    
    Returns
    -------
    xarray.Dataset
        Dataset with mean values along the specified dimension(s).
    """
    return ds.mean(dim=dim)


def std(ds, dim):
    """
    Calculate the standard deviation of a dataset along specified dimension(s).
    
    Parameters
    ----------
    ds : xarray.Dataset
        Input dataset.
    dim : str or list of str
        Dimension(s) along which to compute the standard deviation.
    
    Returns
    -------
    xarray.Dataset
        Dataset with standard deviation values along the specified dimension(s).
    """
    return ds.std(dim=dim)


def bias(dsref, dsprod, dim):
    """
    Calculate the bias between reference and product datasets.
    
    The bias is the mean difference between the reference and product datasets
    along the specified dimension(s).
    
    Parameters
    ----------
    dsref : xarray.Dataset
        Reference dataset.
    dsprod : xarray.Dataset
        Product dataset.
    dim : str or list of str
        Dimension(s) along which to compute the mean.
    
    Returns
    -------
    xarray.Dataset
        Mean bias (mean of dsref - dsprod along dim).
    """
    return (dsref - dsprod).mean(dim=dim)

    
def rms(dsref, dsprod, dim):
    """
    Calculate the root mean square difference between reference and product datasets.
    
    Parameters
    ----------
    dsref : xarray.Dataset
        Reference dataset.
    dsprod : xarray.Dataset
        Product dataset.
    dim : str or list of str
        Dimension(s) along which to compute the RMS.
    
    Returns
    -------
    xarray.Dataset
        Root mean square of the difference.
    """
    return np.sqrt((diff(dsref, dsprod) ** 2).mean(dim=dim))

    
def crms(dsref, dsprod, dim):
    """
    Calculate the centered root mean square difference between datasets.
    
    The centered RMS removes the mean bias before computing the RMS,
    measuring the variability difference independent of the mean bias.
    
    Parameters
    ----------
    dsref : xarray.Dataset
        Reference dataset.
    dsprod : xarray.Dataset
        Product dataset.
    dim : str or list of str
        Dimension(s) along which to compute the centered RMS.
    
    Returns
    -------
    xarray.Dataset
        Centered root mean square difference.
    """
    return np.sqrt((cdiff(dsref, dsprod, dim) ** 2).mean(dim=dim))

    
def process_diff(dsref, dsprod):
    """
    Process and merge reference, product, and difference datasets.
    
    Computes the difference between reference and product datasets,
    renames variables with appropriate prefixes, and merges all into
    a single dataset.
    
    Parameters
    ----------
    dsref : xarray.Dataset
        Reference dataset.
    dsprod : xarray.Dataset
        Product dataset.
    
    Returns
    -------
    xarray.Dataset
        Merged dataset containing:
            
        - Variables prefixed with `ref_` from the reference dataset
        - Variables prefixed with `prod_` from the product dataset
        - Variables prefixed with `diff_` for the difference
    
    Notes
    -----
    The 'time_range' variable is dropped if present in the input datasets.
    """
    if "time_range" in dsref:
        dsref, dsprod = drop_time_range(dsref, dsprod)
    ds = diff(dsref, dsprod)
    ds = rename_stat_var(ds, "diff")
    dsref = rename_stat_var(dsref, "ref")
    dsprod = rename_stat_var(dsprod, "prod")
    return xr.merge([dsref, dsprod, ds])


def process_stat(dsref, dsprod, dim):
    """
    Compute comprehensive statistics comparing reference and product datasets.
    
    Calculates mean and standard deviation for both datasets, as well as
    bias, RMS, and centered RMS between them along the specified dimension(s).
    
    Parameters
    ----------
    dsref : xarray.Dataset
        Reference dataset.
    dsprod : xarray.Dataset
        Product dataset.
    dim : str or list of str
        Dimension(s) along which to compute the statistics.
    
    Returns
    -------
    xarray.Dataset
        Merged dataset containing:
            
        - Variables prefixed with `ref_mean_` : mean of reference
        - Variables prefixed with `ref_std_` : standard deviation of reference
        - Variables prefixed with `prod_mean_` : mean of product
        - Variables prefixed with `prod_std_` : standard deviation of product
        - Variables prefixed with `bias_` : mean difference (ref - prod)
        - Variables prefixed with `rms_` : root mean square difference
        - Variables prefixed with `crms_` : centered root mean square difference
    
    Notes
    -----
    The 'time_range' variable is dropped if present in the input datasets.
    """
    if "time_range" in dsref:
        dsref, dsprod = drop_time_range(dsref, dsprod)
    ds = xr.Dataset()
    for func in [mean, std]:
        fname = func.__name__
        for dsname, ds0 in zip(("ref", "prod"), (dsref, dsprod)):
            ds1 = func(ds0, dim)
            ds1 = rename_stat_var(ds1, f"{dsname}_{fname}")
            ds = xr.merge([ds, ds1])
    for func in [bias, rms, crms]:
        ds1 = func(dsref, dsprod, dim)
        ds1 = rename_stat_var(ds1, func.__name__)
        ds = xr.merge([ds, ds1])
    if "trange" in ds.sizes:
        ds = ds.swap_dims({"trange": "time"})
    if "time_range" in ds:
        ds = ds.rename_vars({"time_range": "time"})
    return ds

def get_parser_comp():
    """Create argument parser for comparison operations.
    
    Returns
    -------
    ArgumentParser
        Configured argument parser.
    """
    parser = ArgumentParser(
        description="Apply comparison over a list of input files.",
        formatter_class=ArmoorArgumentHelpFormatter,
        )
    add_logging_parser_arguments(parser)
    add_comp_io_parser_arguments(parser)
    add_dask_parser_arguments(parser)
    parser.add_argument(
        '--dim',
        nargs="*",
        type=str,
        default=[],
        help="Dimensions to compare."
        )
    return parser

def main_comp():
    """Apply comparison to input files via command line interface.
    
    This function serves as the main entry point for comparison operations.
    It parses command line arguments and processes input files 
    using Dask distributed computing for optimal performance.
    
    Positional Arguments
    --------------------
    dim : str
        Dimensions to compare.
        
    Examples
    --------
    Command line usage:
    
    .. code-block:: bash
    
        # Comparison over time
        armoor-comp ref_input.nc prod_input.nc output.nc --dim time
        
        # Comparison over time and z  
        armoor-comp ref_input.nc prod_input.nc output.nc --dim time z
    
    Notes
    -----
    - Leverages Dask for memory-efficient processing of large datasets
    - Supports all input/output formats available in the ARMOOR ecosystem
    """
    # Get parser
    parser = get_parser_comp()

    # Parse
    args = parser.parse_args()
    
    # Setup logging
    main_setup_logging(args)
    
    with LocalCluster(**setup_dask_client(args.dask_nworkers, args.dask_processes, args.dask_memorylimit)) as cluster:
        with Client(cluster):
            dsref = open_decode(args.ref_fins, args.ref_ifmt)
            dsprod = open_decode(args.fins, args.ifmt)
            dsref = dsref.persist()
            dsprod = dsprod.persist()
            if dsref.sizes != dsprod.sizes:
                logger.error(f"Reference dims: {dsref.sizes}")
                logger.error(f"Product dims: {dsprod.sizes}")
                raise CompError(
                    "Reference and product don't have the same dimensions."
                    "Comparison cannot be performed."
                    )
            stat_dim = args.dim
            time_range = False
            if ("time" in stat_dim) and ("time_range" in dsref):
                time_range = True
            vertical_range = False
            if ("z" in stat_dim) and ("vertical_range" in dsref):
                vertical_range = True
            
            if (time_range == False) and ("time" in stat_dim):
                raise CompError(
                    "Statistics over time cannot be performed."
                    "No time range found."
                    )
            if (vertical_range == False) and ("z" in stat_dim):
                raise CompError(
                    "Statistics over z cannot be performed."
                    "No vertical range found."
                    )
            
            if (time_range == False) and (vertical_range == False):
                ds = process_diff(dsref, dsprod)
            else:
                ds = process_stat(dsref, dsprod, stat_dim)
                
            save_output(ds, args.fout, args.ofmt)
            