import xarray as xr
from datetime import datetime
from backend.config import ERA5_CACHE_DIR
from backend.utils.era5_extract import extract_value_at_point

try:
    import cdsapi
    CDS_AVAILABLE = True
    cds_client = cdsapi.Client()
except:
    CDS_AVAILABLE = False
    cds_client = None

def fetch_era5_single_levels(lat, lon, target_dt, area):
    cache_file = ERA5_CACHE_DIR / f"ERA5_SL_{target_dt.strftime('%Y%m%d_%H')}_{lat:.2f}_{lon:.2f}.nc"
    if cache_file.exists():
        return xr.open_dataset(cache_file)
    request_params = {
        "product_type": ["reanalysis"],
        "variable": ["100m_u_component_of_wind", "100m_v_component_of_wind",
                     "convective_available_potential_energy", "volumetric_soil_water_layer_3",
                     "volumetric_soil_water_layer_4"],
        "year": str(target_dt.year),
        "month": f"{target_dt.month:02d}",
        "day": f"{target_dt.day:02d}",
        "time": f"{target_dt.hour:02d}:00",
        "data_format": "netcdf",
        "download_format": "unarchived",
        "area": area
    }
    temp_file = cache_file.with_suffix('.temp.nc')
    cds_client.retrieve("reanalysis-era5-single-levels", request_params, str(temp_file))
    temp_file.rename(cache_file)
    return xr.open_dataset(cache_file)

def fetch_era5_pressure_levels(lat, lon, target_dt, area):
    cache_file = ERA5_CACHE_DIR / f"ERA5_PL_{target_dt.strftime('%Y%m%d_%H')}_{lat:.2f}_{lon:.2f}.nc"
    if cache_file.exists():
        return xr.open_dataset(cache_file)
    request_params = {
        "product_type": ["reanalysis"],
        "variable": ["geopotential", "temperature", "specific_humidity"],
        "pressure_level": ["700", "850", "1000"],
        "year": str(target_dt.year),
        "month": f"{target_dt.month:02d}",
        "day": f"{target_dt.day:02d}",
        "time": f"{target_dt.hour:02d}:00",
        "data_format": "netcdf",
        "download_format": "unarchived",
        "area": area
    }
    temp_file = cache_file.with_suffix('.temp.nc')
    cds_client.retrieve("reanalysis-era5-pressure-levels", request_params, str(temp_file))
    temp_file.rename(cache_file)
    return xr.open_dataset(cache_file)

def fetch_fire_weather_index(lat, lon, target_dt):
    cache_file = ERA5_CACHE_DIR / f"CEMS_FWI_{target_dt.strftime('%Y%m%d')}_{lat:.2f}_{lon:.2f}.nc"
    if cache_file.exists():
        return xr.open_dataset(cache_file)
    request_params = {
        "product_type": "reanalysis",
        "variable": "fire_weather_index",
        "version": "4.1",
        "dataset": "Consolidated dataset",
        "year": str(target_dt.year),
        "month": f"{target_dt.month:02d}",
        "day": f"{target_dt.day:02d}"
    }
    temp_file = cache_file.with_suffix('.temp.nc')
    cds_client.retrieve("cems-fire-historical", request_params, str(temp_file))
    temp_file.rename(cache_file)
    return xr.open_dataset(cache_file)