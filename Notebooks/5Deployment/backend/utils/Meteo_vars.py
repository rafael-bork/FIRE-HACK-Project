import numpy as np
import pandas as pd
import xarray as xr
from scipy.interpolate import griddata
from metpy.units import units
from metpy.calc import saturation_vapor_pressure, vapor_pressure, wind_speed
from contextlib import nullcontext

def safe_open(path):
    return xr.open_dataset(path, engine="netcdf4") if path else nullcontext(None)

def prepare_datasets(sl_file, pl_file, fwi_file, land_file, target_res=0.1):
    """
    Prepare ERA5 Single Levels, Pressure Levels, FWI and ERA5-Land datasets.

    Parameters:
    -----------
    sl_file : str
        Path to ERA5 Single Levels NetCDF file.
    pl_file : str
        Path to ERA5 Pressure Levels NetCDF file.
    fwi_file : str
        Path to Fire Weather Index NetCDF file.
    land_file : str
        Path to ERA5-Land NetCDF file.
    target_res : float
        Target grid resolution in degrees (default: 0.1°).

    Returns:
    --------
    ds_SL : xarray.Dataset
    ds_PL : xarray.Dataset
    ds_FWI : xarray.Dataset
    ds_Land : xarray.Dataset
    """

    # ==================== LOAD DATASETS ====================
    print("Loading datasets...")
    with safe_open(sl_file) as ds_SL, \
        safe_open(pl_file) as ds_PL, \
        safe_open(fwi_file) as ds_FWI, \
        safe_open(land_file) as ds_Land:

        # ==================== RENAME VARIABLES ====================
        ds_SL = ds_SL.rename({"u100": "u100_ms", "v100": "v100_ms"})
        # ds_PL = ds_PL.rename({"u": "u_ms", "v": "v_ms"})
        ds_FWI = ds_FWI.rename({"fwinx": "FWI_12h"})
        # ds_Land = ds_Land.rename({"t2m": "t2m_K", "d2m": "d2m_K"})

        # ==================== DROP UNNECESSARY VARIABLES ====================
        if 'number' in ds_SL: ds_SL = ds_SL.drop_vars(['number'])
        if 'expver' in ds_SL: ds_SL = ds_SL.drop_vars(['expver'])
        if 'surface' in ds_FWI: ds_FWI = ds_FWI.drop_vars(['surface'])

        # ==================== CREATE TARGET GRID ====================
        lat_min, lat_max = 36.9, 43.0
        lon_min, lon_max = -10.0, -6.0
        lat_new = np.arange(lat_max, lat_min - target_res, -target_res)
        lon_new = np.arange(lon_min, lon_max + target_res, target_res)

        lon_grid, lat_grid = np.meshgrid(lon_new, lat_new)

        # ==================== INTERPOLATE ERA5 DATA ====================
        print("Interpolating ERA5 datasets to 0.1° grid...")
        ds_SL = ds_SL.interp(latitude=lat_new, longitude=lon_new, method='linear')
        # ds_PL = ds_PL.interp(latitude=lat_new, longitude=lon_new, method='linear')
        # ds_Land = ds_Land.interp(latitude=lat_new, longitude=lon_new, method='linear')

        # ==================== PREPARE FWI DATA ====================
        print("Regridding FWI dataset to match ERA5 grid...")

        if 'values' in ds_FWI.dims:
            ds_FWI = ds_FWI.set_index(values=('latitude', 'longitude')).unstack('values')

        ds_FWI = ds_FWI.assign_coords(longitude=(((ds_FWI.longitude + 180) % 360) - 180))

        # Expandir FWI diário → horário
        times_hourly = pd.date_range(
            start=ds_FWI.valid_time.min().values,
            end=ds_FWI.valid_time.max().values + pd.Timedelta(hours=23),
            freq='h'
        )
        ds_FWI = ds_FWI.reindex(valid_time=times_hourly, method='ffill')

        # ==================== INTERPOLAÇÃO 2D CORRETA ====================
        print("Interpolating FWI to regular grid...")

        lat_points = ds_FWI['latitude'].values
        lon_points = ds_FWI['longitude'].values

        fw_interp_list = []

        for t in range(len(ds_FWI.valid_time)):
            lat_grid_orig, lon_grid_orig = np.meshgrid(lat_points, lon_points, indexing='ij')

            fw_values = ds_FWI['FWI_12h'].isel(valid_time=t).values
            valid_mask = ~np.isnan(fw_values)

            points_valid = np.column_stack((lat_grid_orig.ravel()[valid_mask.ravel()],
                                            lon_grid_orig.ravel()[valid_mask.ravel()]))

            values_valid = fw_values.ravel()[valid_mask.ravel()]

            interp_values = griddata(
                points=points_valid,
                values=values_valid,
                xi=(lat_grid, lon_grid),
                method='linear',
                fill_value=np.nan
            )

            fw_interp_list.append(interp_values)

        fw_interp_array = np.stack(fw_interp_list)

        ds_FWI_interp = xr.Dataset(
            data_vars={
                'FWI_12h': (('valid_time', 'latitude', 'longitude'), fw_interp_array)
            },
            coords={
                'valid_time': ds_FWI.valid_time,
                'latitude': lat_new,
                'longitude': lon_new
            }
        )

        ds_FWI = ds_FWI_interp

        print(ds_SL)
        print(ds_PL)
        print(ds_FWI)
        print(ds_Land)

    return ds_SL, ds_PL, ds_FWI, ds_Land




# ============================================================
#            CALCULATE WEATHER VARIABLES (UPDATED)
# ============================================================

def calculate_weather_variables(ds_SL, ds_PL, ds_FWI, ds_Land):
    """
    Calculate weather variables:
    - wv100_kh : Wind speed at 100m (km/h)
    - FWI_12h  : Fire Weather Index
    - rh_2m    : Relative humidity at 2m (%)
    - wdir_950 : Wind direction at 950 hPa (°)
    """

    # ==================== UNIT CONVERSIONS ====================
    print("Converting units...")

    ds_SL["u100_kh"] = ds_SL["u100_ms"] * 3.6
    ds_SL["v100_kh"] = ds_SL["v100_ms"] * 3.6

    wv100_kh = np.sqrt(ds_SL["u100_kh"]**2 + ds_SL["v100_kh"]**2)

    '''    # ==================== WIND DIRECTION 950 hPa ====================
        print("Computing wind direction at 950 hPa...")

        u950 = ds_PL["u_ms"].sel(pressure_level=950) * units("m/s")
        v950 = ds_PL["v_ms"].sel(pressure_level=950) * units("m/s")

        wdir_950 = wind_direction(u950, v950)'''

    '''    # ==================== RELATIVE HUMIDITY AT 2m ====================
        print("Computing blended RH at 2m...")

        # ERA5-Land temperature & dewpoint
        T2_land = ds_Land["t2m_K"]
        Td2_land = ds_Land["d2m_K"]

        # ERA5-SL fallback temperature & dewpoint (convert to K if necessário)
        T2_sl = ds_SL["t2m"].values + 273.15 if "t2m" in ds_SL else None
        Td2_sl = ds_SL["d2m"].values + 273.15 if "d2m" in ds_SL else None

        # Blend LAND + SL: usar alpha para LAND, 1-alpha para SL
        alpha = 0.9
        if T2_sl is not None:
            T2_combined = xr.where(~np.isnan(T2_land), alpha*T2_land + (1-alpha)*T2_sl, T2_sl)
        else:
            T2_combined = T2_land

        if Td2_sl is not None:
            Td2_combined = xr.where(~np.isnan(Td2_land), alpha*Td2_land + (1-alpha)*Td2_sl, Td2_sl)
        else:
            Td2_combined = Td2_land

        # Convert to MetPy units
        T2 = T2_combined * units.kelvin
        Td2 = Td2_combined * units.kelvin

        rh_2m = relative_humidity_from_dewpoint(T2, Td2) * 100.0'''

    # ==================== CREATE OUTPUT DATASET ====================
    ds_output = xr.Dataset(
        {
            'wv100_kh': wv100_kh,
            'FWI_12h': ds_FWI["FWI_12h"]
        },
        coords={
            'valid_time': ds_SL.valid_time,
            'latitude': ds_SL.latitude,
            'longitude': ds_SL.longitude
        }
    )

    # Remove unidades MetPy
    for var in ds_output.data_vars:
        if hasattr(ds_output[var].data, 'magnitude'):
            ds_output[var] = (ds_output[var].dims, ds_output[var].data.magnitude)

    return ds_output
