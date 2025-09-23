import logging

from armoor.base.io import get_zarr_encoding

logger = logging.getLogger(__name__)

def add_input_parser_arguments(parser):
    parser.add_argument(
        "fins",
        type=str,
        help="Pattern of input file. Ex: croco_*.zarr",
    )
    
def add_output_parser_arguments(parser):
    parser.add_argument(
        "fout",
        type=str,
        help="Name of the output file",
    )
    
def add_input_fmt_parser_arguments(parser):
    parser.add_argument(
        "--ifmt",
        type=str,
        choices=("hycom", "cmems_model", "croco", "armoor"),
        help="Format of the input files",
    )
    
def add_output_fmt_parser_arguments(parser):
    parser.add_argument(
        "--ofmt",
        type=str,
        default="zarr",
        choices=("netcdf", "zarr"),
        help="Format of the output files",
    )
    
def add_io_parser_arguments(parser):
    add_input_parser_arguments(parser)
    add_input_fmt_parser_arguments(parser)
    add_output_parser_arguments(parser)
    add_output_fmt_parser_arguments(parser)


def save_output(ds, fout, ofmt="zarr"):
    if ofmt == "zarr":
        to_zarr(ds, fout)
    elif ofmt == "netcdf":
        ds.to_netcdf(fout)
        

def to_zarr(ds, fout):
    encoding = get_zarr_encoding(ds)
    for ivar, var_name in enumerate(ds.data_vars):
        logger.info(f"put {var_name} in {fout}")
        var_ds = ds[[var_name]]  # Select single variable
        var_ds = var_ds.chunk("auto")
        
        if ivar == 0:
            mode = "w"
        else:
            mode = "a"
        
        var_ds.to_zarr(
            store=fout,
            mode=mode,
        )
        
        del var_ds
