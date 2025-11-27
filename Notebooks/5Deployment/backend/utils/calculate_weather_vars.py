"""
This script calculates weather variables from downloaded CDS API NetCDF files.
Calculates: sW_100_av, FWI_12h_av, wv100_k_av, wv_850_av, Cape_av, gT_8_7_av
Output: NetCDF file with calculated variables for the entire grid.
"""
import numpy as np
import xarray as xr
from metpy.units import units
from pathlib import Path
from typing import Dict


def calculate_weather_variables(
    sl_file: str,
    pl_file: str,
    fwi_file: str,
    output_file: str = None
) -> xr.Dataset:
    """
    Calculate weather variables from CDS API NetCDF files for the entire grid.

    Parameters:
    -----------
    sl_file : str
        Path to ERA5 single levels NetCDF file
    pl_file : str
        Path to ERA5 pressure levels NetCDF file
    fwi_file : str
        Path to CEMS Fire Weather Index NetCDF file
    output_file : str, optional
        Path to save the output NetCDF file with calculated variables

    Returns:
    --------
    xr.Dataset: Dataset containing calculated variables with dimensions (duration, latitude, longitude):
        - sW_100_av: Soil water at 100cm depth (m³/m³) - cumulative time averaged
        - FWI_12h_av: Fire Weather Index (dimensionless) - cumulative time averaged
        - wv100_k_av: Wind speed at 100m (km/h) - cumulative time averaged
        - wv_850_av: Wind speed at 850 hPa (km/h) - cumulative time averaged
        - Cape_av: Convective Available Potential Energy (J/kg) - cumulative time averaged
        - gT_8_7_av: Temperature gradient 850-700 hPa (°C/km) - cumulative time averaged

        The 'duration' coordinate contains values [1, 2, 3, 4] representing:
        - duration=1: Average of hour 0 only
        - duration=2: Average of hours 0-1
        - duration=3: Average of hours 0-2
        - duration=4: Average of hours 0-3
    """

    # ==================== LOAD DATASETS ====================
    print(f"Loading datasets...")
    ds_SL = xr.open_dataset(sl_file, engine="netcdf4")
    ds_PL = xr.open_dataset(pl_file, engine="netcdf4")
    ds_FWI = xr.open_dataset(fwi_file, engine="netcdf4")

    print(f"ERA5 Single Levels grid shape: {ds_SL.dims}")
    print(f"ERA5 Pressure Levels grid shape: {ds_PL.dims}")
    print(f"FWI grid shape: {ds_FWI.dims}")

    # ==================== INSPECT AND RENAME VARIABLES ====================
    print(f"Available variables in Single Levels: {list(ds_SL.data_vars.keys())}")
    print(f"Available variables in Pressure Levels: {list(ds_PL.data_vars.keys())}")
    print(f"Available variables in FWI: {list(ds_FWI.data_vars.keys())}")

    # Single levels
    rename_map_sl = {}
    if "u100" in ds_SL.data_vars:
        rename_map_sl["u100"] = "u100_ms"
    if "v100" in ds_SL.data_vars:
        rename_map_sl["v100"] = "v100_ms"
    if "swvl3" in ds_SL.data_vars:
        rename_map_sl["swvl3"] = "sW_100"
    if "cape" in ds_SL.data_vars:
        rename_map_sl["cape"] = "Cape"
    if "sp" in ds_SL.data_vars:
        rename_map_sl["sp"] = "sP_Pa"

    ds_SL = ds_SL.rename(rename_map_sl)

    # Pressure levels
    rename_map_pl = {}
    if "u" in ds_PL.data_vars:
        rename_map_pl["u"] = "u_ms"
    if "v" in ds_PL.data_vars:
        rename_map_pl["v"] = "v_ms"
    if "t" in ds_PL.data_vars:
        rename_map_pl["t"] = "t_K"
    if "z" in ds_PL.data_vars:
        rename_map_pl["z"] = "gp"

    ds_PL = ds_PL.rename(rename_map_pl)

    # Fire Weather Index
    rename_map_fwi = {}
    if "fwinx" in ds_FWI.data_vars:
        rename_map_fwi["fwinx"] = "FWI_12h"

    ds_FWI = ds_FWI.rename(rename_map_fwi)

    # ==================== REGRID FWI TO MATCH ERA5 GRID ====================
    # FWI data comes as unstructured grid (1D with lat/lon coordinates)
    # Need to regrid to match ERA5 2D grid
    print("Regridding FWI data to match ERA5 grid...")

    # Get target coordinates from ERA5
    target_lats = ds_SL['latitude'].values
    target_lons = ds_SL['longitude'].values

    # Check if FWI has structured or unstructured grid
    if 'values' in ds_FWI.dims:
        # Unstructured grid - need to interpolate from scattered points
        print("  FWI has unstructured grid, interpolating to ERA5 grid...")

        from scipy.interpolate import griddata

        # Get FWI coordinates (1D arrays)
        fwi_lats = ds_FWI['latitude'].values
        fwi_lons = ds_FWI['longitude'].values

        # Convert longitude from 0-360 to -180-180 if needed
        if fwi_lons.max() > 180:
            print(f"    Converting FWI longitudes from 0-360 to -180-180 format")
            fwi_lons = np.where(fwi_lons > 180, fwi_lons - 360, fwi_lons)

        # Create 2D meshgrid for target
        target_lon_2d, target_lat_2d = np.meshgrid(target_lons, target_lats)

        # Create new dataset with regridded data
        regridded_vars = {}
        for var_name in ['FWI_12h']:
            if var_name in ds_FWI.data_vars:
                print(f"    Regridding variable: {var_name}")

                # Get data for each timestep
                var_data = ds_FWI[var_name]
                n_times = len(ds_FWI['valid_time'])

                # Initialize output array
                regridded = np.zeros((n_times, len(target_lats), len(target_lons)), dtype=np.float32)

                for t in range(n_times):
                    # Get values for this timestep
                    values = var_data.isel(valid_time=t).values

                    # Interpolate using scipy griddata (linear first, then fill with nearest)
                    regridded_linear = griddata(
                        (fwi_lons, fwi_lats),
                        values,
                        (target_lon_2d, target_lat_2d),
                        method='linear',
                        fill_value=np.nan
                    )

                    # Fill NaN values with nearest neighbor interpolation
                    if np.isnan(regridded_linear).any():
                        regridded_nearest = griddata(
                            (fwi_lons, fwi_lats),
                            values,
                            (target_lon_2d, target_lat_2d),
                            method='nearest'
                        )
                        # Fill NaN values from linear with nearest
                        regridded[t] = np.where(np.isnan(regridded_linear), regridded_nearest, regridded_linear)
                    else:
                        regridded[t] = regridded_linear

                # Create DataArray
                regridded_vars[var_name] = (
                    ['valid_time', 'latitude', 'longitude'],
                    regridded
                )

        # Create new dataset
        ds_FWI = xr.Dataset(
            regridded_vars,
            coords={
                'valid_time': ds_FWI['valid_time'],
                'latitude': target_lats,
                'longitude': target_lons
            }
        )
        print("  Regridding complete!")

    else:
        # Already structured grid - check if dimensions match
        fwi_lat_name = 'latitude' if 'latitude' in ds_FWI.dims else 'lat'
        fwi_lon_name = 'longitude' if 'longitude' in ds_FWI.dims else 'lon'

        fwi_lats = ds_FWI[fwi_lat_name].values
        fwi_lons = ds_FWI[fwi_lon_name].values

        if len(fwi_lats) != len(target_lats) or len(fwi_lons) != len(target_lons):
            print(f"  FWI grid: {len(fwi_lats)}x{len(fwi_lons)}, ERA5 grid: {len(target_lats)}x{len(target_lons)}")
            print("  Performing interpolation...")

            # Regrid using xarray interpolation
            ds_FWI_regridded = ds_FWI.interp(
                {fwi_lat_name: target_lats, fwi_lon_name: target_lons},
                method='linear'
            )

            # Rename coordinates to match ERA5 convention
            if fwi_lat_name != 'latitude':
                ds_FWI_regridded = ds_FWI_regridded.rename({fwi_lat_name: 'latitude'})
            if fwi_lon_name != 'longitude':
                ds_FWI_regridded = ds_FWI_regridded.rename({fwi_lon_name: 'longitude'})

            ds_FWI = ds_FWI_regridded
            print("  Regridding complete!")
        else:
            print("  FWI grid already matches ERA5 grid, no regridding needed")

    # ==================== UNIT CONVERSIONS ====================
    print("Converting units...")

    # --- 100m Wind Components: m/s to km/h ---
    ds_SL["u100_ms"] = ds_SL["u100_ms"] * (units.meter / units.second)
    ds_SL["v100_ms"] = ds_SL["v100_ms"] * (units.meter / units.second)
    ds_SL["u100_kh"] = ds_SL["u100_ms"].metpy.convert_units("km/h")
    ds_SL["v100_kh"] = ds_SL["v100_ms"].metpy.convert_units("km/h")

    # --- Pressure Level Wind Components: m/s to km/h ---
    ds_PL["u_ms"] = ds_PL["u_ms"] * (units.meter / units.second)
    ds_PL["v_ms"] = ds_PL["v_ms"] * (units.meter / units.second)
    ds_PL["u_kh"] = ds_PL["u_ms"].metpy.convert_units("km/h")
    ds_PL["v_kh"] = ds_PL["v_ms"].metpy.convert_units("km/h")

    # --- Temperature: K to °C ---
    ds_PL["t_K"] = ds_PL["t_K"] * units.kelvin
    ds_PL["t_C"] = ds_PL["t_K"].metpy.convert_units("degC")

    # --- Surface Pressure: Pa to hPa (if available) ---
    has_surface_pressure = "sP_Pa" in ds_SL.data_vars
    if has_surface_pressure:
        ds_SL["sP_Pa"] = ds_SL["sP_Pa"] * units.pascal
        ds_SL["sP_hPa"] = ds_SL["sP_Pa"].metpy.convert_units("hPa")

    # ==================== CALCULATE DERIVED VARIABLES ====================
    print("Calculating derived variables with cumulative averaging...")

    # Get number of timesteps
    n_timesteps = len(ds_SL['valid_time'])
    print(f"Processing {n_timesteps} timesteps")

    # Calculate intermediate variables (not time-averaged yet)
    # --- 3. wv100_k: Wind Speed at 100m (km/h) ---
    u100_kh = ds_SL["u100_kh"].metpy.dequantify()
    v100_kh = ds_SL["v100_kh"].metpy.dequantify()
    wv100_k = np.sqrt(u100_kh**2 + v100_kh**2)

    # --- 4. wv_850: Wind Speed at 850 hPa (km/h) ---
    u_850_kh = ds_PL["u_kh"].sel(pressure_level=850).metpy.dequantify()
    v_850_kh = ds_PL["v_kh"].sel(pressure_level=850).metpy.dequantify()
    wv_850 = np.sqrt(u_850_kh**2 + v_850_kh**2)

    # --- 6. gT_8_7: Temperature Gradient 850-700 hPa (°C/km) ---
    t_850 = ds_PL["t_C"].sel(pressure_level=850).metpy.dequantify()
    t_700 = ds_PL["t_C"].sel(pressure_level=700).metpy.dequantify()
    z_850 = ds_PL["gp"].sel(pressure_level=850) / 9.80665  # Convert to meters
    z_700 = ds_PL["gp"].sel(pressure_level=700) / 9.80665

    # Calculate temperature gradient (°C/km)
    gT_8_7 = (t_850 - t_700) / ((z_700 - z_850) / 1000.0)

    # Apply surface pressure mask if available
    if has_surface_pressure:
        psfc = ds_SL["sP_hPa"].metpy.dequantify()
        mask_valid = psfc > 720
        gT_8_7 = gT_8_7.where(mask_valid, -999)
    else:
        print("Warning: Surface pressure not available. Temperature gradient calculated without masking.")

    # ==================== CUMULATIVE AVERAGING ====================
    # Create outputs for duration 1, 2, 3, 4 (cumulative averages)
    print("Computing cumulative averages for each duration...")

    durations = np.arange(1, min(n_timesteps + 1, 5))  # [1, 2, 3, 4]
    n_durations = len(durations)

    # Initialize output arrays
    lat_coords = ds_SL['latitude']
    lon_coords = ds_SL['longitude']
    n_lat = len(lat_coords)
    n_lon = len(lon_coords)

    sW_100_av = np.zeros((n_durations, n_lat, n_lon), dtype=np.float32)
    FWI_12h_av = np.zeros((n_durations, n_lat, n_lon), dtype=np.float32)
    wv100_k_av = np.zeros((n_durations, n_lat, n_lon), dtype=np.float32)
    wv_850_av = np.zeros((n_durations, n_lat, n_lon), dtype=np.float32)
    Cape_av = np.zeros((n_durations, n_lat, n_lon), dtype=np.float32)
    gT_8_7_av = np.zeros((n_durations, n_lat, n_lon), dtype=np.float32)

    # Check if FWI has enough timesteps
    n_fwi_times = len(ds_FWI['valid_time'])
    if n_fwi_times < n_timesteps:
        print(f"  Warning: FWI has only {n_fwi_times} timestep(s), while ERA5 has {n_timesteps}")
        print(f"  FWI values will be replicated across all durations")

    # Compute cumulative averages
    for i, duration in enumerate(durations):
        print(f"  Computing averages for duration {duration}h...")

        # Average from timestep 0 to timestep (duration-1)
        sW_100_av[i] = ds_SL["sW_100"].isel(valid_time=slice(0, duration)).mean(dim='valid_time').values

        # FWI: if only 1 timestep available, use it for all durations
        if n_fwi_times == 1:
            FWI_12h_av[i] = ds_FWI["FWI_12h"].isel(valid_time=0).values
        else:
            FWI_12h_av[i] = ds_FWI["FWI_12h"].isel(valid_time=slice(0, min(duration, n_fwi_times))).mean(dim='valid_time').values

        wv100_k_av[i] = wv100_k.isel(valid_time=slice(0, duration)).mean(dim='valid_time').values
        wv_850_av[i] = wv_850.isel(valid_time=slice(0, duration)).mean(dim='valid_time').values
        Cape_av[i] = ds_SL["Cape"].isel(valid_time=slice(0, duration)).mean(dim='valid_time').values

        # Handle gT_8_7 with -999 masking
        if has_surface_pressure:
            gT_slice = gT_8_7.isel(valid_time=slice(0, duration))
            # Average only valid values (not -999)
            gT_8_7_av[i] = xr.where(
                (gT_slice == -999).all(dim='valid_time'),  # If all timesteps are -999
                -999,  # Keep as -999
                gT_slice.where(gT_slice != -999).mean(dim='valid_time')  # Otherwise average valid values
            ).values
        else:
            gT_8_7_av[i] = gT_8_7.isel(valid_time=slice(0, duration)).mean(dim='valid_time').values

    # Convert to xarray DataArrays with duration dimension
    sW_100_av = xr.DataArray(sW_100_av, coords={'duration': durations, 'latitude': lat_coords, 'longitude': lon_coords}, dims=['duration', 'latitude', 'longitude'])
    FWI_12h_av = xr.DataArray(FWI_12h_av, coords={'duration': durations, 'latitude': lat_coords, 'longitude': lon_coords}, dims=['duration', 'latitude', 'longitude'])
    wv100_k_av = xr.DataArray(wv100_k_av, coords={'duration': durations, 'latitude': lat_coords, 'longitude': lon_coords}, dims=['duration', 'latitude', 'longitude'])
    wv_850_av = xr.DataArray(wv_850_av, coords={'duration': durations, 'latitude': lat_coords, 'longitude': lon_coords}, dims=['duration', 'latitude', 'longitude'])
    Cape_av = xr.DataArray(Cape_av, coords={'duration': durations, 'latitude': lat_coords, 'longitude': lon_coords}, dims=['duration', 'latitude', 'longitude'])
    gT_8_7_av = xr.DataArray(gT_8_7_av, coords={'duration': durations, 'latitude': lat_coords, 'longitude': lon_coords}, dims=['duration', 'latitude', 'longitude'])

    # ==================== CREATE OUTPUT DATASET ====================
    print("Creating output dataset...")

    # Create new dataset with calculated variables
    ds_output = xr.Dataset(
        {
            'sW_100_av': sW_100_av,
            'FWI_12h_av': FWI_12h_av,
            'wv100_k_av': wv100_k_av,
            'wv_850_av': wv_850_av,
            'Cape_av': Cape_av,
            'gT_8_7_av': gT_8_7_av
        },
        coords={
            'duration': durations,
            'latitude': lat_coords,
            'longitude': lon_coords
        }
    )

    # Add coordinate metadata
    ds_output['duration'].attrs = {
        'long_name': 'Fire duration (hours)',
        'units': 'hours',
        'description': 'Cumulative averaging window. duration=N means average of hours 0 to N-1'
    }

    # Add variable metadata
    ds_output['sW_100_av'].attrs = {
        'long_name': 'Soil water at 100cm depth (cumulative time-averaged)',
        'units': 'm³/m³',
        'description': 'Volumetric soil water content at layer 3 (~100cm depth), cumulative average over duration'
    }
    ds_output['FWI_12h_av'].attrs = {
        'long_name': 'Fire Weather Index (cumulative time-averaged)',
        'units': 'dimensionless',
        'description': '12-hourly Fire Weather Index from CEMS, cumulative average over duration'
    }
    ds_output['wv100_k_av'].attrs = {
        'long_name': 'Wind speed at 100m (cumulative time-averaged)',
        'units': 'km/h',
        'description': 'Wind speed magnitude at 100m height, cumulative average over duration'
    }
    ds_output['wv_850_av'].attrs = {
        'long_name': 'Wind speed at 850 hPa (cumulative time-averaged)',
        'units': 'km/h',
        'description': 'Wind speed magnitude at 850 hPa pressure level, cumulative average over duration'
    }
    ds_output['Cape_av'].attrs = {
        'long_name': 'Convective Available Potential Energy (cumulative time-averaged)',
        'units': 'J/kg',
        'description': 'CAPE - measure of atmospheric instability, cumulative average over duration'
    }
    ds_output['gT_8_7_av'].attrs = {
        'long_name': 'Temperature gradient 850-700 hPa (cumulative time-averaged)',
        'units': '°C/km',
        'description': 'Temperature lapse rate between 850 and 700 hPa, cumulative average over duration. -999 indicates invalid data.',
        'valid_min': -999
    }

    # ==================== SAVE OUTPUT ====================
    if output_file:
        print(f"Saving output to {output_file}...")
        ds_output.to_netcdf(output_file, engine='netcdf4')
        print("Done!")

    # ==================== CLOSE DATASETS ====================
    ds_SL.close()
    ds_PL.close()
    ds_FWI.close()

    return ds_output


def calculate_weather_variables_from_files(
    files: Dict[str, Path],
    output_file: str = None
) -> xr.Dataset:
    """
    Convenience wrapper that takes the output from fetch_era5_data().

    Parameters:
    -----------
    files : dict
        Dictionary with keys 'single_levels', 'pressure_levels', 'fwi'
        containing Paths to downloaded NetCDF files
    output_file : str, optional
        Path to save the output NetCDF file with calculated variables

    Returns:
    --------
    xr.Dataset: Dataset containing calculated weather variables with dimensions
                (duration, latitude, longitude). Duration coordinate contains
                [1, 2, 3, 4] representing cumulative averages over 1-4 hours.
    """
    return calculate_weather_variables(
        sl_file=str(files['single_levels']),
        pl_file=str(files['pressure_levels']),
        fwi_file=str(files['fwi']),
        output_file=output_file
    )


def find_latest_era5_files(cache_dir: str = "Data/web_cache/") -> Dict[str, Path]:
    """
    Scan the cache directory for the latest ERA5 NetCDF files.

    Parameters:
    -----------
    cache_dir : str
        Path to the cache directory containing downloaded NetCDF files

    Returns:
    --------
    dict: Dictionary with keys 'single_levels', 'pressure_levels', 'fwi'
          containing Paths to the latest NetCDF files
    """
    cache_path = Path(cache_dir)

    if not cache_path.exists():
        raise FileNotFoundError(f"Cache directory not found: {cache_dir}")

    # Find files by pattern
    sl_files = sorted(cache_path.glob("ERA5_SL_*.nc"))
    pl_files = sorted(cache_path.glob("ERA5_PL_*.nc"))
    fwi_files = sorted(cache_path.glob("ERA5_FWI_*.nc"))

    if not sl_files:
        raise FileNotFoundError(f"No ERA5 Single Levels files found in {cache_dir}")
    if not pl_files:
        raise FileNotFoundError(f"No ERA5 Pressure Levels files found in {cache_dir}")
    if not fwi_files:
        raise FileNotFoundError(f"No ERA5 FWI files found in {cache_dir}")

    # Get the latest file from each category (by filename, which includes timestamp)
    latest_files = {
        'single_levels': sl_files[-1],
        'pressure_levels': pl_files[-1],
        'fwi': fwi_files[-1]
    }

    print(f"Found latest files:")
    print(f"  Single Levels: {latest_files['single_levels'].name}")
    print(f"  Pressure Levels: {latest_files['pressure_levels'].name}")
    print(f"  FWI: {latest_files['fwi'].name}")

    return latest_files


# Example usage
if __name__ == "__main__":
    # Scan for existing NetCDF files in cache
    print("Scanning Data/web_cache/ for NetCDF files...")
    files = find_latest_era5_files()

    # Calculate variables for the entire grid
    print("\nCalculating weather variables for entire grid...")
    output_path = "Data/web_cache/calculated_vars.nc"
    ds_result = calculate_weather_variables_from_files(files, output_file=output_path)

    # Print summary
    print("\nCalculated Variables:")
    print("=" * 60)
    print(f"Durations: {ds_result['duration'].values}")
    print(f"Grid shape (lat, lon): ({len(ds_result['latitude'])}, {len(ds_result['longitude'])})")

    for var_name in ds_result.data_vars:
        var_data = ds_result[var_name]
        print(f"\n{var_name}:")
        print(f"  Shape (duration, lat, lon): {var_data.shape}")
        print(f"  Overall Min: {float(var_data.min().values):.4f}")
        print(f"  Overall Max: {float(var_data.max().values):.4f}")
        print(f"  Overall Mean: {float(var_data.mean().values):.4f}")

        # Print stats by duration
        for duration in ds_result['duration'].values:
            slice_data = var_data.sel(duration=duration)
            print(f"    Duration {duration}h - Mean: {float(slice_data.mean().values):.4f}")
