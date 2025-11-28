"""
This script uses the CDS API to fetch climate data for Portugal for real-time predictions.
Downloads ERA5 data needed to calculate: sW_100_av, FWI_12h_av, wv100_k_av, wv_850_av, Cape_av, gT_8_7_av
"""
import cdsapi
from datetime import datetime
from pathlib import Path
import xarray as xr

def fetch_era5_data(year, month, day, hour):
    """
    Fetch ERA5 data needed for fire prediction variables.
    For each requested hour, fetches that hour plus the next 3 hours.

    Parameters:
    -----------
    year : list
        Year (e.g., [2016])
    month : list
        Month (e.g., [9])
    day : list
        Day (e.g., [10])
    hour : list
        Hour (e.g., [11, 12, 13])

    Returns:
    --------
    dict: Paths to downloaded files
    """


    # Caminho do ficheiro de tokens
    token_file = Path("API_tokens.txt")

    # Ler o ficheiro e guardar num dicionário
    tokens = {}
    with token_file.open() as f:
        for line in f:
            if "=" in line:
                key, value = line.strip().split("=", 1)
                tokens[key] = value

    # Criar clientes CDS e EWDS
    cds_client = cdsapi.Client(url=tokens['CDS_URL'], key=tokens['CDS_KEY'])
    ewds_client = cdsapi.Client(url=tokens['EWDS_URL'], key=tokens['EWDS_KEY'])


    cds_client = cdsapi.Client(url=tokens['CDS_URL'], key=tokens['CDS_KEY'])
    ewds_client = cdsapi.Client(url=tokens['EWDS_URL'], key=tokens['EWDS_KEY'])


    output_folder = Path("Data")

    downloaded_files = {}

    year_str  = "".join(str(x) for x in year)
    month_str = "".join(str(x) for x in month)
    day_str   = "".join(str(x) for x in day)
    hour_str  = "".join(str(x) for x in hour)

    time_code = f"{year_str}_{month_str}_{day_str}_{hour_str}"



    # ==================== SINGLE LEVELS DATA ====================
    # Variables needed: sW_100_av, wv100_k_av, Cape_av

    sl_filename = f"ERA5_SL_{time_code}.nc"
    sl_target = output_folder / sl_filename  # caminho completo

    single_levels_request = {
        "product_type": ["reanalysis"],
        "variable": [
            "100m_u_component_of_wind",
            "100m_v_component_of_wind",
            "volumetric_soil_water_layer_3",
            "convective_available_potential_energy"
        ],
        "year": year,
        "month": month,
        "day": day,
        "time": hour,
        "data_format": "netcdf",
        "download_format": "unarchived",
        "area": [43, -10, 36, -6]
    }

    print(f"Requesting: {sl_filename}")
    cds_client.retrieve("reanalysis-era5-single-levels", single_levels_request, str(sl_target))
    downloaded_files['single_levels'] = sl_target





    # ==================== PRESSURE LEVELS DATA ====================
    pl_filename = f"ERA5_PL_{time_code}.nc"
    pl_target = output_folder / pl_filename

    pressure_levels_request = {
        "product_type": ["reanalysis"],
        "variable": [
            "u_component_of_wind",
            "v_component_of_wind",
            "temperature",
            "geopotential"
        ],
        "pressure_level": [
            "700",  # 700 hPa (~3000m)
            "850"   # 850 hPa (~1500m)
        ],
        "year": year,
        "month": month,
        "day": day,
        "time": hour,
        "data_format": "netcdf",
        "download_format": "unarchived",
        "area": [43, -10, 36, -6]
    }

    print(f"Requesting: {pl_filename}")
    cds_client.retrieve("reanalysis-era5-pressure-levels", pressure_levels_request, str(pl_target))
    downloaded_files['pressure_levels'] = pl_target




    # ==================== FIRE WEATHER INDEX DATA ====================
    fwi_filename = f"ERA5_FWI_{time_code}.nc"
    fwi_target = output_folder / fwi_filename

    fwi_request = {
        "product_type": "reanalysis",
        "variable": [
            "fire_weather_index"
        ],
        "dataset_type": "consolidated_dataset",
        "system_version": ["4_1"],
        "year": year,
        "month": month,
        "day": day,
        "time": hour,
        "grid": "original_grid",
        "data_format": "netcdf",
        "area": [43, -10, 36, -6]
    }

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
