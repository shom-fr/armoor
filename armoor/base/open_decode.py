"""XrReaderAccessor
"""
import os
import logging
import datetime
import concurrent.futures
import xarray as xr
import xoa
import xoa.cf as xcf
import xoa.geo as xgeo
from xoa.grid import dz2depth, shift, to_rect
import numpy as np
import gsw
import pandas as pd
import dask
from pyproj import Geod

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
     steps : float
        Horizontal and vertical steps.

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
        logger.info('using path : %s', path)
    except:
        logger.warning('cf.cfg file not found')
        directory = os.getcwd()
        logger.warning('using path : %s', directory)
    xcf.register_cf_specs(path)

    if not isinstance(path_files, (list, dict)):
        raise TypeError("Only list or dict are allowed : %s", path_files)

    # Open file
    if func == 'forecaster':
        logger.info("forecaster")
        return open_forecaster(path_files, type)

    if type == "WOA18":
        logger.info("Opening WOA18")
        return open_decode_woa18(path_files)
    if type == "CMEMS":
        logger.info("Opening CMEMS")
        return open_decode_cmems(path_files, steps=steps)
    if type == "scanfish":
        logger.info("Opening Scanfish")
        return open_decode_scanfish(path_files[0], steps=steps)
    if type == "seasoar":
        logger.info("Opening Seasoar")
        return open_decode_seasoar(path_files[0], steps=steps)
    if type == "LADCP":
        logger.info("Opening L-ADCP")
        return open_decode_l_adcp(path_files[0])
    if type == "mouillage":
        logger.info("Opening Mooring")
        return open_decode_mouillages(path_files[0])
    if type == "VMADCP":
        logger.info("Opening VMADCP")
        return open_decode_vmadcp(path_files[0], steps=steps)
    if type in ['CROCO', 'CROCO_currents']:
        logger.info("Opening CROCO")
        return open_decode_croco(path_files[0])
    if type == 'HYCOM_currents':
        logger.info("Opening HYCOM currents")
        return open_decode_hycom_currents(path_files)
    if type == 'HYCOM_3D':
        logger.info("Opening HYCOM 3D")
        return open_decode_hycom_3d(path_files)
    if type == 'CORA':
        logger.info("Opening CORA")
        return open_decode_cora(path_files[0])

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
     steps : float
        Horizontal and vertical steps
     Returns
     -------
     xarray.Dataset
         CMEMS dataset.
     """
    # Open
    if len(path_files) > 1:
        list_ds_cmems = []
        for path in path_files:
            dataset = xr.open_dataset(path)
            lon_ds = dataset.LONGITUDE.assign_coords(LONGITUDE=dataset.TIME.data).rename(
                {'LONGITUDE': 'TIME'})
            lat_ds = dataset.LATITUDE.assign_coords(LATITUDE=dataset.TIME.data).rename(
                {'LATITUDE': 'TIME'})
            dataset = dataset.drop_vars(['LONGITUDE', 'LATITUDE'])
            dataset['LATITUDE'] = lat_ds
            dataset['LONGITUDE'] = lon_ds
            list_ds_cmems.append(dataset)

        cmems = concat_cmems(list_ds_cmems)
    else:
        cmems = xr.open_dataset(path_files[0])

    # Variables to drop/rename to prevent random behaviours
    for var in list(cmems.keys()):
        if "POSITION" in var or 'LOCATION' in var or '_DM' in var:
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
        # Remove otherwise interp won't work
        if var in ['DATA_MODE', 'DIRECTION', 'VERTICAL_SAMPLING_SCHEME']:
            cmems = cmems.drop_vars(var)

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
    if "PRES" in cmems:
        cmems = cmems.rename({'PRES':'pres'})

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
            cmems = cmems.drop_vars(var)

    if steps and steps[1]:
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
    file = pd.read_csv(path_file, sep='\t', encoding='latin1')

    # List the index labels of the measurements
    idx_stations = np.unique(file['Station'])

    # Separate the measurements
    list_ds = []
    for idx in idx_stations:
        measur = file[file['Station'] == idx]
        head = measur.iloc[0]
        lat = head[' Latitude']
        lon = head[' Longitude']
        time = f"{head[' Mon/Day/Yr']} {head[' hh:mm']}"
        time = datetime.datetime.strptime(time, ' %m/%d/%Y %H:%M')
        time = np.datetime64(time)

        measur = measur[[' ud', ' vd', ' z']].astype(float).rename(
            columns={' ud': 'U', ' vd': 'V', ' z': 'depth'}).set_index('depth')

        measur_ds = measur.to_xarray()
        measur_ds = measur_ds.assign_coords(lon=lon, lat=lat, time=time)
        list_ds.append(measur_ds.reset_coords())

    # Concat the dataset
    ladcp = xr.concat(list_ds, dim='time')
    ladcp = ladcp.set_coords(['lon', 'lat'])

    # Add variables attributes
    ladcp['U'] = ladcp['U'].assign_attrs(
        {'long_name': "W-E current", 'units': "m/s", '_FillValue': 9999999.
         })
    ladcp['V'] = ladcp['V'].assign_attrs(
        {'long_name': "S-N current", 'units': "m/s", '_FillValue': 9999999.
         })

    ladcp['depth'] = ladcp['depth'].assign_attrs(
        {'long_name': "Instrument depth", 'units': "m", '_FillValue': 9999999.
         })

    # Decode
    ladcp = ladcp.xoa.decode()

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
    steps : float
        Horizontal and vertical steps
    Returns
    -------
    dataset : xarray.dataset
        VMADCP observation dataset.
    """
    # Read the .txt file
    file = pd.read_csv(path_file, sep='\t', encoding='latin1')

    # List the index labels of the measurements
    idx_stations = np.unique(file['Station'])

    # Separate the measurements
    list_ds = []
    for idx in idx_stations:
        measur = file[file['Station'] == idx]
        head = measur.iloc[0]
        lat = head['Latitude [degrees_north]']
        lon = head['Longitude [degrees_east]']
        time = f"{head['mon/day/yr']} {head['hh:mm:ss']}"
        time = datetime.datetime.strptime(time, '%m/%d/%Y %H:%M:%S')
        time = np.datetime64(time)

        measur = measur[['U [cm/s]', 'V [cm/s]', 'Depth [m]']].astype(float).rename(
            columns={'U [cm/s]': 'U', 'V [cm/s]': 'V', 'Depth [m]': 'depth'}).set_index('depth')
        measur_ds = measur.to_xarray()
        measur_ds = measur_ds.assign_coords(lon=lon, lat=lat, time=time)
        list_ds.append(measur_ds.reset_coords())

    # Concat the dataset
    vmadcp = xr.concat(list_ds, dim='time').set_coords(['lon', 'lat'])

    # Add variables attributes
    vmadcp['U'] = (vmadcp['U'] / 100).assign_attrs(
        {'long_name': "W-E current", 'units': "m/s", '_FillValue': 9999999.
         })
    vmadcp['V'] = (vmadcp['V'] / 100).assign_attrs(
        {'long_name': "S-N current", 'units': "m/s", '_FillValue': 9999999.
         })

    vmadcp['depth'] = vmadcp['depth'].assign_attrs(
        {'long_name': "Instrument depth", 'units': "m", '_FillValue': 9999999.
         })

    # Decode
    vmadcp = vmadcp.xoa.decode()

    # Convert lons
    vmadcp = convert_lons(vmadcp)

    if steps and steps[1]:
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
    # Read the .txt file
    file = pd.read_csv(path_file, sep='\t', encoding='latin1')

    # Rename the columns
    for col in file.columns.tolist():
        if 'BinDep' in col:
            file = file.rename(columns={col: 'depth'})
        elif 'S-N' in col:
            file = file.rename(columns={col: 'V'})
        elif 'W-E' in col:
            file = file.rename(columns={col: 'U'})
        elif 'Ampl' in col:
            file = file.rename(columns={col: 'Ampl'})
        elif 'Dir' in col:
            file = file.rename(columns={col: 'Dir'})

    # Get the line indexes of the start of each new measurement
    index_mesures = file[file['Cruise'].notna()].index

    # Separate the measurements
    list_ds = []
    for i in range(len(index_mesures) - 1):
        # Get coordinates
        line_deb = file.iloc[index_mesures[i]]
        lon = line_deb['Longitude [degrees_east]']
        lat = line_deb['Latitude [degrees_north]']
        date = line_deb['yyyy-mm-ddThh:mm:ss.sss']
        date = np.datetime64(date, "ns")
        bottom_depth = line_deb['Bot. Depth [m]']

        # Get measurements
        measur = file.iloc[index_mesures[i] + 1:index_mesures[i + 1]].set_index('depth')
        unwanted_prefixes = ['Cruise', 'Station', 'Type', 'yyyy', 'Lon', 'Lat', 'Bot', 'Unnamed']
        columns_to_drop = measur.columns[measur.columns.str.startswith(tuple(unwanted_prefixes))]
        measur_ds = measur.drop(columns=columns_to_drop).astype(float).to_xarray()
        measur_ds = measur_ds.expand_dims(lon=[lon], lat=[lat])
        measur_ds = measur_ds.assign_coords(time=date, bottom_depth=bottom_depth)
        list_ds.append(measur_ds.reset_coords())

    # Merge datasets
    mouillage = xr.concat(list_ds, dim='time').set_coords(['lon', 'lat'])

    # Set variables attributes
    mouillage['U'] = mouillage['U'].assign_attrs(
        {'long_name': "Corrected Flow 2D W-E", 'units': "m/s", '_FillValue': 9999999.
         })
    mouillage['V'] = mouillage['V'].assign_attrs(
        {'long_name': "Corrected Flow 2D S-N", 'units': "m/s", '_FillValue': 9999999.
         })
    mouillage['Ampl'] = mouillage['Ampl'].assign_attrs(
        {'long_name': "Corrected Flow 2D Amplitude", 'units': "m/s", '_FillValue': 9999999.
         })
    mouillage['Dir'] = mouillage['Dir'].assign_attrs(
        {'long_name': "Corrected Flow 2D Direction", 'units': "deg", '_FillValue': 9999999.
         })
    mouillage['depth'] = mouillage['depth'].assign_attrs(
        {'long_name': "Instrument depth", 'units': "m", '_FillValue': 9999999.
         })

    # Decode
    mouillage = mouillage.xoa.decode()

    # Convert lons
    mouillage = convert_lons(mouillage)
    if len(np.unique(mouillage.lon)) == 1 and len(np.unique(mouillage.lat)) == 1:
        lon = np.unique(mouillage.lon.data)
        lat = np.unique(mouillage.lat.data)
        mouillage = mouillage.drop(['lon', 'lat']).assign_coords({'lon': lon, 'lat': lat})
    return mouillage


def open_decode_scanfish(path_file, steps):
    """
    Open txt file form scanfish observation and store it in dataset.
    Parameters
    ----------
    path_file : str
        Path to the scanfish txt file.
    steps : float
        Horizontal and vertical steps.
    Returns
    -------
    dataset : xarray.dataset
        scanfish observation dataset.
    """
    # Read the .txt file
    file = pd.read_csv(path_file, sep='\t', encoding='latin1')
    depth = file['DepSM']
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
    if steps and steps[1]:
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
    steps : float
        Horizontal and vertical steps.
    Returns
    -------
    dataset : xarray.dataset
        seasoar observation dataset.
    """
    # Read the .txt file
    file = pd.read_csv(path_file, sep='\t', encoding='latin1')
    depth = file['DepSM']
    time = (file["TimeJ"] * 24 * 3600 * np.timedelta64(1, 's')) + np.datetime64('2000-01-01') + \
           file["TimeQ"] * np.timedelta64(1, 's')

    # Create the dataset
    file = file.assign(time=time, depth=depth, temp=file['T190C'], sal=file['Sal11'], ptemp=file['Potemp190C'])
    file = file.set_index("time")
    seasoar = file.to_xarray()

    # Decode
    seasoar = seasoar.xoa.decode()

    # Convert lons
    seasoar = convert_lons(seasoar)

    # Add attrs
    seasoar = seasoar.assign_attrs({"type": 'seasoar'})

    # Regrid
    if steps and steps[1]:
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
    list_to_keep = ['temp', 'salt', 'u', 'v', 'h', 'angle', 'mask_rho']
    for var in list(croco.keys()):
        if var not in list_to_keep:
            croco = croco.drop_vars(var)

    # Convert currents if necessary
    if 'u' in croco:
        # U processing
        da_u = shift(croco.u, {"xi_u": "left"}).xoa.reloc(u=False)
        da_u = da_u.sel(xi=croco.xi_rho, method='nearest')
        croco['u'] = da_u

        # V processing
        da_v = shift(croco.v, {"eta_v": "left"}).xoa.reloc(v=False)
        da_v = da_v.sel(eta=croco.eta_rho, method='nearest')
        croco['v'] = da_v

        # Rotate currents
        if 'angle' in croco:
            angle = croco['angle']
            da_u = croco['u'] * np.cos(angle) - croco['v'] * np.sin(angle)
            da_v = croco['v'] * np.cos(angle) + croco['u'] * np.sin(angle)
            croco = croco.drop(['u', 'v', 'angle'])
            croco['u'] = da_u
            croco['v'] = da_v

            # Remove duplicate coords
    if 'lon' in croco and 'lon_rho' in croco:
        croco = croco.drop_vars(['lon', 'lat'])

    # Clean coordinates
    croco = croco.rename({'xi_rho': 'x', 
                          'eta_rho': 'y', 
                          's_rho': 'z', 
                          'lon_rho': 'lon', 
                          'lat_rho': 'lat'})
    if 'mask_rho' in list(croco.keys()):
        croco = croco.rename({'mask_rho': 'mask'})

    for var in ['lat_rho', 'lon_rho', 'xi', 'eta', 'lat_u', 'lat_v', 'lon_u', 'lon_v', 'xi_u',
                'eta_v', 'depth_w', 'sig', 's_w']:
        if var in croco:
            croco = croco.drop_vars(var)

    # Regrid if necessary
    test_regrid = to_rect(croco)
    if 'lon' in test_regrid.dims and 'lat' in test_regrid.dims:
        croco = test_regrid
    elif 'x' in test_regrid.dims and 'y' in test_regrid.dims:
        croco = test_regrid

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

    # Assign croco attrs
    croco = croco.assign_attrs({'type': 'CROCO'})

    # Rename ptemp
    if 'temp' in croco:
        croco = croco.rename({'temp': 'ptemp'})
    # Remove values outside mask
    
    if 'mask' in list(croco.keys()):
        croco = croco.where(croco['mask'] > 0, drop=True)

    return croco


def open_decode_hycom_currents(path_files):
    """
    Open 2D or 3D current from HYCOM model.
    Parameters
    ----------
    path_files : list of str
        List of the files to decode. The first path must refer to the h file, the following ones
        are the variables.

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
            raise ValueError('Ooops ! Pour lire une sortie de courant du modèle HYCOM,'
                             ' vous devez renseigner les fichiers dans l\'ordre suivant : h, u, v')
        hycom.coords["depth"] = dz2depth(hycom.dz, centered=True)

    ds_u = xr.open_dataset(path_u).xoa.decode().squeeze(drop=True)
    ds_v = xr.open_dataset(path_v).xoa.decode().squeeze(drop=True)
    if 'u' not in ds_u.variables or 'v' not in ds_v.variables:
        raise ValueError('Ooops ! Pour lire une sortie de courant du modèle HYCOM,'
                         ' vous devez renseigner les fichiers dans l\'ordre suivant : h, u, v.')
    da_u = ds_u.u
    da_v = ds_v.v

    ut_hycom = shift(da_u, {"x": "right"}).xoa.reloc(u=False)
    vt_hycom = shift(da_v, {"y": "top"}).xoa.reloc(v=False)
    hycom["u"] = ut_hycom.assign_coords(**hycom.coords)
    hycom["v"] = vt_hycom.assign_coords(**hycom.coords)

    # Rename depth
    if 'level' in hycom:
        hycom = hycom.rename({'level': 'z'})

    # Regrid if necessary
    hycom = to_rect(hycom)

    # Convert lons
    hycom = convert_lons(hycom)

    return hycom


def open_decode_hycom_3d(path_files):
    """
    Open some 3D variables from HYCOM model.
    Parameters
    ----------
    path_files : list of str
        List of the files to decode. The first path must refer to the h file, the following ones
        are the variables.

    Returns
    -------
    hycom : xarray.Dataset
         Model dataset decoded.

    """
    logger.info("Decoding HYCOM 3D")
    # Open the file with depth values
    path_h = path_files[0]
    hycom = xr.open_dataset(path_h)

    if 'h' not in hycom.variables and 'sigma' not in hycom.variables:
        raise ValueError('Ooops ! To read a 3D output from the HYCOM model,'
                         ' you need to provide the files in the following order: '
                         'h/sigma, variables.')
    if 'h' in hycom:
        hycom = hycom.rename({'h': 'dz'}).xoa.decode().squeeze(drop=True)
        hycom.coords["depth"] = dz2depth(hycom.dz, centered=True)
    elif 'sigma' in hycom:
        hycom = hycom.rename({'sigma': 'dens'}).xoa.decode().squeeze(drop=True)

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
    if 'temp' in hycom:
        hycom = hycom.rename({'temp': 'ptemp'})

    # Regrid if necessary
    hycom = to_rect(hycom)

    # Convert lons
    hycom = convert_lons(hycom)

    # Add dens coordinate
    if 'dens' in hycom:
        hycom = hycom.assign_coords(dens=hycom.dens)

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
        if "POSITION" in var or 'LOCATION' in var:
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
        datasets = [xr.open_dataset(path) for path in path_files]
        dataset = xr.concat(datasets, dim='time')
    else:
        dataset = xr.open_dataset(path_files[0])

    list_to_remove = ['sst_dtime']
    for var in list(dataset.keys()):
        if var in list_to_remove:
            dataset = dataset.drop_vars(var)

    # Decode
    dataset = dataset.xoa.decode()
    if "lon_longitude" in dataset:
        dataset = dataset.drop_vars(["lon_longitude", 'lat_latitude'])

    if 'temp' in dataset and 'potential' in dataset.temp.attrs['standard_name']:
        dataset = dataset.rename({'temp': 'ptemp'})

    # Regrid if necessary
    dataset = to_rect(dataset)

    # Convert depths
    dataset = convert_depths(dataset)

    # Convert lons
    dataset = convert_lons(dataset)

    # Remove duplicate values
    if 'lon' in dataset.dims:
        dataset = dataset.drop_duplicates(['lon'])
    if 'lat' in dataset.dims:
        dataset = dataset.drop_duplicates(['lat'])
    if 'DEPTH' in dataset.dims and 'depth' in dataset.coords:
        dataset = dataset.swap_dims({'DEPTH': 'depth'})
    return dataset


def open_forecaster(path_files, model_type=None) -> xr.Dataset:
    """

    Parameters
    ----------
    path_files
    model_type

    Returns
    -------

    """
    if model_type == 'HYCOM_currents':
        logger.info("HYCOM_currents")
        return open_decode_hycom_currents(path_files)

    if model_type == 'HYCOM_3D':
        logger.info("HYCOM_3D")
        return open_decode_hycom_3d(path_files)

    if model_type == 'woa18':
        logger.info("woa18")
        data_set_temp = xr.open_mfdataset(path_files, decode_times=False)
        variables_to_drop = ['depth_bnds', 's_oa', 's_ma', 's_dd', 's_sd', 's_gp', 's_mn', 's_se',
                             't_oa', 't_ma', 't_dd', 't_sd', 't_gp', 't_mn', 't_se']
        for var in variables_to_drop:
            if var in data_set_temp:
                data_set_temp = data_set_temp.drop_vars(var)
        return data_set_temp

    if model_type == 'rivers':
        logger.info("rivers")
        data_set_list = []
        for path_list in path_files:
            data_set_list.append(xr.open_mfdataset(path_files[path_list],
                                                   drop_variables=["LATITUDE", "LONGITUDE",
                                                                   "POSITION_QC"]))
        return data_set_list

    if model_type == 'atmfrc/cumul':
        logger.info("atmfrc - cumul")
        cumul_gribs = path_files

        def open_dataset(grib):
            return xr.open_dataset(grib, engine="cfgrib", backend_kwargs={"indexpath": ""})

        # Use parallel processing to load datasets
        with concurrent.futures.ThreadPoolExecutor() as executor:
            dss_cumul = list(executor.map(open_dataset, cumul_gribs))

        # Use Dask to parallelize and concatenate the datasets
        dask_dss_cumul = [dask.delayed(ds.drop_vars(["time", "surface"]).rename(
            {"longitude": "lon", "latitude": "lat", "valid_time": "time"})) for ds in dss_cumul]

        # Compute the concatenated result using Dask
        ds_cumul = xr.concat(dask.compute(*dask_dss_cumul), dim="time")

        # Sort the result
        ds_cumul = ds_cumul.sortby('time')
        return ds_cumul.xoa.decode()

    if model_type == 'atmfrc/insta':
        logger.info("atmfrc - insta")
        insta_gribs = path_files

        def open_dataset_for_level(grib, level):
            return xr.open_dataset(grib, engine="cfgrib", backend_kwargs={"indexpath": "",
                                                                          "filter_by_keys": {
                                                                              "edition": 2,
                                                                              "level": level
                                                                              }
                                                                          },
                                   drop_variables=["heightAboveGround", "meanSea", "surface"])

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
        return ds_insta.xoa.decode()

    logger.info("Basic type")
    return open_decode_basic(path_files)


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


def convert_lons(dataset):
    """
    Convert latitudes in case they go 0 -> 360°
    Returns
    -------
    xarray.dataset
        Dataset with homogeneous longitudes
    """
    if np.nanmax(dataset.lon.where(dataset.lon < 1e+30).data) > 180:
        dataset = dataset.assign_coords({"lon": (((dataset.lon + 180) % 360) - 180)})
    return dataset


def convert_depths(dataset):
    """
    Convert depths to have positive values only.
    Returns
    -------
    xarray.dataset
        Dataset with positive depths.
    """
    if 'depth' in dataset:
        if np.nanmean(dataset.depth.data) < 0:
            dataset["depth"] = - dataset.depth
    return dataset


def depth_from_press(dataset):
    """
    Calculate depth values from pressure.

    Returns
    -------
    xarray.Dataset
        Formatted dataset.

    """
    alat = dataset.lat.broadcast_like(dataset.pres)
    adepth = gsw.z_from_p(dataset.pres, alat)
    adepth = adepth.where(adepth.notnull(), adepth.min())
    adepth.attrs.update({"long_name": "Depth", "units": "m"})
    dataset = dataset.rename({'depth': 'z'})
    adepth = adepth.rename({'depth': 'z'})
    dataset = dataset.assign_coords(depth=adepth)
    return dataset


def set_hor_vert_step_radiales(obs, horizontal_step, vertical_step):
    """
    Regrid the observation following the required vertical and horizontal grids for radiales.
    Parameters
    ----------
    obs : xarray.dataset
    horizontal_step : float
    vertical_step : float

    Returns
    -------
    Regridded observation.
    """
    # Seasor/scanfish binning (method from SHOM Jupyter Notebook)
    lons = obs.lon
    lats = obs.lat
    depth = obs.depth
    time = obs.time
    ptemp_in_obs = 'ptemp' in obs.attrs

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
    if ptemp_in_obs:
        ptemp = np.full((n_time_bin - 1, n_depth_bin), np.nan)
    sal = np.full((n_time_bin - 1, n_depth_bin), np.nan)

    # Binning
    for it in range(n_time_bin - 1):
        i_0, i_1 = i_time_bins[it:it + 2]
        temp[it] = np.histogram(depth[i_0:i_1], i_depth_bins, weights=obs['temp'][i_0:i_1])[0]
        if ptemp_in_obs:
            ptemp[it] = np.histogram(depth[i_0:i_1], i_depth_bins, weights=obs['ptemp'][i_0:i_1])[0]
        sal[it] = np.histogram(depth[i_0:i_1], i_depth_bins, weights=obs['sal'][i_0:i_1])[0]
        denom = np.histogram(depth[i_0:i_1], i_depth_bins)[0]
        temp[it] = np.where(denom == 0, np.nan, temp[it] / denom)
        if ptemp_in_obs:
            ptemp[it] = np.where(denom == 0, np.nan, ptemp[it] / denom)
        sal[it] = np.where(denom == 0, np.nan, sal[it] / denom)
        mean_times.append(time[i_0:i_1].mean().values)
        mean_lons.append(lons[i_0:i_1].mean())
        mean_lats.append(lats[i_0:i_1].mean())

    # Create xarray dataset
    da_temp = xr.DataArray(data=temp, dims=["time", "depth"])
    if ptemp_in_obs:
        da_ptemp = xr.DataArray(data=ptemp, dims=["time", "depth"])
    da_sal = xr.DataArray(data=sal, dims=["time", "depth"])
    obs_grid = xr.Dataset()
    if ptemp_in_obs:
        obs_grid['ptemp'] = da_ptemp
    obs_grid['temp'], obs_grid['sal']= da_temp, da_sal
    obs_grid = obs_grid.assign_coords(
        {'lon': ('time', mean_lons), 'lat': ('time', mean_lats), 'depth': ('depth', depth_bins),
         'time': ('time', mean_times)
         })

    return obs_grid


def set_hor_vert_step(obs, horizontal_step, vertical_step, method='linear', method_z='linear'):
    """
    Regrid the observation following the required vertical and horizontal grids.
    Parameters
    ----------
    obs : xarray.dataset
    horizontal_step : float
    vertical_step : float
    method : str
    method_z : str
    Returns
    -------
    Regridded observation.
    """
    # Horizontal gridding
    # horizontal_step = obs.meta.km_to_deg(horizontal_step)

    obs_deb, obs_end = obs.isel(time=0), obs.isel(time=-1)
    geod = Geod(ellps='WGS84')
    total_distance_obs = geod.line_length(obs.lon.data, obs.lat.data) / 1000
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
    # Warning if steps too large
    if len(obs_grid.depth) == 1:
        logger.warning(
            'Caution! The vertical_step requested is too large, the targetted grid has only one depth value. The code may fail.')

    if len(obs_grid.time) == 1:
        logger.warning(
            'Caution! The horizontal_step requested is too large, the targetted grid has only one time value. The code may fail.')
    return obs_grid


def concat_cmems(list_ds):
    times = np.unique([len(ds.TIME.data) for ds in list_ds])
    depths = np.unique([len(ds.DEPTH.data) for ds in list_ds])

    # Cas où on concat plusieurs fichiers d'1 instrument, même nombre de depth et time dans tous les fichiers
    if len(depths) == 1 and len(times) == 1:
        cmems = xr.concat(list_ds, dim='TIME')

    # Cas où on concat plusieurs instruments
    else:
        # Compute same DEPTH
        nb_depth_max = np.nanmax(depths)
        common_depths = list(range(nb_depth_max))

        # Compute same TIME
        common_times = [ds.TIME.data for ds in list_ds]
        common_times = np.unique(np.concatenate(common_times))

        for i_ds, ds in enumerate(list_ds):
            if 'POSITION' in ds.dims:
                ds = ds.drop_dims('POSITION')
            # Clean lon/lat
            lon, lat = ds.LONGITUDE, ds.LATITUDE

            # Put all datasets on the same depth
            depths_in_ds = ds.DEPTH.data
            ds = ds.assign_coords({'DEPTH': ds.DEPTH.data})
            ds = ds.sel(DEPTH=common_depths, method='nearest')
            ds = ds.assign_coords({'DEPTH': common_depths})
            ds = ds.drop(['LONGITUDE', 'LATITUDE'])
            ds = ds.where(ds.DEPTH.isin(depths_in_ds))
            ds = ds.assign_coords({'LONGITUDE': lon, 'LATITUDE': lat})
            # Put all TIMES on the same values
            times_in_ds = ds.TIME.data
            ds = ds.drop_duplicates('TIME')
            ds = ds.sel(TIME=common_times, method='nearest')
            ds = ds.assign_coords({'TIME': common_times})
            ds = ds.where(ds.TIME.isin(times_in_ds))

            list_ds[i_ds] = ds
        cmems = xr.concat(list_ds, dim='instr')
        cmems = cmems.drop_vars(names='DEPTH')

    return cmems
