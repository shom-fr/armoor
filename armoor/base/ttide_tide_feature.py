import logging
import os
import xarray as xr
import numpy as np
import ttide as tt

logger = logging.getLogger(__name__)


def run_harmonic_analysis_map(ds, output):
    # Definition of the period for the harmonic analysis
    if 'analysis_start' in output and 'analysis_end' in output:
        analysis_start = np.datetime64(output["analysis_start"])
        analysis_end = np.datetime64(output["analysis_end"])
        ds = ds.sel(time=slice(analysis_start, analysis_end))
    else:
        logger.info("Oops, to perform harmonic analysis, you should specify "
                    "the period over which to calculate the harmonic analysis. "
                    "The calculation will be done over the entire period of the input files.")

    # Get wave list
    if "tidal_waves" in output:
        list_waves = output["tidal_waves"].upper().split()
    else:
        raise ValueError("Oops, to perform harmonic analysis, you should specify the tidal "
                         "waves to calculate...")
    # Initialise vectors
    res_ua = np.empty([len(ds.lon), len(ds.lat), len(list_waves)])
    res_va = np.empty([len(ds.lon), len(ds.lat), len(list_waves)])
    res_ug = np.empty([len(ds.lon), len(ds.lat), len(list_waves)])
    res_vg = np.empty([len(ds.lon), len(ds.lat), len(list_waves)])
    for array in [res_ua, res_va, res_ug, res_vg]:
        array[:] = np.nan

    # Compute analysis for each lon lat
    for i_lon, lon in enumerate(ds.lon):
        for i_lat, lat in enumerate(ds.lat):
            ds_to_anal = ds.sel(lon=lon, lat=lat)
            if np.sum(np.isnan(ds_to_anal.u.data)) < np.sum(~np.isnan(ds_to_anal.u.data)):
                dt = (ds_to_anal.time[1] - ds_to_anal.time[0]).data.astype('timedelta64[h]').astype(
                    float)
                if dt == 0:
                    dt = (ds_to_anal.time[1] - ds_to_anal.time[0]).data.astype(
                        'timedelta64[m]').astype(float) / 60

                xout_u = tt.t_tide(ds_to_anal.squeeze().u.data, dt=dt, out_style=None)
                xout_v = tt.t_tide(ds_to_anal.squeeze().v.data, dt=dt, out_style=None)

                wave_names = np.array(xout_u['nameu']).astype(str)
                wave_names = np.char.strip(wave_names)

                for i_wave, wave in enumerate(list_waves):
                    if wave in wave_names:
                        idx_wave = int(np.where(wave_names == wave)[0])

                        res_ua[i_lon, i_lat, i_wave] = (xout_u['tidecon'][idx_wave][0])
                        res_va[i_lon, i_lat, i_wave] = (xout_v['tidecon'][idx_wave][0])
                        res_ug[i_lon, i_lat, i_wave] = (xout_u['tidecon'][idx_wave][2])
                        res_vg[i_lon, i_lat, i_wave] = (xout_v['tidecon'][idx_wave][2])

    ds_res = xr.Dataset(
        dict(u_a=(['lon', 'lat', 'wave'], res_ua), v_a=(['lon', 'lat', 'wave'], res_va),
             u_g=(['lon', 'lat', 'wave'], res_ug), v_g=(['lon', 'lat', 'wave'], res_vg)))
    ds_res = ds_res.assign_coords({'lon': ds.lon.data, 'lat': ds.lat.data, 'wave': list_waves})

    # Filter values
    ds_res = ds_res.where(ds_res.u_a < 10000)
    ds_res = ds_res.where(ds_res.v_a < 10000)

    # Remove waves where the harmonic analyses could not be computed
    ds_res = ds_res.where(~ds_res.isnull())
    ds_res = ds_res.dropna('wave', how='all')

    # Print waves that have not been computed
    waves = [wave for wave in list_waves if wave not in ds_res.wave.data]
    if len(waves) > 0:
        logger.warning(
            f'Tidal wave(s) {waves} could not be retrieved from the harmonic analysis in {ds.attrs["name"]}. '
            f'Try with a longer time series.')

    # Add attributes
    ds_res = ds_res.assign_attrs({'name': ds.attrs['name']})
    time_min = np.datetime_as_string(ds_to_anal.time.min(skipna=True).values, unit='s')
    time_max = np.datetime_as_string(ds_to_anal.time.max(skipna=True).values, unit='s')
    title_time = f'{time_min} to {time_max}'
    ds_res = ds_res.assign_attrs({'analysis_period': title_time})

    return ds_res


def run_harmonic_analysis(ds, output):
    # Definition of the period for the harmonic analysis
    if 'analysis_start' in output and 'analysis_end' in output:
        analysis_start = np.datetime64(output["analysis_start"])
        analysis_end = np.datetime64(output["analysis_end"])
        ds = ds.sel(time=slice(analysis_start, analysis_end))
    else:
        logger.info("Oops, to perform harmonic analysis, you should specify "
                    "the period over which to calculate the harmonic analysis. "
                    "The calculation will be done over the entire period of the input files.")

    # Get wave list
    if "tidal_waves" in output:
        list_waves = output["tidal_waves"].upper().split()
    else:
        raise ValueError("Oops, to perform harmonic analysis, you should specify the tidal "
                         "waves to calculate...")
    if 'lon' in ds.dims and len(ds.lon) > 1:
        for i_lon, lon in enumerate(ds.lon.data):
            ds_to_anal = ds.isel(lon=i_lon, lat=i_lon)
            ds_res = harmonic_analysis_depth_slice(ds_to_anal, list_waves)
    else:
        ds_res = harmonic_analysis_depth_slice(ds, list_waves)

    # Assign attributes
    ds_res = ds_res.assign_attrs({'name': ds.attrs['name']})

    # Remove waves where the harmonic analyses could not be computed
    ds_res = ds_res.where(~ds_res.isnull())
    ds_res = ds_res.dropna('wave', how='all')

    # Print waves that have not been computed
    waves = [wave for wave in list_waves if wave not in ds_res.wave.data]
    if len(waves) > 0:
        logger.warning(
            f'Tidal wave(s) {waves} could not be retrieved from the harmonic analysis in '
            f'{ds_res.attrs["name"]}. '
            f'Try with a longer time series.')

    return ds_res


def harmonic_analysis_depth_slice(ds, list_waves):
    if "depth" in ds.dims:
        ds_res = []
        for i_depth, depth in enumerate(ds.depth):
            ds_to_anal = ds.isel(depth=i_depth).squeeze()
            res = harmonic_analysis(ds_to_anal, list_waves)
            if res:
                ds_res.append(res.assign_coords({"depth": depth}))
        ds_res = xr.concat(ds_res, dim='depth')
    elif "slice" in ds.dims:
        # If metazone per slice, calculate average per slice
        if len(ds['idx_depth'].values) > 1:
            ds = ds.mean('idx_depth')

        ds_res = []
        for i_slice, slice in enumerate(ds.slice):
            ds_to_anal = ds.isel(slice=i_slice).squeeze()
            res = harmonic_analysis(ds_to_anal, list_waves)
            if res:
                ds_res.append(res.assign_coords({"slice": slice}))
        ds_res = xr.concat(ds_res, dim='slice')
    else:
        ds_res = harmonic_analysis(ds, list_waves)

    if np.size(ds_res.freq.data) > len(list_waves):
        freq = ds_res.freq.data[0]
        ds_res['freq'] = ('wave', freq)

    return ds_res


def harmonic_analysis(ds_to_anal, list_waves):
    # Calculate time step
    dt = (ds_to_anal.time[1] - ds_to_anal.time[0]).data.astype('timedelta64[h]').astype(float)
    if dt == 0:
        dt = (ds_to_anal.time[1] - ds_to_anal.time[0]).data.astype('timedelta64[m]').astype(
            float) / 60

    # Initialize results
    a_u = []
    a_v = []
    g_u = []
    g_v = []
    freq = []

    time_min = np.datetime_as_string(ds_to_anal.time.min(skipna=True).values, unit='s')
    time_max = np.datetime_as_string(ds_to_anal.time.max(skipna=True).values, unit='s')
    title_time = f'{time_min} to {time_max}'

    if np.sum(np.isnan(ds_to_anal.u.data)) < np.sum(~np.isnan(ds_to_anal.u.data)):
        xout_u = tt.t_tide(ds_to_anal.squeeze().u.data, dt=dt, out_style=None)
        xout_v = tt.t_tide(ds_to_anal.squeeze().v.data, dt=dt, out_style=None)

        wave_names = np.array(xout_u['nameu']).astype(str)
        wave_names = np.char.strip(wave_names)
        for wave in list_waves:
            if wave in wave_names:
                idx_wave = int(np.where(wave_names == wave)[0])
                a_u.append(xout_u['tidecon'][idx_wave][0])
                g_u.append(xout_u['tidecon'][idx_wave][2])
                a_v.append(xout_v['tidecon'][idx_wave][0])
                g_v.append(xout_v['tidecon'][idx_wave][2])
                freq.append(xout_u['fu'][idx_wave])
            else:
                a_u.append(np.nan)
                g_u.append(np.nan)
                a_v.append(np.nan)
                g_v.append(np.nan)
                freq.append(np.nan)
        ds_res = xr.Dataset(
            data_vars=dict(u_a=(["wave"], a_u), u_g=(["wave"], g_u), v_a=(["wave"], a_v),
                           v_g=(["wave"], g_v), freq=(["wave"], freq)),
            coords=dict(wave=(["wave"], list_waves)), attrs=dict(analysis_period=title_time))
        ds_res['lat'] = ds_to_anal.lat.data
        ds_res['lon'] = ds_to_anal.lon.data

    else:
        empty = [np.nan for i in list_waves]
        ds_res = xr.Dataset(
            data_vars=dict(u_a=(["wave"], empty), u_g=(["wave"], empty), v_a=(["wave"], empty),
                           v_g=(["wave"], empty), freq=(["wave"], empty)),
            coords=dict(wave=(["wave"], list_waves)), attrs=dict(analysis_period=title_time))
    return ds_res
