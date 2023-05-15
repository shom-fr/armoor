"""Create figures for feature 5:clim_hydro"""
import os
import copy
from armoor import base
import calendar
import armoor.hmi.script_tools as st

import logging

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

    # SET THE FLAGS
    flag_interval = False
    flag_slice = False

    observation = copy.copy(config_obj["observation"])
    models = copy.copy(config_obj["models"])

    for index_output, output in enumerate(outputs):
        if output_path:
            sub_func_output_folder = os.path.join(output_path, output["folder_name"])
            st.create_folder(sub_func_output_folder)
        else:
            sub_func_output_folder = output_path

        # Get the figure parameters from config obj
        if 'vmin' in output:
            vmin = output["vmin"]
        else:
            vmin = None

        if 'vmax' in output:
            vmax = output["vmax"]
        else:
            vmax = None

        if 'colormap' in output:
            cmap = 'cmo.' + output["colormap"]
        else:
            cmap = None

        # Select the variables in the model and in the observations
        if "attribute" in output:
            var0 = output['attribute']
            if "list" not in str(type(var0)):  # si une seule var
                var = [var0]
            else:
                var = var0
        else:
            raise Exception("Oops, vous devriez fournir au moins une variable à laquelle appliquer le tracé demandé :"
                            " 'attribute' ...")

        observation["xarray_meta"] = observation["xarray_meta"].read_sst.sel(var)

        # Select the variables and calculate the climatology for the models
        for i_mod, mod in enumerate(models):
            mod["xarray_meta"] = mod["xarray_meta"].read_sst.sel(var).groupby("time.month").mean("time").rename(
                {'month': 'time'})

            mod["xarray_meta_coloc"] = mod["xarray_meta_coloc"].read_sst.sel(var).groupby("time.month").mean(
                "time").rename({'month': 'time'}).assign_coords({'time': calendar.month_name[1:13]})
            observation["xarray_meta_coloc"][i_mod] = observation["xarray_meta_coloc"][i_mod].read_sst.sel(
                var).assign_coords({'time': calendar.month_name[1:13]})

            # Remove missing values
            models, observation = base.remove_missing_values_ds(models, observation, i_mod, var, var)

        # PLOTS
        ################################################################################################################
        # TIME SERIES POINT
        plot_ts_metr_point = {"plot_ts_metr_ecart_point": 'difference_point'}
        if output["plot"] in plot_ts_metr_point:
            base.plot_features.plot_ts_metr_point(models, observation, plot_ts_metr_point[output["plot"]],
                                                  flag_interval, flag_slice, output_path=sub_func_output_folder)

        ################################################################################################################
        # TIME SERIES STATS
        plot_ts_metr_stats = {"plot_ts_metr_ecart_stats": 'difference_stats', "plot_ts_metr_bias_stats": 'bias_stats',
                              "plot_ts_metr_RMSE_stats": 'RMSEc_stats', "plot_ts_metr_stats": 'all_metrics'
                              }
        if output["plot"] in plot_ts_metr_stats:
            # for i, mod in enumerate(models):
            #     base.plot_features.plot_ts_metr(mod["xarray_meta"],
            #                                      mod["xarray_meta_coloc"],
            #                                      observation["xarray_meta"],
            #                                      observation["xarray_meta_coloc"][i],
            #                                      plot_ts_metr[output["plot"]])

            base.plot_features.plot_ts_metr_stats(models, observation, flag_interval, flag_slice,
                                                  output_path=sub_func_output_folder)

        ################################################################################################################
        # MAP METRIC
        plot_map_metr = {"plot_map_metr_ecart": 'difference'}
        if output["plot"] in plot_map_metr:
            for i, mod in enumerate(models):
                if 'depth' not in mod["xarray_meta_coloc"].dims:
                    base.plot_features.plot_map_metr(flag_interval, flag_slice, mod["xarray_meta"],
                                                     mod["xarray_meta_coloc"], observation["xarray_meta"],
                                                     observation["xarray_meta_coloc"][i], plot_map_metr[output["plot"]],
                                                     cmap, vmin, vmax, output_path=sub_func_output_folder)
                else:
                    for depth in [float(mod["xarray_meta_coloc"].depth.values)]:
                        try:
                            mod["xarray_meta"] = mod["xarray_meta"].sel(depth=depth, method='nearest')
                        except:
                            logger.warning("model-meta depth selection : Failed")
                        try:
                            mod["xarray_meta_coloc"] = mod["xarray_meta_coloc"].sel(depth=depth, method='nearest')
                        except:
                            logger.warning("model-meta-coloc depth selection : Failed")
                        try:
                            observation["xarray_meta"] = observation["xarray_meta"].sel(depth=depth, method='nearest')
                        except:
                            logger.warning("obs-meta depth selection : Failed")
                        try:
                            observation["xarray_meta_coloc"][i] = observation["xarray_meta_coloc"][i].sel(depth=depth,
                                                                                                          method='nearest')
                        except:
                            logger.warning("obs-meta-coloc depth selection : Failed")

                        base.plot_features.plot_map_metr(flag_interval, flag_slice, mod["xarray_meta"],
                                                         mod["xarray_meta_coloc"], observation["xarray_meta"],
                                                         observation["xarray_meta_coloc"][i],
                                                         plot_map_metr[output["plot"]], cmap, vmin, vmax,
                                                         output_path=sub_func_output_folder)
