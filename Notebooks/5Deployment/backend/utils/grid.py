"""
Grid generation utilities for Portugal
Generates 0.1° grid cells across Portugal's territory
"""

import numpy as np

# Portugal bounding box (approximate)
PORTUGAL_BOUNDS = {
    'lat_min': 36.9,
    'lat_max': 42.2,
    'lon_min': -9.6,
    'lon_max': -6.1
}

def generate_portugal_grid(resolution=0.1):
    """
    Generate a grid of points covering Portugal at specified resolution

    Args:
        resolution: Grid cell size in degrees (default 0.1°)

    Returns:
        list of dicts with 'lat', 'lon' for each grid cell center
    """
    lats = np.arange(
        PORTUGAL_BOUNDS['lat_min'],
        PORTUGAL_BOUNDS['lat_max'],
        resolution
    )
    lons = np.arange(
        PORTUGAL_BOUNDS['lon_min'],
        PORTUGAL_BOUNDS['lon_max'],
        resolution
    )

    # Generate center points of each grid cell
    grid_points = []
    for lat in lats:
        for lon in lons:
            # Use center of grid cell
            center_lat = lat + resolution / 2
            center_lon = lon + resolution / 2
            grid_points.append({
                'lat': round(center_lat, 4),
                'lon': round(center_lon, 4)
            })

    return grid_points

def get_grid_bounds(resolution=0.1):
    """
    Get the bounding box coordinates for the grid

    Returns:
        dict with lat_min, lat_max, lon_min, lon_max
    """
    return PORTUGAL_BOUNDS.copy()

def get_grid_cell_bounds(lat, lon, resolution=0.1):
    """
    Get the bounding box for a specific grid cell

    Args:
        lat: Latitude of cell center
        lon: Longitude of cell center
        resolution: Grid cell size in degrees

    Returns:
        dict with lat_min, lat_max, lon_min, lon_max for the cell
    """
    half_res = resolution / 2
    return {
        'lat_min': lat - half_res,
        'lat_max': lat + half_res,
        'lon_min': lon - half_res,
        'lon_max': lon + half_res
    }
