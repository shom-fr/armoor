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
import pandas as pd
from xoa.grid import dz2depth, shift
import matplotlib.pyplot as plt
import xoa.geo as xgeo

import concurrent.futures
import dask

logger = logging.getLogger(__name__)


def open_decode(path_files, func=None, type=None, steps=None) -> xr.Dataset:
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
        logger.info("forecaster")
        return open_forecaster(path_files, type)

    else:
        if type == "WOA18":
            logger.info("Opening WOA18")
            return open_decode_woa18(path_files)
        elif type == "CMEMS":
            logger.info("Opening CMEMS")
            return open_decode_cmems(path_files, steps=steps)
        elif type == "scanfish":
            logger.info("Opening Scanfish")
            return open_decode_scanfish(path_files[0], steps=steps)
        elif type == "seasoar":
            logger.info("Opening Seasoar")
            return open_decode_seasoar(path_files[0], steps=steps)
        elif type == "LADCP":
            logger.info("Opening L-ADCP")
            return open_decode_l_adcp(path_files[0])
        elif type == "mouillage":
            logger.info("Opening Mooring")
            return open_decode_mouillages(path_files[0])
        elif type == "VMADCP":
            logger.info("Opening VMADCP")
            return open_decode_vmadcp(path_files[0], steps=steps)
        elif type in ['CROCO', 'CROCO_currents']:
            logger.info("Opening CROCO")
            return open_decode_croco(path_files[0])
        elif type == 'HYCOM_currents':
            logger.info("Opening HYCOM currents")
            return open_decode_hycom_currents(path_files)
        elif type == 'HYCOM_3D':
            logger.info("Opening HYCOM 3D currents")
            return open_decode_hycom_3d(path_files)
        elif type == 'CORA':
            logger.info("Opening CORA")
            return open_decode_cora(path_files[0])
        else:
            logger.info("Opening non specific file type")
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

    # Convert lons
    woa18 = convert_lons(woa18)

    # Convert long names
    for var in list(woa18.keys()):
        if var == 'sal':
            woa18['sal'] = woa18['sal'].assign_attrs({'long_name': "Average salinity"})
        if var == 'temp':
            woa18['temp'] = woa18['temp'].assign_attrs({'long_name': "Average  sea temperature"})

    return woa18


def open_decode_cmems(path_files, steps):
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
            lon_ds = ds.LONGITUDE.assign_coords(LONGITUDE=ds.TIME.data).rename(
                {'LONGITUDE': 'TIME'})
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
            if f"{var}_CNDC" in cmems:
                cmems = cmems.drop_vars(f"{var}_CNDC")

    # Decode
    cmems = cmems.xoa.decode()

    # Manage lon(time) and lat(time)
    len_lon = len(cmems.lon)
    len_lat = len(cmems.lat)
    len_time = len(cmems.time)
    if len_lat == len_time and len_lon == len_time:
        cmems = convert_trajectory(cmems)

    # Manage profiler depths
    if 'DEPH' in cmems.variables:
        cmems = decode_profiler(cmems)

    # Calculate depth from pressure
    if 'depth' in cmems.dims and 'depth' not in cmems.coords and 'pres' in cmems:
        cmems = depth_from_press(cmems)

    # Convert depth
    cmems = convert_depths(cmems)
    # Convert lons
    cmems = convert_lons(cmems)

    # Remove duplicate time and depth values
    cmems = cmems.drop_duplicates('time')
    if 'depth' in cmems.dims:
        cmems = cmems.drop_duplicates('depth')

    # Remove useless variables
    list_to_remove = ['DC_REFERENCE', 'DEPH', 'QC_DEPH']
    for var in list(cmems.keys()):
        if var in list_to_remove:
            cmems = cmems.drop(var)

    if steps[1]:
        horizontal_step, vertical_step = steps
        cmems = set_hor_vert_step(cmems, horizontal_step, vertical_step)

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
        array_same_size = np.lib.pad(array_series, ((0, size_max - len(array_series)), (0, 0)),
                                     'constant', constant_values='NaN')
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

    # Convert lons
    ladcp = convert_lons(ladcp)

    return ladcp


def open_decode_vmadcp(path_file, steps=None) -> xr.Dataset:
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

    # Convert lons
    vmadcp = convert_lons(vmadcp)

    if steps[1]:
        horizontal_step, vertical_step = steps
        vmadcp = set_hor_vert_step(vmadcp, horizontal_step, vertical_step)

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
    lines = lines[1:]

    # Get the line indexes of the start of each new measurement, set fill values
    first_column = np.array([line[0] for line in lines], dtype=object)
    first_column[first_column == ''] = '9999999'
    first_column = first_column.astype(float)
    index_mesures = np.where(first_column != 9999999.)[0]
    np.append(index_mesures, len(lines))
    nb_dates = len(index_mesures)

    # Separate the measurements
    list_ds = []
    for i in range(nb_dates - 1):
        # Get measurements coordinates
        i_line_deb = index_mesures[i]
        date = np.datetime64(lines[i_line_deb][3], "ns")
        lon = float(lines[i_line_deb][4])
        lat = float(lines[i_line_deb][5])
        bottom_depth = float(lines[i_line_deb][6])

        # Subset the numpy array selecting only the specific measurements
        array_series_0 = lines[index_mesures[i]:index_mesures[i + 1]]
        array_series_1 = []
        for line in array_series_0[1:]:
            line_edit = line[:-1] if line[-1] == "" else line
            line_edit = np.array(line_edit[7:], dtype=object)
            line_edit[line_edit == ''] = '999999.'
            line_edit = line_edit.astype(float)
            array_series_1.append(line_edit)
        array_series = np.array(array_series_1)

        # Convert the array into xr.dataset and add it to the list of measurements
        list_ds.append(array2ds(array_series, lon, lat, date, bottom_depth, 'mouillages'))

    # Merge the datasets
    mouillage = xr.concat(list_ds, dim='time')

    # Decode
    mouillage = mouillage.xoa.decode()

    # Convert lons
    mouillage = convert_lons(mouillage)
    return mouillage


def open_decode_scanfish(path_file, steps):
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
    file = pd.read_csv(path_file, sep='\t')
    lons, lats, depth = file["Longitude"], file["Latitude"], file['DepSM']
    time = (file["TimeJ"] * 24 * 3600 * np.timedelta64(1, 's')) + np.datetime64('1970-01-01') + \
           file["TimeY"] * np.timedelta64(1, 's')

    # Create the dataset
    file = file.assign(time=time, depth=depth, temp=file['T4990C'], sal=file['Sal00'])
    file = file.set_index("time")
    scanfish = file.to_xarray()

    # Decode
    scanfish = scanfish.xoa.decode()

    # Convert lons
    scanfish = convert_lons(scanfish)

    # Add attrs
    scanfish = scanfish.assign_attrs({"type": 'scanfish'})

    # Regrid
    horizontal_step, vertical_step = steps
    scanfish = set_hor_vert_step_radiales(scanfish, horizontal_step, vertical_step)
    return scanfish


def open_decode_seasoar(path_file, steps):
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
    file = pd.read_csv(path_file, sep='\t')
    lons, lats, depth = file["Longitude"], file["Latitude"], file['DepSM']
    time = (file["TimeJ"] * 24 * 3600 * np.timedelta64(1, 's')) + np.datetime64('2000-01-01') + \
           file["TimeQ"] * np.timedelta64(1, 's')

    # Create the dataset
    file = file.assign(time=time, depth=depth, temp=file['T190C'], sal=file['Sal11'])
    file = file.set_index("time")
    seasoar = file.to_xarray()

    # Decode
    seasoar = seasoar.xoa.decode()

    # Convert lons
    seasoar = convert_lons(seasoar)

    # Add attrs
    seasoar = seasoar.assign_attrs({"type": 'seasoar'})

    # Regrid
    horizontal_step, vertical_step = steps
    seasoar = set_hor_vert_step_radiales(seasoar, horizontal_step, vertical_step)
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
    croco = xr.open_dataset(path_file).decode_sigma()

    # Remove variables that are never used in the features. May need to be completed.
    list_to_keep = ['temp', 'salt', 'u', 'v', 'h']
    for var in list(croco.keys()):
        if var not in list_to_keep:
            croco = croco.drop_vars(var)

    # Convert currents if necessary
    if 'u' in croco:
        # U processing
        u = shift(croco.u, {"xi_u": "left"}).xoa.reloc(u=False)
        u = u.sel(xi=croco.xi_rho, method='nearest')
        croco['u'] = u

        # V processing
        v = shift(croco.v, {"eta_v": "left"}).xoa.reloc(v=False)
        v = v.sel(eta=croco.eta_rho, method='nearest')
        croco['v'] = v

    # Remove duplicate coords
    if 'lon' in croco and 'lon_rho' in croco:
        croco = croco.drop(['lon', 'lat'])

    # Clean coordinates
    croco = croco.rename(
        {'xi_rho': 'x', 'eta_rho': 'y', 's_rho': 'z', 'lon_rho': 'lon', 'lat_rho': 'lat'})
    for var in ['lat_rho', 'lon_rho', 'xi', 'eta', 'lat_u', 'lat_v', 'lon_u', 'lon_v', 'xi_u',
                'eta_v', 'depth_w', 'sig', 's_w']:
        if var in croco:
            croco = croco.drop(var)

    # Regrid if necessary
    croco = xoa.grid.to_rect(croco)

    # Convert lons
    croco = convert_lons(croco)

    # Convert depths
    croco['depth'] = croco.depth.where(abs(croco.depth) < 1e30)
    croco = convert_depths(croco)

    # Decode
    croco = croco.xoa.decode()
    if 'lon_u' in croco:
        croco = croco.rename({'lon_u': 'lon'})
    if 'lat_u' in croco:
        croco = croco.rename({'lat_u': 'lat'})

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
    logger.info("Decoding HYCOM currents")
    if len(path_files) == 2:  # Test if 2D
        logger.info("HYCOM 2D")
        path_u, path_v = path_files[0], path_files[1]
        hycom = xr.Dataset()
    elif len(path_files) == 3:  # Test if 3D
        logger.info("HYCOM 3D")
        path_h, path_u, path_v = path_files[0], path_files[1], path_files[2]
        hycom = xr.open_dataset(path_h).rename({'h': 'dz'}).xoa.decode().squeeze(drop=True)
        if 'level' not in hycom.variables:
            raise Exception('Ooops ! Pour lire une sortie de courant du modèle HYCOM,'
                            ' vous devez renseigner les fichiers dans l\'ordre suivant : h, u, v')
        hycom.coords["depth"] = dz2depth(hycom.dz, centered=True)

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

    # Rename depth
    if 'level' in hycom:
        hycom = hycom.rename({'level': 'z'})

    # Regrid if necessary
    hycom = xoa.grid.to_rect(hycom)

    # Convert lons
    hycom = convert_lons(hycom)
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
    logger.info("Decoding HYCOM 3D")
    # Open the file with depth values
    path_h = path_files[0]
    hycom = xr.open_dataset(path_h).rename({'h': 'dz'}).xoa.decode().squeeze(drop=True)
    if 'level' not in hycom.variables:
        raise Exception('Ooops ! Pour lire une sortie 3D du modèle HYCOM,'
                        ' vous devez renseigner les fichiers dans l\'ordre suivant :  h, variables.')

    hycom.coords["depth"] = dz2depth(hycom.dz, centered=True)

    # Open the variable(s) and add them to the dataset
    for path in path_files[1:]:
        ds_var = xr.open_dataset(path).xoa.decode().squeeze(drop=True)
        # Get the name of the variable
        list_coords = ['lon', 'lat', 'bathymetry', 'time', 'lev']
        for var in list(ds_var.keys()):
            if var not in list_coords:
                var_name = var
        hycom[var_name] = ds_var[var_name]

    # Rename
    hycom = hycom.rename({'level': 'z'})

    # Regrid if necessary
    hycom = xoa.grid.to_rect(hycom)

    # Convert lons
    hycom = convert_lons(hycom)
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
         CORA dataset.
     """
    # Open
    cora = xr.open_dataset(path_files)
    cora = cora.drop_dims(['N_HISTORY', 'N_CALIB', 'N_PARAM'])
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

    for var in list(cora.keys()):
        if 'N_PROF' not in list(cora[var].dims) and 'N_LEVELS' not in list(cora[var].dims):
            cora = cora.drop_vars(var)

    # Decode
    cora = cora.xoa.decode()

    # Rename time
    cora = cora.assign_coords({"N_prof": cora.time.values})
    cora = cora.drop_vars('time')
    cora = cora.rename({'N_prof': 'time'})

    # Convert depths
    cora = cora.rename({'N_levels': 'depth'})
    cora = depth_from_press(cora)
    cora = convert_depths(cora)

    # Convert lons
    cora = convert_lons(cora)

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

    list_to_remove = ['sst_dtime']
    for var in list(ds.keys()):
        if var in list_to_remove:
            ds = ds.drop(var)

    # Decode
    ds = ds.xoa.decode()
    if "lon_longitude" in ds:
        ds = ds.drop_vars(["lon_longitude", 'lat_latitude'])

    # Regrid if necessary
    ds = xoa.grid.to_rect(ds)

    # Convert depths
    ds = convert_depths(ds)

    # Convert lons
    ds = convert_lons(ds)

    # Remove duplicate values
    if 'lon' in ds.dims:
        ds = ds.drop_duplicates(['lon'])
    if 'lat' in ds.dims:
        ds = ds.drop_duplicates(['lat'])
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

        def open_dataset(grib):
            return xr.open_dataset(grib, engine="cfgrib", backend_kwargs={"indexpath": ""})

        # Use parallel processing to load datasets
        with concurrent.futures.ThreadPoolExecutor() as executor:
            dss_cumul = list(executor.map(open_dataset, cumul_gribs))

        # Use Dask to parallelize and concatenate the datasets
        dask_dss_cumul = [dask.delayed(ds.drop_vars(["time", "surface"])
                                       .rename({"longitude": "lon", "latitude": "lat", "valid_time": "time"}))
                          for ds in dss_cumul]

        # Compute the concatenated result using Dask
        ds_cumul = xr.concat(dask.compute(*dask_dss_cumul), dim="time")

        # Sort the result
        ds_cumul = ds_cumul.sortby('time')
        return ds_cumul

    elif model_type == 'atmfrc/insta':
        logger.info("atmfrc - insta")
        insta_gribs = path_files

        def open_dataset_for_level(grib, level):
            return xr.open_dataset(
                grib,
                engine="cfgrib",
                backend_kwargs={
                    "indexpath": "",
                    "filter_by_keys": {
                        "edition": 2,
                        "level": level
                    }
                },
                drop_variables=["heightAboveGround", "meanSea", "surface"]
            )

        # Use parallel processing to load datasets
        dss_insta = []
        for grib in insta_gribs:
            dss = [dask.delayed(open_dataset_for_level)(grib, level) for level in [0, 2, 10]]
            dss_insta.append(dask.compute(*dss))

        # Merge datasets for different levels
        merged_dss_insta = [xr.merge(ds_list, combine_attrs="override") for ds_list in dss_insta]

        # Combine merged datasets along 'valid_time' dimension
        ds_insta = xr.concat(merged_dss_insta, dim="valid_time")
        ds_insta = ds_insta.drop_vars(["step", "time"])
        ds_insta = ds_insta.rename({"longitude": "lon", "latitude": "lat", "valid_time": "time"})
        ds_insta = ds_insta.sortby('time')
        return ds_insta

    else:
        logger.info("Basic type")
        return open_forecaster_basic(path_files)


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
        else:  # if depth is truely depth(time,z)
            return decode_depths_vmadcp(profiler)
    profiler = profiler.assign_coords({'depth': depth_values})
    profiler = convert_trajectory(profiler)
    return profiler


def decode_depths_vmadcp(profiler):
    """
    Decode profiler datasets
    Returns
    -------
    xarray.dataset
        Decoded dataset
    """
    profiler = profiler.drop_duplicates('time')
    profiler = profiler.rename({'depth': 'z'})
    profiler = profiler.rename({'DEPH': 'depth'})
    profiler = profiler.assign_coords(depth=profiler.depth)
    plt.pcolormesh(profiler.depth)
    plt.savefig('depth.png')
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
    # Define the columns to read and variable names for each type of observation
    if type == 'mouillages':
        long_names = ["Corrected Flow 2D S-N", "Corrected Flow 2D W-E",
                      "Corrected Flow 2D Amplitude", "Corrected Flow 2D Direction"]
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
                        attrs=dict(long_name="Corrected Flow 2D W-E", units="m/s",
                                   _FillValue=9999999.), )

    depth = xr.DataArray(data=depth, dims=["depth"], coords=dict(depth=('depth', depth)),
                         attrs=dict(long_name="Instrument depth", units="m", _FillValue=9999999), )
    # Create the dataset and add the data arrays
    ds = xr.Dataset()
    ds["lon"], ds["lat"], ds["depth"] = lon, lat, depth
    ds["V"], ds["U"] = da_u, da_v

    # If current magnitude and direction are included in the data, add them to the dataset
    if type != 'LADCP':
        da_mag = xr.DataArray(data=array_series[:, indexes[2]].astype(float), dims=["depth"],
                              coords=dict(depth=('depth', depth.data), time=date,
                                          bottom_depth=bot_depth),
                              attrs=dict(long_name="Corrected Flow 2D Amplitude", units="m/s",
                                         _FillValue=9999999.), )

        da_dir = xr.DataArray(data=array_series[:, indexes[3]].astype(float), dims=["depth"],
                              coords=dict(depth=('depth', depth.data), time=date,
                                          bottom_depth=bot_depth),
                              attrs=dict(long_name="Corrected Flow 2D Direction", units="deg T",
                                         _FillValue=9999999., ), )

        ds["Ampl"], ds["Dir"] = da_mag, da_dir

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
        ds = ds.assign_coords({"lon": (((ds.lon + 180) % 360) - 180)})
    return ds


def convert_depths(ds):
    """
    Convert depths to have positive values only.
    Returns
    -------
    xarray.dataset
        Dataset with positive depths.
    """
    if 'depth' in ds:
        if np.nanmean(ds.depth.data) < 0:
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


def open_forecaster_basic(path_files):
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
        logger.info("multiple files from list")
        ds = xr.open_mfdataset(path_files)
    else:
        logger.info("single file")
        ds = xr.open_dataset(path_files[0])

    # Regrid if necessary
    ds = xoa.grid.to_rect(ds)

    # Convert depths
    ds = convert_depths(ds)

    # Convert lons
    ds = convert_lons(ds)

    return ds


def set_hor_vert_step_radiales(obs, horizontal_step, vertical_step):
    # Seasor/scanfish binning (method from SHOM Jupyter Notebook)
    lons = obs.lon
    lats = obs.lat
    depth = obs.depth
    time = obs.time

    # Define depth and time bins
    dist_deb_fin = xgeo.haversine(lons.values[0], lats.values[0], lons.values[-1],
                                  lats.values[-1]) / 1000
    depth_top_bottom = depth.max() - depth.min()

    n_time_bin = int(np.floor(dist_deb_fin / horizontal_step))
    n_depth_bin = int(np.floor(depth_top_bottom / vertical_step))

    i_time_bins = [int(np.floor(len(obs.time) / n_time_bin)) * i for i in range(n_time_bin)]
    i_depth_bins = np.linspace(0, np.ceil(depth.max() / n_depth_bin) * n_depth_bin, n_depth_bin + 1)

    depth_bins = i_depth_bins[:-1] + i_depth_bins[1] / 2
    mean_times, mean_lons, mean_lats = [], [], []
    temp = np.full((n_time_bin - 1, n_depth_bin), np.nan)
    sal = np.full((n_time_bin - 1, n_depth_bin), np.nan)

    # Binning
    for it in range(n_time_bin - 1):
        i0, i1 = i_time_bins[it:it + 2]
        temp[it] = np.histogram(depth[i0:i1], i_depth_bins, weights=obs['temp'][i0:i1])[0]
        sal[it] = np.histogram(depth[i0:i1], i_depth_bins, weights=obs['sal'][i0:i1])[0]
        denom = np.histogram(depth[i0:i1], i_depth_bins)[0]
        temp[it] = np.where(denom == 0, np.nan, temp[it] / denom)
        sal[it] = np.where(denom == 0, np.nan, sal[it] / denom)
        mean_times.append(time[i0:i1].mean().values)
        mean_lons.append(lons[i0:i1].mean())
        mean_lats.append(lats[i0:i1].mean())

    # Create xarray dataset
    da_temp = xr.DataArray(data=temp, dims=["time", "depth"])
    da_sal = xr.DataArray(data=sal, dims=["time", "depth"])
    obs_grid = xr.Dataset()
    obs_grid['temp'], obs_grid['sal'] = da_temp, da_sal
    obs_grid = obs_grid.assign_coords(
        {'lon': ('time', mean_lons), 'lat': ('time', mean_lats), 'depth': ('depth', depth_bins),
         'time': ('time', mean_times)
         })

    return obs_grid


def set_hor_vert_step(obs, horizontal_step, vertical_step, method='linear', method_z='linear'):
    # Horizontal gridding
    horizontal_step = obs.meta.km_to_deg(horizontal_step)

    obs_deb, obs_end = obs.isel(time=0), obs.isel(time=-1)
    total_distance_obs = np.sqrt(
        (obs_deb.lon - obs_end.lon) ** 2 + (obs_deb.lat - obs_end.lat) ** 2)
    total_duration_obs = obs_end.time - obs_deb.time

    time_step_grid = horizontal_step * total_duration_obs / total_distance_obs

    time_step_grid = time_step_grid.data.astype('timedelta64[s]')
    time_step_grid = str(time_step_grid).split()[0] + 'S'
    time_min, time_max = obs_deb.time.values, obs_end.time.values
    time_min, time_max = np.datetime64(time_min), np.datetime64(time_max)

    # Create the new times array to select to retrieve the horizontal resolution
    tgt_time = pd.date_range(time_min, time_max, freq=time_step_grid)

    # Interpolate the observation on the targeted times
    obs_grid = obs.interp(time=tgt_time, method=method)

    # Vertical gridding
    # Define the target vertical grid
    depths = np.arange(np.nanmin(obs.depth.values), np.nanmax(obs.depth.values), vertical_step)
    depths = [depth for depth in depths if depth > 0]
    if 'z' in obs.depth.dims:  # Case CMEMS data : depth(z,time)
        obs_grid = obs_grid.meta.vertical_selection_list(depths)
    else:
        obs_grid = obs_grid.interp(depth=depths, method=method_z)

    return obs_grid
