"""
Flask Backend for Fire ROS Prediction System
Provides API endpoints for model prediction and data fetching
"""

from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import joblib
import numpy as np
import pandas as pd
import rasterio
from rasterio.windows import from_bounds
import openmeteo_requests
import requests_cache
from retry_requests import retry
from pathlib import Path
import json
from datetime import datetime, timedelta
import os

# Try to import CDS API (optional)
try:
    import cdsapi
    CDS_AVAILABLE = True
except ImportError:
    CDS_AVAILABLE = False
    print("⚠️  cdsapi not installed. CDS API features disabled.")
    print("   Install with: pip install cdsapi")

app = Flask(__name__, static_folder='.', static_url_path='')
CORS(app)  # Enable CORS for frontend requests

# ==================== CONFIGURATION ====================

# Paths
MODEL_DIR = Path('../../Data/Models')
RASTER_DIR = Path('../../Data/web_rasters')
ERA5_CACHE_DIR = Path('../../Data/Interim/Meteorological_data/ERA5_cache')
ERA5_CACHE_DIR.mkdir(parents=True, exist_ok=True)

# Weather API Selection
WEATHER_API = os.getenv('WEATHER_API', 'openmeteo')  # 'openmeteo' or 'cds'

# Load trained models
MODELS = {
    'linear': joblib.load(MODEL_DIR / 'Linear.pkl'),
    # 'xgboost': joblib.load(MODEL_DIR / 'XGBoost.pkl'),  # Add when available
    # 'rfr': joblib.load(MODEL_DIR / 'RFR.pkl'),
}

# Model variable definitions
COMPLEX_VARIABLES = [
    "1h_fuel_moisture", "10h_fuel_moisture", "100h_fuel_moisture",
    "live_herb_moisture", "live_woody_moisture", "wind_speed_midflame",
    "wind_direction", "slope", "aspect", "fuel_bed_depth", "fuel_load",
    "sav_ratio", "heat_content", "moisture_damping", "mineral_damping",
    "packing_ratio", "bulk_density", "emissivity", "cloud_cover", "solar_radiation"
]

LINEAR_VARIABLES = [
    "wind_speed_midflame", "wind_direction", "slope",
    "1h_fuel_moisture", "fuel_load"
]

# Setup OpenMeteo API with caching
cache_session = requests_cache.CachedSession('.cache', expire_after=3600)
retry_session = retry(cache_session, retries=5, backoff_factor=0.2)
openmeteo = openmeteo_requests.Client(session=retry_session)

# Setup CDS API client (if available)
if CDS_AVAILABLE:
    try:
        cds_client = cdsapi.Client()
        print("✅ CDS API client initialized")
    except Exception as e:
        print(f"⚠️  CDS API client initialization failed: {e}")
        print("   Make sure ~/.cdsapirc is configured")
        CDS_AVAILABLE = False

# ==================== HELPER FUNCTIONS ====================

def get_raster_value_at_point(raster_path, lon, lat):
    """
    Extract raster value at given coordinates

    Parameters:
    -----------
    raster_path : Path
        Path to raster file (GeoTIFF/COG)
    lon : float
        Longitude
    lat : float
        Latitude

    Returns:
    --------
    float : Value at point, or None if outside bounds
    """
    try:
        with rasterio.open(raster_path) as src:
            # Get pixel coordinates
            row, col = src.index(lon, lat)

            # Read value
            if 0 <= row < src.height and 0 <= col < src.width:
                value = src.read(1, window=((row, row+1), (col, col+1)))[0, 0]
                return float(value) if value != src.nodata else None
            else:
                return None
    except Exception as e:
        print(f"Error reading raster {raster_path}: {e}")
        return None


def fetch_weather_data(lat, lon):
    """
    Fetch real-time weather data from Open-Meteo API

    Parameters:
    -----------
    lat : float
        Latitude
    lon : float
        Longitude

    Returns:
    --------
    dict : Weather variables
    """
    url = "https://api.open-meteo.com/v1/forecast"

    params = {
        "latitude": lat,
        "longitude": lon,
        "current": [
            "temperature_2m",
            "relative_humidity_2m",
            "wind_speed_10m",
            "wind_direction_10m",
            "cloud_cover",
            "shortwave_radiation"
        ],
        "timezone": "auto"
    }

    try:
        responses = openmeteo.weather_api(url, params=params)
        response = responses[0]

        current = response.Current()

        return {
            "temperature": current.Variables(0).Value(),
            "humidity": current.Variables(1).Value(),
            "wind_speed": current.Variables(2).Value(),
            "wind_direction": current.Variables(3).Value(),
            "cloud_cover": current.Variables(4).Value(),
            "solar_radiation": current.Variables(5).Value(),
        }

    except Exception as e:
        print(f"Error fetching weather data: {e}")
        return None


def fetch_weather_data_cds(lat, lon, datetime_str=None):
    """
    Fetch weather data from CDS API (ERA5 reanalysis)

    Parameters:
    -----------
    lat : float
        Latitude
    lon : float
        Longitude
    datetime_str : str, optional
        Date/time in format 'YYYY-MM-DD HH:MM' (default: current hour)

    Returns:
    --------
    dict : Weather variables from ERA5

    Note:
    -----
    CDS API provides historical reanalysis data. For current conditions,
    use Open-Meteo instead. ERA5 data has ~5 days delay.
    """
    if not CDS_AVAILABLE:
        print("CDS API not available")
        return None

    try:
        import xarray as xr

        # Parse datetime or use current
        if datetime_str:
            target_dt = datetime.strptime(datetime_str, '%Y-%m-%d %H:%M')
        else:
            target_dt = datetime.utcnow().replace(minute=0, second=0, microsecond=0)

        # ERA5 has ~5 day delay, check if date is too recent
        if (datetime.utcnow() - target_dt).days < 5:
            print(f"⚠️  ERA5 data not yet available for {target_dt}")
            print("   Using Open-Meteo instead for recent dates")
            return fetch_weather_data(lat, lon)

        # Create cache filename
        cache_file = ERA5_CACHE_DIR / f"ERA5_{target_dt.strftime('%Y%m%d_%H')}_{lat:.2f}_{lon:.2f}.nc"

        # Check cache
        if cache_file.exists():
            print(f"Loading cached ERA5 data: {cache_file.name}")
            ds = xr.open_dataset(cache_file)
        else:
            # Download from CDS API
            print(f"Downloading ERA5 data for {target_dt}...")

            # Bounding box around point (±0.5 degrees)
            area = [lat + 0.5, lon - 0.5, lat - 0.5, lon + 0.5]  # [N, W, S, E]

            # ERA5 Land request (2m temperature, wind, pressure)
            request_land = {
                "product_type": ["reanalysis"],
                "variable": [
                    "2m_temperature",
                    "2m_dewpoint_temperature",
                    "10m_u_component_of_wind",
                    "10m_v_component_of_wind",
                    "surface_pressure"
                ],
                "year": str(target_dt.year),
                "month": f"{target_dt.month:02d}",
                "day": [f"{target_dt.day:02d}"],
                "time": [f"{target_dt.hour:02d}:00"],
                "data_format": "netcdf",
                "download_format": "unarchived",
                "area": area
            }

            # Download
            temp_file = cache_file.with_suffix('.temp.nc')
            cds_client.retrieve("reanalysis-era5-land", request_land, str(temp_file))
            temp_file.rename(cache_file)

            ds = xr.open_dataset(cache_file)

        # Extract data at point (nearest neighbor)
        ds_point = ds.sel(latitude=lat, longitude=lon, method='nearest')

        # Calculate wind speed and direction from u/v components
        u_wind = float(ds_point['u10'].values)
        v_wind = float(ds_point['v10'].values)
        wind_speed = np.sqrt(u_wind**2 + v_wind**2)  # m/s
        wind_direction = (np.degrees(np.arctan2(u_wind, v_wind)) + 180) % 360  # degrees

        # Extract other variables
        temp_2m = float(ds_point['t2m'].values) - 273.15  # K to °C
        dewpoint = float(ds_point['d2m'].values) - 273.15  # K to °C
        pressure = float(ds_point['sp'].values) / 100  # Pa to hPa

        # Calculate relative humidity from temperature and dewpoint
        def calculate_relative_humidity(temp_c, dewpoint_c):
            """Magnus formula for RH calculation"""
            temp_k = temp_c + 273.15
            dewpoint_k = dewpoint_c + 273.15
            es = 6.112 * np.exp((17.67 * temp_c) / (temp_c + 243.5))
            e = 6.112 * np.exp((17.67 * dewpoint_c) / (dewpoint_c + 243.5))
            return (e / es) * 100

        humidity = calculate_relative_humidity(temp_2m, dewpoint)

        # Note: ERA5 Land doesn't include cloud cover or solar radiation
        # These would need to be fetched from ERA5 Single Levels separately

        result = {
            "temperature": temp_2m,
            "humidity": humidity,
            "wind_speed": wind_speed * 3.6,  # m/s to km/h
            "wind_direction": wind_direction,
            "pressure": pressure,
            "source": "ERA5",
            "datetime": target_dt.isoformat(),
            "note": "Cloud cover and solar radiation not available in ERA5 Land"
        }

        ds.close()
        return result

    except Exception as e:
        print(f"Error fetching CDS weather data: {e}")
        import traceback
        traceback.print_exc()
        return None


def fetch_topography_data(lat, lon):
    """
    Fetch topography data from rasters or external API

    Parameters:
    -----------
    lat : float
        Latitude
    lon : float
        Longitude

    Returns:
    --------
    dict : Topography variables (elevation, slope, aspect)
    """

    topo_data = {}

    # Try to read from local rasters if available
    slope_raster = RASTER_DIR / 'slope.tif'
    aspect_raster = RASTER_DIR / 'aspect.tif'
    elevation_raster = RASTER_DIR / 'elevation.tif'

    if slope_raster.exists():
        topo_data['slope'] = get_raster_value_at_point(slope_raster, lon, lat)

    if aspect_raster.exists():
        topo_data['aspect'] = get_raster_value_at_point(aspect_raster, lon, lat)

    if elevation_raster.exists():
        topo_data['elevation'] = get_raster_value_at_point(elevation_raster, lon, lat)

    # Fallback: use Open-Meteo elevation API
    if 'elevation' not in topo_data or topo_data['elevation'] is None:
        try:
            url = "https://api.open-meteo.com/v1/elevation"
            params = {"latitude": lat, "longitude": lon}
            response = requests.get(url, params=params)
            data = response.json()
            topo_data['elevation'] = data.get('elevation', [None])[0]
        except Exception as e:
            print(f"Error fetching elevation: {e}")
            topo_data['elevation'] = None

    return topo_data


# ==================== API ENDPOINTS ====================

@app.route('/')
def index():
    """Serve the main HTML interface"""
    return send_from_directory('.', 'index.html')


@app.route('/api/location-data', methods=['POST'])
def get_location_data():
    """
    Fetch topography and meteorology data for a clicked location

    Request JSON:
    {
        "lat": 39.5,
        "lon": -8.0,
        "api": "openmeteo",  # optional: "openmeteo" or "cds"
        "datetime": "2023-08-15 14:00"  # optional: for historical CDS queries
    }

    Response JSON:
    {
        "topography": {"elevation": 1240, "slope": 12, "aspect": 180},
        "meteorology": {"temperature": 25, "humidity": 32, "wind_speed": 15, ...}
    }
    """
    try:
        data = request.get_json()
        lat = float(data['lat'])
        lon = float(data['lon'])
        api_source = data.get('api', WEATHER_API)  # Use configured default
        datetime_str = data.get('datetime', None)

        # Fetch topography data
        topo_data = fetch_topography_data(lat, lon)

        # Fetch weather data based on API source
        if api_source == 'cds' and CDS_AVAILABLE:
            weather_data = fetch_weather_data_cds(lat, lon, datetime_str)
        else:
            if api_source == 'cds' and not CDS_AVAILABLE:
                print("⚠️  CDS API requested but not available, falling back to Open-Meteo")
            weather_data = fetch_weather_data(lat, lon)

        return jsonify({
            'success': True,
            'topography': topo_data,
            'meteorology': weather_data,
            'api_used': 'cds' if (api_source == 'cds' and CDS_AVAILABLE and weather_data and weather_data.get('source') == 'ERA5') else 'openmeteo'
        })

    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 400


@app.route('/api/predict', methods=['POST'])
def predict_ros():
    """
    Run fire spread prediction model

    Request JSON:
    {
        "model": "linear",  # or "complex", "xgboost"
        "variables": {
            "wind_speed_midflame": 5.2,
            "wind_direction": 270,
            "slope": 12,
            ...
        }
    }

    Response JSON:
    {
        "success": true,
        "prediction": 8.45,
        "unit": "m/min",
        "error_estimate": 2.1
    }
    """
    try:
        data = request.get_json()
        model_name = data.get('model', 'linear')
        variables = data['variables']

        # Validate model
        if model_name not in MODELS:
            return jsonify({
                'success': False,
                'error': f'Model "{model_name}" not found'
            }), 400

        # Get model
        model = MODELS[model_name]

        # Determine expected variables
        if model_name == 'linear':
            expected_vars = LINEAR_VARIABLES
        else:
            expected_vars = COMPLEX_VARIABLES

        # Build feature vector
        feature_values = []
        for var in expected_vars:
            if var not in variables:
                return jsonify({
                    'success': False,
                    'error': f'Missing variable: {var}'
                }), 400
            feature_values.append(float(variables[var]))

        # Create DataFrame with proper column names
        X = pd.DataFrame([feature_values], columns=expected_vars)

        # Make prediction
        prediction = model.predict(X)[0]

        # Estimate error (placeholder - you should compute this from your validation)
        # For linear models, you might have residual std dev
        error_estimate = abs(prediction * 0.15)  # Example: 15% error

        return jsonify({
            'success': True,
            'prediction': float(prediction),
            'unit': 'm/min',
            'error_estimate': float(error_estimate),
            'model_used': model_name
        })

    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/models', methods=['GET'])
def list_models():
    """List available models"""
    return jsonify({
        'models': list(MODELS.keys())
    })


@app.route('/api/status', methods=['GET'])
def api_status():
    """Get API status and available features"""
    return jsonify({
        'success': True,
        'models': list(MODELS.keys()),
        'weather_apis': {
            'openmeteo': True,
            'cds': CDS_AVAILABLE
        },
        'default_weather_api': WEATHER_API,
        'features': {
            'raster_data': RASTER_DIR.exists(),
            'historical_weather': CDS_AVAILABLE
        }
    })


# ==================== RASTER TILE SERVING (optional) ====================

@app.route('/api/raster/<raster_name>/value', methods=['GET'])
def get_raster_value(raster_name):
    """
    Get raster value at specific coordinates

    Query params: ?lat=39.5&lon=-8.0
    """
    try:
        lat = float(request.args.get('lat'))
        lon = float(request.args.get('lon'))

        raster_path = RASTER_DIR / f'{raster_name}.tif'

        if not raster_path.exists():
            return jsonify({
                'success': False,
                'error': f'Raster "{raster_name}" not found'
            }), 404

        value = get_raster_value_at_point(raster_path, lon, lat)

        return jsonify({
            'success': True,
            'value': value,
            'raster': raster_name,
            'coordinates': {'lat': lat, 'lon': lon}
        })

    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 400


# ==================== RUN SERVER ====================

if __name__ == '__main__':
    print("🔥 Starting Fire ROS Prediction API Server...")
    print(f"   Models loaded: {list(MODELS.keys())}")
    print(f"   Raster directory: {RASTER_DIR}")
    print(f"   Weather APIs:")
    print(f"      - Open-Meteo: ✅ Available (real-time)")
    print(f"      - CDS API (ERA5): {'✅ Available (historical)' if CDS_AVAILABLE else '❌ Not available'}")
    print(f"   Default weather API: {WEATHER_API}")
    print(f"   Server running on http://localhost:5000")
    print(f"   API status: http://localhost:5000/api/status")

    if CDS_AVAILABLE:
        print(f"\n   💡 CDS API enabled for historical weather data")
        print(f"      To use: Add 'api': 'cds' and 'datetime': 'YYYY-MM-DD HH:MM' to requests")
    else:
        print(f"\n   ℹ️  To enable CDS API:")
        print(f"      1. pip install cdsapi")
        print(f"      2. Configure ~/.cdsapirc with your CDS credentials")
        print(f"      3. Get free API key at: https://cds.climate.copernicus.eu/")

    app.run(debug=True, host='0.0.0.0', port=5000)
