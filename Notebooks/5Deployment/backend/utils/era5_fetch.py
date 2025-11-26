import xarray as xr
from datetime import datetime
from backend.config import ERA5_CACHE_DIR
from backend.utils.era5_extract import extract_value_at_point

# Check if cdsapi is installed
try:
    import cdsapi
    CDS_AVAILABLE = True
except ImportError:
    CDS_AVAILABLE = False
    cdsapi = None

# Lazy initialization of CDS client
_cds_client = None

def get_cds_client():
    """Get or create CDS API client (lazy initialization)"""
    global _cds_client

    if not CDS_AVAILABLE:
        raise RuntimeError("cdsapi package is not installed")

    if _cds_client is None:
        try:
            # Initialize client without connecting yet
            _cds_client = cdsapi.Client(
                retry_max=1,  # Reduce retries during init
                sleep_max=1   # Reduce sleep time
            )
        except Exception as e:
            raise RuntimeError(f"Failed to initialize CDS API client: {e}")

    return _cds_client

def fetch_era5_single_levels(lat, lon, target_dt, area):
    cache_file = ERA5_CACHE_DIR / f"ERA5_SL_{target_dt.strftime('%Y%m%d_%H')}_{lat:.2f}_{lon:.2f}.nc"
    if cache_file.exists():
        return xr.open_dataset(cache_file)

    client = get_cds_client()
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
    client.retrieve("reanalysis-era5-single-levels", request_params, str(temp_file))
    temp_file.rename(cache_file)
    return xr.open_dataset(cache_file)

def fetch_era5_pressure_levels(lat, lon, target_dt, area):
    cache_file = ERA5_CACHE_DIR / f"ERA5_PL_{target_dt.strftime('%Y%m%d_%H')}_{lat:.2f}_{lon:.2f}.nc"
    if cache_file.exists():
        return xr.open_dataset(cache_file)

    client = get_cds_client()
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
    client.retrieve("reanalysis-era5-pressure-levels", request_params, str(temp_file))
    temp_file.rename(cache_file)
    return xr.open_dataset(cache_file)

def fetch_fire_weather_index(lat, lon, target_dt):
    cache_file = ERA5_CACHE_DIR / f"CEMS_FWI_{target_dt.strftime('%Y%m%d')}_{lat:.2f}_{lon:.2f}.nc"
    if cache_file.exists():
        return xr.open_dataset(cache_file)

    client = get_cds_client()
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
    client.retrieve("cems-fire-historical", request_params, str(temp_file))
    temp_file.rename(cache_file)
    return xr.open_dataset(cache_file)