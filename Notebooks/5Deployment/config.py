from pathlib import Path

# ==================== DIRECTORIES ====================
MODEL_DIR = Path('../../Data/Models')
RASTER_DIR = Path('../../Data/web_rasters')
ERA5_CACHE_DIR = Path('../../Data/Interim/Meteorological_data/ERA5_cache')
ERA5_CACHE_DIR.mkdir(parents=True, exist_ok=True)
FUEL_LOAD_DIR = Path('../../Data/Processed/Fuel_load')

# ==================== VARIABLES ====================
COMPLEX_VARIABLES = [
    "duration_p", "sW_100_av", "8_ny_fir_p", "3_8y_fir_p",
    "f_load_av", "f_start", "FWI_12h_av", "wv100_k_av",
    "wv_850_av", "Cape_av", "gT_8_7_av"
]

LINEAR_VARIABLES = [
    "wind_speed_midflame", "wind_direction", "slope",
    "1h_fuel_moisture", "fuel_load"
]