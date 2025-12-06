"""
This script assembles meteorological input data for fire prediction.
It ensures all necessary ERA5 data is downloaded and processes it into a dataset.
GIS variables and spatial mask are handled separately in Compile_data.
Uses modules:
- CDS_API: fetch ERA5 data
- Meteo_vars: calculate meteorological variables from ERA5 data
"""

import pandas as pd
import xarray as xr
from pathlib import Path
import importlib
import os
import glob


from . import CDS_API, Meteo_vars

# Reload modules in case of updates
importlib.reload(CDS_API)
importlib.reload(Meteo_vars)


def assemble_meteorological_data(required_times):
    """
    Assemble meteorological input for the given time range.
    
    This function checks for missing meteorological hours and downloads
    them from ERA5 if needed. Returns an xarray.Dataset with calculated
    meteorological variables only. GIS variables and spatial mask are
    added later in Compile_data.
    
    Parameters
    ----------
    start_time : str or pd.Timestamp
        Start time of the requested data (e.g., "2023-08-01 12:00").
    duration_hours : int
        Duration in hours for which meteorological data is needed.
    
    Returns
    -------
    xr.Dataset
        Dataset with calculated meteorological variables for the requested times.
    """

    # ---------------------- Download ERA5 data for required times ----------------------
    years  = sorted(set(t.year for t in required_times))
    months = sorted(set(t.month for t in required_times))
    days   = sorted(set(t.day for t in required_times))
    hours  = sorted(set(t.hour for t in required_times))

    print("Downloading ERA5 data for:")
    print(f"  Years:  {years}")
    print(f"  Months: {months}")
    print(f"  Days:   {days}")
    print(f"  Hours:  {hours}")

    era5_files = CDS_API.fetch_era5_data(years, months, days, hours)

    # ---------------------- Process downloaded data ----------------------
    ds_SL, ds_PL, ds_FWI, ds_Land = Meteo_vars.prepare_datasets(
        sl_file=era5_files.get('single_levels'),
        pl_file=era5_files.get('pressure_levels'),  
        fwi_file=era5_files.get('fwi'),
        land_file=era5_files.get('Land')
    )

    ds_meteovars = Meteo_vars.calculate_weather_variables(ds_SL, ds_PL, ds_FWI, ds_Land)
    ds_meteovars = ds_meteovars.sel(valid_time=required_times)
    if 'pressure_level' in ds_meteovars:
        ds_meteovars = ds_meteovars.drop_vars('pressure_level')

    for f in glob.glob("Data/ERA5*.nc"):
        os.remove(f)

    # ---------------------- Return dataset ----------------------
    print(f"Prepared meteorological dataset for {len(required_times)} hours.")
    return ds_meteovars
