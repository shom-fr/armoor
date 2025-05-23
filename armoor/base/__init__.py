FILTERS = {
    "tbound": lambda obj: obj.armoorfilters.time_selection_bounds,
    "trange_seq": lambda obj: obj.armoorfilters.time_selection_range_seq,
    "trange_clim": lambda obj: obj.armoorfilters.time_selection_range_clim,
    "polygon": lambda obj: obj.armoorfilters.horizontal_selection_polygon,
    "vrange": lambda obj: obj.armoorfilters.vertical_selection_range,
    "vlevel": lambda obj: obj.armoorfilters.vertical_selection_levels,
}
