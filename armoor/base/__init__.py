FILTERS = {
    "tbound": lambda obj: obj.armoorfilters.time_selection_bounds,
    "trange_seq": lambda obj: obj.armoorfilters.time_selection_range_seq,
    "trange_clim": lambda obj: obj.armoorfilters.time_selection_range_clim,
    "polygon": lambda obj: obj.armoorfilters.horizontal_selection_polygon,
    "polygon_dilat": lambda obj: obj.armoorfilters.horizontal_selection_polygon_dilat,
    "vrange": lambda obj: obj.armoorfilters.vertical_selection_range,
    "vlevel": lambda obj: obj.armoorfilters.vertical_selection_levels,
}

LINE_COLORS = [
    '#1f77b4',
    '#ff7f0e',
    '#2ca02c',
    '#d62728',
    '#9467bd',
    '#8c564b',
    '#e377c2',
    '#7f7f7f',
    '#bcbd22',
    '#17becf'
    ]

CMAP_VARS = {
    "ptemp": "cmo.thermal",
    "temp": "cmo.thermal",
    "sal": "cmo.haline",
    "pdens": "cmo.dense",
    "sndspeed": "cmo.speed",
    "mld": "cmo.deep",
    "depth": "cmo.deep",
    "ssh": "cmo.delta",
    "u": "cmo.delta",
    "v": "cmo.delta"
    }

MINMAX_VARS = {
    "ptemp": "pos",
    "temp": "pos",
    "sal": "pos",
    "pdens": "pos",
    "sndspeed": "pos",
    "mld": "pos",
    "depth": "pos",
    "ssh": "rel",
    "u": "rel",
    "v": "rel",
    }