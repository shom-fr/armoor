"""Command-line interface for armoor.

Heavy imports (dask.distributed, cartopy, scipy, xoa, …) are deferred to
the functions that actually need them so that CLI startup is fast even on
slow HPC parallel file-systems.
"""
import os
# Limit OpenMP/BLAS to 1 thread per process. Must happen before numpy is
# imported anywhere so that libgomp picks it up during initialisation.
# Parallelism is achieved via multiple processes (dask workers), not threads.
os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("MKL_NUM_THREADS", "1")
os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")

import json
import logging
import time
from argparse import ArgumentParser
from pathlib import Path

from argparse import ArgumentDefaultsHelpFormatter, RawDescriptionHelpFormatter

from armoor import ArmoorError
from armoor.base.misc import (comma_separated, parse_coords,
                              parse_mixed_param, parse_qc_tuple)


class ArmoorArgumentHelpFormatter(RawDescriptionHelpFormatter,
                                 ArgumentDefaultsHelpFormatter):
    pass
from armoor.cli import FILTERS_INI, COMP_INI, DATA_INI, METAZONES_INI, BULL_INI
from armoor.cli.io import add_dask_parser_arguments, get_dask_args, add_comp_parser_arguments
from armoor.cli.log import add_logging_parser_arguments, main_setup_logging

logger = logging.getLogger(__name__)


_heavy_done = False

def _init_heavy():
    """One-time lazy initialisation of heavy dependencies."""
    global _heavy_done
    if _heavy_done:
        return
    _heavy_done = True
    import os
    for var in ('OMP_NUM_THREADS', 'MKL_NUM_THREADS', 'OPENBLAS_NUM_THREADS'):
         os.environ.setdefault(var, '1')

    logging.getLogger('distributed').setLevel(logging.ERROR)
    import armoor.base.filters  # noqa: F401 — registers xarray accessor
    import armoor.base.oceanvars  # noqa: F401 — registers xarray accessor
    from xoa.cfgm import register_validation_functions
    register_validation_functions(coordinates=parse_coords)
    register_validation_functions(mlist=parse_mixed_param)


def check_metazones_in(metazones_arg, metazones_cfg, func_param=None, **kwargs):
    """Check if all metazone-names given in command-line are present in cfgfile.

    This function checks if all elements of the first list are present in the
    second list. If any element from the first list is not found in the second
    list, it raises a ValueError.

    Parameters
    ----------
    metazones_arg : list
        List of metazones given in the command-line.
    metazones_cfg:
        List of metazones given in the cfgfile.
    func_param: list
        List of parameters available regarding the current functionnality.

    Raises
    ------
    ValueError: If any element of list1 is not found in list2.
    """
    metazones_bad = []
    for metazone in metazones_arg:
        if metazone not in metazones_cfg:
            metazones_bad.append(metazone)           
    if len(metazones_bad) > 0:
        raise ArmoorError(
            f"Missing metazones in cfgfile: {metazones_bad}."
            )
    if kwargs:
        for metazone in metazones_arg:
            for k, v in kwargs.items():
                if v != None:
                    metazones_cfg[metazone].update({k: v})
    metazones = {}
    for metazone in metazones_arg:
        if (metazones_cfg[metazone].get("tfreq") != None) & (metazones_cfg[metazone].get("thours") != None):
            raise ArmoorError(f"`tfreq` and `thours` cannot be configured together in {metazone}")
        for k, v in metazones_cfg[metazone].items():
            if v == None:
                del metazones_cfg[metazone][k]
        metazones[metazone] = metazones_cfg[metazone]
    if func_param:
        for metazone_name, metazone_param in metazones.items():
            for k, v in metazone_param.items():
                if (k != "name") and (k not in func_param):
                    logger.warning(
                        f"{k} cannot be defined to use this functionnality.\n"
                        f"{k} is removed to run this functionnality."
                    )
                    del metazones[metazone_name][k]
                # if (k == "polygon") and ("href" in metazone_param.keys()):
                #     metazones[metazone_name].update({
                #         "polygon_dilat": metazones[metazone_name].get("polygon")
                #         })
                #     del metazones[metazone_name]["polygon"]
    return metazones

def get_parser_filters():
    """Get parser for filtering."""
    # Setup argument parser
    parser = ArgumentParser(
        description="Apply filters over metazones.",
        formatter_class=ArmoorArgumentHelpFormatter,
        )
    add_logging_parser_arguments(parser)
    add_dask_parser_arguments(parser)
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
    parser.add_argument(
        '--jsonfile',
        type=Path,
        help="Path of the output json file.",
        default='ncs_filter.json'
        )
    
    return parser

def main_filters():
    """Apply filters over metazones."""
    import dask
    from xoa.cfgm import ConfigManager
    from armoor.base.io import zarrs2netcdfs
    from armoor.data.load import load_datasets
    _init_heavy()

    dask.config.set({
        'scheduler': 'threads',
        'array.slicing.split_large_chunks': True,
        'optimization.fuse.active': True,
    })

    # Get parser
    parser = get_parser_filters()

    # Parse
    args = parser.parse_args()

    # Setup logging
    main_setup_logging(args)

    # Load configuration
    if not args.cfgfile.exists():
        raise ArmoorError(
            f"File not found: {args.cfgfile}."
            )

    cfg = ConfigManager(FILTERS_INI).load(str(args.cfgfile))
    metazones = ConfigManager(METAZONES_INI).load(str(args.metazonesfile))

    metazones = check_metazones_in(
       args.metazones,
       metazones
       )

    logger.info(f"Processing {len(cfg['data'])} datasets × {len(metazones)} metazones")

    zarrs = load_datasets(cfg["data"], metazones, None)
    ncs = zarrs2netcdfs(zarrs)

    with open(args.jsonfile, 'w') as f:
        json.dump(ncs, f, indent=4)

    logger.info(f"Find the list of NetCDF files in: {args.jsonfile}")

def get_parser_data():
    """Get parser for data."""
    # Setup argument parser
    parser = ArgumentParser(
        description="Plot and compute on data.",
        formatter_class=ArmoorArgumentHelpFormatter,
        )
    add_logging_parser_arguments(parser)
    add_dask_parser_arguments(parser)
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
    parser.add_argument(
        '--jsonfile',
        type=Path,
        help="Path of the output json file.",
        default='ncs_filter.json'
        )
    parser.add_argument(
        '--filters-only',
        action='store_true',
        help="Use for exiting after filters processes.",
        )
    
    return parser

def main_data():
    """Process data over metazones."""
    import dask
    from xoa.cfgm import ConfigManager
    from armoor.base.io import zarrs2netcdfs
    from armoor.base.misc import dict_to_list
    from armoor.data.load import load_datasets
    from armoor.data.output import main_output as output_data
    _init_heavy()

    dask.config.set({
        'scheduler': 'threads',
        'array.slicing.split_large_chunks': True,
        'optimization.fuse.active': True,
    })

    # Get parser
    parser = get_parser_data()

    # Parse
    args = parser.parse_args()

    # Setup logging
    main_setup_logging(args)

    # Load configuration
    if not args.cfgfile.exists():
        raise ArmoorError(
            f"File not found: {args.cfgfile}."
            )

    cfg = ConfigManager(DATA_INI).load(str(args.cfgfile))
    metazones = ConfigManager(METAZONES_INI).load(str(args.metazonesfile))

    metazones = check_metazones_in(
       args.metazones,
       metazones
       )

    logger.info(f"Processing {len(cfg['data'])} datasets × {len(metazones)} metazones")

    zarrs = load_datasets(cfg["data"], metazones, "data")

    if args.filters_only:

        ncs = zarrs2netcdfs(zarrs)

        with open(args.jsonfile, 'w') as f:
            json.dump(ncs, f, indent=4)

        logger.info(f"Find the list of NetCDF files in: {args.jsonfile}")

    else:

        zarr_outputs = output_data(zarrs, metazones, cfg.get("outputs").copy())

        ofmt = cfg["outputs"].get("fmt")

        if "png" in ofmt:
            from armoor.data.plot import main_plot as plot_data
            plot_data(zarr_outputs, metazones)

        zarr_outputs = dict_to_list(zarr_outputs)

        if "zarr" in ofmt:
            with open(args.jsonfile, 'w') as f:
                json.dump(zarr_outputs, f, indent=4)

        if "netcdf" in ofmt:
            ncs_outputs = zarrs2netcdfs(zarr_outputs)
            with open(args.jsonfile, 'w') as f:
                json.dump(ncs_outputs, f, indent=4)

def main_comp(cfgfile, metafile, metazones, func_comp, jsonfile, ofilter, ocoloc, kw_dask, comp_args={}):
    import dask
    from xoa.cfgm import ConfigManager
    from armoor.base.io import zarrs2netcdfs
    from armoor.base.misc import dict_to_list
    from armoor.comp import METAZONE_PARAMS
    from armoor.comp.coloc import main_coloc
    from armoor.data.load import load_datasets

    # No distributed cluster — use local threaded scheduler for I/O,
    # synchronous where already set in colocation code.
    # This avoids worker memory interference and GIL contention.
    dask.config.set({
        'scheduler': 'threads',
        'array.slicing.split_large_chunks': True,
        'optimization.fuse.active': True,
    })

    logger.info("Initial diagnostic:")
    monitor_performance()

    start_time = time.time()

    cfg = ConfigManager(COMP_INI).load(str(cfgfile))
    metas = ConfigManager(METAZONES_INI).load(str(metafile))

    if not cfg:
        raise ArmoorError("Data section empty: Check [data] in your cfgfile.")

    # Metazones
    metazones = check_metazones_in(
        metazones,
        metas,
        func_param=METAZONE_PARAMS[func_comp],
        **comp_args
        )

    jsonfile = str(jsonfile).format(**locals())

    logger.info(f"Processing {len(cfg['data'])} datasets × {len(metazones)} metazones")

    zarr = load_datasets(cfg["data"], metazones, func_comp)

    if ofilter:
        zarr = [str(z) for z in zarr]
        ncs_outputs = zarrs2netcdfs(zarr)
        with open(jsonfile, 'w') as f:
            json.dump(ncs_outputs, f, indent=4)

    else:
        zarr_coloc = main_coloc(zarr, metazones, func_comp)

        if ocoloc:
            zarr_coloc = dict_to_list(zarr_coloc)
            zarr_coloc = [str(z) for z in zarr_coloc]
            ncs_outputs = zarrs2netcdfs(zarr_coloc)
            with open(jsonfile, 'w') as f:
                json.dump(ncs_outputs, f, indent=4)

        else:
            from armoor.comp.output import main_output as output_comp
            zarr_outputs = output_comp(zarr_coloc, metazones, cfg.get("outputs"), func_comp, **comp_args)
            ofmt = cfg["outputs"].get("fmt")

            if "png" in ofmt:
                from armoor.comp.plot import main_plot as plot_comp
                plot_comp(zarr_outputs, metazones, func_comp, kw_dask=kw_dask)

            zarr_outputs = dict_to_list(zarr_outputs)

            if "zarr" in ofmt:
                with open(jsonfile, 'w') as f:
                    json.dump(zarr_outputs, f, indent=4)

            if "netcdf" in ofmt:
                ncs_outputs = zarrs2netcdfs(zarr_outputs)
                with open(jsonfile, 'w') as f:
                    json.dump(ncs_outputs, f, indent=4)

    logger.info(f"Find the list of generated files in: {jsonfile}")

    elapsed = time.time() - start_time
    logger.info(f"Execution time: {elapsed:.1f} seconds")

    logger.info("Final diagnostic:")
    monitor_performance()


def get_parser_comp_models():
    """Get parser for models comparison."""
    # Setup argument parser
    parser = ArgumentParser(
        description="Compare models ouputs.",
        formatter_class=ArmoorArgumentHelpFormatter,
        )
    add_logging_parser_arguments(parser)
    add_dask_parser_arguments(parser)
    add_comp_parser_arguments(parser)
    
    return parser

def main_comp_models():
    """Compare a model reference with other products."""
    _init_heavy()
    # Get parser
    parser = get_parser_comp_sst()
    func_comp = "comp_models"

    # Parse
    args = parser.parse_args()
    
    # Setup logging
    main_setup_logging(args)

    # Load configuration
    if not args.cfgfile.exists():
        raise ArmoorError(
            f"File not found: {args.cfgfile}."
            )
    kw_dask = get_dask_args(args)
    kw_comp = {"tbound": args.tbound}
    main_comp(
        args.cfgfile,
        args.metazonesfile,
        args.metazones,
        func_comp,
        args.jsonfile,
        args.filters_only,
        args.coloc_only,
        kw_dask,
        comp_args=kw_comp
        )

def get_parser_comp_sst():
    """Get parser for sst comparison."""
    # Setup argument parser
    parser = ArgumentParser(
        description="Compare sst satellite with model ouputs.",
        formatter_class=ArmoorArgumentHelpFormatter,
        )
    add_logging_parser_arguments(parser)
    add_dask_parser_arguments(parser)
    add_comp_parser_arguments(parser)
    parser.add_argument(
        '--qc',
        type=parse_qc_tuple,
        default=None,
        help="Tuple specifying quality tresholds, ex: ptemp,1,7"
        )
    return parser

def main_comp_sst():
    """Compare sst reference with other products."""
    _init_heavy()
    # Get parser
    parser = get_parser_comp_sst()
    func_comp = "comp_sst"

    # Parse
    args = parser.parse_args()
    
    # Setup logging
    main_setup_logging(args)

    # Load configuration
    if not args.cfgfile.exists():
        raise ArmoorError(
            f"File not found: {args.cfgfile}."
            )
    kw_comp = {
        "qc": args.qc,
        "tbound": args.tbound
        }
    
    kw_dask = get_dask_args(args)

    main_comp(
        args.cfgfile,
        args.metazonesfile,
        args.metazones,
        func_comp,
        args.jsonfile,
        args.filters_only,
        args.coloc_only,
        kw_dask,
        comp_args=kw_comp
        )
    
def get_parser_comp_argo():
    """Get parser for argo comparison."""
    # Setup argument parser
    parser = ArgumentParser(
        description="Compare argo data with model ouputs.",
        formatter_class=ArmoorArgumentHelpFormatter,
        )
    add_logging_parser_arguments(parser)
    add_dask_parser_arguments(parser)
    add_comp_parser_arguments(parser)
    parser.add_argument(
        'radius',
        type=float,
        help="Radius (in km) of disk to filter model point around observation."
        )
    parser.add_argument(
        '--qc',
        type=parse_qc_tuple,
        default=None,
        help="Tuple specifying quality tresholds, ex: ptemp,1,7"
        )
    
    return parser

def main_comp_argo():
    """Compare argo with other products."""
    _init_heavy()
    # Get parser
    parser = get_parser_comp_argo()
    func_comp = "comp_argo"

    # Parse
    args = parser.parse_args()
    
    # Setup logging
    main_setup_logging(args)
    
    # Load configuration
    if not args.cfgfile.exists():
        raise ArmoorError(f"File not found: {args.cfgfile}.")
    
    kw_comp = {"radius": args.radius, "qc": args.qc, "tbound": args.tbound}
    
    kw_dask = get_dask_args(args)
    
    main_comp(
        args.cfgfile,
        args.metazonesfile,
        args.metazones,
        func_comp,
        args.jsonfile,
        args.filters_only,
        args.coloc_only,
        kw_dask,
        comp_args=kw_comp
        )

def get_parser_comp_mooring():
    """Get parser for mooring comparison."""
    # Setup argument parser
    parser = ArgumentParser(
        description="Compare mooring data with model ouputs.",
        formatter_class=ArmoorArgumentHelpFormatter,
        )
    add_logging_parser_arguments(parser)
    add_dask_parser_arguments(parser)
    add_comp_parser_arguments(parser)
    parser.add_argument(
        'radius',
        type=float,
        help="Radius (in km) of disk to filter model point around observation."
        )
    parser.add_argument(
        '--qc',
        type=dict,
        default=None,
        help="Dictionnary specifying quality tresholds, ex: ptemp:1,7"
        )
    
    return parser

def main_comp_mooring():
    """Compare argo with other products."""
    _init_heavy()
    # Get parser
    parser = get_parser_comp_mooring()
    func_comp = "comp_mooring"

    # Parse
    args = parser.parse_args()
    
    # Setup logging
    main_setup_logging(args)
    
    # Load configuration
    if not args.cfgfile.exists():
        raise ArmoorError(f"File not found: {args.cfgfile}.")
    
    kw_comp = {"radius": args.radius, "qc": args.qc, "tbound": args.tbound}

    kw_dask = get_dask_args(args)

    main_comp(
        args.cfgfile,
        args.metazonesfile,
        args.metazones,
        func_comp,
        args.jsonfile,
        args.filters_only,
        args.coloc_only,
        kw_dask,
        comp_args=kw_comp
        )

def get_parser_comp_drifter():
    """Get parser for drifter comparison."""
    # Setup argument parser
    parser = ArgumentParser(
        description="Compare drifter data with model ouputs.",
        formatter_class=ArmoorArgumentHelpFormatter,
        )
    add_logging_parser_arguments(parser)
    add_dask_parser_arguments(parser)
    add_comp_parser_arguments(parser)
    parser.add_argument(
        'period',
        type=str,
        help="Time period of the particle integration (pandas period string). Ex: 1h, 6h, 1d"
        )
    parser.add_argument(
        'freq',
        type=str,
        help="Time frequency of trajectory comparison (pandas frequency string). Ex: 1h, 6h, 1d"
        )
    return parser

def main_comp_drifter():
    """Compare drifter trajectory with other products."""
    _init_heavy()
    # Get parser
    parser = get_parser_comp_drifter()
    func_comp = "comp_drifter"

    # Parse
    args = parser.parse_args()
    
    # Setup logging
    main_setup_logging(args)
    
    # Load configuration
    if not args.cfgfile.exists():
        raise ArmoorError(f"File not found: {args.cfgfile}.")
    
    kw_comp = {
        "period_drift": args.period,
        "freq_drift": args.freq,
        "tbound": args.tbound
        }
    
    kw_dask = get_dask_args(args)
    
    main_comp(
        args.cfgfile,
        args.metazonesfile,
        args.metazones,
        func_comp,
        args.jsonfile,
        args.filters_only,
        args.coloc_only,
        kw_dask,
        comp_args=kw_comp
        )

def get_parser_bull():
    """Get parser for building bull."""
    # Setup argument parser
    parser = ArgumentParser(
        description="Build bull",
        formatter_class=ArmoorArgumentHelpFormatter,
        )
    add_logging_parser_arguments(parser)
    parser.add_argument(
        'bullname',
        type=str,
        help="Name of html file generated."
        )
    parser.add_argument(
        'cfgfile',
        type=Path,
        help="Path of the configuration file."
        )
    parser.add_argument(
        '--period',
        type=str,
        help="Period covering bull."
        )
    parser.add_argument(
        '--fmt',
        type=str,
        default="html",
        choices=("html", "pdf"),
        nargs="*",
        help="Format of file generated."
        )
    
    return parser

def main_bull():
    """Build bull."""
    from xoa.cfgm import ConfigManager
    from armoor.bull.build import Bull

    # Get parser
    parser = get_parser_bull()

    # Parse
    args = parser.parse_args()

    # Setup logging
    main_setup_logging(args)

    # Load configuration
    if not args.cfgfile.exists():
        raise ArmoorError(f"File not found: {args.cfgfile}.")

    cfg = ConfigManager(BULL_INI).load(str(args.cfgfile))

    if args.period:
        cfg["header"]["period"] = args.period
        if "summary" in cfg.keys():
            cfg["summary"]["period"] = args.period
    bull = Bull(cfg)
    bull_fmt = args.fmt
    bull_name = args.bullname
    for fmt in ("html", "pdf"):
        if fmt in bull_fmt:
            file = f"{bull_name}.{fmt}"
            if fmt == "html":
                bull.generate_html(file)
            else:
                bull.generate_pdf(file)
    

# Fonction de diagnostic pour surveiller les performances
def monitor_performance():
    """Surveille les performances du système."""
    try:
        import psutil

        # Mémoire
        memory = psutil.virtual_memory()
        swap = psutil.swap_memory()
        
        logger.info(f"Mémoire: {memory.percent:.1f}% utilisée ({memory.available/1e9:.1f}GB libre)")
        logger.info(f"Swap: {swap.percent:.1f}% utilisé ({swap.free/1e9:.1f}GB libre)")
        
        # CPU
        cpu_percent = psutil.cpu_percent(interval=1)
        logger.info(f"CPU: {cpu_percent:.1f}% utilisé")
        
        # Alertes
        if memory.percent > 90:
            logger.warning("Mémoire critique (>90%)")
        if swap.percent > 50:
            logger.warning("Swap élevé (>50%)")
            
    except ImportError:
        logger.debug("psutil non disponible")
    except Exception as e:
        logger.debug(f"Erreur monitoring: {e}")
