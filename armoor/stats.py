import numpy as np
import xarray as xr
from scipy.stats import gaussian_kde


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
    return (dsprod - dsprod.mean(dim=dim)) - (dsref - dsref.mean(dim=dim))


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


def corr(dsprod, dsref, dim):
    """
    Calculate the Pearson correlation between reference and product datasets.

    Only the samples that are valid in both datasets are used, and the
    correlation is missing where a dataset is constant.

    Parameters
    ----------
    dsprod : xarray.Dataset
        Product dataset.
    dsref : xarray.Dataset
        Reference dataset.
    dim : str or list of str
        Dimension(s) along which to compute the correlation.

    Returns
    -------
    xarray.Dataset
        Correlation of the variables that are in both datasets.
    """
    return xr.Dataset(
        {var: xr.corr(dsprod[var], dsref[var], dim=dim) for var in dsprod.data_vars if var in dsref}
    )


def pdf(ds, vars):
    """
    Calculate the probability density function of a variable.

    Parameters
    ----------
    ds : xarray.Dataset
        Product dataset.
    vars : str or list of str
        Variable(s) for which to compute the PDF.

    Returns
    -------
    xarray.Dataset
        Dataset with new probability density function variable(s) (format pdf_{var}).
    """
    if isinstance(vars, str):
        vars = [vars]
    for var in vars:
        kde = gaussian_kde(ds[var])
        bins = np.linspace(0, max(ds[var]).values, 100)
        pdf_values = kde.pdf(bins)
        ds[f'{var}_pdf'] = xr.DataArray(pdf_values, dims=['pdf_bins'], attrs=ds[var].attrs)
        ds[f'{var}_pdf_bins'] = xr.DataArray(
            bins, dims=['pdf_bins'], attrs={'info': f'bins used to calculate pdf for {var}'}
        )
    return ds
