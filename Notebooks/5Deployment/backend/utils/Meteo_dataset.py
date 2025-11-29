"""
This script assembles meteorological input data for fire prediction.
It ensures all necessary ERA5 data is downloaded and processes it into a complete NetCDF dataset.
Uses modules:
- CDS_API: fetch ERA5 data
- Meteo_vars: calculate meteorological variables from ERA5 data
"""

import pandas as pd
import xarray as xr
from pathlib import Path
import importlib

import CDS_API
import Meteo_vars

# Reload modules in case of updates
importlib.reload(CDS_API)
importlib.reload(Meteo_vars)

def assemble_meteorological_data(start_time, duration_hours):
    """
    Assemble meteorological input for the given time range.
    
    This function checks for existing data in "Meteo_Complete.nc". 
    If some hours are missing, it downloads them from ERA5 using CDS_API.
    After downloading, it processes the datasets to calculate weather variables 
    and merges them into a single complete NetCDF dataset.
    
    Parameters
    ----------
    start_time : str or pd.Timestamp
        Start time of the requested data (e.g., "2023-08-01 12:00").
    duration_hours : int
        Duration in hours for which meteorological data is needed.
    
    Returns
    -------
    xr.Dataset
        Complete dataset with calculated meteorological variables.
    """
    
    # ---------------------- Check if the NetCDF already exists ----------------------
    netcdf_path = Path("Data") / "Meteo_Complete.nc"
    netcdf_path.parent.mkdir(parents=True, exist_ok=True)
    netcdf_exists = netcdf_path.exists()
    
    ds_complete = None
    if netcdf_exists:
        try:
            ds_complete = xr.open_dataset(netcdf_path)
            print("Existing NetCDF found. Checking for missing time steps...")
        except FileNotFoundError:
            netcdf_exists = False
    
    # ---------------------- Generate list of required times ----------------------
    start_time = pd.Timestamp(start_time)
    end_time = start_time + pd.Timedelta(hours=duration_hours)
    
    required_times = pd.date_range(
        start=start_time.ceil("h"),
        end=end_time.floor("h"),
        freq="1h"
    ).to_list()
    
    # ---------------------- Identify missing time steps ----------------------
    if ds_complete is not None:
        missing_times = [t for t in required_times if t not in ds_complete.valid_time]
    else:
        missing_times = required_times  # everything is missing if no file exists
    
    # ---------------------- Case: all data exists ----------------------
    if not missing_times:
        print("All requested time steps are already available locally.")
        return ds_complete
    
    # ---------------------- Download missing ERA5 data ----------------------
    years  = sorted(set(t.year for t in missing_times))
    months = sorted(set(t.month for t in missing_times))
    days   = sorted(set(t.day for t in missing_times))
    hours  = sorted(set(t.hour for t in missing_times))
    
    print("Downloading missing ERA5 data for:")
    print(f"  Years:  {years}")
    print(f"  Months: {months}")
    print(f"  Days:   {days}")
    print(f"  Hours:  {hours}")
    
    era5_files = CDS_API.fetch_era5_data(years, months, days, hours)
    
    # ---------------------- Process downloaded data ----------------------
    ds_SL, ds_PL, ds_FWI = Meteo_vars.prepare_datasets(
        sl_file=era5_files['single_levels'],
        pl_file=era5_files['pressure_levels'],
        fwi_file=era5_files['fwi']
    )
    
    ds_meteovars = Meteo_vars.calculate_weather_variables(ds_SL, ds_PL, ds_FWI)
    ds_meteovars = ds_meteovars.sel(valid_time=missing_times)
    
    ds_SL.close()
    ds_PL.close()
    ds_FWI.close()
    
    # ---------------------- Merge with existing dataset if present ----------------------
    if ds_complete is not None:
        ds_complete = xr.concat([ds_complete, ds_meteovars], dim="valid_time")
        valid_times = pd.Index(ds_complete.valid_time.values)
        ds_complete = ds_complete.sel(valid_time=~valid_times.duplicated())
    else:
        ds_complete = ds_meteovars
    
    # ---------------------- Save complete dataset ----------------------
    ds_complete.to_netcdf(netcdf_path)
    ds_meteovars.close()
    
    print(f"\nSaved complete dataset to: {netcdf_path}")
    print(ds_meteovars.sortby('latitude', ascending=True))
    
    return ds_complete