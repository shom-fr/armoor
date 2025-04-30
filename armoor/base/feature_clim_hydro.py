"""Create figures for feature 5:clim_hydro"""

import copy
import logging
import os

import armoor.hmi.script_tools as st
from armoor.base import plot_features
from armoor.base.tools_features import (
    remove_missing_values_ds,
    sel_default_vars,
    sel_one_var,
)
from armoor.hmi.script_tools import create_folder

logger = logging.getLogger(__name__)


def plot(config_obj):
    """
    Plot figures required in functionality 5 : clim_hydro.

    Parameters
    ----------
    config_obj : dict
        Dictionary with observations and models names and DataSets.

    Returns
    -------
    str
        Path to the generated figures.

    """
    outputs = config_obj["outputs"]
    output_path = config_obj.get("output_path")

    flag_interval = True
    flag_slice = False

    trange = {
        "trange_clim": config_obj["metazone"]["trange_clim"],
        "tbound": config_obj["metazone"]["tbound"],
    }

    config_obj, vars = sel_default_vars(config_obj)
    observation = copy.copy(config_obj["observation"])
    models = copy.copy(config_obj["models"])
    # Plot the outputs
    for oname in outputs:
        output = outputs[oname]
        sub_func_output_folder = os.path.join(output_path, oname)
        create_folder(sub_func_output_folder)

        # Get parameters from config obj
        vmin = output.get("vmin")
        vmax = output.get("vmax")
        dvmin = output.get("dvmin")
        dvmax = output.get("dvmax")
        cmap = output.get("colormap")
        cmap = cmap if cmap is None else f"cmo.{cmap}"

        # PLOTS
        for var in vars:
            mods = [
                models[mod]["ds_coloc"][[var]].assign_attrs(
                    {
                        "varname": var,
                        **models[mod]["ds_coloc"][var].attrs,
                        **models[mod]["ds_coloc"].attrs,
                    }
                )
                for mod in models
            ]
            obss = [
                observation["ds_coloc"][mod][[var]].assign_attrs(
                    {
                        "varname": var,
                        **observation["ds_coloc"][mod][var].attrs,
                        **observation["ds_coloc"][mod].attrs,
                    }
                )
                for mod in models
            ]
            plot_ts_metr_point = {
                "plot_ts_metr_cloud": "difference_point",
            }
            if output["plot"] in plot_ts_metr_point:
                plot_features.plot_ts_metr_cloud(
                    trange,
                    mods,
                    obss,
                    output_path=sub_func_output_folder,
                )
            plot_ts_metr_stats = {
                "plot_ts_metr_ecart_stats": "difference_stats",
                "plot_ts_metr_bias_stats": "bias_stats",
                "plot_ts_metr_RMSE_stats": "RMSEc_stats",
                "plot_ts_metr_stats": "all_metrics",
            }
            if output["plot"] in plot_ts_metr_stats:
                plot_features.plot_ts_metr_stats(
                    trange,
                    None,
                    mods,
                    obss,
                    output_path=sub_func_output_folder,
                )
                
            plot_map_metr = {
                "plot_map_metr_ecart_interval": "difference",
                "plot_map_metr_ecart": "difference",
            }
            if output["plot"] in plot_map_metr:
                for i, mod in enumerate(mods):
                    plot_features.plot_map_metr_profiles(
                        trange,
                        None,
                        mod,
                        obss[i],
                        plot_map_metr[output["plot"]],
                        cmap,
                        vmin,
                        vmax,
                        output_path=sub_func_output_folder,
                        dvmin=dvmin,
                        dvmax=dvmax,
                    )
