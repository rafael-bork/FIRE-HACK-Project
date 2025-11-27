"""
This script uses the CDS API to fetch climate data for Portugal for real-time predictions.
Downloads ERA5 data needed to calculate: sW_100_av, FWI_12h_av, wv100_k_av, wv_850_av, Cape_av, gT_8_7_av
"""
import cdsapi
from datetime import datetime
from pathlib import Path

def fetch_era5_data(year, month, day, hour=None):
    """
    Fetch ERA5 data needed for fire prediction variables.
    For each requested hour, fetches that hour plus the next 3 hours.

    Parameters:
    -----------
    year : str or int
        Year (e.g., '2016' or 2016)
    month : str or int
        Month (e.g., '09' or 9)
    day : str or int
        Day (e.g., '15' or 15)
    hour : str, int, or list, optional
        Hour(s) to download (e.g., '12', 12, or [0, 12]).
        For each hour, will fetch that hour + next 3 hours.
        Example: hour=14 fetches [14:00, 15:00, 16:00, 17:00]
        If None, downloads all 24 hours.

    Returns:
    --------
    dict: Paths to downloaded files
    """
    # CDS client for ERA5 data
    cds_client = cdsapi.Client()

    # EWDS client for Fire Weather Index data
    ewds_client = cdsapi.Client(url="https://ewds.climate.copernicus.eu/api", wait_until_complete=True)

    # Create output directory
    output_folder = Path("Data/web_cache/")
    output_folder.mkdir(parents=True, exist_ok=True)

    # Format parameters
    year_str = str(year)
    month_str = f"{int(month):02d}"
    day_str = f"{int(day):02d}"

    # Handle hour parameter - fetch requested hour + next 3 hours
    if hour is None:
        hours = [f"{h:02d}:00" for h in range(24)]
    elif isinstance(hour, (list, tuple)):
        # For each hour in list, add that hour + next 3 hours
        hours_set = set()
        for h in hour:
            base_hour = int(h)
            for offset in range(4):  # 0, 1, 2, 3 (current + next 3)
                hours_set.add((base_hour + offset) % 24)
        hours = [f"{h:02d}:00" for h in sorted(hours_set)]
    else:
        # Single hour: fetch that hour + next 3 hours
        base_hour = int(hour)
        hours = [f"{(base_hour + offset) % 24:02d}:00" for offset in range(4)]

    # Timestamp for filename
    timestamp = datetime.now().strftime("%H%M%S")

    downloaded_files = {}

    # ==================== SINGLE LEVELS DATA ====================
    # Variables needed: sW_100_av, wv100_k_av, Cape_av
    single_levels_request = {
        "product_type": ["reanalysis"],
        "variable": [
            # For wv100_k_av (100m wind speed in km/h)
            "100m_u_component_of_wind",
            "100m_v_component_of_wind",

            # For sW_100_av (soil water at 100cm depth)
            "volumetric_soil_water_layer_3",

            # For Cape_av (Convective Available Potential Energy)
            "convective_available_potential_energy",

            # For gT_8_7_av masking (surface pressure)
            "surface_pressure"
        ],
        "year": year_str,
        "month": month_str,
        "day": day_str,
        "time": hours,
        "data_format": "netcdf",
        "download_format": "unarchived",
        "area": [43, -10, 37, -6]  # Portugal bounding box [North, West, South, East]
    }

    sl_filename = f"ERA5_SL_{year_str}{month_str}{day_str}_{timestamp}.nc"
    sl_target = output_folder / sl_filename

    print(f"Requesting: {sl_filename}")
    cds_client.retrieve("reanalysis-era5-single-levels", single_levels_request, str(sl_target))
    downloaded_files['single_levels'] = sl_target

    # ==================== PRESSURE LEVELS DATA ====================
    # Variables needed: wv_850_av, gT_8_7_av
    pressure_levels_request = {
        "product_type": ["reanalysis"],
        "variable": [
            # For wv_850_av (wind speed at 850 hPa)
            "u_component_of_wind",
            "v_component_of_wind",

            # For gT_8_7_av (temperature gradient between 800-700 hPa)
            "temperature",
            "geopotential"
        ],
        "pressure_level": [
            "700",  # 700 hPa (~3000m) - needed for gT_8_7_av
            "850"   # 850 hPa (~1500m) - needed for wv_850_av and gT_8_7_av
        ],
        "year": year_str,
        "month": month_str,
        "day": day_str,
        "time": hours,
        "data_format": "netcdf",
        "download_format": "unarchived",
        "area": [43, -10, 37, -6]
    }

    pl_filename = f"ERA5_PL_{year_str}{month_str}{day_str}_{timestamp}.nc"
    pl_target = output_folder / pl_filename

    print(f"Requesting: {pl_filename}")
    cds_client.retrieve("reanalysis-era5-pressure-levels", pressure_levels_request, str(pl_target))
    downloaded_files['pressure_levels'] = pl_target

    # ==================== FIRE WEATHER INDEX DATA ====================
    # Variables needed: FWI_12h_av
    fwi_request = {
        "product_type": "reanalysis",
        "variable": [
            "fire_weather_index",  # For FWI_12h_av
            "drought_code",        # Optional: useful for additional fire risk metrics
            "fine_fuel_moisture_code"  # Optional: useful for additional fire risk metrics
        ],
        "dataset_type": "consolidated_dataset",
        "system_version": ["4_1"],
        "year": [year_str],
        "month": [month_str],
        "day": [day_str],
        "time": hours,
        "grid": "original_grid",
        "data_format": "netcdf",
        "area": [43, -10, 37, -6]  # [North, West, South, East]
    }

    fwi_filename = f"ERA5_FWI_{year_str}{month_str}{day_str}_{timestamp}.nc"
    fwi_target = output_folder / fwi_filename

    print(f"Requesting: {fwi_filename}")
    ewds_client.retrieve("cems-fire-historical-v1", fwi_request, str(fwi_target))
    downloaded_files['fwi'] = fwi_target

    return downloaded_files


# Example usage
if __name__ == "__main__":
    # Example: Download data for September 15, 2016 at 14:00
    # This will fetch: 14:00, 15:00, 16:00, 17:00
    files = fetch_era5_data(
        year=2016,
        month=9,
        day=15,
        hour=14
    )

    print("\nDownloaded files:")
    for dataset_name, filepath in files.items():
        print(f"  {dataset_name}: {filepath}")

    # Example with multiple hours:
    # hour=[12, 18] will fetch: 12:00-15:00 and 18:00-21:00
    # hour=None will fetch all 24 hours (00:00-23:00)
