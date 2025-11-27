"""
Create fuel load and fire percentage TIFs, then regrid both these TIFs and ERA5 NetCDF
data to the same perfectly aligned 0.1° grid for Portugal.

This ensures:
1. All data uses the exact same 0.1° grid
2. Perfect pixel alignment between weather and fuel/fire data
3. No aliasing issues from shifting grids
"""
import numpy as np
import xarray as xr
import rasterio
from rasterio.warp import reproject, Resampling, calculate_default_transform
from rasterio.transform import from_bounds
from rasterio.features import rasterize
import geopandas as gpd
from pathlib import Path
from typing import Dict, Tuple
import warnings

warnings.filterwarnings('ignore')


# ============================================================================
# FUEL LOAD TABLE (from notebook)
# ============================================================================
FUEL_LOAD_TABLE = {
    4:   34.67,   # Mato Alto com continuidade h e v
    98:  0.00,    # sem combustível
    221: 15.49,   # M-CAD
    222: 15.04,   # M-ESC
    223: 16.69,   # M-EUC
    227: 17.10,   # M-PIN
    231:  3.55,   # V-Ha
    232:  1.50,   # V-Hb
    233: 26.50,   # V-MAa
    234: 14.00,   # V-MAb
    235:  9.00,   # V-MH
    236: 23.00,   # V-MMa
    237: 11.50    # V-MMb
}


def define_0_1deg_grid_portugal() -> Tuple[float, float, float, float, int, int, rasterio.Affine]:
    """
    Define a standard 0.1° grid for Portugal.

    Returns:
    --------
    tuple: (minx, miny, maxx, maxy, width, height, transform)
    """
    # Portugal bounding box (rounded to 0.1° boundaries)
    minx = -10.0
    maxx = -6.0
    miny = 37.0
    maxy = 43.0

    # 0.1° resolution
    resolution = 0.1

    # Calculate dimensions
    width = int((maxx - minx) / resolution)
    height = int((maxy - miny) / resolution)

    # Create transform (pixel centers at 0.1° intervals)
    transform = from_bounds(minx, miny, maxx, maxy, width, height)

    print(f"Defined 0.1° grid for Portugal:")
    print(f"  Bounds: {minx}, {miny}, {maxx}, {maxy}")
    print(f"  Resolution: {resolution}°")
    print(f"  Dimensions: {width} x {height} pixels")
    print(f"  Transform: {transform}")

    return minx, miny, maxx, maxy, width, height, transform


def calc_mean_fuelload(geom, year, fuel_maps, fuel_load_table=FUEL_LOAD_TABLE):
    """Calculate mean fuel load for a geometry (from notebook)."""
    from rasterstats import zonal_stats

    fuel_path = fuel_maps.get(str(year))
    if not fuel_path or not fuel_path.exists():
        return np.nan

    with rasterio.open(fuel_path) as src:
        # Try pixels fully inside first
        stats_full = zonal_stats(
            geom,
            str(fuel_path),
            categorical=True,
            all_touched=False,
            nodata=src.nodata
        )

        if not stats_full or not stats_full[0]:
            # If no pixels fully inside, allow partially inside
            stats_full = zonal_stats(
                geom,
                str(fuel_path),
                categorical=True,
                all_touched=True,
                nodata=src.nodata
            )

    counts = stats_full[0]
    if not counts:
        return np.nan

    total_pixels = sum(counts.values())
    if total_pixels == 0:
        return np.nan

    weighted_sum = 0.0
    for fm, n in counts.items():
        fuel_load = fuel_load_table.get(fm)
        if fuel_load is not None:
            weighted_sum += fuel_load * n

    return weighted_sum / total_pixels if total_pixels > 0 else np.nan


def calc_fire_percentages(geom, year, fire_maps):
    """Calculate fire percentage for a geometry (from notebook)."""
    from rasterstats import zonal_stats

    results = {
        "1_3y_fir_p": 0.0,
        "3_8y_fir_p": 0.0,
        "8_ny_fir_p": 0.0
    }

    key = f"years_since_fire_{year}_p"
    if key not in fire_maps or not fire_maps[key].exists():
        return results

    fire_stats = zonal_stats(geom, str(fire_maps[key]), stats=None, nodata=None,
                            raster_out=True, all_touched=False)
    fire_arr = fire_stats[0]["mini_raster_array"]
    mask = fire_stats[0].get("mini_raster_mask")

    if hasattr(fire_arr, "filled"):
        fire_arr = fire_arr.filled(np.nan)
    fire_arr = fire_arr.astype(float)

    if mask is not None:
        fire_arr[mask] = np.nan

    valid = ~np.isnan(fire_arr)
    valid_values = fire_arr[valid]

    if valid_values.size == 0:
        return results

    total = valid_values.size
    fire_positive = valid_values[valid_values > 0]

    if total > 0:
        results["1_3y_fir_p"] = ((fire_positive >= 1) & (fire_positive <= 3)).sum() / total * 100
        results["3_8y_fir_p"] = ((fire_positive > 3) & (fire_positive <= 8)).sum() / total * 100
        results["8_ny_fir_p"] = (fire_positive > 8).sum() / total * 100

    return results


def create_fuel_fire_tifs(
    shapefile_path: str,
    fuel_maps_dir: str,
    fire_maps_dir: str,
    output_dir: str,
    target_transform: rasterio.Affine,
    target_width: int,
    target_height: int
):
    """
    Create fuel load and fire percentage TIFs on the target 0.1° grid.

    Parameters:
    -----------
    shapefile_path : str
        Path to shapefile with fire polygons
    fuel_maps_dir : str
        Directory containing fuel model TIFs
    fire_maps_dir : str
        Directory containing years since fire TIFs
    output_dir : str
        Output directory for created TIFs
    target_transform : rasterio.Affine
        Target grid transform
    target_width : int
        Target grid width
    target_height : int
        Target grid height
    """
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    print("\n" + "=" * 70)
    print("CREATING FUEL LOAD AND FIRE PERCENTAGE TIFS")
    print("=" * 70)

    # Load shapefile
    print(f"\nLoading shapefile: {shapefile_path}")
    gdf = gpd.read_file(shapefile_path)
    gdf = gdf.to_crs("EPSG:4326")  # Convert to WGS84
    print(f"  Loaded {len(gdf)} fire polygons")

    # Find fuel and fire maps
    fuel_path = Path(fuel_maps_dir)
    fire_path = Path(fire_maps_dir)

    fuel_maps = {p.parent.stem: p for p in fuel_path.rglob("fuelmap.tif")}
    fire_maps = {p.stem: p for p in fire_path.glob("years_since_fire_*_p.tif")}

    print(f"\nFound {len(fuel_maps)} fuel maps")
    print(f"Found {len(fire_maps)} fire maps")

    # Calculate fuel load and fire percentages for each polygon
    print("\nCalculating fuel load and fire percentages...")
    gdf["f_load_av"] = np.nan
    gdf["8_ny_fir_p"] = 0.0
    gdf["3_8y_fir_p"] = 0.0

    for idx, row in gdf.iterrows():
        if idx % 500 == 0:
            print(f"  Processing polygon {idx}/{len(gdf)}...")

        geom = row.geometry
        year = row["year"]

        # Calculate fuel load
        gdf.at[idx, "f_load_av"] = calc_mean_fuelload(geom, year, fuel_maps)

        # Calculate fire percentages
        fire_perc = calc_fire_percentages(geom, year, fire_maps)
        for col, val in fire_perc.items():
            gdf.at[idx, col] = val

    print(f"  Completed all {len(gdf)} polygons")

    # Export fuel load for each year
    print("\nExporting fuel load TIFs by year...")
    years = sorted(gdf['year'].unique())

    for year in years:
        gdf_year = gdf[gdf['year'] == year]

        if len(gdf_year) == 0:
            continue

        # Create shapes list
        shapes = [(geom, value) for geom, value in zip(gdf_year.geometry, gdf_year['f_load_av'])
                 if not np.isnan(value)]

        if len(shapes) == 0:
            continue

        # Rasterize directly to target grid
        raster = rasterize(
            shapes,
            out_shape=(target_height, target_width),
            transform=target_transform,
            fill=-9999,
            dtype=rasterio.float32
        )

        # Write to file
        output_file = output_path / f'fuel_load_{year}.tif'
        with rasterio.open(
            output_file,
            'w',
            driver='GTiff',
            height=target_height,
            width=target_width,
            count=1,
            dtype=rasterio.float32,
            crs='EPSG:4326',
            transform=target_transform,
            nodata=-9999,
            compress='lzw'
        ) as dst:
            dst.write(raster, 1)

        print(f"  Created {output_file.name} ({len(shapes)} polygons)")

    # Export fire percentage variables (aggregated across all years)
    print("\nExporting fire percentage TIFs...")

    fire_variables = {
        '8_ny_fir_p': '8_ny_fir_p.tif',
        '3_8y_fir_p': '3_8y_fir_p.tif'
    }

    for var_name, filename in fire_variables.items():
        shapes = [(geom, value) for geom, value in zip(gdf.geometry, gdf[var_name])
                 if not np.isnan(value) and value > 0]

        if len(shapes) == 0:
            print(f"  No data for {var_name}, skipping...")
            continue

        # Rasterize directly to target grid
        raster = rasterize(
            shapes,
            out_shape=(target_height, target_width),
            transform=target_transform,
            fill=-9999,
            dtype=rasterio.float32
        )

        # Write to file
        output_file = output_path / filename
        with rasterio.open(
            output_file,
            'w',
            driver='GTiff',
            height=target_height,
            width=target_width,
            count=1,
            dtype=rasterio.float32,
            crs='EPSG:4326',
            transform=target_transform,
            nodata=-9999,
            compress='lzw'
        ) as dst:
            dst.write(raster, 1)

        print(f"  Created {output_file.name} ({len(shapes)} polygons)")

    print("\nFuel and fire TIF creation complete!")


def regrid_netcdf_to_0_1deg(
    input_nc: str,
    output_nc: str,
    target_transform: rasterio.Affine,
    target_width: int,
    target_height: int
):
    """
    Regrid a NetCDF file to 0.1° grid.

    Parameters:
    -----------
    input_nc : str
        Input NetCDF file
    output_nc : str
        Output NetCDF file
    target_transform : rasterio.Affine
        Target grid transform
    target_width : int
        Target grid width
    target_height : int
        Target grid height
    """
    print(f"\nRegridding {Path(input_nc).name} to 0.1° grid...")

    # Open input dataset
    ds = xr.open_dataset(input_nc)

    # Get original coordinates
    lat_name = 'latitude' if 'latitude' in ds.coords else 'lat'
    lon_name = 'longitude' if 'longitude' in ds.coords else 'lon'

    src_lats = ds[lat_name].values
    src_lons = ds[lon_name].values

    # Create source transform
    src_transform = from_bounds(
        src_lons.min(), src_lats.min(),
        src_lons.max(), src_lats.max(),
        len(src_lons), len(src_lats)
    )

    # Create target lat/lon arrays
    # Extract from transform
    target_lons = np.array([target_transform * (i + 0.5, 0) for i in range(target_width)])[:, 0]
    target_lats = np.array([target_transform * (0, j + 0.5) for j in range(target_height)])[:, 1]

    # Regrid each variable
    regridded_vars = {}

    for var_name in ds.data_vars:
        print(f"  Regridding variable: {var_name}")

        var = ds[var_name]

        # Create output array
        dst_array = np.full((target_height, target_width), np.nan, dtype=np.float32)

        # Get source data
        if len(var.shape) == 2:
            src_data = var.values
        elif len(var.shape) == 3 and 'valid_time' in var.dims:
            # Take mean over time
            src_data = var.mean(dim='valid_time').values
        else:
            print(f"    Skipping {var_name}: unsupported dimensions")
            continue

        # Reproject using rasterio
        reproject(
            source=src_data,
            destination=dst_array,
            src_transform=src_transform,
            src_crs='EPSG:4326',
            dst_transform=target_transform,
            dst_crs='EPSG:4326',
            resampling=Resampling.bilinear
        )

        regridded_vars[var_name] = (('latitude', 'longitude'), dst_array)
        print(f"    Regridded to shape: {dst_array.shape}")

    # Create new dataset
    ds_regridded = xr.Dataset(
        regridded_vars,
        coords={
            'latitude': target_lats,
            'longitude': target_lons
        }
    )

    # Copy attributes
    for var_name in regridded_vars:
        if var_name in ds.data_vars:
            ds_regridded[var_name].attrs = ds[var_name].attrs

    # Save
    ds_regridded.to_netcdf(output_nc, engine='netcdf4')
    print(f"  Saved: {output_nc}")

    ds.close()


# ============================================================================
# MAIN EXECUTION
# ============================================================================
if __name__ == "__main__":
    print("=" * 70)
    print("CREATING ALIGNED 0.1° GRIDS FOR PORTUGAL")
    print("=" * 70)

    # Define paths - ADJUST THESE AS NEEDED
    SHAPEFILE = "Data/Interim/PT-FireSprd_v2.1/L2_FireBehavior/PT-FireProg_v2.1_L2_valid.shp"
    FUEL_MAPS_DIR = "Data/Interim/GIS_data/fuel_models/100m/portugal/PT-FireSprd"
    FIRE_MAPS_DIR = "/Volumes/Externo/PT-FireSprd/"
    OUTPUT_DIR = "Data/web_rasters"
    NETCDF_INPUT = "Data/web_cache/calculated_vars.nc"
    NETCDF_OUTPUT = "Data/web_rasters/calculated_vars_0.1deg.nc"

    # Step 1: Define standard 0.1° grid
    minx, miny, maxx, maxy, width, height, transform = define_0_1deg_grid_portugal()

    # Step 2: Create fuel and fire TIFs on this grid
    try:
        create_fuel_fire_tifs(
            SHAPEFILE,
            FUEL_MAPS_DIR,
            FIRE_MAPS_DIR,
            OUTPUT_DIR,
            transform,
            width,
            height
        )
    except Exception as e:
        print(f"\nError creating fuel/fire TIFs: {e}")
        print("Continuing with NetCDF regridding...")

    # Step 3: Regrid NetCDF to same grid
    try:
        regrid_netcdf_to_0_1deg(
            NETCDF_INPUT,
            NETCDF_OUTPUT,
            transform,
            width,
            height
        )
    except Exception as e:
        print(f"\nError regridding NetCDF: {e}")

    print("\n" + "=" * 70)
    print("COMPLETE!")
    print("=" * 70)
    print(f"\nAll outputs are on the same 0.1° grid:")
    print(f"  Resolution: 0.1° x 0.1°")
    print(f"  Dimensions: {width} x {height}")
    print(f"  Bounds: {minx}°W to {maxx}°W, {miny}°N to {maxy}°N")
    print(f"\nOutput directory: {OUTPUT_DIR}")
