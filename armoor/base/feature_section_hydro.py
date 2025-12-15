"""Create figures for section_hydro."""

import copy
import logging
import os

from armoor.base import plot_features
from armoor.base.tools_features import sel_default_vars
from armoor.hmi.script_tools import create_folder

logger = logging.getLogger(__name__)


def plot(config_obj):
    """
    Plot figures required in functionality section_hydro.

    Parameters
    ----------
    config_obj : dict
        Dictionary with observations and models names and DataSets.

    Returns
    -------
    str
        Path to the generated figures.

    """
    # Select the variables
    outputs = config_obj["outputs"]
    output_path = config_obj.get("output_path")

    # Select the variables
    for k in config_obj["models"].keys():
        nb_mooring = len(config_obj["observation"]["ds_coloc"][k])
    for iobs in range(nb_mooring):
        cfg = copy.deepcopy(config_obj)
        observation = copy.copy(cfg["observation"])
        models = copy.copy(cfg["models"])
        for model in config_obj["models"].keys():
            models[model].update(
                {"ds_coloc": config_obj["models"][model]["ds_coloc"][iobs]}
            )
            observation["ds_coloc"].update(
                {model: config_obj["observation"]["ds_coloc"][model][iobs]}
            )
        cfg["observation"] = observation
        cfg["models"] = models
        cfg, vars = sel_default_vars(cfg)
        observation = copy.copy(cfg["observation"])
        models = copy.copy(cfg["models"])

        # PLOT THE OUTPUTS
        for oname in outputs:
            output = outputs[oname]
            sub_func_output_folder = os.path.join(output_path, oname)
            create_folder(sub_func_output_folder)

            # get parameters from config obj
            vmin = output.get("vmin")
            vmax = output.get("vmax")
            dvmin = output.get("dvmin")
            dvmax = output.get("dvmax")
            cmap = output.get("colormap")
            cmap = cmap if cmap is None else f"cmo.{cmap}"

            for var in vars:
                if var == "current_geos":
                    vmin = -0.5
                    vmax = 0.5
                else:
                    vmin = None
                    vmax = None
                mods = [
                    models[mod]["ds_coloc"][var].assign_attrs(
                        {
                            "varname": var,
                            **models[mod]["ds_coloc"][var].attrs,
                            **models[mod]["ds_coloc"].attrs,
                        }
                    )
                    for mod in models
                ]
                obss = [
                    observation["ds_coloc"][mod][var].assign_attrs(
                        {
                            "varname": var,
                            **observation["ds_coloc"][mod][var].attrs,
                            **observation["ds_coloc"][mod].attrs,
                        }
                    )
                    for mod in models
                ]
                for idx in range(len(models)):
                    if "z" in obss[idx].dims:
                        vmin = obss[idx].min()
                        vmax = obss[idx].max()
                        plot_features.plot_variable_3d(
                            obss[idx],
                            mods[idx],
                            output_path=sub_func_output_folder,
                            vmin=vmin,
                            vmax=vmax,
                            dvmin=dvmin,
                            dvmax=dvmax,
                            cmap=cmap,
                        )
                    else:
                        plot_features.plot_variable_2d(
                            obss[idx],
                            mods[idx],
                            output_path=sub_func_output_folder,
                        )
