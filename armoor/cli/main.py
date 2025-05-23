"""Command-line interface for armoor."""
from argparse import ArgumentParser
from configobj import ConfigObj
from dask.distributed import Client
import logging
from pathlib import Path
from xoa.cfgm import ConfigManager, register_validation_functions

from armoor import ArmoorError
from armoor.cli import VALIDATION_INI
from armoor.base import FILTERS
from armoor.base.io import ArmoorArgumentHelpFormatter
from armoor.base.log import add_logging_parser_arguments, main_setup_logging
from armoor.base.misc import string_to_tuples_float
from armoor.comp import METAZONE_PARAMS
from armoor.comp.io import to_netcdf_ref_prods
from armoor.comp.coloc import main_coloc
from armoor.comp.comp import main_comp
from armoor.data.open_decode import register_cf, open_decode

logger = logging.getLogger(__name__)

def coords(s):
    """
    Parse a string into latitude and longitude coordinates.
    
    Parameters
    ----------
    s: str
        A string representing the coordinates in the format "lat,lon".
    
    Returns
    -------
    tuple: A tuple containing the latitude and longitude as floats.
    
    Raises
    ------
        ArmoorError: If the string is not in the correct format.
    """
    try:
        return string_to_tuples_float(",".join(s))
    except:
        raise ArmoorError("Coordinates must be a list of tuples (lat,lon)")

register_validation_functions(coordinates=coords)

def comma_separated(sarg):
    """Parse a string of comma-separated list."""
    return [a.strip() for a in sarg.split(",")]

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
            metazones_cfg[metazone].update(kwargs)
    metazones = {}
    for metazone in metazones_arg:
        for k, v in metazones_cfg[metazone].items():
            if v == None:
                del metazones_cfg[metazone][k]
        metazones[metazone] = metazones_cfg[metazone]
    for metazone_name, metazone_param in metazones.items():
        for k, v in metazone_param.items():
            if (k != "name") and (k not in func_param):
                raise ArmoorError(
                    f"{k} cannot be defined to use this functionnality.\n"
                    f"See the parameters available for this functionnalité {func_param}"
                )
    return metazones

def main_open_datasets(cfg: ConfigObj):
    """Open and decode list of data.
    
    Parameters
    ----------
    cfg: ConfigObj
        List of data to be opened and decoded.
    
    Return
    ------
    dss: list
        List of datasets.
    """
    if not cfg:
        raise ArmoorError(
            "Data section empty: Check [data] in your cfgfile."
            )
    register_cf()
    dss = []
    data_ref = {}
    for _, cfg_data in cfg.items():
        ds = open_decode(
            cfg_data["path"],
            fmt=cfg_data["fmt"],
            platform=cfg_data["platform"]
            )
        ds.attrs["data_name"] = cfg_data["name"]
        ds.attrs["data_ref"] = str(cfg_data["ref"])
        data_ref.update({
            cfg_data["name"]: str(cfg_data["ref"])
            })
        dss.append(ds)
    return dss, data_ref

def main_metazones(dsins, metazones):
    """Apply metazones to a list of xarray.Dataset.
    
    Parameters
    ----------
    dsins: list
        List of xarray.Dataset
    metazones: dict
        Dictionary of metazones
        
    Return
    ------
    dsouts: dict
        Dictionnary of type {mz1_name: xr.Dataset, mz2_name: xr.Dataset}
    """
    dsouts = {}
    for mz_name, mz_param in metazones.items():
        logger.info(f"apply metazone: {mz_name}")
        dsouts[mz_name] = []
        for ds in dsins:
            data_name = ds.attrs["data_name"]
            data_ref = ds.attrs["data_ref"]
            logger.info(f"{data_name}")
            # time
            time_meta = ["tbound", "terms", "trange_cut"]
            for k in time_meta:
                if k in mz_param:
                    if "climatology" not in ds.time.attrs:
                        dsout = FILTERS[k](ds)(*mz_param[k])
                    if dsout is None:
                        raise ArmoorError(
                            f"{k} filter returns None for {ds.attrs['name']} dataset."
                        )
            # horizontal
            horizontal_meta = [
                "polygon",
                "bathy",
            ]
            for k in horizontal_meta:
                if k in mz_param:
                    if k == "polygon":
                        args = mz_param[k]
                    else:
                        args = (*mz_param[k],)
                    ds = FILTERS[k](ds)(args)
                    if ds is None:
                        raise ArmoorError(
                            f"{k} filter return None for {ds.attrs['name']} dataset."
                        )
            # vertical
            vertical_meta = [
                "vlevel",
            ]
            for k in vertical_meta:
                if k in mz_param:
                    ds = FILTERS[k](ds)(*mz_param[k].items()[0])
                    if ds is None:
                        raise ArmoorError(
                            f"{k} filter return None for {ds.attrs['name']} dataset."
                        )
            ds.attrs = {
                "data_name": data_name,
                "data_ref": data_ref,
                #**mz_param
            }
            dsouts[mz_name].append(ds)
    return dsouts

def get_parser_comp_sst():
    """Get parser for sst comparison."""
    # Setup argument parser
    parser = ArgumentParser(
        description="Compare sst satellite with model ouputs.",
        formatter_class=ArmoorArgumentHelpFormatter,
        )
    add_logging_parser_arguments(parser)
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
        '--qc',
        type=dict,
        default=None,
        help="Dictionnary specifying quality tresholds, ex: ptemp:1,7"
        )
    
    return parser

def main_comp_sst():
    """Compare sst reference with other products."""
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
    cfg = ConfigManager(VALIDATION_INI).load(str(args.cfgfile))
    
    with Client():
        # Open-decode data
        dss, data_ref = main_open_datasets(cfg["data"])
    
        # Metazones
        kw_comp_sst = {"qc": args.qc}
        metazones = check_metazones_in(
            args.metazones,
            cfg["metazones"],
            func_param=METAZONE_PARAMS[func_comp],
            **kw_comp_sst
            )
        dss = main_metazones(dss, metazones)
        ncs_metazone = to_netcdf_ref_prods(
            dss,
            f"{func_comp}/metazones",
            "{mz_name}/{data_name}/{refprod}.nc"
            )

        # Colocation
        ncs_coloc = main_coloc(ncs_metazone, metazones, func_comp)

    # Comp
    main_comp(ncs_coloc, metazones)

        
        

    
    