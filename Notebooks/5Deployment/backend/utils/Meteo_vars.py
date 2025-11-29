import numpy as np
import pandas as pd
import xarray as xr
from scipy.interpolate import griddata

def prepare_datasets(sl_file, pl_file, fwi_file, target_res=0.1):
    """
    Prepare ERA5 Single Levels, Pressure Levels, and FWI datasets.

    Parameters:
    -----------
    sl_file : str
        Path to ERA5 Single Levels NetCDF file.
    pl_file : str
        Path to ERA5 Pressure Levels NetCDF file.
    fwi_file : str
        Path to Fire Weather Index NetCDF file.
    target_res : float
        Target grid resolution in degrees (default: 0.1°).

    Returns:
    --------
    ds_SL : xarray.Dataset
        Single Levels dataset interpolated to 0.1° grid.
    ds_PL : xarray.Dataset
        Pressure Levels dataset interpolated to 0.1° grid.
    ds_FWI : xarray.Dataset
        FWI dataset interpolated to 0.1° grid matching ERA5.
    """

    # ==================== LOAD DATASETS ====================
    print("Loading datasets...")
    with xr.open_dataset(sl_file, engine="netcdf4") as ds_SL, \
         xr.open_dataset(pl_file, engine="netcdf4") as ds_PL, \
         xr.open_dataset(fwi_file, engine="netcdf4") as ds_FWI:

        # ==================== RENAME VARIABLES ====================
        ds_SL = ds_SL.rename({"u100": "u100_ms", "v100": "v100_ms", "swvl3": "sW_100", "cape": "Cape"})
        ds_PL = ds_PL.rename({"u": "u_ms", "v": "v_ms", "t": "t_K", "z": "gp"})
        ds_FWI = ds_FWI.rename({"fwinx": "FWI_12h"})

        # ==================== DROP UNNECESSARY VARIABLES ====================
        ds_SL = ds_SL.drop_vars(['number', 'expver'])
        ds_PL = ds_PL.drop_vars(['number', 'expver'])
        ds_FWI = ds_FWI.drop_vars(['surface'])

        # ==================== CREATE TARGET GRID ====================
        lat_min, lat_max = 36.9, 43.0
        lon_min, lon_max = -10.0, -6.0
        lat_new = np.arange(lat_max, lat_min - target_res, -target_res)
        lon_new = np.arange(lon_min, lon_max + target_res, target_res)
        lon_grid, lat_grid = np.meshgrid(lon_new, lat_new)

        # ==================== INTERPOLATE ERA5 DATA ====================
        print("Interpolating ERA5 datasets to 0.1° grid...")
        ds_SL = ds_SL.interp(latitude=lat_new, longitude=lon_new, method='linear')
        ds_PL = ds_PL.interp(latitude=lat_new, longitude=lon_new, method='linear')

        # ==================== PREPARE FWI DATA ====================
        print("Regridding FWI dataset to match ERA5 grid...")

        # Transformar 1D irregular grid para 2D
        if 'values' in ds_FWI.dims:
            ds_FWI = ds_FWI.set_index(values=('latitude','longitude')).unstack('values')

        # Converter longitudes para -180..180
        ds_FWI = ds_FWI.assign_coords(longitude=(((ds_FWI.longitude + 180) % 360) - 180))

        # Expandir FWI diário para horário
        times_hourly = pd.date_range(
            start=ds_FWI.valid_time.min().values,
            end=ds_FWI.valid_time.max().values + pd.Timedelta(hours=23),
            freq='H'
        )
        ds_FWI = ds_FWI.reindex(valid_time=times_hourly, method='ffill')

        # ==================== INTERPOLAÇÃO 2D CORRETA ====================
        print("Interpolating FWI to regular grid...")

        # Obter coordenadas dos pontos irregulares
        lat_points = ds_FWI['latitude'].values
        lon_points = ds_FWI['longitude'].values

        fw_interp_list = []

        for t in range(len(ds_FWI.valid_time)):
            lat_grid_orig, lon_grid_orig = np.meshgrid(lat_points, lon_points, indexing='ij')

            fw_values = ds_FWI['FWI_12h'].isel(valid_time=t).values  # shape (25,52)

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

    return ds_SL, ds_PL, ds_FWI



"""
Script to calculate weather variables from prepared datasets.
Variables calculated:
- sW_100: Soil water at 100cm depth (m³/m³)
- FWI_12h: Fire Weather Index (dimensionless)
- wv100_k: Wind speed at 100m (km/h)
- wv_850: Wind speed at 850 hPa (km/h)
- Cape: Convective Available Potential Energy (J/kg)
- gT_8_7: Temperature gradient 850-700 hPa (°C/km)
"""
import numpy as np
import xarray as xr
from metpy.units import units

def calculate_weather_variables(ds_SL, ds_PL, ds_FWI):
    """
    Calculate weather variables for all valid times without cumulative averaging.

    Parameters:
    -----------
    ds_SL : xarray.Dataset
        ERA5 Single Levels dataset (0.1° grid)
    ds_PL : xarray.Dataset
        ERA5 Pressure Levels dataset (0.1° grid)
    ds_FWI : xarray.Dataset
        Fire Weather Index dataset (0.1° grid)

    Returns:
    --------
    ds_output : xarray.Dataset
        Dataset containing all calculated variables with dimensions (valid_time, latitude, longitude)
    """

    # ==================== UNIT CONVERSIONS ====================
    print("Converting units...")

    # --- 100m Wind Components: m/s to km/h ---
    ds_SL["u100_kh"] = (ds_SL["u100_ms"] * units.meter / units.second).metpy.convert_units("km/h")
    ds_SL["v100_kh"] = (ds_SL["v100_ms"] * units.meter / units.second).metpy.convert_units("km/h")

    # --- Pressure Level Wind Components: m/s to km/h ---
    ds_PL["u_kh"] = (ds_PL["u_ms"] * units.meter / units.second).metpy.convert_units("km/h")
    ds_PL["v_kh"] = (ds_PL["v_ms"] * units.meter / units.second).metpy.convert_units("km/h")

    # --- Temperature: K to °C ---
    ds_PL["t_C"] = (ds_PL["t_K"] * units.kelvin).metpy.convert_units("degC")

    # ==================== DERIVED VARIABLES ====================
    print("Calculating derived variables...")

    # Wind speed 100m
    wv100_k = np.sqrt(ds_SL["u100_kh"]**2 + ds_SL["v100_kh"]**2)

    # Wind speed 850 hPa
    wv_850 = np.sqrt(ds_PL["u_kh"].sel(pressure_level=850)**2 + ds_PL["v_kh"].sel(pressure_level=850)**2)

    # Temperature gradient 850-700 hPa (°C/km)
    t_850 = ds_PL["t_C"].sel(pressure_level=850)
    t_700 = ds_PL["t_C"].sel(pressure_level=700)
    z_850 = ds_PL["gp"].sel(pressure_level=850) / 9.80665
    z_700 = ds_PL["gp"].sel(pressure_level=700) / 9.80665
    gT_8_7 = (t_850 - t_700) / ((z_700 - z_850) / 1000.0)
            
    # ==================== CREATE OUTPUT DATASET ====================
    ds_output = xr.Dataset(
        {
            'sW_100': ds_SL["sW_100"],
            'FWI_12h': ds_FWI["FWI_12h"],
            'wv100_k': wv100_k,
            'wv_850': wv_850,
            'Cape': ds_SL["Cape"],
            'gT_8_7': gT_8_7
        },
        coords={
            'valid_time': ds_SL.valid_time,
            'latitude': ds_SL.latitude,
            'longitude': ds_SL.longitude
        }
    )

    if 'pressure_level' in ds_output.coords:
        ds_output = ds_output.drop_vars('pressure_level')


    for var in ds_output.data_vars:
        if hasattr(ds_output[var].data, 'magnitude'):
            ds_output[var] = (ds_output[var].dims, ds_output[var].data.magnitude)

    return ds_output
