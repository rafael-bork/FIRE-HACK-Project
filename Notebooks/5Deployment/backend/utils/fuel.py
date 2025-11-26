from backend.config import FUEL_LOAD_DIR
from backend.utils.raster import get_raster_value_at_point

def fetch_fuel_load_data(lat, lon, year):
    for y in [year, year-1, year+1, year-2, year+2]:
        fuel_load_raster = FUEL_LOAD_DIR / f'fuel_load_0.1deg_{y}.tif'
        if fuel_load_raster.exists():
            fuel_load = get_raster_value_at_point(fuel_load_raster, lon, lat)
            if fuel_load is not None:
                return fuel_load, y

    generic_raster = FUEL_LOAD_DIR / 'fuel_load.tif'
    if generic_raster.exists():
        fuel_load = get_raster_value_at_point(generic_raster, lon, lat)
        if fuel_load is not None:
            return fuel_load, None

    return None, None