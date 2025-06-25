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
        }
    }

COLOCATION_PARAMS_DEFAULT = {
    "comp_sst": {
        "vertical": ("vlevel", ("depth", [0.]))
        },
    "comp_argo": {
        "time": ("trange_seq", ("*", "reference", "nearest"))
        }
    }

OUTPUTS_PARAMS = {
    "comp_sst":[
        "diagdisp_glob",
        "diagdisp_sel",
        "timeseries",
        "maps",
        ],
    "comp_argo":[
        "diagdisp_glob",
        "diagdisp_sel",
        "timeseries",
        "mvprofiles",
        "uvprofiles",
        "mdiagts",
        "udiagts",
        "maps",
        ]
    }

COMP_VARS = {
    "comp_sst": ["ptemp"],
    "comp_argo": ["ptemp", "sal", "pdens", "temp", "sndspeed"]
    }

TITLE_PLOTS = {
    "comp_sst": "Sea surface temperature",
    "comp_argo": "Hydrological profiles"
    }

CMAP_VARS = {
    "ptemp": "cmo.thermal",
    "temp": "cmo.thermal",
    "sal": "cmo.haline",
    "pdens": "cmo.dense",
    "sndspeed": "cmo.speed"
    }

METRIC_LABELS = {
    "bias": "Bias",
    "rmse": "Rmse",
    "rmsec": "Ce.Rmse"
    }