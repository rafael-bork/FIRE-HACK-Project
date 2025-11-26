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

    Fetches from multiple ERA5 datasets:
    - ERA5 Single Levels: CAPE, soil water, 100m wind
    - ERA5 Pressure Levels: water vapor, geopotential at 850/700 hPa
    - CEMS Fire Weather: Fire Weather Index

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

        # Create cache filenames
        cache_sl = ERA5_CACHE_DIR / f"ERA5_SL_{target_dt.strftime('%Y%m%d_%H')}_{lat:.2f}_{lon:.2f}.nc"
        cache_pl = ERA5_CACHE_DIR / f"ERA5_PL_{target_dt.strftime('%Y%m%d_%H')}_{lat:.2f}_{lon:.2f}.nc"
        cache_fwi = ERA5_CACHE_DIR / f"ERA5_FWI_{target_dt.strftime('%Y%m%d_%H')}_{lat:.2f}_{lon:.2f}.nc"

        # Bounding box around point (±0.5 degrees)
        area = [lat + 0.5, lon - 0.5, lat - 0.5, lon + 0.5]  # [N, W, S, E]

        # ========== ERA5 Single Levels ==========
        if cache_sl.exists():
            print(f"Loading cached ERA5 Single Levels: {cache_sl.name}")
            ds_sl = xr.open_dataset(cache_sl)
        else:
            print(f"Downloading ERA5 Single Levels for {target_dt}...")
            request_sl = {
                "product_type": ["reanalysis"],
                "variable": [
                    "100m_u_component_of_wind",
                    "100m_v_component_of_wind",
                    "convective_available_potential_energy",
                    "volumetric_soil_water_layer_3",  # 28-100 cm depth
                    "volumetric_soil_water_layer_4"   # 100-289 cm depth
                ],
                "year": str(target_dt.year),
                "month": f"{target_dt.month:02d}",
                "day": [f"{target_dt.day:02d}"],
                "time": [f"{target_dt.hour:02d}:00"],
                "data_format": "netcdf",
                "download_format": "unarchived",
                "area": area
            }
            temp_file = cache_sl.with_suffix('.temp.nc')
            cds_client.retrieve("reanalysis-era5-single-levels", request_sl, str(temp_file))
            temp_file.rename(cache_sl)
            ds_sl = xr.open_dataset(cache_sl)

        # ========== ERA5 Pressure Levels ==========
        if cache_pl.exists():
            print(f"Loading cached ERA5 Pressure Levels: {cache_pl.name}")
            ds_pl = xr.open_dataset(cache_pl)
        else:
            print(f"Downloading ERA5 Pressure Levels for {target_dt}...")
            request_pl = {
                "product_type": ["reanalysis"],
                "variable": [
                    "geopotential",
                    "temperature",
                    "specific_humidity"  # Water vapor
                ],
                "pressure_level": ["850", "700", "1000"],
                "year": str(target_dt.year),
                "month": f"{target_dt.month:02d}",
                "day": [f"{target_dt.day:02d}"],
                "time": [f"{target_dt.hour:02d}:00"],
                "data_format": "netcdf",
                "download_format": "unarchived",
                "area": area
            }
            temp_file = cache_pl.with_suffix('.temp.nc')
            cds_client.retrieve("reanalysis-era5-pressure-levels", request_pl, str(temp_file))
            temp_file.rename(cache_pl)
            ds_pl = xr.open_dataset(cache_pl)

        # ========== CEMS Fire Weather Index ==========
        if cache_fwi.exists():
            print(f"Loading cached FWI: {cache_fwi.name}")
            ds_fwi = xr.open_dataset(cache_fwi)
        else:
            print(f"Downloading FWI for {target_dt}...")
            request_fwi = {
                "product_type": "reanalysis",
                "variable": ["fire_weather_index"],
                "dataset_type": "consolidated_dataset",
                "system_version": "4_1",
                "year": str(target_dt.year),
                "month": f"{target_dt.month:02d}",
                "day": [f"{target_dt.day:02d}"],
                "grid": "original_grid",
                "data_format": "netcdf"
            }
            temp_file = cache_fwi.with_suffix('.temp.nc')
            cds_client.retrieve("cems-fire-historical-v1", request_fwi).download(str(temp_file))
            temp_file.rename(cache_fwi)
            ds_fwi = xr.open_dataset(cache_fwi)

        # ========== Extract data at point ==========
        ds_sl_point = ds_sl.sel(latitude=lat, longitude=lon, method='nearest')
        ds_pl_point = ds_pl.sel(latitude=lat, longitude=lon, method='nearest')
        ds_fwi_point = ds_fwi.sel(latitude=lat, longitude=lon, method='nearest')

        # Extract Single Level variables
        u_100 = float(ds_sl_point['u100'].values)
        v_100 = float(ds_sl_point['v100'].values)
        cape = float(ds_sl_point['cape'].values)
        swvl3 = float(ds_sl_point['swvl3'].values)  # Soil water layer 3
        swvl4 = float(ds_sl_point['swvl4'].values)  # Soil water layer 4

        # Calculate 100m wind speed
        wv100_k = np.sqrt(u_100**2 + v_100**2)  # m/s

        # Extract Pressure Level variables
        wv_850 = float(ds_pl_point['q'].sel(pressure_level=850).values)  # kg/kg
        wv_1000 = float(ds_pl_point['q'].sel(pressure_level=1000).values)  # kg/kg
        z_850 = float(ds_pl_point['z'].sel(pressure_level=850).values)  # m²/s²
        z_700 = float(ds_pl_point['z'].sel(pressure_level=700).values)  # m²/s²
        t_850 = float(ds_pl_point['t'].sel(pressure_level=850).values) - 273.15  # K to °C
        t_700 = float(ds_pl_point['t'].sel(pressure_level=700).values) - 273.15  # K to °C

        # Extract FWI
        fwi = float(ds_fwi_point['fwi'].values)

        # Calculate derived variables
        sW_100_av = (swvl3 + swvl4) / 2  # Average soil water at 100cm depth
        gT_8_7_av = ((z_850 - z_700) / 9.81) / 1000  # Geopotential height difference in km

        # Build result dictionary with your variable names
        result = {
            # Required variables for your model
            "sW_100_av": sW_100_av,
            "FWI_12h_av": fwi,  # Using current FWI (12h average would need multiple timesteps)
            "wv100_k_av": wv100_k * 3.6,  # m/s to km/h
            "wv_850_av": wv_850 * 1000,  # kg/kg to g/kg
            "Cape_av": cape,
            "gT_8_7_av": gT_8_7_av,

            # Additional useful variables
            "temperature_850": t_850,
            "temperature_700": t_700,
            "wind_100m_speed": wv100_k * 3.6,  # km/h
            "water_vapor_1000": wv_1000 * 1000,  # g/kg

            # Metadata
            "source": "ERA5",
            "datetime": target_dt.isoformat()
        }

        # Close datasets
        ds_sl.close()
        ds_pl.close()
        ds_fwi.close()

        return result

    except Exception as e:
        print(f"Error fetching CDS weather data: {e}")
        import traceback
        traceback.print_exc()
        return None


def fetch_fuel_load_data(lat, lon, year):
    """
    Fetch fuel load data from year-specific raster

    Parameters:
    -----------
    lat : float
        Latitude
    lon : float
        Longitude
    year : int
        Year for fuel load raster (2015-2025)

    Returns:
    --------
    float : Fuel load value (kg/m²) or None
    """
    # Path to fuel load rasters by year
    FUEL_LOAD_DIR = Path('../../Data/Processed/Fuel_load')
    fuel_load_raster = FUEL_LOAD_DIR / f'fuel_load_{year}.tif'

    if fuel_load_raster.exists():
        fuel_load = get_raster_value_at_point(fuel_load_raster, lon, lat)
        return fuel_load
    else:
        print(f"⚠️  Fuel load raster for year {year} not found: {fuel_load_raster}")
        return None


# ==================== API ENDPOINTS ====================

@app.route('/')
def index():
    """Serve the main HTML interface"""
    return send_from_directory('.', 'index.html')


@app.route('/api/location-data', methods=['POST'])
def get_location_data():
    """
    Fetch fuel load and historical meteorology data for a location

    Request JSON:
    {
        "lat": 39.5,
        "lon": -8.0,
        "datetime": "2023-08-15 14:00"  # REQUIRED: Historical date/time for ERA5 data
    }

    Response JSON:
    {
        "success": true,
        "fuel_load": 1.5,
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

        # Parse datetime to extract year
        fire_datetime = datetime.strptime(datetime_str, '%Y-%m-%d %H:%M')
        year = fire_datetime.year

        # Fetch fuel load data for the specific year
        fuel_load = fetch_fuel_load_data(lat, lon, year)

        # Fetch historical weather data from CDS API
        weather_data = fetch_weather_data(lat, lon, datetime_str)

        if not weather_data:
            return jsonify({
                'success': False,
                'error': 'Failed to fetch weather data. Check CDS API configuration.'
            }), 500

        return jsonify({
            'success': True,
            'fuel_load': fuel_load,
            'meteorology': weather_data,
            'year': year
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
