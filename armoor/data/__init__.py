INTERP_PARAMS_USER = {
    "time": ("tfreq",),
    "horizontal": ("cloud",),
    "vertical": ("vlevel",),
    }

OUTPUTS_PARAMS = {
    "maps": {
        "sort": ["time", "z"],
        "stat": ["time", "z"],
        "mparams_con": {
            "time": ["tfreq"],
            }
        },
    "timeseries": {
        "sort": ["z"],
        "concat": ["time"],
        "stat": ["time", "z", "y", "x"],
        "output": "merge",
        },
    "mvprofiles": {
        "sort": ["time", "z"],
        "mparams_con": {
            "vertical": ["vlevel"],
            }
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
        "mparams_con": {
            "vertical": ["vlevel"],
            }
        },
    "udiagts": {
        "concat": ["time"],
        "output": "merge",
        "mparams_pro": {
            "horizontal": ["cloud"]
            },
        },
    }