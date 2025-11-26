import rasterio

def get_raster_value_at_point(raster_path, lon, lat):
    """Extract raster value at given coordinates"""
    try:
        with rasterio.open(raster_path) as src:
            row, col = src.index(lon, lat)
            if 0 <= row < src.height and 0 <= col < src.width:
                value = src.read(1, window=((row, row+1), (col, col+1)))[0, 0]
                return float(value) if value != src.nodata else None
            return None
    except Exception as e:
        print(f"Error reading raster {raster_path}: {e}")
        return None