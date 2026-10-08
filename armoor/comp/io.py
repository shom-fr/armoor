import gc
import logging
from pathlib import Path


logger = logging.getLogger(__name__)

def to_netcdf_ref_prods(dss, parent_dir, ncpat):
    """Save in netcdf files reference and products from data.

    This function separates datasets into references and products based on the
    'ref' attribute in each dataset.

    Parameters
    ----------
    dss : Dict[str, List[xr.Dataset]]
        Dictionary where keys are measurement zone names and values are lists of datasets.
        Each dataset must have 'data_name' and 'data_ref' attributes.
    parent_dir : str or Path
        Parent directory where NetCDF files will be saved.
    ncpat : str
        Filename pattern with format placeholders. Should include variables like:
        {mz_name}, {data_name}, {refprod} for proper file organization.
        Example: "{refprod}/{mz_name}/{data_name}.nc"

    Returns
    -------
    tuple: Two list, one for reference and one for products.
    """
    ncs_prod = []
    for mz_name, datasets in dss.items():
        for ds in datasets:
            data_name = ds.attrs["data_name"]
            refprod = "ref" if ds.attrs["data_ref"] == "True" else "prod"
            nc = Path(parent_dir) / ncpat.format(**locals())
            ncs_prod.append(nc)
            nc.parent.mkdir(parents=True, exist_ok=True)
            ds.to_netcdf(nc, compute=True)
            ds.close()
            gc.collect()
    return ncs_prod
