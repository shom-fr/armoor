from pathlib import Path

def to_netcdf_ref_prods(dss, parent_dir, ncpat):
    """Save in netcdf files reference and products from data.

    This function separates datasets into references and products based on the
    'ref' attribute in each dataset.

    Parameters
    ----------
    dss: dict 
        A dictionary where keys are names and values are lists of datasets.

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
            ds.to_netcdf(nc)
            ds.close()
    return ncs_prod
