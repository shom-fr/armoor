FILTERS = {
    "tbound": lambda obj: obj.meta.time_selection_bounds,
    "trange_seq": lambda obj: obj.meta.time_selection_range_seq,
    "vrange": lambda obj: obj.meta.vertical_selection_range,
    "vlevel": lambda obj: obj.meta.vertical_selection_levels,
}