def geo_vars(ds):

    geo_vars = [
        var
        for var in ds.data_vars
        if ("x" in ds[var].dims) and ("y" in ds[var].dims)
    ]

    return geo_vars


def nongeo_vars(ds):

    nongeo_vars = [
        var
        for var in ds.data_vars
        if ("x" not in ds[var].dims) and ("y" not in ds[var].dims)
    ]

    return nongeo_vars

def string_to_tuples_float(s):
    """
    Convert a string of tuples into a list of tuples.

    Parameters
    ----------
    s: str
        A string representing tuples, e.g., "(elm1, elm2), (elm3, elm4)".

    Returns
    -------
        list: A list of tuples.
    """
    s = s.replace(" ", "")
    tuples_str = s.split("),(")
    tuples = []
    for tuple_str in tuples_str:
        tuple_str = tuple_str.strip("()")
        elements = tuple_str.split(",")
        for iel, el in enumerate(elements):
            elements[iel] = float(el)
        tuples.append(tuple(elements))

    return tuples