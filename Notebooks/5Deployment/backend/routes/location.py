"""
Location data fetching routes
Provides endpoints for fetching weather and fuel data for specific locations
"""

from flask import Blueprint, request, jsonify
from datetime import datetime
from backend.utils.weather import fetch_weather_data
from backend.utils.fuel import fetch_fuel_load_data
from backend.utils.raster import get_raster_value_at_point
from backend.config import RASTER_DIR

bp = Blueprint('location', __name__)

@bp.route('/api/location-data', methods=['POST'])
def get_location_data():
    """
    Fetch weather and fuel data for a specific location and datetime

    Request body:
    {
        "lat": float,
        "lon": float,
        "datetime": "YYYY-MM-DD HH:MM"
    }
    """
    try:
        data = request.get_json()
        lat = float(data.get('lat'))
        lon = float(data.get('lon'))
        datetime_str = data.get('datetime')

        if not datetime_str:
            return jsonify({
                'success': False,
                'error': 'datetime is required'
            }), 400

        # Parse datetime and extract year
        try:
            dt = datetime.strptime(datetime_str, '%Y-%m-%d %H:%M')
            year = dt.year
        except ValueError:
            return jsonify({
                'success': False,
                'error': 'Invalid datetime format. Use YYYY-MM-DD HH:MM'
            }), 400

        # Fetch weather data
        weather_data = fetch_weather_data(lat, lon, datetime_str)
        if 'error' in weather_data:
            return jsonify({
                'success': False,
                'error': f'Weather data error: {weather_data["error"]}'
            }), 500

        # Fetch fuel load data
        fuel_load, fuel_year = fetch_fuel_load_data(lat, lon, year)

        # Fetch burned area percentage data
        burned_3_8y = None
        burned_8_ny = None

        burned_3_8y_path = RASTER_DIR / '3_8y_fir_p.tif'
        if burned_3_8y_path.exists():
            burned_3_8y = get_raster_value_at_point(burned_3_8y_path, lon, lat)

        burned_8_ny_path = RASTER_DIR / '8_ny_fir_p.tif'
        if burned_8_ny_path.exists():
            burned_8_ny = get_raster_value_at_point(burned_8_ny_path, lon, lat)

        return jsonify({
            'success': True,
            'lat': lat,
            'lon': lon,
            'datetime': datetime_str,
            'year': year,
            'fuel_load': fuel_load,
            'fuel_year': fuel_year,
            'burned_3_8y': burned_3_8y,
            'burned_8_ny': burned_8_ny,
            'meteorology': {
                'wind_speed': weather_data.get('wind_100m_speed_kmh'),
                'wind_direction': None,  # TODO: calculate from u/v components
                'temperature': weather_data.get('temperature_850'),
                'humidity': None  # TODO: calculate from weather data
            },
            'weather_full': weather_data
        })

    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500
