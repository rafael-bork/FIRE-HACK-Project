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
from pathlib import Path
import json
from datetime import datetime, timedelta
import os
import xarray as xr

# Import CDS API (required)
try:
    import cdsapi
    CDS_AVAILABLE = True
    cds_client = cdsapi.Client()
    print("✅ CDS API client initialized")
except ImportError:
    CDS_AVAILABLE = False
    print("❌ ERROR: cdsapi not installed!")
    print("   This application requires CDS API for historical weather data.")
    print("   Install with: pip install cdsapi")
    print("   Configure: https://cds.climate.copernicus.eu/api-how-to")
except Exception as e:
    CDS_AVAILABLE = False
    print(f"❌ ERROR: CDS API client initialization failed: {e}")
    print("   Make sure ~/.cdsapirc is configured with your credentials")
    print("   Get API key at: https://cds.climate.copernicus.eu/")

app = Flask(__name__, static_folder='.', static_url_path='')
CORS(app)  # Enable CORS for frontend requests

# ==================== CONFIGURATION ====================

# Paths
MODEL_DIR = Path('../../Data/Models')
RASTER_DIR = Path('../../Data/web_rasters')
ERA5_CACHE_DIR = Path('../../Data/Interim/Meteorological_data/ERA5_cache')
ERA5_CACHE_DIR.mkdir(parents=True, exist_ok=True)

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


def fetch_weather_data(lat, lon, datetime_str=None):
    """
    Fetch historical weather data from CDS API (ERA5 reanalysis)

    Parameters:
    -----------
    lat : float
        Latitude
    lon : float
        Longitude
    datetime_str : str, optional
        Date/time in format 'YYYY-MM-DD HH:MM' (required for historical queries)

    Returns:
    --------
    dict : Weather variables from ERA5

    Note:
    -----
    ERA5 provides historical reanalysis data with ~5 day delay.
    This application is designed for historical fire analysis, not real-time prediction.
    """
    if not CDS_AVAILABLE:
        print("❌ CDS API not available")
        return None

    try:
        # Parse datetime (required)
        if not datetime_str:
            raise ValueError("datetime parameter is required (format: 'YYYY-MM-DD HH:MM')")

        target_dt = datetime.strptime(datetime_str, '%Y-%m-%d %H:%M')

        # ERA5 has ~5 day delay, warn if date is too recent
        days_ago = (datetime.utcnow() - target_dt).days
        if days_ago < 5:
            print(f"⚠️  ERA5 data may not yet be available for {target_dt}")
            print(f"   Requested date is only {days_ago} days ago. ERA5 typically has a 5-day delay.")
            # Continue anyway - CDS API will queue the request or fail gracefully

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
    Fetch topography and historical meteorology data for a location

    Request JSON:
    {
        "lat": 39.5,
        "lon": -8.0,
        "datetime": "2023-08-15 14:00"  # REQUIRED: Historical date/time for ERA5 data
    }

    Response JSON:
    {
        "success": true,
        "topography": {"elevation": 1240, "slope": 12, "aspect": 180},
        "meteorology": {"temperature": 25, "humidity": 32, "wind_speed": 15, ...}
    }
    """
    try:
        data = request.get_json()
        lat = float(data['lat'])
        lon = float(data['lon'])
        datetime_str = data.get('datetime', None)

        if not datetime_str:
            return jsonify({
                'success': False,
                'error': 'datetime parameter is required (format: "YYYY-MM-DD HH:MM")'
            }), 400

        # Fetch topography data
        topo_data = fetch_topography_data(lat, lon)

        # Fetch historical weather data from CDS API
        weather_data = fetch_weather_data(lat, lon, datetime_str)

        if not weather_data:
            return jsonify({
                'success': False,
                'error': 'Failed to fetch weather data. Check CDS API configuration.'
            }), 500

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


@app.route('/api/status', methods=['GET'])
def api_status():
    """Get API status and available features"""
    return jsonify({
        'success': True,
        'models': list(MODELS.keys()),
        'cds_api_available': CDS_AVAILABLE,
        'features': {
            'raster_data': RASTER_DIR.exists(),
            'historical_weather': CDS_AVAILABLE,
            'model_prediction': len(MODELS) > 0
        },
        'note': 'This application requires CDS API for historical weather data analysis'
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
    print("🔥 Fire ROS Historical Analysis API Server")
    print("="*60)
    print(f"\n📊 Configuration:")
    print(f"   Models loaded: {list(MODELS.keys())}")
    print(f"   Raster directory: {RASTER_DIR}")
    print(f"   ERA5 cache directory: {ERA5_CACHE_DIR}")

    print(f"\n🌦️  Weather Data Source:")
    if CDS_AVAILABLE:
        print(f"   ✅ CDS API (ERA5 Historical Reanalysis) - READY")
        print(f"      Data range: 1940 to present (~5 day delay)")
    else:
        print(f"   ❌ CDS API NOT CONFIGURED")
        print(f"      This application requires CDS API for historical weather analysis.")
        print(f"\n   📝 Setup Instructions:")
        print(f"      1. Register at: https://cds.climate.copernicus.eu/")
        print(f"      2. Get your API key from: https://cds.climate.copernicus.eu/api-how-to")
        print(f"      3. Install: pip install cdsapi")
        print(f"      4. Configure ~/.cdsapirc with your UID and API key")
        print(f"      5. Restart this server")
        print(f"\n   ⚠️  Server will run but weather data requests will fail!")

    print(f"\n🌐 Server Info:")
    print(f"   URL: http://localhost:5000")
    print(f"   API Status: http://localhost:5000/api/status")
    print(f"   Mode: Historical Fire Analysis (not real-time prediction)")

    print(f"\n📍 Usage:")
    print(f'   POST /api/location-data with {{"lat": 39.5, "lon": -8.0, "datetime": "2023-08-15 14:00"}}')
    print(f"   Datetime parameter is REQUIRED for historical ERA5 queries")

    print("\n" + "="*60)

    if not CDS_AVAILABLE:
        print("\n⚠️  WARNING: Starting server without CDS API configuration!")
        print("   Configure CDS API to enable weather data functionality.\n")
    print(f"   Server running on http://localhost:5050")
    print(f"   API docs: http://localhost:5050/api/models")

    app.run(debug=True, host='0.0.0.0', port=5050)
