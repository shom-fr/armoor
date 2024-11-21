import numpy as np
import xarray as xr
import xoa

import logging
logger = logging.getLogger(__name__)


def ensemble_mean(ds):
    coords = []
    for coord in ds.coords:
        if ("member" in ds[coord].dims) and (coord != "member"):
            ds = ds.reset_coords(coord)
            coords.append(coord)
    ds = ds.mean("member")
    ds = ds.set_coords(coords)
    return ds

def rmse_generic(observation, model, dims):
    """
    Calculate the RMSE between model and observation.
    Parameters
    ----------
    observation : xr.Dataset
        Observation dataset.
    model : xr.Dataset
        Model dataset.
    dims : list of str
        List of dimensions on which to calculate the RMSE.

    Returns
    -------
    RMSE : xr.xarray
        RMSE of the model and observation

    """
    logger.info('Computing RMSE between model and observation')

    return np.sqrt(
        ((model - observation) ** 2).mean(dim=dims, skipna=True)
    )


def rmse_center_generic(observation, model, dims):
    """
    Calculate the centered RMSE between model and observation.
    Parameters
    ----------
    observation : xr.Dataset
        Observation dataset.
    model : xr.Dataset
        Model dataset.
    dims : list of str
        List of dimensions on which to calculate the centered RMSE.

    Returns
    -------
    RMSE : xr.xarray
        Centered RMSE of the model and observation

    """
    logger.info('Computing centered RMSE between model and observation')
    meanmod = model.mean(dims)
    meanobs = observation.mean(dims)

    return np.sqrt(
       (((model - meanmod) - (observation - meanobs)) ** 2).mean(dim=dims, skipna=True)
    )


def rmsec_diag_disp(observation, model):
    logger.info('Computing centered RMSE for dispersion diagram')
    rmsec = 0
    for i, obs in enumerate(observation):
        rmsec += (model[i] - observation[i]) ** 2
    rmsec /= len(observation)
    return np.sqrt(rmsec)


def mld_dsigma(dataset):
    """
    https://xoa.readthedocs.io/en/develop/api/xoa.thermdyn.mixed_layer_depth.html#xoa.thermdyn.mixed_layer_depth
    Parameters
    ----------
    dataset
    dsigma
    slice

    Returns
    -------

    """

    return xoa.thermdyn.mixed_layer_depth(dataset)
