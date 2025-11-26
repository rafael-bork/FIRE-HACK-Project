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

app = Flask(__name__, static_folder='.', static_url_path='')
CORS(app)  # Enable CORS for frontend requests

# ==================== CONFIGURATION ====================

# Paths
MODEL_DIR = Path('../../Data/Models')
RASTER_DIR = Path('../../Data/web_rasters')

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
        "lon": -8.0
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

        # Fetch data
        topo_data = fetch_topography_data(lat, lon)
        weather_data = fetch_weather_data(lat, lon)

        return jsonify({
            'success': True,
            'topography': topo_data,
            'meteorology': weather_data
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
    print(f"   Server running on http://localhost:5050")
    print(f"   API docs: http://localhost:5050/api/models")

    app.run(debug=True, host='0.0.0.0', port=5050)
