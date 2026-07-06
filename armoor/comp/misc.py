import logging
from pathlib import Path

from armoor.base.misc import validate_metazone_params

logger = logging.getLogger(__name__)


def validate_colocation(metazones, params):
    """Validate that only one of the two parameters is defined for each metazone.

    This function checks if either param1 or param2 is defined, but not both,
    for each metazone in the metazones dictionary.

    Parameters
    ----------
    metazones : dict
        A dictionary of metazones with their parameters.
    params : dict
        A dictionary where keys are colocation types and values are lists
        of parameter pairs to validate.

    Raises
    ------
    ArmoorError
        If both parameters are defined or neither is defined.
    """
    return validate_metazone_params(metazones, params)

def get_colocation_params(metazones, params_user, params_default=None):
    """
    Retrieve colocation parameters for each metazone based on given parameters.

    This function takes two dictionaries as input: `metazones` and `params`. It
    returns a dictionary where each key is a metazone and each value is a
    dictionary containing the colocation parameters ("time", "horizontal",
    "vertical") that were found in `metazones` using the parameter candidates
    specified in `params`.

    Parameters
    ----------
    metazones: dict
        A dictionary where each key is the name of a metazone
        and each value is a dictionary containing the
        parameters of that metazone.
    params_user: dict
        A dictionary defined by users where each key is a type of colocation
        ("time", "horizontal", "vertical") and each value is a
        list of parameter candidates to search for in `metazones`.
    params_default: dict
        A dictionary where each key is a type of colocation
        ("time", "horizontal", "vertical") and each value is a
        list of default parameters.

    Returns
    -------
    dict 
        A dictionary where each key is a metazone and each value is a
        dictionary containing the colocation parameters found for that
        metazone.
    """
    coloc_params = {}
    for mz_name, mz_params in metazones.items():
        if mz_params:
            if params_default:
                coloc_params[mz_name] = {}
                for coloc, param in params_default.items():
                    coloc_params[mz_name][coloc] = param
            coloc_params[mz_name] = {
                coloc: (param_candidate, mz_params.get(param_candidate))
                for coloc in ("time", "horizontal", "vertical") 
                for param_candidate in params_user.get(coloc, [])
                if (mz_params.get(param_candidate) is not None)
                }
            if params_default:
                for coloc, param in params_default.items():
                    if coloc_params[mz_name].get(coloc) is None:
                        coloc_params[mz_name][coloc] = param
        else:
            coloc_params[mz_name] = None
    return coloc_params
    
def get_tbound(metazones):
    """Get tbound for each metazone.
    
    Parameters
    ----------
    metazones: dict
        Dictionnary containing metazone parameters
    
    Returns
    -------
    dict
        tbound for each metazones.
    """
    return {
        metazone: v for metazone, params in metazones.items()
        for k, v in params.items() if k == "tbound"
        }

    