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

        print(ds_SL)
        print(ds_PL)
        print(ds_FWI)
        print(ds_Land)

        # ==================== RENAME VARIABLES ====================
        ds_SL = ds_SL.rename({"t2m": "t_2m_K", "d2m": "d_2m_K", "u10": "u10_ms", "v10": "v10_ms", "cape": "cape"})
        ds_PL = ds_PL.rename({"t": "t_K", "u": "u_ms", "v": "v_ms", "z": "gp_m2s2"})
        ds_FWI = ds_FWI.rename({"fwinx": "FWI_12h", "drtcode": "DC_12h"})
        ds_Land = ds_Land.rename({"t2m": "t_2m_K", "d2m": "d_2m_K", "u10": "u10_ms", "v10": "v10_ms"})

        # ==================== DROP UNNECESSARY VARIABLES ====================
        if 'number' in ds_SL: ds_SL = ds_SL.drop_vars(['number'])
        if 'expver' in ds_SL: ds_SL = ds_SL.drop_vars(['expver'])
        if 'number' in ds_PL: ds_PL = ds_PL.drop_vars(['number'])
        if 'expver' in ds_PL: ds_PL = ds_PL.drop_vars(['expver'])
        if 'surface' in ds_FWI: ds_FWI = ds_FWI.drop_vars(['surface'])
        if 'number' in ds_Land: ds_Land = ds_Land.drop_vars(['number'])
        if 'expver' in ds_Land: ds_Land = ds_Land.drop_vars(['expver'])

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
        ds_Land = ds_Land.interp(latitude=lat_new, longitude=lon_new, method='linear')

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
        dc_interp_list = []

        for t in range(len(ds_FWI.valid_time)):
            lat_grid_orig, lon_grid_orig = np.meshgrid(lat_points, lon_points, indexing='ij')

            # FWI
            fw_values = ds_FWI['FWI_12h'].isel(valid_time=t).values
            valid_mask_fw = ~np.isnan(fw_values)
            points_valid_fw = np.column_stack((lat_grid_orig.ravel()[valid_mask_fw.ravel()],
                                            lon_grid_orig.ravel()[valid_mask_fw.ravel()]))
            values_valid_fw = fw_values.ravel()[valid_mask_fw.ravel()]
            interp_fw = griddata(
                points=points_valid_fw,
                values=values_valid_fw,
                xi=(lat_grid, lon_grid),
                method='linear',
                fill_value=np.nan
            )
            fw_interp_list.append(interp_fw)

            # DC
            dc_values = ds_FWI['DC_12h'].isel(valid_time=t).values
            valid_mask_dc = ~np.isnan(dc_values)
            points_valid_dc = np.column_stack((lat_grid_orig.ravel()[valid_mask_dc.ravel()],
                                            lon_grid_orig.ravel()[valid_mask_dc.ravel()]))
            values_valid_dc = dc_values.ravel()[valid_mask_dc.ravel()]
            interp_dc = griddata(
                points=points_valid_dc,
                values=values_valid_dc,
                xi=(lat_grid, lon_grid),
                method='linear',
                fill_value=np.nan
            )
            dc_interp_list.append(interp_dc)

        fw_interp_array = np.stack(fw_interp_list)
        dc_interp_array = np.stack(dc_interp_list)

        ds_FWI_interp = xr.Dataset(
            data_vars={
                'FWI_12h': (('valid_time', 'latitude', 'longitude'), fw_interp_array),
                'DC_12h': (('valid_time', 'latitude', 'longitude'), dc_interp_array)
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


    # ==================== WIND SPEED 850 hPa (km/h) ====================
    print("Computing wind speed at 850 hPa...")

    u850 = ds_PL["u_ms"].sel(pressure_level=850) * units("m/s")
    v850 = ds_PL["v_ms"].sel(pressure_level=850) * units("m/s")

    # velocidade do vento (m/s)
    wspd_850 = wind_speed(u850, v850)

    # converter para km/h
    wspd_850_kmh = wspd_850 * 3.6

    # ==================== VPD A 2m (ERA5-LAND) ====================
    print("Computando VPD a 2m para ERA5-Land...")

    T2_land  = ds_Land["t_2m_K"] * units.kelvin
    Td2_land = ds_Land["d_2m_K"] * units.kelvin

    es_land = saturation_vapor_pressure(T2_land)
    ea_land = saturation_vapor_pressure(Td2_land)

    vpd_land = (es_land - ea_land) 

    # ==================== VPD A 2m (ERA5-SL) ====================
    print("Computando VPD a 2m para ERA5-SL...")

    # ERA5-SL vem em °C → converter para Kelvin
    T2_sl  = (ds_SL["t_2m_K"]) * units.kelvin
    Td2_sl = (ds_SL["d_2m_K"]) * units.kelvin

    es_sl = saturation_vapor_pressure(T2_sl)
    ea_sl = saturation_vapor_pressure(Td2_sl)

    vpd_sl = (es_sl - ea_sl) * 0.001

    # ==================== HDW (Hot Dry Windy Index) ====================
    print("Computando HDW para ERA5-Land e ERA5-SL...")

    # ---- WIND SPEED 10m (km/h) ----
    # LAND
    ws10_land = wind_speed(
        ds_Land["u10_ms"] * units("m/s"),
        ds_Land["v10_ms"] * units("m/s")
    ) * 3.6

    # SL
    ws10_sl = wind_speed(
        ds_SL["u10_ms"] * units("m/s"),
        ds_SL["u10_ms"] * units("m/s")
    ) * 3.6

    # ---- HDW ----
    hdw_land = vpd_land * ws10_land
    hdw_sl   = vpd_sl   * ws10_sl

    hdw_final = xr.where(~np.isnan(hdw_land), hdw_land, hdw_sl)

    # ==================== GRADIENTE 850–700 hPa ====================
    print("Computando gradiente vertical de temperatura entre 850 e 700 hPa...")

    g = 9.80665  # m/s²

    # --- Temperatura em 850 e 700 hPa (K) ---
    T850 = ds_PL["t_K"].sel(pressure_level=850)
    T700 = ds_PL["t_K"].sel(pressure_level=700)

    # --- Geopotencial Φ (m²/s²) ---
    phi850 = ds_PL["gp_m2s2"].sel(pressure_level=850)
    phi700 = ds_PL["gp_m2s2"].sel(pressure_level=700)

    # --- Conversão de geopotencial Φ para altura geopotencial Z (m) ---
    Z850 = phi850 / g
    Z700 = phi700 / g

    # --- Diferenças ---
    dT = T700 - T850   # K → equivalente a °C
    dZ = Z700 - Z850   # m

    # --- Gradiente em °C/km ---
    temp_grad_C_per_km = (dT / dZ) * 1000.0

    # Output final
    gradT_850_700_C_per_km = temp_grad_C_per_km

    print("Gradiente calculado: C/km")


    # ==================== CREATE OUTPUT DATASET ====================
    ds_output = xr.Dataset(
        {
            'HDW': hdw_final,
            'wv_850': wspd_850_kmh,
            'Cape': ds_SL["cape"],                  # Assumindo variável existe
            'gT_8_7': gradT_850_700_C_per_km,
            'DC_12h': ds_FWI["DC_12h"],
            'FWI_12h': ds_FWI["FWI_12h"]
        },
        coords={
            'valid_time': ds_SL.valid_time,
            'latitude': ds_SL.latitude,
            'longitude': ds_SL.longitude
        }
    )

    print(ds_output)

    # Remove unidades MetPy
    for var in ds_output.data_vars:
        if hasattr(ds_output[var].data, 'magnitude'):
            ds_output[var] = (ds_output[var].dims, ds_output[var].data.magnitude)

    return ds_output
