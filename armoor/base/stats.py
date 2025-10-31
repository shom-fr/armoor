import numpy as np

def diff(dsprod, dsref):
    """
    Calculate the difference between reference and product datasets.
    
    Parameters
    ----------
    dsprod : xarray.Dataset
        Product dataset.
    dsref : xarray.Dataset
        Reference dataset.
    
    Returns
    -------
    xarray.Dataset
        Element-wise difference (dsref - dsprod).
    """
    return dsprod - dsref


def cdiff(dsprod, dsref, dim):
    """
    Calculate the centered difference between reference and product datasets.
    
    The centered difference removes the mean along the specified dimension
    from both datasets before computing the difference.
    
    Parameters
    ----------
    dsprod : xarray.Dataset
        Product dataset.
    dsref : xarray.Dataset
        Reference dataset.
    dim : str or list of str
        Dimension(s) along which to compute the mean.
    
    Returns
    -------
    xarray.Dataset
        Centered difference: (dsref - mean(dsref)) - (dsprod - mean(dsprod)).
    """
    return ((
        dsprod - dsprod.mean(dim=dim)
    ) - (
        dsref - dsref.mean(dim=dim)
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


def bias(dsprod, dsref, dim):
    """
    Calculate the bias between reference and product datasets.
    
    The bias is the mean difference between the reference and product datasets
    along the specified dimension(s).
    
    Parameters
    ----------
    dsprod : xarray.Dataset
        Product dataset.
    dsref : xarray.Dataset
        Reference dataset.
    dim : str or list of str
        Dimension(s) along which to compute the mean.
    
    Returns
    -------
    xarray.Dataset
        Mean bias (mean of dsref - dsprod along dim).
    """
    return (dsprod - dsref).mean(dim=dim)

    
def rms(dsprod, dsref, dim):
    """
    Calculate the root mean square difference between reference and product datasets.
    
    Parameters
    ----------
    dsprod : xarray.Dataset
        Product dataset.
    dsref : xarray.Dataset
        Reference dataset.
    dim : str or list of str
        Dimension(s) along which to compute the RMS.
    
    Returns
    -------
    xarray.Dataset
        Root mean square of the difference.
    """
    return np.sqrt((diff(dsprod, dsref) ** 2).mean(dim=dim))

    
def crms(dsprod, dsref, dim):
    """
    Calculate the centered root mean square difference between datasets.
    
    The centered RMS removes the mean bias before computing the RMS,
    measuring the variability difference independent of the mean bias.
    
    Parameters
    ----------
    dsprod : xarray.Dataset
        Product dataset.
    dsref : xarray.Dataset
        Reference dataset.
    dim : str or list of str
        Dimension(s) along which to compute the centered RMS.
    
    Returns
    -------
    xarray.Dataset
        Centered root mean square difference.
    """
    return np.sqrt((cdiff(dsprod, dsref, dim) ** 2).mean(dim=dim))