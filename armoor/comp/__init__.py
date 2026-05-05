METAZONE_PARAMS = {
    "comp_sst": [
        "tbound",
        "thours",
        "trange_seq",
        "tfreq",
        "polygon",
        "href",
        "cloud",
        "oceanvars",
        "qc",
        "bathy"
        ],
    "comp_argo": [
        "tbound",
        "thours",
        "trange_seq",
        "vrange",
        "vlevel",
        "polygon",
        "radius",
        "oceanvars",
        "qc",
        "bathy"
        ],
    "comp_mooring": [
        "tfreq",
        "thours",
        "tbound",
        "trange_seq",
        "polygon",
        "oceanvars",
        "radius",
        "qc",
        "bathy"
        ],
    "comp_drifter": [
        "tbound",
        "polygon",
        "oceanvars",
        "freq_drift",
        "period_drift",
        "tresample",
        "tsmooth",
        "bathy"
        ],
    "comp_models": [
        "tfreq",
        "tbound",
        "thours",
        "trange_seq",
        "polygon",
        "href",
        "cloud",
        "vrange",
        "vlevel",
        "oceanvars",
        "bathy"
        ],
    "comp_clim": [
        "tbound",
        "polygon",
        "href",
        "vlevel",
        "oceanvars",
        "bathy",
        ]
    }

COLOCATION_PARAMS_USER = {
    "comp_sst": {
        "time": ("trange_seq", "tfreq"),
        "horizontal": ("href", "cloud"),
        },
    "comp_argo": {
        "time": ("trange_seq",),
        "horizontal": ("radius",),
        "vertical": ("vrange", "vlevel"),
        },
    "comp_mooring": {
        "time": ("trange_seq", "tfreq"),
        "horizontal": ("radius",),
        },
    "comp_drifter": {},
    "comp_models": {
        "time": ("trange_seq", "tfreq"),
        "horizontal": ("href", "cloud"),
        "vertical": ("vrange", "vlevel"),
        },
    "comp_clim": {
        "time":       ("tmonth",),
        "horizontal": ("href",),
        "vertical":   ("vlevel",),
        },
    }

COLOCATION_PARAMS_DEFAULT = {
    "comp_sst": {
        "vertical": ("vlevel", ("depth", [0.]))
        },
    "comp_argo": {
        "time": ("trange_seq", ("*", "reference", "nearest"))
        },
    "comp_mooring": {
        "vertical": ("vrange", ("reference", "depth", "*"))
        },
    "comp_drifter": {
        "vertical": ("vrange", ("reference", "depth", "*"))
        }
    }

OUTPUTS_PARAMS = {
    "comp_sst":{
        "diagdisp_glob": {
            "concat": ["time"],
            },
        "diagdisp_sel": {
            "sort": ["time"],
            "concat": ["time"]
            },
        "timeseries": {
            "concat": ["time"],
            "stat": ["time", "x", "y"],
            "output": "merge"
            },
        "maps": {
            "sort": ["time"],
            "stat": ["time"],
            },
        },
    "comp_argo":{
        "maps": {
            "sort": ["time", "z"],
            "stat": ["z"],
            "mparams_pro": {
                "time": ["trange_seq"],
                "vertical": ["vlevel", "vrange"]
                },
            },
        "diagdisp_glob": {
            "concat": ["time"],
            "mparams_pro": {
                "vertical": ["vlevel", "vrange"]
                }
            },
        "diagdisp_sel": {
            "sort": ["time", "z"],
            "mparams_pro": {
                "time": ["trange_seq"],
                "vertical": ["vlevel", "vrange"]
                }
            },
        "timeseries": {
            "sort": ["z"],
            "concat": ["time"],
            "stat": ["time", "z"],
            "output": "merge",
            "mparams_pro": {
                "time": ["trange_seq"],
                "vertical": ["vlevel", "vrange"]
                }
            },
        "mvprofiles": {
            "sort": ["time", "z"],
            "mparams_pro": {
                "time": ["trange_seq"],
                },
            "mparams_con": {
                "vertical": ["vlevel"],
                }
            },
        "mdiagts": {
            "sort": ["time", "z"],
            "mparams_pro": {
                "time": ["trange_seq"],
                }
            },
        "uvprofiles": {
            "concat": ["time"],
            "output": "merge",
            "mparams_con": {
                "vertical": ["vlevel"]
                }
            },
        "udiagts": {
            "concat": ["time"],
            "output": "merge"
            },
        },
    "comp_drifter": {
        "preproc": "oceanparcels",
        "timeseries_drifter":{
            "output": "merge"
            },
        "maps_current_drifter":{
            },
        "maps_trajectory_drifter":{
            }
        },
    "comp_mooring": {
        "timeseries": {
            "sort": ["z"],
            "stat": ["time"],
            "concat": ["time"],
            "output": "merge"
            }
        },
    "comp_models":{
        "maps": {
            "sort": ["time", "z"],
            "stat": ["time", "z"],
            "mparams_con": {
                "time": ["tfreq"],
                }
            },
        "diagdisp_glob": {
            "concat": ["time"],
            },
        "diagdisp_sel": {
            "sort": ["time", "z"],
            },
        "timeseries": {
            "sort": ["z"],
            "concat": ["time"],
            "stat": ["time", "z", "y", "x"],
            "output": "merge",
            },
        "mvprofiles": {
            "sort": ["time", "z"],
            },
        "mdiagts": {
            "sort": ["time", "z"],
            },
        "uvprofiles": {
            "concat": ["time"],
            "output": "merge",
            "mparams_pro": {
                "horizontal": ["cloud"]
                },
            },
        "udiagts": {
            "concat": ["time"],
            "output": "merge",
            "mparams_pro": {
                "horizontal": ["cloud"]
                },
            },

        },
    "comp_clim": {
        "maps": {
            "sort": ["time", "z"],
            "stat": ["time"],
            },
        "timeseries": {
            "sort": ["z"],
            "concat": ["time"],
            "stat": ["y", "x"],
            "output": "merge",
            },
        },
    }

COMP_VARS = {
    "comp_sst": ["ptemp"],
    "comp_argo": ["ptemp", "sal", "pdens", "temp", "sndspeed"],
    "comp_mooring": ["ptemp", "sal", "pdens", "temp", "sndspeed", "cdir", "cspeed"],
    "comp_drifter": ["ptemp", "sal", "u", "v"],
    "comp_models": ["ptemp", "sal", "pdens", "sndspeed"],
    "comp_clim": ["ptemp", "sal"],
    }

TITLE_PLOTS = {
    "comp_sst": "Sea surface temperature",
    "comp_argo": "Hydrological profiles",
    "comp_mooring": "Hydrological mooring",
    "comp_models": "",
    "comp_drifter": "Drifters",
    "comp_clim": "Hydrological climatology",
    }

METRIC_LABELS = {
    "diff": "Difference",
    "bias": "Bias",
    "rmse": "Rmse",
    "rmsec": "Ce.Rmse"
    }
