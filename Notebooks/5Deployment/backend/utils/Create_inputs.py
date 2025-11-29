"""
This script compiles meteorological and GIS data for fire analysis.
It merges meteorological variables with GIS layers, applies spatial masks, 
and calculates cumulative mean datasets over the requested duration.
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

import Meteo_dataset
importlib.reload(Meteo_dataset)


def Compile_data(duration, mins_since_fire_start, start_time):
    """
    Compile meteorological and GIS data for a fire event.

    This function assembles meteorological data for the requested duration,
    enriches it with GIS variables (fuel, slope, etc.), applies a spatial mask
    for Portugal cells, and calculates cumulative mean datasets per hour.
    
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

    # ---------------------- Assemble meteorological dataset ----------------------
    ds_complete = Meteo_dataset.assemble_meteorological_data(start_time, duration)

    # ---------------------- Open GIS dataset ----------------------
    ds_GIS = xr.open_dataset("Data/GIS_data.nc")
    ds_GIS = ds_GIS.rename({"lat": "latitude", "lon": "longitude"})

    # ---------------------- Extract year coordinate ----------------------
    ds_complete = ds_complete.assign_coords(
        year=("valid_time", ds_complete.valid_time.dt.year.values)
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
    ds_complete = add_yearly_vars(ds_complete, ds_GIS, list(ds_GIS.data_vars))

    # ---------------------- Add fire start time variable ----------------------
    fstart_data = xr.full_like(
        ds_complete[list(ds_complete.data_vars.keys())[0]], 
        mins_since_fire_start, 
        dtype=int
    )
    fstart_data = fstart_data.drop_vars([var for var in fstart_data.coords if var not in ['latitude', 'longitude', 'valid_time']])
    ds_complete = ds_complete.assign(fstart=fstart_data)

    # ---------------------- Load Portugal cells GeoPackage ----------------------
    cells_fp = "Data/Portugal_cells.gpkg"
    gdf_cells = gpd.read_file(cells_fp)

    # ---------------------- Transform CRS to WGS84 ----------------------
    if gdf_cells.crs.to_string() != "EPSG:4326":
        gdf_cells = gdf_cells.to_crs("EPSG:4326")

    # ---------------------- Combine geometries ----------------------
    cells_union = gdf_cells.geometry.unary_union

    # ---------------------- Create grid points ----------------------
    lon = ds_complete.longitude.values
    lat = ds_complete.latitude.values
    lon_grid, lat_grid = np.meshgrid(lon, lat, indexing='xy')
    points = [Point(lon_val, lat_val) for lon_val, lat_val in zip(lon_grid.ravel(), lat_grid.ravel())]

    # ---------------------- Create spatial mask ----------------------
    print("Creating spatial mask... this may take a moment")
    mask = np.array([cells_union.contains(pt) for pt in points])
    mask_2d = mask.reshape(len(lat), len(lon))

    mask_da = xr.DataArray(
        mask_2d, 
        coords=[ds_complete.latitude, ds_complete.longitude],
        dims=["latitude", "longitude"]
    )

    # ---------------------- Apply mask ----------------------
    ds_filtered = ds_complete.where(mask_da)
    print("Dataset filtered by spatial mask")

    # ---------------------- Calculate cumulative mean per duration ----------------------
    mean_list = []
    for dur in range(1, duration + 1):
        ds_slice = ds_filtered.isel(valid_time=slice(0, dur))
        ds_mean = ds_slice.mean(dim="valid_time")
        ds_mean = ds_mean.assign_coords(duration_hours=dur)
        mean_list.append(ds_mean)

    ds_mean_all = xr.concat(mean_list, dim="duration_hours")

    # ---------------------- Convert to DataFrame ----------------------
    # Converter Dataset para DataFrame
    df_all = ds_mean_all.to_dataframe().reset_index()

    # Selecionar apenas as colunas de dados (excluindo coordenadas)
    data_cols = [c for c in df_all.columns if c not in ['latitude', 'longitude', 'duration_hours']]

    # Remover linhas onde **todas as variáveis de dados são NaN**
    df_all = df_all.dropna(subset=data_cols, how='all')

    return df_all
