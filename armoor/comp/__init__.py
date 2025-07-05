METAZONE_PARAMS = {
    "comp_sst": [
        "tbound",
        "trange_seq",
        "tfreq",
        "polygon",
        "href",
        "cloud",
        "vars",
        "qc"
        ],
    "comp_argo": [
        "tbound",
        "trange_seq",
        "vrange",
        "vlevel",
        "polygon",
        "vars",
        "radius",
        "qc"
        ],
    "comp_mooring": [
        "tfreq",
        "tbound",
        "trange_seq",
        "polygon",
        "vars",
        "radius",
        "qc"
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
        }
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
    "comp_mooring": {
        "timeseries": {
            "sort": ["z"],
            "stat": ["time"],
            "concat": ["time"],
            "output": "merge"
            }
        },
    }

COMP_VARS = {
    "comp_sst": ["ptemp"],
    "comp_argo": ["ptemp", "sal", "pdens", "temp", "sndspeed"],
    "comp_mooring": ["ptemp", "sal", "pdens", "temp", "sndspeed"]
    }

TITLE_PLOTS = {
    "comp_sst": "Sea surface temperature",
    "comp_argo": "Hydrological profiles",
    "comp_mooring": "Hydrological mooring",
    }

CMAP_VARS = {
    "ptemp": "cmo.thermal",
    "temp": "cmo.thermal",
    "sal": "cmo.haline",
    "pdens": "cmo.dense",
    "sndspeed": "cmo.speed"
    }

METRIC_LABELS = {
    "diff": "Difference",
    "bias": "Bias",
    "rmse": "Rmse",
    "rmsec": "Ce.Rmse"
    }
