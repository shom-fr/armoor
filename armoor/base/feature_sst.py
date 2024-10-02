"""Create figures for feature 1:sst"""
import os
import copy
import logging
from armoor.base.tools_features import remove_missing_values_ds, sel_one_var, sel_default_vars
from armoor.base import plot_features
from armoor.hmi.script_tools import create_folder

logger = logging.getLogger(__name__)


def plot(config_obj):
    """
    Plot figures required in functionality 1 : sst.

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

    # Set the flags
    flag_interval = 'trange' in config_obj["metazone"]
    flag_slice = 'vrange' in config_obj["metazone"]

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
    config_obj, vars = sel_default_vars(config_obj)
    observation = copy.copy(config_obj["observation"])
    models = copy.copy(config_obj["models"])

    # Remove missing values
    #vars = ['ptemp']
    # for i_mod, mod in enumerate(models):
    #     models, observation = remove_missing_values_ds(models, observation, i_mod, vars)

    # Plot the outputs
    for oname in outputs:
        output = outputs[oname]
        sub_func_output_folder = os.path.join(output_path, oname)
        create_folder(sub_func_output_folder)

        # Get parameters from config obj
        vmin = output.get('vmin')
        vmax = output.get('vmax')
        dvmin = output.get('dvmin')
        dvmax = output.get('dvmax')
        cmap = output.get("colormap")
        cmap = cmap if cmap is None else f'cmo.{cmap}'

        # PLOTS
        for var in vars:
            mods = [
                models[mod]["ds_coloc"][[var]].assign_attrs({
                    "varname": var,
                    **models[mod]["ds_coloc"][var].attrs,
                    **models[mod]["ds_coloc"].attrs
                }) for mod in models
            ]
            obss = [
                observation["ds_coloc"][mod][[var]].assign_attrs({
                    "varname": var,
                    **observation["ds_coloc"][mod][var].attrs,
                    **observation["ds_coloc"][mod].attrs
                }) for mod in models
            ]
            ########################################################################################
            # TIME SERIES POINT
            plot_ts_metr_point = {"plot_ts_metr_cloud": 'difference_point',
                                  "plot_ts_metr_bias_point": 'bias_point',
                                  "plot_ts_metr_RMSE_point": 'RMSEc_point',
                                  "plot_ts_metr_point": 'all_metrics'
                                  }
            if output["plot"] in plot_ts_metr_point:
                plot_features.plot_ts_metr_cloud(
                    trange,
                    mods,
                    obss,
                    output_path=sub_func_output_folder,
                )
            ########################################################################################
            # TIME SERIES STATS
            plot_ts_metr_stats = {"plot_ts_metr_ecart_stats": 'difference_stats',
                                  "plot_ts_metr_bias_stats": 'bias_stats',
                                  "plot_ts_metr_RMSE_stats": 'RMSEc_stats',
                                  "plot_ts_metr_stats": 'all_metrics'
                                  }
            if output["plot"] in plot_ts_metr_stats:
                plg = config_obj["metazone"].get("polygon")
                plot_features.plot_ts_metr_stats(
                    trange,
                    None,
                    mods,
                    obss,
                    output_path=sub_func_output_folder,
                )

            ########################################################################################
            # MAP METRIC
            plot_map_metr = {"plot_map_metr_ecart_interval": 'difference',
                             "plot_map_metr_ecart": 'difference', "plot_map_metr_biais": 'bias',
                             "plot_map_metr_RMSE": 'RMSE', "plot_map_metr_RMSEc": 'RMSEc'
                             }
            # if output["plot"] in plot_map_metr:
            #     for i, mod in enumerate(mods):

            #         plot_features.plot_map_metr(flag_interval, flag_slice, mod["xarray_meta"],
            #                                     mod["xarray_meta_coloc"],
            #                                     observation_var["xarray_meta"],
            #                                     observation_var["xarray_meta_coloc"][i],
            #                                     plot_map_metr[output["plot"]], cmap, vmin, vmax,
            #                                     output_path=sub_func_output_folder, dvmin=dvmin,
            #                                     dvmax=dvmax)
                    
            if output["plot"] in plot_map_metr:
                for i, mod in enumerate(mods):
                    plot_features.plot_map_metr_profiles(
                        trange,
                        None,
                        mod,
                        obss[i],
                        plot_map_metr[output["plot"]],
                        cmap, vmin, vmax,
                        output_path=sub_func_output_folder,
                        dvmin=dvmin, dvmax=dvmax
                    )        

            ########################################################################################
            # DISP DIAG
            if "diag_disp" in output["plot"]:
                for i, mod in enumerate(mods):
                    plot_features.diag_disp(
                        trange,
                        None,
                        output["plot"],
                        mod,
                        obss[i],
                        tfreq=tfreq,
                        output_path=sub_func_output_folder
                    )
