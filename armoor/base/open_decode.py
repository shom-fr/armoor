"""XrReaderAccessor
"""
import xarray as xr
import xoa.grid
import xoa.cf as xcf
import numpy as np
import os
import xoa
import gsw
import logging
import datetime
from xoa.grid import dz2depth, shift

logger = logging.getLogger(__name__)


def open_decode(path_files, func=None, type=None) -> xr.Dataset:
    """
     Open a netcdf/txt file and store it into a dataset
     Parameters
     ----------
     path_files : str, list of str
         Path to the netcdf files.
     func : str
        Poste 1 : functionnality.
     type : str
        type of txt file or model.

     Returns
     -------
     xarray.Dataset
         Model or observation dataset.
     """
    # Xoa initialisation
    xoa.register_accessors()
    xoa.register_accessors(decode_sigma=True)

    # Read cfg file
    try:
        rootdir = os.path.abspath(os.path.dirname(__file__))
        path = os.path.join(rootdir, '..', '..', 'config', 'cf.cfg')
        logger.info(f'using path : {path}')
    except:
        logger.warning('cf.cfg file not found')
        directory = os.getcwd()
        logger.warning(f'using path : {directory}')
    xcf.register_cf_specs(path)

    if not isinstance(path_files, (list, dict)):
        raise TypeError(f"Only list or dict are allowed : {path_files} ")

    # Open file
    if func == 'forecaster':
        logger.info(f"forecaster")
        return open_forecaster(path_files, type)

    else:
        if type == "WOA18":
            logger.info(f"Opening WOA18")
            return open_decode_woa18(path_files)
        elif type == "CMEMS":
            logger.info(f"Opening CMEMS")
            return open_decode_cmems(path_files)
        elif type == "scanfish":
            logger.info(f"Opening Scanfish")
            return open_decode_scanfish(path_files[0])
        elif type == "seasoar":
            logger.info(f"Opening Seasoar")
            return open_decode_seasoar(path_files[0])
        elif type == "LADCP":
            logger.info(f"Opening L-ADCP")
            return open_decode_l_adcp(path_files[0])
        elif type == "mouillage":
            logger.info(f"Opening Mooring")
            return open_decode_mouillages(path_files[0])
        elif type == "VMADCP":
            logger.info(f"Opening VMADCP")
            return open_decode_vmadcp(path_files[0])
        elif type == 'CROCO':
            logger.info(f"Opening CROCO")
            return open_decode_croco(path_files[0])
        elif type == 'CROCO_currents':
            logger.info(f"Opening CROCO currents")
            return open_decode_croco_currents(path_files[0])
        elif type == 'HYCOM_currents':
            logger.info(f"Opening HYCOM currents")
            return open_decode_hycom_currents(path_files)
        elif type == 'HYCOM_3D':
            logger.info(f"Opening HYCOM 3D currents")
            return open_decode_hycom_3d(path_files)
        elif type == 'CORA':
            logger.info(f"Opening CORA")
            return open_decode_cora(path_files[0])
        else:
            logger.info(f"Opening non specific file type")
            return open_decode_basic(path_files)


def open_decode_woa18(path_files):
    """
     Open WOA18 netcdf files and store it into a ready-to-use dataset.
     Parameters
     ----------
     path_files : str, list of str
         Path to the netcdf files.
     Returns
     -------
     xarray.Dataset
         WOA18 dataset.
     """
    # Open
    woa18 = xr.open_mfdataset(path_files, decode_times=False)

    # Decode
    vars_to_drop = ['_dd', '_gp', '_oa', '_sd', '_se', 'bnds', 'bounds']
    for var in list(woa18.keys()):
        if any(item in var for item in vars_to_drop):
            woa18 = woa18.drop_vars(var)

    if 's_an' in woa18:
        woa18 = woa18.rename({'s_an': 'sal'})
        if 's_mn' in woa18:
            woa18 = woa18.drop_vars({'s_mn'})
    elif 's_mn' in woa18:
        woa18 = woa18.rename({'s_mn': 'sal'})

    if 't_an' in woa18:
        woa18 = woa18.rename({'t_an': 'temp'})
        if 't_mn' in woa18:
            woa18 = woa18.drop_vars({'t_mn'})
    elif 't_mn' in woa18:
        woa18 = woa18.rename({'t_mn': 'temp'})

    try:
        woa18 = woa18.xoa.decode()
    except:
        pass

    return woa18


def open_decode_cmems(path_files):
    """
     Open CMEMS netcdf file(s) and store it into a ready-to-use dataset.
     Parameters
     ----------
     path_files : str, list of str
         Path to the netcdf files.
     Returns
     -------
     xarray.Dataset
         CMEMS dataset.
     """
    # Open
    if len(path_files) > 1:
        list_ds_cmems = []
        for path in path_files:
            ds = xr.open_dataset(path)
            lon_ds = ds.LONGITUDE.assign_coords(LONGITUDE=ds.TIME.data).rename({'LONGITUDE': 'TIME'})
            lat_ds = ds.LATITUDE.assign_coords(LATITUDE=ds.TIME.data).rename({'LATITUDE': 'TIME'})
            ds = ds.drop_vars(['LONGITUDE', 'LATITUDE'])
            ds['LATITUDE'] = lat_ds
            ds['LONGITUDE'] = lon_ds
            list_ds_cmems.append(ds)
        cmems = xr.concat(list_ds_cmems, dim='TIME')
    else:
        cmems = xr.open_dataset(path_files[0])

    # Variables to drop/rename to prevent random behaviours
    for var in list(cmems.keys()):
        if "POSITION" in var:
            cmems = cmems.drop_vars(var)
        elif var[-3:] == "_QC":
            cmems = cmems.rename({var: f"QC_{var[:-3]}"})
        if len(var) == 4:
            if f"{var}_ADJUSTED" in cmems:
                cmems = cmems.drop_vars(f"{var}_ADJUSTED")
            if f"{var}_ADJUSTED_ERROR" in cmems:
                cmems = cmems.drop_vars(f"{var}_ADJUSTED_ERROR")

    # Decode
    cmems = cmems.xoa.decode()

    # Manage profiler depths
    if 'DEPH' in cmems.variables:
        cmems = decode_profiler(cmems)

    # Manage lon(time) and lat(time)
    len_lon = len(cmems.lon)
    len_lat = len(cmems.lat)
    len_time = len(cmems.time)
    if len_lat == len_time and len_lon == len_time:
        cmems = convert_trajectory(cmems)

    # Calculate depth from pressure
    if 'depth' in cmems.dims and 'depth' not in cmems.coords and 'pres' in cmems:
        cmems = depth_from_press(cmems)

    # Convert depth
    cmems = convert_depths(cmems)

    return cmems


def open_decode_l_adcp(path_file):
    """
    Open txt file form L-ADCP observation and store it in a ready-to-use dataset.
    Parameters
    ----------
    path_file : str
        Path to the L-ADCP txt file.

    Returns
    -------
    dataset : xarray.dataset
        L-ADCP observation dataset.
    """
    # Read the .txt file
    file = open(path_file, 'r', encoding="ISO-8859-1")
    lines = file.readlines()
    n_line = len(lines)
    for i in range(n_line):
        lines[i] = lines[i].split('\t')
        lines[i][-1] = lines[i][-1].rstrip('\n')

    # Remove header
    lines = np.array(lines[1:])

    # List the index labels of the measurements
    list_measures = []
    for i, i_station in enumerate(np.unique(lines[:, 0])):
        list_measures.append(lines[lines[:, 0] == i_station])

    # Because the depths size is not always the same, we need to fill the smaller arrays with nan values
    # Get the maximum size of the depths list
    size_max = max([len(a) for a in list_measures])
    # Get the exhaustive list of depth values
    index_sizemax = [len(a) for a in list_measures].index(size_max)
    depth = list_measures[index_sizemax][:, 6]

    # Separate the measurements
    list_ds = []
    for i_mes, array_series in enumerate(list_measures):
        # Fill the small arrays with nan values
        array_same_size = np.lib.pad(array_series, ((0, size_max - len(array_series)), (0, 0)), 'constant',
                                     constant_values='NaN')
        # Set the right depth values
        array_same_size[:, 6] = depth

        # Get measurements coordinates
        lon = float(array_same_size[0][5])
        lat = float(array_same_size[0][4])
        time = f"{array_same_size[0][2]} {array_same_size[0][3]}"
        if time[0] == ' ':
            time = time[1:]
        time = datetime.datetime.strptime(time, '%m/%d/%Y %H:%M')
        time = np.datetime64(time)
        bottom_depth = np.nan

        # Convert the array into xr.dataset and add it to the list of measurements
        list_ds.append(array2ds(array_same_size, lon, lat, time, bottom_depth, 'LADCP'))

    # Merge the datasets
    ladcp = xr.concat(list_ds, dim='time')

    # Decode
    ladcp = ladcp.xoa.decode()

    # Clean lon/lat
    if len(np.unique(ladcp.lon.values)) == 1:
        lon_values = np.unique(ladcp.lon.values)
        lat_values = np.unique(ladcp.lat.values)
        ladcp = ladcp.drop_vars(['lon', 'lat'])
        ladcp = ladcp.assign_coords({'lon': lon_values, 'lat': lat_values})

    return ladcp


def open_decode_vmadcp(path_file) -> xr.Dataset:
    """
    Open txt file form VMADCP observation and store it in dataset.
    Parameters
    ----------
    path_file : str
        Path to the VMADCP txt file.

    Returns
    -------
    dataset : xarray.dataset
        VMADCP observation dataset.
    """
    logger.info("VMADCP")
    # Read the .txt file
    file = open(path_file, 'r', encoding="ISO-8859-1")
    lines = file.readlines()
    n_line = len(lines)
    for i in range(n_line):
        lines[i] = lines[i].split('\t')
        lines[i][-1] = lines[i][-1].rstrip('\n')

    # Remove header, set fill values
    lines = np.array(lines[1:])
    lines[lines == ''] = 9999999.

    # Get the number of measurements and the number of depths
    size_depth = np.count_nonzero(lines[:, 1] == '1')
    nb_measures = int(lines[-1, 1])

    # Separate the measurements
    list_ds = []
    for i in range(0, nb_measures):
        # Get measurements coordinates
        lon = float(lines[i * size_depth][5])
        lat = float(lines[i * size_depth][6])

        if lines[i * size_depth][7] == '':
            bottom_depth = np.nan
        else:
            bottom_depth = float(lines[i * size_depth][7])

        time = f"{lines[i * size_depth][3]} {lines[i * size_depth][4]}"
        time = datetime.datetime.strptime(time, '%m/%d/%Y %H:%M:%S')
        time = np.datetime64(time)

        # Subset the numpy array selecting only the specific measurements
        array_series = lines[i * size_depth:(i + 1) * size_depth, :]

        # Convert the array into xr.dataset and add it to the list of measurements
        list_ds.append(array2ds(array_series, lon, lat, time, bottom_depth, 'VMADCP'))

    # Merge the datasets
    vmadcp = xr.concat(list_ds, dim='time')

    # Decode
    vmadcp = vmadcp.xoa.decode()

    return vmadcp


def open_decode_mouillages(path_file):
    """
    Open txt file form mooring observation and store it in dataset.
    Parameters
    ----------
    path_file : str
        Path to the mooring txt file.

    Returns
    -------
    dataset : xarray.dataset
        mooring observation dataset.
    """
    logger.info("mooring")
    # Read the .txt file
    file = open(path_file, 'r', encoding="ISO-8859-1")
    lines = file.readlines()
    n_line = len(lines)
    for i in range(n_line):
        lines[i] = lines[i].split('\t')
        lines[i][-1] = lines[i][-1].rstrip('\n')  # Remove header
    lines = np.array(lines[1:])

    # Get the line indexes of the start of each new measurement, set fill values
    first_column = np.array(lines)[:, 0]
    first_column[first_column == ''] = 9999999.
    first_column = first_column.astype(float)
    index_mesures = np.where(first_column != 9999999.)[0]
    np.append(index_mesures, len(lines))
    nb_dates = len(index_mesures)

    # Separate the measurements
    list_ds = []
    for i in range(nb_dates - 1):
        # Get measurements coordinates
        i_line_deb = index_mesures[i]
        date = np.datetime64(lines[i_line_deb][3])
        lon = float(lines[i_line_deb][4])
        lat = float(lines[i_line_deb][5])
        bottom_depth = float(lines[i_line_deb][6])

        # Subset the numpy array selecting only the specific measurements
        array_series = np.array(lines[index_mesures[i]:index_mesures[i + 1], 7:]).astype(float)
        # Convert the array into xr.dataset and add it to the list of measurements
        list_ds.append(array2ds(array_series, lon, lat, date, bottom_depth, 'mouillages'))

    # Merge the datasets
    mouillage = xr.concat(list_ds, dim='time')

    # Decode
    mouillage = mouillage.xoa.decode()
    return mouillage


def open_decode_scanfish(path_file):
    """
    Open txt file form scanfish observation and store it in dataset.
    Parameters
    ----------
    path_file : str
        Path to the scanfish txt file.

    Returns
    -------
    dataset : xarray.dataset
        scanfish observation dataset.
    """
    # Read the .txt file
    file = open(path_file, 'r', encoding="ISO-8859-1")
    lines = file.readlines()
    n_line = len(lines)
    for i in range(n_line):
        lines[i] = lines[i].split('\t')
        lines[i][-1] = lines[i][-1].rstrip('\n')  # Remove header
    lines = np.array(lines[1:])
    lines[lines == ''] = 9999999.

    list_measures = []
    for i, i_station in enumerate(np.unique(lines[:, 0])):
        list_measures.append(lines[lines[:, 0] == i_station])

    # Separate the measurements
    list_ds = []
    for i_mes, array_series in enumerate(list_measures):
        # Get measurements coordinates
        lon = float(array_series[0][4])
        lat = float(array_series[0][3])
        time_j = float(array_series[0][1])
        time_y = array_series[0][2]
        time_origine_y = np.datetime64('1970-01-01')
        time = time_origine_y + np.timedelta64(time_y, 's') + np.timedelta64(int(time_j * 24 * 60 * 60), 's')
        list_ds.append(array2ds_radiales(array_series, lon, lat, time, 'radiale'))

    # Merge the datasets
    scanfish = xr.concat(list_ds, dim='depth')

    list_ds = []
    times = np.unique(scanfish.time.data)
    depths = np.unique(scanfish.depth.data)
    for time in times:
        ds_time = scanfish.where(scanfish.time == np.datetime64(time), drop=True)
        ds_time = ds_time.assign_coords(time=xr.DataArray([time], dims='time'))
        ds_time = ds_time.assign_coords(lon=xr.DataArray([ds_time.lon.data[0]], dims='time'))
        ds_time = ds_time.assign_coords(lat=xr.DataArray([ds_time.lat.data[0]], dims='time'))
        ds_time = ds_time.drop_duplicates(dim='depth')
        ds_time = ds_time.interp(depth=depths, method='nearest')
        list_ds.append(ds_time)

    scanfish = xr.concat(list_ds, dim='time')
    return scanfish


def open_decode_seasoar(path_file):
    """
    Open txt file form seasoar observation and store it in dataset.
    Parameters
    ----------
    path_file : str
        Path to the seasoar txt file.

    Returns
    -------
    dataset : xarray.dataset
        seasoar observation dataset.
    """
    # Read the .txt file
    file = open(path_file, 'r', encoding="ISO-8859-1")
    lines = file.readlines()
    n_line = len(lines)
    for i in range(n_line):
        lines[i] = lines[i].split('\t')
        lines[i][-1] = lines[i][-1].rstrip('\n')  # Remove header
    lines = np.array(lines[1:])
    lines[lines == ''] = 9999999.

    list_measures = []
    for i, i_station in enumerate(np.unique(lines[:, 0])):
        list_measures.append(lines[lines[:, 0] == i_station])

    # Separate the measurements
    list_ds = []
    for i_mes, array_series in enumerate(list_measures):
        # Get measurements coordinates
        lon = float(array_series[0][4])
        lat = float(array_series[0][3])
        time_j = float(array_series[0][1])
        time_q = array_series[0][2]
        time_origine_q = np.datetime64('2000-01-01')
        time = time_origine_q + np.timedelta64(time_q, 's') + np.timedelta64(int(time_j * 24 * 60 * 60), 's')
        list_ds.append(array2ds_radiales(array_series, lon, lat, time, 'GT1'))

    # Merge the datasets
    seasoar = xr.concat(list_ds, dim='depth')

    # Put time and depth as dimensions
    list_ds = []
    times = np.unique(seasoar.time.data)
    depths = np.unique(seasoar.depth.data)
    for time in times:
        ds_time = seasoar.where(seasoar.time == np.datetime64(time), drop=True)
        ds_time = ds_time.assign_coords(time=xr.DataArray([time], dims='time'))
        ds_time = ds_time.assign_coords(lon=xr.DataArray([ds_time.lon.data[0]], dims='time'))
        ds_time = ds_time.assign_coords(lat=xr.DataArray([ds_time.lat.data[0]], dims='time'))
        ds_time = ds_time.drop_duplicates(dim='depth')
        ds_time = ds_time.interp(depth=depths, method='nearest')
        list_ds.append(ds_time)

    seasoar = xr.concat(list_ds, dim='time')
    seasoar = seasoar.xoa.decode()
    return seasoar


def open_decode_croco(path_file):
    """
    Open netcdf file from CROCO model.
    Parameters
    ----------
    path_file : list of str
        List of the file to decode.

    Returns
    -------
    croco : xarray.Dataset
         Model dataset decoded.
    """
    croco = xr.open_dataset(path_file)

    croco = croco.decode_sigma()

    # Remove variables that are never used in the features. May need to be completed.
    list_to_keep = ['temp', 'salt']
    for var in list(croco.keys()):
        if var not in list_to_keep:
            croco = croco.drop_vars(var)

    # Depth becomes a variable
    if 'depth' in croco:
        croco = croco.reset_coords('depth')

    # Rename coordinates
    croco = croco.rename_dims({'eta_rho': 'lat', 'xi_rho': 'lon', 's_rho': 'z'})
    croco = croco.drop_vars(['xi_rho', 'eta_rho'])

    if len(croco['lon']) == len(np.unique(croco.lon_rho.data)):
        longitude = np.unique(croco.lon_rho.data)
        latitude = np.unique(croco.lat_rho.data)
    elif len(croco['lon']) == len(np.unique(croco.lon_rho.data)) - 1:
        longitude = np.unique(croco.lon_rho.data)[:-1]
        latitude = np.unique(croco.lat_rho.data)[:-1]

    croco['lon'] = longitude
    croco['lat'] = latitude

    # Remove useless coordinates
    croco = croco.reset_coords(drop=True)

    # Set depth as coordinates
    if 'depth' in croco:
        croco = croco.assign_coords(depth=croco.depth)

    # Convert depths
    if 'depth' in croco:
        if croco.depth.min() < 0 and croco.depth.max() > 0:
            croco['depth'] = -croco.depth.where((croco.depth < 0) & (croco.depth > -1e5))
        croco = croco.where(~np.isnan(croco.depth))

    croco = convert_depths(croco)
    croco = convert_lons(croco)

    # Decode
    croco = croco.xoa.decode()

    return croco


def open_decode_croco_currents(path_files):
    """
    Open 2D or 3D current from CROCO model.
    Parameters
    ----------
    path_files : list of str
        List of the file to decode.

    Returns
    -------
    hycom : xarray.Dataset
         Model dataset decoded.
    """
    logger.info(f"Decode CROCO currents")
    ds = xr.open_dataset(path_files).decode_sigma()
    ds = xoa.grid.to_rect(ds)

    # Verify Croco
    if 's_rho' not in ds.dims:
        raise Exception('Attention, le fichier que vous essayez d\'ouvrir ne semble pas être du Croco....')

    # Retrieve grid
    ds = ds.rename_dims({'s_rho': 'z'})
    longitude = ds.lon_rho.where(ds.lon_rho < 1e30)
    latitude = ds.lat_rho.where(ds.lat_rho < 1e30)
    longitude = np.unique(longitude.data)[:-1]
    latitude = np.unique(latitude.data)[:-1]

    # Depth processing
    depth = ds.depth
    if depth.min() < 0 < depth.max():
        depth = -depth.where((depth < 0) & (depth > -1e5))
    depth = depth.rename({'eta_rho': 'lat', 'xi_rho': 'lon', 's_rho': 'z'})
    depth['lat'] = latitude
    depth['lon'] = longitude
    depth = depth.drop_vars(['lon_rho', 'lat_rho'])

    # U processing
    u = shift(ds.u, {"xi_u": "left"}).xoa.reloc(u=False)
    longitude_u = np.unique(u.lon.data)[:-2]
    latitude_u = np.unique(u.lat.data)[:-2]
    u = u.drop_vars(['lon', 'lat'])
    u = u.rename({'eta_rho': 'lat', 'xi': 'lon', 's_rho': 'z'})
    u['lon'] = longitude_u
    u['lat'] = latitude_u
    u = u.where(u < 1e30)
    u = u.interp(lon=longitude)

    # V processing
    v = shift(ds.v, {"eta_v": "left"}).xoa.reloc(v=False)
    longitude_v = np.unique(v.lon.data)[:-2]
    latitude_v = np.unique(v.lat.data)[:-2]
    v = v.drop_vars(['lon', 'lat'])
    v = v.rename({'eta': 'lat', 'xi_rho': 'lon', 's_rho': 'z'})
    v['lon'] = longitude_v
    v['lat'] = latitude_v
    v = v.where(v < 1e30)
    v = v.interp(lat=latitude)

    # Create output croco dataset
    croco = xr.Dataset()
    croco['u'] = u
    croco['v'] = v
    croco = croco.assign_coords(depth=depth)

    # Regrid if necessary
    croco = xoa.grid.to_rect(croco)

    return croco


def open_decode_hycom_currents(path_files):
    """
    Open 2D or 3D current from HYCOM model.
    Parameters
    ----------
    path_files : list of str
        List of the files to decode. The first path must refer to the h file, the following ones are the variables.

    Returns
    -------
    hycom : xarray.Dataset
         Model dataset decoded.
    """
    logger.info(f"Decoding HYCOM currents")
    if len(path_files) == 2:  # Test if 2D
        logger.info(f"HYCOM 2D")
        path_u, path_v = path_files[0], path_files[1]
        hycom = xr.Dataset()
    elif len(path_files) == 3:  # Test if 3D
        logger.info(f"HYCOM 3D")
        path_h, path_u, path_v = path_files[0], path_files[1], path_files[2]
        hycom = xr.open_dataset(path_h).xoa.decode().squeeze(drop=True)
        if 'level' not in hycom.variables:
            raise Exception('Ooops ! Pour lire une sortie de courant du modèle HYCOM,'
                            ' vous devez renseigner les fichiers dans l\'ordre suivant : h, u, v')
        hycom.coords["depth"] = dz2depth(hycom.level, centered=True)

    u = xr.open_dataset(path_u).xoa.decode().squeeze(drop=True)
    v = xr.open_dataset(path_v).xoa.decode().squeeze(drop=True)
    if 'u' not in u.variables or 'v' not in v.variables:
        raise Exception('Ooops ! Pour lire une sortie de courant du modèle HYCOM,'
                        ' vous devez renseigner les fichiers dans l\'ordre suivant : h, u, v.')
    u = u.u
    v = v.v

    ut_hycom = shift(u, {"x": "left", "y": "left"}).xoa.reloc(u=False)
    vt_hycom = shift(v, {"x": "left", "y": "left"}).xoa.reloc(v=False)
    hycom["u"] = ut_hycom.assign_coords(**hycom.coords)
    hycom["v"] = vt_hycom.assign_coords(**hycom.coords)
    if 'level' in hycom:
        hycom = hycom.drop_vars('level')

    # Regrid if necessary
    hycom = xoa.grid.to_rect(hycom)

    return hycom


def open_decode_hycom_3d(path_files):
    """
    Open some 3D variables from HYCOM model.
    Parameters
    ----------
    path_files : list of str
        List of the files to decode. The first path must refer to the h file, the following ones are the variables.

    Returns
    -------
    hycom : xarray.Dataset
         Model dataset decoded.

    """
    logger.info(f"Decoding HYCOM 3D")
    # Open the file with depth values
    path_h = path_files[0]
    hycom = xr.open_dataset(path_h).xoa.decode().squeeze(drop=True)
    if 'level' not in hycom.variables:
        raise Exception('Ooops ! Pour lire une sortie 3D du modèle HYCOM,'
                        ' vous devez renseigner les fichiers dans l\'ordre suivant :  h, variables.')

    hycom.coords["depth"] = dz2depth(hycom.level, centered=True)

    # Open the variable(s) and add them to the dataset
    for path in path_files[1:]:
        ds_var = xr.open_dataset(path).xoa.decode().squeeze(drop=True)
        # Get the name of the variable
        list_coords = ['lon', 'lat', 'bathymetry', 'time', 'lev']
        for var in list(ds_var.keys()):
            if var not in list_coords:
                var_name = var

        hycom[var_name] = ds_var[var_name]

    if list(hycom.depth.dims) == ['level']:
        depths = hycom.depth
        hycom = hycom.drop_vars('depth')
        hycom = hycom.rename({'level': 'depth'})
        hycom['depth'] = depths.data

    hycom = xoa.grid.to_rect(hycom)

    return hycom


def open_decode_cora(path_files):
    """
     Open CORA netcdf files and store it into a ready-to-use dataset.
     Parameters
     ----------
     path_files : str, list of str
         Path to the netcdf files.
     Returns
     -------
     xarray.Dataset
         WOA18 dataset.
     """
    # Open
    cora = xr.open_dataset(path_files)

    # Variables to drop/rename to prevent random behaviours
    for var in list(cora.keys()):
        if "POSITION" in var:
            cora = cora.drop_vars(var)
        elif var[-3:] == "_QC":
            cora = cora.rename({var: f"QC_{var[:-3]}"})
        if len(var) == 4:
            if f"{var}_ADJUSTED" in cora:
                cora = cora.drop_vars(f"{var}_ADJUSTED")
            if f"{var}_ADJUSTED_ERROR" in cora:
                cora = cora.drop_vars(f"{var}_ADJUSTED_ERROR")
    # Decode
    cora = cora.xoa.decode()

    # Rename time
    cora = cora.assign_coords({"N_prof": cora.time.values})
    cora = cora.drop_vars('time')
    cora = cora.rename({'N_prof': 'time'})

    # Convert depths
    cora = cora.rename({'N_levels': 'depth'})
    cora = depth_from_press(cora)

    return cora


def open_decode_basic(path_files):
    """
     Open netcdf file(s) and store it into a ready-to-use dataset.
     Parameters
     ----------
     path_files : str, list of str
         Path to the netcdf files.
     Returns
     -------
     xarray.Dataset
         dataset.
     """
    # Open
    if len(path_files) > 1:
        ds = xr.open_mfdataset(path_files)
    else:
        ds = xr.open_dataset(path_files[0])

    # Decode
    ds = ds.xoa.decode()
    if "lon_longitude" in ds:
        ds = ds.drop_vars(["lon_longitude", 'lat_latitude'])

    # Regrid if necessary
    ds = xoa.grid.to_rect(ds)

    # Convert depths
    ds = convert_depths(ds)

    return ds


def open_forecaster(path_files, model_type=None) -> xr.Dataset:
    if model_type == 'HYCOM_currents':
        logger.info("HYCOM_currents")
        return open_decode_hycom_currents(path_files)

    elif model_type == 'HYCOM_3D':
        logger.info("HYCOM_3D")
        return open_decode_hycom_3d(path_files)

    elif model_type == 'woa18':
        logger.info("woa18")
        data_set_temp = xr.open_mfdataset(path_files, decode_times=False)
        data_set_temp = data_set_temp.drop_vars('depth_bnds')
        return data_set_temp

    elif model_type == 'rivers':
        logger.info("rivers")
        data_set_list = []
        for path_list in path_files:
            data_set_list.append(xr.open_mfdataset(path_files[path_list]))
        return data_set_list

    elif model_type == 'atmfrc/cumul':
        logger.info("atmfrc - cumul")
        cumul_gribs = path_files
        dss_cumul = []
        for grib in cumul_gribs:
            dss_cumul.append(xr.open_dataset(grib, engine="cfgrib", backend_kwargs={"indexpath": ""}))

        ds_cumul = xr.combine_nested(dss_cumul, concat_dim="valid_time", combine_attrs="override")
        ds_cumul = ds_cumul.drop_vars(["time", "surface"])
        ds_cumul = ds_cumul.rename({"longitude": "lon", "latitude": "lat", "valid_time": "time"})
        ds_cumul = ds_cumul.sortby('time')
        return ds_cumul

    elif model_type == 'atmfrc/insta':
        logger.info("atmfrc - insta")
        insta_gribs = path_files
        dss_insta = []
        for grib in insta_gribs:
            dss = []
            for level in [0, 2, 10]:
                dss.append(xr.open_dataset(grib, engine="cfgrib", backend_kwargs={"indexpath": "",
                                                                                  "filter_by_keys": {"edition": 2,
                                                                                                     "level": level
                                                                                                     },
                                                                                  },
                                           drop_variables=["heightAboveGround", "meanSea", "surface", ], ))

            dss_insta.append(xr.merge(dss, combine_attrs="override"))

        ds_insta = xr.combine_nested(dss_insta, concat_dim="valid_time", combine_attrs="override")
        ds_insta = ds_insta.drop_vars(["step", "time"])
        ds_insta = ds_insta.rename({"longitude": "lon", "latitude": "lat", "valid_time": "time"})
        ds_insta = ds_insta.sortby('time')
        return ds_insta

    elif len(path_files) > 1:
        logger.info("multiple files from list")
        return xr.open_mfdataset(path_files)

    else:
        logger.info("single file")
        return xr.open_dataset(path_files[0])


####################### Tools #######################


def decode_profiler(profiler):
    """
    Decode profiler datasets
    Returns
    -------
    xarray.dataset
        Decoded dataset
    """
    colonnes = profiler.DEPH.values
    depth_values = np.empty(np.size(colonnes, 1))
    for i in range(np.size(colonnes, 1)):
        colonne_test = colonnes[:, i]
        colonne_test = colonne_test[~np.isnan(colonne_test)]
        depth_column = set(colonne_test)
        if len(depth_column) == 1:  # Tests if the depth values are all the same throughout time
            depth_values[i] = list(depth_column)[0]
    profiler = profiler.assign_coords({'depth': depth_values})
    profiler = convert_trajectory(profiler)
    return profiler


def convert_trajectory(profiler):
    """
    Convert trajectories (lon/lat depend on time).
    Returns
    -------
    xarray.dataset
        Decoded dataset.
    """
    da_lon = xr.DataArray(profiler.lon.values, coords=[profiler.time.values], dims="time")
    da_lat = xr.DataArray(profiler.lat.values, coords=[profiler.time.values], dims="time")
    profiler = profiler.drop_vars(['lon', 'lat'])
    profiler = profiler.assign_coords({'lon': da_lon})
    profiler = profiler.assign_coords({'lat': da_lat})
    return profiler


def array2ds(array_series, lon, lat, date, bot_depth, type):
    """
    Convert np.array from the reading of ADCP txt observation data into datarray 7.
    Parameters
    ----------
    array_series : np.array
        array from the txt file.
    lon : float
        longitude of the measure.
    lat : float
        latitude of the measure.
    date : np.datetime64
        time of the measure.
    bot_depth : float
        bottom depth of the measure.
    type : str
        type of ADCP data. can be 'mouillages', 'VMADCP' or 'LADCP'.

    Returns
    -------
    ds : xarray.dataset
        observation dataset.
    """
    logger.info("ADCP")
    # Define the columns to read and variable names for each type of observation
    if type == 'mouillages':
        long_names = ["Corrected Flow 2D S-N", "Corrected Flow 2D W-E", "Corrected Flow 2D Amplitude",
                      "Corrected Flow 2D Direction"]
        indexes = [2, 1, 3, 4, 0]  # indexes in array for U,V,mag,dir,depth
    elif type == 'VMADCP':
        long_names = ['V', 'U', 'Mag', "Dir"]
        indexes = [11, 12, 14, 15, 8]  # indexes in array for U,V,mag,dir,depth
    elif type == 'LADCP':
        long_names = ['ud', 'vd']
        indexes = [10, 11, 0, 0, 6]  # indexes in array for U,V,mag,dir,depth

    # Create the u & v data arrays
    depth = array_series[:, indexes[4]].astype(float)

    da_u = xr.DataArray(data=array_series[:, indexes[0]].astype(float), dims=["depth"],
                        coords=dict(depth=('depth', depth), time=date, bottom_depth=bot_depth),
                        attrs=dict(long_name=long_names[0], units="m/s", _FillValue=9999999.), )
    da_v = xr.DataArray(data=array_series[:, indexes[1]].astype(float), dims=["depth"],
                        coords=dict(depth=('depth', depth), time=date, bottom_depth=bot_depth),
                        attrs=dict(long_name="Corrected Flow 2D W-E", units="m/s", _FillValue=9999999.), )

    depth = xr.DataArray(data=depth, dims=["depth"], coords=dict(depth=('depth', depth)),
                         attrs=dict(long_name="Instrument depth", units="m", _FillValue=9999999), )
    # Create the dataset and add the data arrays
    ds = xr.Dataset()
    ds["lon"], ds["lat"], ds["depth"] = lon, lat, depth
    ds["V"], ds["U"] = da_u, da_v

    # If current magnitude and direction are included in the data, add them to the dataset
    if type != 'LADCP':
        da_mag = xr.DataArray(data=array_series[:, indexes[2]].astype(float), dims=["depth"],
                              coords=dict(depth=('depth', depth.data), time=date, bottom_depth=bot_depth),
                              attrs=dict(long_name="Corrected Flow 2D Amplitude", units="m/s", _FillValue=9999999.), )

        da_dir = xr.DataArray(data=array_series[:, indexes[3]].astype(float), dims=["depth"],
                              coords=dict(depth=('depth', depth.data), time=date, bottom_depth=bot_depth),
                              attrs=dict(long_name="Corrected Flow 2D Direction", units="deg T",
                                         _FillValue=9999999., ), )

        ds["Ampl"], ds["Dir"] = da_mag, da_dir

    return ds


def array2ds_radiales(array_series, lon, lat, date, type):
    # Define the columns to read and variable names for each type of observation
    if type == 'GT1':
        long_names = ['Temperature', 'Salinity', 'Density', 'depth']
        indexes = [6, 13, 14, 19]
        data_type = 'seasoar'
    elif type == 'radiale':
        long_names = ['Temperature', 'Salinity', 'Density', 'depth']
        indexes = [6, 8, 9, 11]
        data_type = 'scanfish'

    depth = array_series[:, indexes[3]].astype(float64)
    da_temp = xr.DataArray(data=array_series[:, indexes[0]].astype(float64), dims=["depth"],
                           coords=dict(depth=('depth', depth), time=date, lon=lon, lat=lat),
                           attrs=dict(long_name=long_names[0], units="deg C", _FillValue=9999999.), )
    da_sal = xr.DataArray(data=array_series[:, indexes[1]].astype(float64), dims=["depth"],
                          coords=dict(depth=('depth', depth), time=date, lon=lon, lat=lat),
                          attrs=dict(long_name=long_names[1], units="PSU", _FillValue=9999999.), )
    da_dens = xr.DataArray(data=array_series[:, indexes[2]].astype(float64), dims=["depth"],
                           coords=dict(depth=('depth', depth), time=date, lon=lon, lat=lat),
                           attrs=dict(long_name=long_names[2], units="kg/m^3", _FillValue=9999999.), )

    # Create the dataset and add the data arrays
    ds = xr.Dataset(attrs=dict(DATA_TYPE=data_type))
    ds["Temperature"], ds["Salinity"], ds["Density"] = da_temp, da_sal, da_dens
    return ds


def convert_lons(ds):
    """
    Convert latitudes in case they go 0 -> 360°
    Returns
    -------
    xarray.dataset
        Dataset with homogeneous longitudes
    """
    if np.nanmax(ds.lon.where(ds.lon < 1e+30).data) > 180:
        ds.assign_coords({"lon": (((ds.lon + 180) % 360) - 180)})
    return ds


def convert_depths(ds):
    """
    Convert depths to have positive values only.
    Returns
    -------
    xarray.dataset
        Dataset with positive depths.
    """
    if 'depth' in ds.variables:
        if np.nanmax(ds.depth.data) < 0:
            ds["depth"] = -ds.depth
    elif 'depth' in ds.dims:
        if np.nanmax(ds.depth.data) < 0:
            ds["depth"] = -ds.depth

    return ds


def depth_from_press(ds):
    """
    Calculate depth values from pressure.

    Returns
    -------
    xarray.Dataset
        Formatted dataset.

    """
    alat = ds.lat.broadcast_like(ds.pres)
    adepth = gsw.z_from_p(ds.pres, alat)
    adepth = adepth.where(adepth.notnull(), adepth.min())
    adepth.attrs.update({"long_name": "Depth", "units": "m"})
    ds = ds.rename({'depth': 'z'})
    adepth = adepth.rename({'depth': 'z'})
    ds = ds.assign_coords(depth=adepth)
    return ds
