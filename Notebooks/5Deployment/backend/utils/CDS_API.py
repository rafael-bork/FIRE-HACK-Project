"""
Este script usa a API do CDS para obter dados climáticos para Portugal para previsões em tempo real.
Faz o download dos dados ERA5 necessários para calcular: FWI_12h_av, wv100_k_av, wdir_950_av, rh_2m_av
"""

import cdsapi
from datetime import datetime
from pathlib import Path
import xarray as xr


def fetch_era5_data(year, month, day, hour):
    """
    Faz o download dos dados ERA5 necessários para variáveis de previsão de incêndio.
    Para cada hora pedida, obtém essa hora e as 3 horas seguintes.

    Parameters
    ----------
    year : list
        Ano (ex.: [2016])
    month : list
        Mês (ex.: [9])
    day : list
        Dia (ex.: [10])
    hour : list
        Hora (ex.: [11, 12, 13])

    Returns
    -------
    dict
        Caminhos dos ficheiros descarregados
    """

    token_file = Path("backend/utils/API_tokens.txt")

    # Ler tokens
    tokens = {}
    with token_file.open() as f:
        for line in f:
            if "=" in line:
                key, value = line.strip().split("=", 1)
                tokens[key] = value

    # Criar clientes CDS
    cds_client = cdsapi.Client(url=tokens["CDS_URL"], key=tokens["CDS_KEY"])
    ewds_client = cdsapi.Client(url=tokens["EWDS_URL"], key=tokens["EWDS_KEY"])

    output_folder = Path("Data")
    downloaded_files = {}

    year_str = "".join(str(x) for x in year)
    month_str = "".join(str(x) for x in month)
    day_str = "".join(str(x) for x in day)
    hour_str = "".join(str(x) for x in hour)

    time_code = f"{year_str}_{month_str}_{day_str}_{hour_str}"

    # ==================== SINGLE LEVELS ====================
    sl_filename = f"ERA5_SL_{time_code}.nc"
    sl_target = output_folder / sl_filename

    if not sl_target.exists():
        single_levels_request = {
            "product_type": ["reanalysis"],
            "variable": [
                "10m_u_component_of_wind",
                "10m_v_component_of_wind",
                "2m_temperature",
                "2m_dewpoint_temperature",
                "convective_available_potential_energy",
            ],
            "year": year,
            "month": month,
            "day": day,
            "time": hour,
            "data_format": "netcdf",
            "download_format": "unarchived",
            "area": [43, -10, 36, -6],
        }

        print(f"Requesting: {sl_filename}")
        cds_client.retrieve(
            "reanalysis-era5-single-levels",
            single_levels_request,
            str(sl_target),
        )

    else:
        print("SL dataset already exists")

    downloaded_files["single_levels"] = sl_target

    # ==================== PRESSURE LEVELS ====================
    pl_filename = f"ERA5_PL_{time_code}.nc"
    pl_target = output_folder / pl_filename

    if not pl_target.exists():
        pressure_levels_request = {
            "product_type": ["reanalysis"],
            "variable": [
                "geopotential",
                "temperature",
                "u_component_of_wind",
                "v_component_of_wind"
            ],
            "pressure_level": ["850", "700"],
            "year": year,
            "month": month,
            "day": day,
            "time": hour,
            "data_format": "netcdf",
            "download_format": "unarchived",
            "area": [43, -10, 36, -6],
        }

        print(f"Requesting: {pl_filename}")
        cds_client.retrieve(
            "reanalysis-era5-pressure-levels",
            pressure_levels_request,
            str(pl_target),
        )

    else:
        print("PL dataset already exists")

    downloaded_files["pressure_levels"] = pl_target

    # ==================== FIRE WEATHER INDEX ====================
    fwi_filename = f"ERA5_FWI_{time_code}.nc"
    fwi_target = output_folder / fwi_filename

    if not fwi_target.exists():
        fwi_request = {
            "product_type": "reanalysis",
            "variable": [
                "drought_code",
                "fine_fuel_moisture_code",
                "fire_weather_index"
            ],
            "dataset_type": "consolidated_dataset",
            "system_version": "4_1",
            "year": [str(y) for y in year],
            "month": [f"{int(m):02d}" for m in month],
            "day": [f"{int(d):02d}" for d in day],
            "grid": "original_grid",
            "data_format": "netcdf",
            "area": [43, -10, 36, -6]
        }

        print(f"Requesting: {fwi_filename}")
        ewds_client.retrieve(
            "cems-fire-historical-v1",
            fwi_request,
            str(fwi_target),
        )

    else:
        print("FWI dataset already exists")

    downloaded_files["fwi"] = fwi_target

    # ==================== ERA5 LAND ====================
    land_filename = f"ERA5_Lan_{time_code}.nc"
    land_target = output_folder / land_filename

    if not land_target.exists():
        land_request = {
            "product_type": ["reanalysis"],
            "variable": [
                "2m_dewpoint_temperature",
                "2m_temperature",
                "10m_u_component_of_wind",
                "10m_v_component_of_wind"
            ],
            "year": year,
            "month": month,
            "day": day,
            "time": hour,
            "data_format": "netcdf",
            "download_format": "unarchived",
            "area": [43, -10, 36, -6],
        }

        print(f"Requesting: {land_filename}")
        cds_client.retrieve(
            "reanalysis-era5-land",
            land_request,
            str(land_target),
        )

    else:
        print("Land dataset already exists")

    downloaded_files["Land"] = land_target

    return downloaded_files


# ==================== EXAMPLE USAGE ====================
if __name__ == "__main__":
    files = fetch_era5_data(
        year=2016,
        month=9,
        day=15,
        hour=14,
    )

    print("\nDownloaded files:")
    for dataset_name, filepath in files.items():
        print(f"  {dataset_name}: {filepath}")

    # Exemplo com horas múltiplas:
    # hour=[12, 18] → obtém 12:00–15:00 e 18:00–21:00
    # hour=None → obtém as 24 horas do dia
