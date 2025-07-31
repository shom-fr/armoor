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
    }
