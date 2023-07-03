"""Create figures for feature 1:sst"""
import os
import copy

from armoor import base
import armoor.base.feature_tools as ft
import armoor.hmi.script_tools as st
import matplotlib.pyplot as plt
import logging

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
    flag_interval = 'interval' in config_obj["meta_zones"].keys()
    flag_slice = 'slice' in config_obj["meta_zones"].keys()

    # Select the variables
    config_obj = base.sel_default_vars(config_obj)
    observation = copy.copy(config_obj["observation"])
    models = copy.copy(config_obj["models"])

    # Remove missing values
    vars = ['sst']
    vars_mod = ['sst']
    for i_mod, mod in enumerate(models):
        models, observation = base.remove_missing_values_ds(models, observation, i_mod, vars_mod, vars)

    obs = observation['xarray_meta_coloc'][0].sst
    mod = models[0]['xarray_meta_coloc'].sst
    # plt.pcolormesh(obs.lon, obs.lat, obs.isel(time=0))
    # plt.savefig('obs.png')
    # plt.close()
    #
    # plt.pcolormesh(mod.lon, mod.lat, mod.isel(time=0))
    # plt.savefig('mod.png')
    # plt.close()

    # Get names
    models_name = [m['name'] for m in models]
    obs_name = observation['name']

    # Plot the outputs
    for index_output, output in enumerate(outputs):
        logger.info(f'Generating plot :: {output["plot"]}')
        if output_path:
            sub_func_output_folder = os.path.join(output_path, output["folder_name"])
            logger.info(f'Storing in folder :: {sub_func_output_folder}')
            st.create_folder(sub_func_output_folder)
        else:
            sub_func_output_folder = output_path

        if 'attribute' in output and output['attribute'] != 'SST':
            logger.debug(f'{config_obj["functionality"]} should be used for SST only.')

        # Get parameters from config obj
        vmin = output.get('vmin')
        vmax = output.get('vmax')
        dvmin = output.get('dvmin')
        dvmax = output.get('dvmax')
        cmap = output.get("colormap")
        cmap = cmap if cmap is None else f'cmo.{cmap}'

        # PLOTS
        for var in vars:
            observation_var, models_var = base.sel_one_var(observation, models, var)

            ################################################################################################################
            # TIME SERIES POINT
            plot_ts_metr_point = {"plot_ts_metr_ecart_point": 'difference_point',
                                  "plot_ts_metr_bias_point": 'bias_point', "plot_ts_metr_RMSE_point": 'RMSEc_point',
                                  "plot_ts_metr_point": 'all_metrics'
                                  }

            if output["plot"] in plot_ts_metr_point:
                base.plot_features.plot_ts_metr_point(models_var, observation_var, plot_ts_metr_point[output["plot"]],
                                                      flag_interval, flag_slice, output_path=sub_func_output_folder)

            ################################################################################################################
            # TIME SERIES STATS
            plot_ts_metr_stats = {"plot_ts_metr_ecart_stats": 'difference_stats',
                                  "plot_ts_metr_bias_stats": 'bias_stats', "plot_ts_metr_RMSE_stats": 'RMSEc_stats',
                                  "plot_ts_metr_stats": 'all_metrics'
                                  }
            if output["plot"] in plot_ts_metr_stats:
                plg = config_obj["meta_zones"].get("polygon")
                base.plot_features.plot_ts_metr_stats(models_var, observation_var, flag_interval, flag_slice,
                                                      output_path=sub_func_output_folder, plg=plg)

            ################################################################################################################
            # MAP METRIC
            plot_map_metr = {"plot_map_metr_ecart_interval": 'difference', "plot_map_metr_ecart": 'difference',
                             "plot_map_metr_biais": 'bias', "plot_map_metr_RMSEc": 'RMSEc',
                             "plot_map_metr_RMSEcentree": 'RMSEcentree'
                             }
            if output["plot"] in plot_map_metr:
                for i, mod in enumerate(models_var):
                    base.plot_features.plot_map_metr(flag_interval, flag_slice, mod["xarray_meta"],
                                                     mod["xarray_meta_coloc"], observation_var["xarray_meta"],
                                                     observation_var["xarray_meta_coloc"][i],
                                                     plot_map_metr[output["plot"]], cmap, vmin, vmax,
                                                     output_path=sub_func_output_folder, dvmin=dvmin, dvmax=dvmax,
                                                     mod_name=models_name[i], obs_name=obs_name)

            ################################################################################################################
            # DISP DIAG
            if "diag_disp" in output["plot"]:
                for i, mod in enumerate(models_var):
                    base.plot_features.diag_disp(flag_interval, flag_slice, obs_name, models_name[i], output["plot"],
                                                 mod["xarray_meta_coloc"], observation_var["xarray_meta_coloc"][i],
                                                 output_path=sub_func_output_folder)
