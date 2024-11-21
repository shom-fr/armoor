"""Create figures for feature 3:prof_hydro_mooring"""
import os
import copy
import logging
import numpy as np
from armoor.base.tools_features import remove_missing_values_ds, sel_one_var, sel_default_vars
from armoor.base import plot_features
from armoor.hmi.script_tools import create_folder

logger = logging.getLogger(__name__)


def plot(config_obj):
    """
    Plot figures required in functionality 3 : prof_hydro_mooring.

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
    
    if "trange_seq" in config_obj["metazone"]:
        trange = {
            "trange_seq": config_obj["metazone"]["trange_seq"],
            "tbound": config_obj["metazone"]["tbound"],
        }
    elif 'trange_clim' in config_obj["metazone"]:
        trange = {
            "trange_clim": config_obj["metazone"]["trange_clim"],
            "tbound": config_obj["metazone"]["tbound"],
        }
    else:
        trange = None
    
    if "tfreq" in config_obj["metazone"]:
        tfreq = config_obj["metazone"]["tfreq"]
    else:
        tfreq = None
        
    # Select the variables
    for k in config_obj["models"].keys():
        nb_mooring = len(config_obj["observation"]["ds_coloc"][k])
    for iobs in range(nb_mooring):
        logger.info(f"Process mooring: {iobs}")
        cfg = copy.deepcopy(config_obj)
        observation = copy.copy(cfg["observation"])
        models = copy.copy(cfg["models"])
        for model in config_obj["models"].keys():
            models[model].update({
                "ds_coloc": config_obj["models"][model]["ds_coloc"][iobs]
            })
            observation["ds_coloc"].update({
                model: config_obj["observation"]["ds_coloc"][model][iobs]
            })
        cfg["observation"] = observation
        cfg["models"] = models
        cfg, vars = sel_default_vars(cfg)
        observation = copy.copy(cfg["observation"])
        models = copy.copy(cfg["models"])
        
        # Plot the outputs
        for oname in outputs:
            output = outputs[oname]
            sub_func_output_folder = os.path.join(output_path, oname)
            create_folder(sub_func_output_folder)
            
            # PLOTS
            for var in vars:
                logger.info(f"Plot {var}")
                # TIME SERIES STATS
                obs = [
                    observation["ds_coloc"][mod][[var]].assign_attrs({
                        "varname": var,
                        **observation["ds_coloc"][mod][var].attrs,
                        **observation["ds_coloc"][mod].attrs
                    }) for mod in models
                ]
                mods = [
                    #models[mod]["ds_coloc"][[var]].mean("member").assign_attrs({
                    models[mod]["ds_coloc"][[var]].assign_attrs({
                        "varname": var,
                        **models[mod]["ds_coloc"][var].attrs,
                        **models[mod]["ds_coloc"].attrs
                    })for mod in models
                ]
                plot_ts_metr_stats = {"plot_ts_metr_ecart_stats": 'difference_stats',
                                      "plot_ts_metr_bias_stats": 'bias_stats',
                                      "plot_ts_metr_RMSE_stats": 'RMSEc_stats',
                                      "plot_ts_metr_stats": 'all_metrics'
                                      }
                if output["plot"] in plot_ts_metr_stats:
                    plot_features.plot_ts_metr_stats(
                        trange,
                        None,
                        mods,
                        obs,
                        output_path=sub_func_output_folder,
                    )
                