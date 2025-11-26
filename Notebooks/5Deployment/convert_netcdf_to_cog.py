"""
Convert NetCDF raster data to Cloud-Optimized GeoTIFF (COG) for web deployment
Resamples to 0.1° resolution and optimizes for web serving
"""

import xarray as xr
import rasterio
from rasterio.transform import from_bounds
from rasterio.crs import CRS
import numpy as np
from pathlib import Path
import subprocess
import os


def netcdf_to_cog(
    input_nc_path,
    output_cog_path,
    variable_name=None,
    target_resolution=0.1,
    compression='DEFLATE',
    nodata_value=-9999
):
    """
    Convert NetCDF to Cloud-Optimized GeoTIFF

    Parameters:
    -----------
    input_nc_path : str
        Path to input NetCDF file
    output_cog_path : str
        Path to output COG file
    variable_name : str, optional
        Variable to extract (if None, uses first data variable)
    target_resolution : float
        Target resolution in degrees (default 0.1)
    compression : str
        Compression algorithm (DEFLATE, LZW, ZSTD)
    nodata_value : float
        NoData value for output raster
    """

    print(f"📂 Loading NetCDF: {input_nc_path}")
    ds = xr.open_dataset(input_nc_path)

    # Select variable
    if variable_name is None:
        variable_name = list(ds.data_vars)[0]
        print(f"   Using variable: {variable_name}")

    data_array = ds[variable_name]

    # Resample to target resolution
    print(f"🔄 Resampling to {target_resolution}° resolution...")

    # Get original bounds
    lon_min, lon_max = float(data_array.lon.min()), float(data_array.lon.max())
    lat_min, lat_max = float(data_array.lat.min()), float(data_array.lat.max())

    # Create new coordinate arrays at target resolution
    new_lon = np.arange(lon_min, lon_max, target_resolution)
    new_lat = np.arange(lat_min, lat_max, target_resolution)

    # Resample using xarray interpolation
    data_resampled = data_array.interp(
        lon=new_lon,
        lat=new_lat,
        method='linear'
    )

    # Convert to numpy array
    data_np = data_resampled.values

    # Handle time dimension if present
    if len(data_np.shape) == 3:
        print(f"   Found time dimension, using first timestep")
        data_np = data_np[0, :, :]

    # Replace NaN with nodata value
    data_np = np.where(np.isnan(data_np), nodata_value, data_np)

    # Flip latitude if needed (GeoTIFF expects top-left origin)
    if new_lat[0] < new_lat[-1]:
        data_np = np.flip(data_np, axis=0)
        new_lat = new_lat[::-1]

    # Create temporary GeoTIFF
    temp_tif = output_cog_path.replace('.tif', '_temp.tif')

    # Calculate transform
    transform = from_bounds(
        lon_min, lat_min, lon_max, lat_max,
        data_np.shape[1], data_np.shape[0]
    )

    # Write temporary GeoTIFF
    print(f"💾 Writing temporary GeoTIFF...")
    with rasterio.open(
        temp_tif,
        'w',
        driver='GTiff',
        height=data_np.shape[0],
        width=data_np.shape[1],
        count=1,
        dtype=data_np.dtype,
        crs=CRS.from_epsg(4326),
        transform=transform,
        nodata=nodata_value,
        compress=compression
    ) as dst:
        dst.write(data_np, 1)

    # Convert to COG using gdal_translate
    print(f"🌐 Converting to Cloud-Optimized GeoTIFF...")
    cmd = [
        'gdal_translate',
        '-of', 'COG',
        '-co', f'COMPRESS={compression}',
        '-co', 'BLOCKSIZE=512',
        '-co', 'OVERVIEW_RESAMPLING=NEAREST',
        temp_tif,
        output_cog_path
    ]

    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode == 0:
        print(f"✅ Successfully created COG: {output_cog_path}")
        # Remove temporary file
        os.remove(temp_tif)
    else:
        print(f"❌ Error creating COG: {result.stderr}")
        return False

    # Clean up
    ds.close()

    # Print file info
    file_size = os.path.getsize(output_cog_path) / (1024 * 1024)
    print(f"   File size: {file_size:.2f} MB")

    return True


def batch_convert_netcdf_directory(input_dir, output_dir, pattern='*.nc', **kwargs):
    """
    Convert all NetCDF files in a directory to COG

    Parameters:
    -----------
    input_dir : str
        Directory containing NetCDF files
    output_dir : str
        Directory for output COG files
    pattern : str
        File pattern to match (default '*.nc')
    **kwargs : additional arguments passed to netcdf_to_cog
    """

    input_path = Path(input_dir)
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    nc_files = list(input_path.glob(pattern))

    print(f"🔍 Found {len(nc_files)} NetCDF files")

    for nc_file in nc_files:
        output_file = output_path / f"{nc_file.stem}.tif"
        print(f"\n{'='*60}")
        print(f"Processing: {nc_file.name}")
        print(f"{'='*60}")

        try:
            netcdf_to_cog(str(nc_file), str(output_file), **kwargs)
        except Exception as e:
            print(f"❌ Error processing {nc_file.name}: {e}")
            continue

    print(f"\n{'='*60}")
    print(f"✅ Batch conversion complete!")
    print(f"{'='*60}")


if __name__ == "__main__":
    # Example usage

    # Single file conversion
    # netcdf_to_cog(
    #     input_nc_path='../Data/example.nc',
    #     output_cog_path='../Data/web_rasters/example.tif',
    #     target_resolution=0.1
    # )

    # Batch conversion
    batch_convert_netcdf_directory(
        input_dir='../../Data/raw_netcdf',  # Adjust to your NetCDF directory
        output_dir='../../Data/web_rasters',
        pattern='*.nc',
        target_resolution=0.1,
        compression='DEFLATE'
    )
