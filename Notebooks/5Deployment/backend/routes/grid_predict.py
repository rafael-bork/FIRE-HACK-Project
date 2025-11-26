"""
Grid-based prediction routes
Runs predictions across all 0.1° grid cells in Portugal
"""

from flask import Blueprint, request, jsonify
from datetime import datetime
import pandas as pd
from backend.utils.grid import generate_portugal_grid
from backend.utils.weather import fetch_weather_data
from backend.utils.fuel import fetch_fuel_load_data
from backend.utils.raster import get_raster_value_at_point
from backend.config import RASTER_DIR, COMPLEX_VARIABLES
from backend.models.loader import MODELS

bp = Blueprint('grid_predict', __name__)

def fetch_grid_cell_data(lat, lon, datetime_str, year):
    """
    Fetch all required data for a single grid cell

    Returns:
        dict with all model variables or None if data unavailable
    """
    try:
        # Fetch weather data
        weather_data = fetch_weather_data(lat, lon, datetime_str)
        if 'error' in weather_data:
            return None

        # Fetch fuel load data
        fuel_load, _ = fetch_fuel_load_data(lat, lon, year)
        if fuel_load is None:
            return None

        # Fetch burned area percentage data
        burned_3_8y_path = RASTER_DIR / '3_8y_fir_p.tif'
        burned_8_ny_path = RASTER_DIR / '8_ny_fir_p.tif'

        burned_3_8y = None
        if burned_3_8y_path.exists():
            burned_3_8y = get_raster_value_at_point(burned_3_8y_path, lon, lat)

        burned_8_ny = None
        if burned_8_ny_path.exists():
            burned_8_ny = get_raster_value_at_point(burned_8_ny_path, lon, lat)

        # If we don't have burned area data, skip this cell
        if burned_3_8y is None or burned_8_ny is None:
            return None

        return {
            'lat': lat,
            'lon': lon,
            'weather': weather_data,
            'fuel_load': fuel_load,
            'burned_3_8y': burned_3_8y,
            'burned_8_ny': burned_8_ny
        }

    except Exception as e:
        print(f"Error fetching data for ({lat}, {lon}): {e}")
        return None

def build_model_variables(cell_data, f_start=0, duration_p=60):
    """
    Build the complex model variables from fetched data

    Args:
        cell_data: Data fetched for a grid cell
        f_start: Fire start value (default 0)
        duration_p: Duration in minutes (default 60)

    Returns:
        dict with all COMPLEX_VARIABLES
    """
    weather = cell_data['weather']

    # Build the variables dict matching COMPLEX_VARIABLES order
    variables = {
        "duration_p": duration_p,
        "sW_100_av": weather.get('sW_100_av', 0.2),
        "8_ny_fir_p": cell_data['burned_8_ny'],
        "3_8y_fir_p": cell_data['burned_3_8y'],
        "f_load_av": cell_data['fuel_load'],
        "f_start": f_start,
        "FWI_12h_av": weather.get('FWI_12h_av', 0),
        "wv100_k_av": weather.get('wv100_k_av', 0),
        "wv_850_av": weather.get('wv_850_av', 5),
        "Cape_av": weather.get('Cape_av', 0),
        "gT_8_7_av": weather.get('gT_8_7_av', 1.5)
    }

    return variables

@bp.route('/api/predict-grid', methods=['POST'])
def predict_grid():
    """
    Run predictions across entire Portugal grid

    Request body:
    {
        "datetime": "YYYY-MM-DD HH:MM",
        "model": "complex" or "linear",
        "f_start": 0 (optional, default 0),
        "duration_p": 60 (optional, default 60)
    }

    Response:
    {
        "success": true,
        "predictions": [
            {
                "lat": float,
                "lon": float,
                "prediction": float,
                "error_estimate": float
            },
            ...
        ],
        "total_cells": int,
        "successful_cells": int
    }
    """
    try:
        data = request.get_json()
        datetime_str = data.get('datetime')
        model_name = data.get('model', 'complex')
        f_start = float(data.get('f_start', 0))
        duration_p = float(data.get('duration_p', 60))

        if not datetime_str:
            return jsonify({
                'success': False,
                'error': 'datetime is required'
            }), 400

        # Parse datetime to get year
        try:
            dt = datetime.strptime(datetime_str, '%Y-%m-%d %H:%M')
            year = dt.year
        except ValueError:
            return jsonify({
                'success': False,
                'error': 'Invalid datetime format. Use YYYY-MM-DD HH:MM'
            }), 400

        # Check if model exists
        if model_name not in MODELS:
            return jsonify({
                'success': False,
                'error': f'Model "{model_name}" not found'
            }), 400

        model = MODELS[model_name]

        # Generate grid
        grid_points = generate_portugal_grid(resolution=0.1)
        total_cells = len(grid_points)

        predictions = []
        successful_cells = 0

        # Process each grid cell
        for point in grid_points:
            lat = point['lat']
            lon = point['lon']

            # Fetch data for this cell
            cell_data = fetch_grid_cell_data(lat, lon, datetime_str, year)

            if cell_data is None:
                continue  # Skip cells with missing data

            # Build model variables
            variables = build_model_variables(cell_data, f_start, duration_p)

            # Run prediction
            try:
                feature_values = [variables[var] for var in COMPLEX_VARIABLES]
                X = pd.DataFrame([feature_values], columns=COMPLEX_VARIABLES)
                prediction = model.predict(X)[0]
                error_estimate = abs(prediction * 0.15)

                predictions.append({
                    'lat': lat,
                    'lon': lon,
                    'prediction': float(prediction),
                    'error_estimate': float(error_estimate)
                })

                successful_cells += 1

            except Exception as e:
                print(f"Prediction error for ({lat}, {lon}): {e}")
                continue

        return jsonify({
            'success': True,
            'predictions': predictions,
            'total_cells': total_cells,
            'successful_cells': successful_cells,
            'model_used': model_name,
            'datetime': datetime_str,
            'f_start': f_start,
            'duration_p': duration_p
        })

    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500
