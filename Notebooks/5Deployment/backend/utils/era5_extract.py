def get_coordinate_names(ds):
    lat_name = next((n for n in ['latitude', 'lat'] if n in ds.coords or n in ds.dims), None)
    lon_name = next((n for n in ['longitude', 'lon'] if n in ds.coords or n in ds.dims), None)
    return lat_name, lon_name

def extract_value_at_point(ds, var_name, lat, lon, pressure_level=None):
    try:
        lat_name, lon_name = get_coordinate_names(ds)
        if lat_name is None or lon_name is None:
            print(f"Lat/Lon coordinates not found. Available: {list(ds.coords)}")
            return None
        if var_name not in ds:
            print(f"Variable '{var_name}' not in dataset. Available: {list(ds.data_vars)}")
            return None
        data = ds[var_name]
        if pressure_level is not None:
            for pl_name in ['pressure_level', 'level', 'plev', 'isobaricInhPa']:
                if pl_name in data.dims:
                    data = data.sel({pl_name: pressure_level}, method='nearest')
                    break
        for time_name in ['time', 'valid_time']:
            if time_name in data.dims:
                data = data.isel({time_name: 0})
                break
        data = data.sel({lat_name: lat, lon_name: lon}, method='nearest')
        return float(data.values)
    except Exception as e:
        print(f"Error extracting {var_name}: {e}")
        return None