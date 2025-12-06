"""
This script compiles meteorological and GIS data for fire analysis.
It merges meteorological variables with GIS layers, applies spatial masks, 
and calculates cumulative mean datasets over the requested duration.
It now saves a NetCDF with meteo + GIS + mask applied, and skips calculations
if the requested times already exist.
Uses modules:
- Meteo_dataset: assemble meteorological datasets
- geopandas: handle GIS vector data
"""

import xarray as xr
import pandas as pd
import numpy as np
from pathlib import Path
from shapely.geometry import Point
import geopandas as gpd
import importlib

from . import Meteo_dataset
importlib.reload(Meteo_dataset)


def Compile_data(duration, mins_since_fire_start, start_time):
    """
    Compile meteorological and GIS data for a fire event.

    This function assembles meteorological data for the requested duration,
    enriches it with GIS variables (fuel, slope, etc.), applies a spatial mask
    for Portugal cells, and calculates cumulative mean datasets per hour.
    Saves a NetCDF with meteo+GIS+mask and reuses existing data if possible.
    
    Parameters
    ----------
    duration : int
        Duration in hours for which data is required.
    mins_since_fire_start : int
        Minutes since fire ignition, added as a variable to the dataset.
    start_time : str or pd.Timestamp
        Start time of the dataset (e.g., "2023-08-01 12:00").

    Returns
    -------
    pd.DataFrame
        DataFrame with cumulative mean variables per hour and spatial points.
    """

    # ---------------------- Generate required times ----------------------
    start_time = pd.Timestamp(start_time)
    end_time = start_time + pd.Timedelta(hours=duration)
    required_times = pd.date_range(start=start_time.ceil("h"), end=end_time.floor("h"), freq="1h")

    # ---------------------- Path to final FireData NetCDF ----------------------
    netcdf_path = Path("Data") / "FireData_Complete.nc"
    netcdf_path.parent.mkdir(parents=True, exist_ok=True)

    # ---------------------- Load existing dataset if present ----------------------
    ds_complete = None
    if netcdf_path.exists():
        try:
            with xr.open_dataset(netcdf_path) as ds:
                ds_complete = ds.load()
            print("Existing FireData NetCDF found.")
        except:
            ds_complete = None

    # ---------------------- Identify missing times ----------------------
    if ds_complete is not None:
        missing_times = [t for t in required_times if t not in ds_complete.valid_time]
    else:
        missing_times = required_times.to_list()

    print("Missing times", missing_times)

    # ---------------------- Case: all data exists ----------------------
    if not missing_times:
        with xr.open_dataset(netcdf_path) as ds_complete:
            ds_filtered = ds_complete.sel(valid_time=required_times)
    else:
        # ---------------------- Assemble missing meteorological data ----------------------
        ds_meteo_missing = Meteo_dataset.assemble_meteorological_data(missing_times)

        # ---------------------- Open GIS dataset ----------------------
        Gis_path = Path("backend/utils/Data/GIS_data.nc")
        fallback_Gis_path = Path("utils/Data/GIS_data.nc")

        if not Gis_path.exists():
            Gis_path = fallback_Gis_path
        
        with xr.open_dataset(Gis_path) as ds_GIS:
            ds_GIS = ds_GIS.rename({"lat": "latitude", "lon": "longitude"})

            # ---------------------- Extract year coordinate ----------------------
            ds_meteo_missing = ds_meteo_missing.assign_coords(
                year=("valid_time", ds_meteo_missing.valid_time.dt.year.values)
            )

            # ---------------------- Function to add yearly GIS variables ----------------------
            def add_yearly_vars(ds, ds_GIS, var_names):
                data_vars = {}
                for var in var_names:
                    yearly_data = []
                    for year in ds.year.values:
                        gis_year = ds_GIS.sel(year=int(year))[var]
                        gis_interp = gis_year.interp(latitude=ds.latitude, longitude=ds.longitude, method="linear")
                        yearly_data.append(gis_interp)
                    data_vars[var] = xr.concat(yearly_data, dim="valid_time")
                return ds.assign(**data_vars).drop_vars("year")

            # ---------------------- Add GIS variables to dataset ----------------------
            ds_meteo_missing = add_yearly_vars(ds_meteo_missing, ds_GIS, list(ds_GIS.data_vars))

        # ---------------------- Load Portugal cells GeoPackage ----------------------
        cells_path = Path("backend/utils/Data/Portugal_cells.gpkg")
        fallback_cells_path = Path("utils/Data/Portugal_cells.gpkg")

        if not cells_path.exists():
            cells_path = fallback_cells_path

        gdf_cells = gpd.read_file(cells_path)
        if gdf_cells.crs.to_string() != "EPSG:4326":
            gdf_cells = gdf_cells.to_crs("EPSG:4326")
        cells_union = gdf_cells.geometry.union_all()

        # ---------------------- Create spatial mask ----------------------
        lon = ds_meteo_missing.longitude.values
        lat = ds_meteo_missing.latitude.values
        lon_grid, lat_grid = np.meshgrid(lon, lat, indexing='xy')
        points = [Point(lon_val, lat_val) for lon_val, lat_val in zip(lon_grid.ravel(), lat_grid.ravel())]

        print("Creating spatial mask... this may take a moment")
        mask = np.array([cells_union.contains(pt) for pt in points])
        mask_2d = mask.reshape(len(lat), len(lon))
        mask_da = xr.DataArray(mask_2d, coords=[ds_meteo_missing.latitude, ds_meteo_missing.longitude], dims=["latitude", "longitude"])

        # ---------------------- Apply mask ----------------------
        ds_filtered_missing = ds_meteo_missing.where(mask_da)
        print("Dataset filtered by spatial mask")

        # ---------------------- Merge with existing dataset ----------------------
        if ds_complete is not None:
            ds_complete = xr.concat([ds_complete, ds_filtered_missing], dim="valid_time")
            valid_times = pd.Index(ds_complete.valid_time.values)
            ds_complete = ds_complete.sel(valid_time=~valid_times.duplicated())
        else:
            ds_complete = ds_filtered_missing

        # ---------------------- Save updated NetCDF ----------------------
        ds_complete.to_netcdf(netcdf_path)
        print(f"Saved/updated FireData NetCDF at {netcdf_path}")

        ds_filtered = ds_complete.sel(valid_time=required_times)

    # ---------------------- Calculate cumulative mean per duration ----------------------
    mean_list = []
    for dur in range(1, duration + 1):
        ds_slice = ds_filtered.isel(valid_time=slice(0, dur))
        ds_mean = ds_slice.mean(dim="valid_time")
        ds_mean = ds_mean.assign_coords(duration_hours=dur)
        mean_list.append(ds_mean)

    ds_mean_all = xr.concat(mean_list, dim="duration_hours")

    # ---------------------- Convert to DataFrame ----------------------
    df_all = ds_mean_all.to_dataframe().reset_index()
    df_all['s_time'] = start_time
    df_all['fstart'] = mins_since_fire_start

    data_cols = [c for c in df_all.columns if c not in ['latitude', 'longitude', 'duration_hours', 's_time']]
    df_all = df_all.dropna(subset=data_cols, how='all')

    df_all = df_all.sort_values(["s_time", "latitude", "longitude", "duration_hours"])[
        ["s_time", "latitude", "longitude", "duration_hours",
         "fuel_load", "pct_3_8", "pct_8p",
         "wv100_kh", "FWI_12h", "fstart"]
    ]

    return df_all
