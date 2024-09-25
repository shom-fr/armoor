"""Create figures for feature 2:prof_hydro_vessel"""
import os
import copy
import logging
from armoor.base.tools_features import remove_missing_values_ds, sel_one_var, sel_default_vars
from armoor.base import plot_features
from armoor.hmi.script_tools import create_folder

logger = logging.getLogger(__name__)


def plot(config_obj):
    """
    Plot figures required in functionality 2 : prof_hydro_vessel.

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
        
    if "vrange" in config_obj["metazone"]:
        vrange = config_obj["metazone"]["vrange"]
    else:
        vrange = None
    # Select the variables
    config_obj, vars = sel_default_vars(config_obj)
    observation = copy.copy(config_obj["observation"])
    models = copy.copy(config_obj["models"])

    # # Remove missing values
    #vars = [var for var in list(observation["ds_metazone"].keys()) if var in models[0]["ds_metazone"]]

    # for i_mod, mod in enumerate(models):
    #      models, observation = remove_missing_values_ds(models, observation, i_mod, vars)

    # PLOT THE OUTPUTS
    for oname in outputs:
        output = outputs[oname]
        sub_func_output_folder = os.path.join(output_path, oname)
        create_folder(sub_func_output_folder)

        # get parameters from config obj
        vmin = output.get('vmin')
        vmax = output.get('vmax')
        dvmin = output.get('dvmin')
        dvmax = output.get('dvmax')
        cmap = output.get("colormap")
        cmap = cmap if cmap is None else f'cmo.{cmap}'

        # PLOTS

        if 'diag_ts' in output["plot"]:  # Plots with several variables (temp sal here)
            ########################################################################################
            
            mods = [
                models[mod]["ds_coloc"].assign_attrs({
                    **models[mod]["ds_coloc"].attrs
                }) for mod in models
            ]
            obss = [
                observation["ds_coloc"][mod].assign_attrs({
                    **observation["ds_coloc"][mod].attrs
                }) for mod in models
            ]
            
            # DIAG TS PROFIL UNIQUE
            plot_profile_u = {"diag_ts_unique": 'diag_ts_unique'}
            if output["plot"] in plot_profile_u:
                plot_features.plot_diag_ts_unique(
                    mods,
                    obss,
                    output_path=sub_func_output_folder
                )

            ########################################################################################
            # DIAG_TS_MULTI
            diag_ts_multi = {"diag_ts_multi": 'diag_ts_multi'}

            if output["plot"] in diag_ts_multi:
                plot_features.plot_diag_ts_multi(
                    trange,
                    mods,
                    obss,
                    output_path=sub_func_output_folder
                )
                plot_features.plot_diag_ts_multi_trange(
                    trange,
                    mods,
                    obss,
                    output_path=sub_func_output_folder
                )

        else:
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
                
                #observation_var, models_var = observationsel_one_var(observation, models, var)
                ####################################################################################
                # TIME SERIES STATS
                plot_ts_metr_stats = {"plot_ts_metr_stats": 'all_metrics'
                                      }
                if output["plot"] in plot_ts_metr_stats:
                    modds = []
                    for mod in mods:
                        if "member" in mod.dims:
                            m = mod.reset_coords(
                                "depth"
                            ).mean("member").set_coords(
                                "depth"
                            ).assign_attrs({**mod.attrs})[[var]]
                        else:
                            m = mod
                        modds.append(m)
                    obbss = []
                    for obs in obss:
                        if "member" in obs.dims:
                            m = obs.reset_coords(
                                "depth"
                            ).mean("member").set_coords(
                                "depth"
                            ).assign_attrs({**obs.attrs})[[var]]
                        else:
                            m = obs
                        obbss.append(m)
                    plg = config_obj["metazone"].get("polygon")
                    plot_features.plot_ts_metr_stats(
                        trange,
                        vrange,
                        modds,
                        obbss,
                        output_path=sub_func_output_folder,
                        plg=plg
                    )

                ####################################################################################
                # MAP METRIC
                plot_map_metr = {"plot_map_metr_ecart": 'difference', "plot_map_metr_biais": 'bias',
                                 "plot_map_metr_RMSE": 'RMSE', "plot_map_metr_RMSEc": 'RMSEc'
                                 }

                if output["plot"] in plot_map_metr:
                    for i, mod in enumerate(mods):
                        plot_features.plot_map_metr_profiles(
                            trange,
                            vrange,
                            mod.reset_coords(
                                "depth"
                            ).mean("member").set_coords(
                                "depth"
                            ).assign_attrs({**mod.attrs})[[var]] if "member" in mod.dims else mod,
                            obss[i].reset_coords(
                                "depth"
                            ).mean("member").set_coords(
                                "depth"
                            ).assign_attrs({**obss[i].attrs})[[var]] if "member" in obss[i].dims else obss[i],
                            plot_map_metr[output["plot"]],
                            cmap, vmin, vmax,
                            output_path=sub_func_output_folder,
                            dvmin=dvmin, dvmax=dvmax
                        )

                ####################################################################################
                # DISP DIAG
                diag_disp = {"diag_disp": 'diag_disp', "diag_disp_g": 'diag_disp_g'}
                if output["plot"] in diag_disp:
                    for i, mod in enumerate(mods):
                        plot_features.diag_disp(
                            trange,
                            vrange,
                            output["plot"],
                            mod.reset_coords(
                                "depth"
                            ).mean("member").set_coords(
                                "depth"
                            ).assign_attrs({**mod.attrs})[[var]] if "member" in mod.dims else mod,
                            obss[i].reset_coords(
                                "depth"
                            ).mean("member").set_coords(
                                "depth"
                            ).assign_attrs({**obss[i].attrs})[[var]] if "member" in obss[i].dims else obss[i],
                            output_path=sub_func_output_folder
                        )

                ####################################################################################
                # COURBE PROFIL UNIQUE
                plot_profile_u = {"plot_profile_u": 'profile_u'}
                if output["plot"] in plot_profile_u:
                    plot_features.plot_profile_unique(
                        var,
                        mods,
                        obss,
                        output_path=sub_func_output_folder
                    )

                ####################################################################################
                # COURBE MULTI PROFILS
                plot_profile_multi = {"plot_profile_multi": 'profile_multi'}
                if output["plot"] in plot_profile_multi:
                    plot_features.plot_profile_multi(
                        trange,
                        var,
                        mods,
                        obss,
                        output_path=sub_func_output_folder
                    )
                    plot_features.plot_profile_multi_trange(
                        trange,
                        var,
                        mods,
                        obss,
                        output_path=sub_func_output_folder
                    )
                    

