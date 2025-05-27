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
        ]
    }

COLOCATION_PARAMS_USER = {
    "comp_sst": {
        "time": ("trange_seq", "tfreq"),
        "horizontal": ("href", "cloud"),
        }
    }

COLOCATION_PARAMS_DEFAULT = {
    "comp_sst": {
        "vertical": ("vlevel", {"depth": [0.]})
        }
    }

OUTPUTS_PARAMS = {
    "comp_sst":{
        "diagdisp_glob": ["product"],
        "diagdisp_sel": ["product", "time"],
        "timeseries": None,
        "maps": ["product", "time"],
        }
    }

OUTPUTS_VARS = {
    "comp_sst": ["ptemp"]
    }

TITLE_PLOTS = {
    "comp_sst": "Sea surface temperature"
    }