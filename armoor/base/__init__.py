FILTERS = {
    "tbound": lambda obj: obj.meta.time_selection_bounds,
    "trange_seq": lambda obj: obj.meta.time_selection_range_seq,
    "trange_clim": lambda obj: obj.meta.time_selection_range_clim,
    "polygon": lambda obj: obj.meta.horizontal_selection_polygon,
    "vrange": lambda obj: obj.meta.vertical_selection_range,
    "vlevel": lambda obj: obj.meta.vertical_selection_levels,
}
