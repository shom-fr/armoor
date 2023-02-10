"""Open observation and model data"""
import xarray as xr
import numpy as np
import datetime
from xoa.grid import dz2depth, shift

import logging
logger = logging.getLogger(__name__)

def open_file(path_files, func=None, type=None) -> xr.Dataset:
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
    logger.info(f"Opening")

    if func == 'forecaster':
        logger.info(f"forecaster")
        return open_forecaster(path_files, type)

    elif isinstance(path_files, list) and type is None:
        if func == "clim_hydro":
            logger.info(f"clim_hydro")
            return xr.open_mfdataset(path_files, decode_times=False)
        else:
            logger.info(f"You are trying to open multiple files. If they corresponds to an "
                        f"HYCOM model, you should specify type='HYCOM_3D' or type='HYCOM_currents'"
                        f"in the configuration file.")
            return xr.open_mfdataset(path_files)

    elif type == 'HYCOM_currents':
        logger.info(f"HYCOM_currents")
        hycom_current = decode_hycom_currents(path_files)
        return hycom_current

    elif type == 'HYCOM_3D':
        logger.info(f"HYCOM_3D")
        hycom_3d = decode_hycom_3d(path_files)
        return hycom_3d

    elif type == 'CROCO_currents':
        logger.info(f"CROCO_currents")
        croco_current = decode_croco_currents(path_files)
        return croco_current

    elif path_files[-2:] == 'nc':
        logger.info(f"Single file dataset")
        return xr.open_dataset(path_files)

    elif type:
        if type == "mouillage":
            logger.info(f"mouillage")
            return open_mouillages(path_files)
        elif type == "LADCP":
            logger.info(f"LADCP")
            return open_L_ADCP(path_files)
        elif type == "VMADCP":
            logger.info(f"VMADCP")
            return open_VMADCP(path_files)


def decode_croco_currents(path_files):
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
    if depth.min() < 0 and depth.max() > 0:
        depth = -depth.where((depth < 0) & (depth > -1e5))
    depth = depth.rename({'eta_rho': 'lat', 'xi_rho': 'lon', 's_rho': 'z'})
    depth['lat'] = latitude
    depth['lon'] = longitude
    depth = depth.drop(['lon_rho', 'lat_rho'])

    # U processing
    u = shift(ds.u, {"xi_u": "left"}).xoa.reloc(u=False)
    longitude_u = np.unique(u.lon.data)[:-2]
    latitude_u = np.unique(u.lat.data)[:-2]
    u = u.drop(['lon', 'lat'])
    u = u.rename({'eta_rho': 'lat', 'xi': 'lon', 's_rho': 'z'})
    u['lon'] = longitude_u
    u['lat'] = latitude_u
    u = u.where(u < 1e30)
    u = u.interp(lon=longitude)

    # V processing
    v = shift(ds.v, {"eta_v": "left"}).xoa.reloc(v=False)
    longitude_v = np.unique(v.lon.data)[:-2]
    latitude_v = np.unique(v.lat.data)[:-2]
    v = v.drop(['lon', 'lat'])
    v = v.rename({'eta': 'lat', 'xi_rho': 'lon', 's_rho': 'z'})
    v['lon'] = longitude_v
    v['lat'] = latitude_v
    v = v.where(v < 1e30)
    v = v.interp(lat=latitude)

    # Create output croco dataset
    ds_croco = xr.Dataset()
    ds_croco['u'] = u
    ds_croco['v'] = v
    ds_croco = ds_croco.assign_coords(depth=depth)
    return ds_croco


def decode_hycom_currents(path_files):
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
        if 'dz' not in hycom.variables:
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
    if 'level' in hycom:
        hycom = hycom.drop('level')

    return hycom


def decode_hycom_3d(path_files):
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

    if 'dz' not in hycom.variables:
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
    return hycom


def open_forecaster(path_files, model_type=None) -> xr.Dataset:
    if model_type == 'HYCOM_currents':
        logger.info("HYCOM_currents")
        return decode_hycom_currents(path_files)

    elif model_type == 'HYCOM_3D':
        logger.info("HYCOM_3D")
        return decode_hycom_3d(path_files)

    elif model_type == 'woa18':
        logger.info("woa18")
        data_set_temp = xr.open_mfdataset(path_files, decode_times=False)
        data_set_temp = data_set_temp.drop('depth_bnds')
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
        ds_cumul = ds_cumul.drop(["time", "surface"])
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
        ds_insta = ds_insta.drop(["step", "time"])
        ds_insta = ds_insta.rename({"longitude": "lon", "latitude": "lat", "valid_time": "time"})
        ds_insta = ds_insta.sortby('time')
        return ds_insta

    elif isinstance(path_files, list):
        logger.info("multiple files from list")
        return xr.open_mfdataset(path_files)

    else:
        logger.info("single file")
        return xr.open_dataset(path_files)


def open_VMADCP(path: str) -> xr.Dataset:
    """
    Open txt file form VMADCP observation and store it in dataset.
    Parameters
    ----------
    path : str
        Path to the VMADCP txt file.

    Returns
    -------
    dataset : xarray.dataset
        VMADCP observation dataset.
    """
    logger.info("VMADCP")
    # Read the .txt file
    file = open(path, 'r', encoding="ISO-8859-1")
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
    ds = xr.concat(list_ds, dim='time')
    return ds


def open_L_ADCP(path: str):
    """
    Open txt file form L-ADCP observation and store it in dataset.
    Parameters
    ----------
    path : str
        Path to the L-ADCP txt file.

    Returns
    -------
    dataset : xarray.dataset
        L-ADCP observation dataset.
    """
    logger.info("L-ADCP")
    # Read the .txt file
    file = open(path, 'r', encoding="ISO-8859-1")
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
        array_same_size = np.lib.pad(array_series,
                                     ((0, size_max - len(array_series)), (0, 0)),
                                     'constant',
                                     constant_values=('NaN'))
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
    ds = xr.concat(list_ds, dim='time')
    return ds


def open_mouillages(path: str):
    """
    Open txt file form mooring observation and store it in dataset.
    Parameters
    ----------
    path : str
        Path to the mooring txt file.

    Returns
    -------
    dataset : xarray.dataset
        mooring observation dataset.
    """
    logger.info("mooring")
    # Read the .txt file
    file = open(path, 'r', encoding="ISO-8859-1")
    lines = file.readlines()
    n_line = len(lines)
    for i in range(n_line):
        lines[i] = lines[i].split('\t')
        lines[i][-1] = lines[i][-1].rstrip('\n')  # Remove header
    lines = np.array(lines[1:])

    # Get the line indexes of the start of each new measurement, set fill values
    first_column = np.array(lines)[:, 0]
    first_column[first_column == ''] = 9999999.
    first_column = first_column.astype(np.float)
    index_mesures = np.where(first_column != 9999999.)[0]
    np.append(index_mesures, len(lines))
    nb_dates = len(index_mesures)

    # Separate the measurements
    list_ds = []
    for i in range(nb_dates - 1):
        # Get measurements coordinates
        i_line_deb = index_mesures[i]
        cruise = int(lines[i_line_deb][0])
        station = lines[i_line_deb][1]
        date = np.datetime64(lines[i_line_deb][3])
        lon = float(lines[i_line_deb][4])
        lat = float(lines[i_line_deb][5])
        bottom_depth = float(lines[i_line_deb][6])

        # Subset the numpy array selecting only the specific measurements
        array_series = np.array(lines[index_mesures[i]:index_mesures[i + 1], 7:]).astype(np.float)
        # Convert the array into xr.dataset and add it to the list of measurements
        list_ds.append(array2ds(array_series, lon, lat, date, bottom_depth, 'mouillages'))

    # Merge the datasets
    ds = xr.concat(list_ds, dim='time')
    return ds


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
    depth = array_series[:, indexes[4]].astype(np.float)

    da_u = xr.DataArray(data=array_series[:, indexes[0]].astype(np.float), dims=["depth"],
                        coords=dict(depth=('depth', depth), time=date, bottom_depth=bot_depth),
                        attrs=dict(long_name=long_names[0], units="m/s", _FillValue=9999999.), )
    da_v = xr.DataArray(data=array_series[:, indexes[1]].astype(np.float), dims=["depth"],
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
        da_mag = xr.DataArray(data=array_series[:, indexes[2]].astype(np.float), dims=["depth"],
                              coords=dict(depth=('depth', depth.data), time=date, bottom_depth=bot_depth),
                              attrs=dict(long_name="Corrected Flow 2D Amplitude", units="m/s", _FillValue=9999999.), )

        da_dir = xr.DataArray(data=array_series[:, indexes[3]].astype(np.float), dims=["depth"],
                              coords=dict(depth=('depth', depth.data), time=date, bottom_depth=bot_depth),
                              attrs=dict(long_name="Corrected Flow 2D Direction", units="deg T",
                                         _FillValue=9999999., ), )

        ds["Ampl"], ds["Dir"] = da_mag, da_dir

    return ds
