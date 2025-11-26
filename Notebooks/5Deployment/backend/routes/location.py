from flask import Blueprint, request, jsonify
from datetime import datetime
from backend.utils.fuel import fetch_fuel_load_data
from backend.utils.weather import fetch_weather_data

bp = Blueprint('location', __name__)

@bp.route('/api/location-data', methods=['POST'])
def get_location_data():
    try:
        data = request.get_json()
        lat = float(data['lat'])
        lon = float(data['lon'])
        datetime_str = data.get('datetime')
        if not datetime_str:
            return jsonify({'success': False, 'error': 'datetime required'}), 400

        fire_datetime = datetime.strptime(datetime_str, '%Y-%m-%d %H:%M')
        year = fire_datetime.year

        fuel_load, fuel_year = fetch_fuel_load_data(lat, lon, year)
        weather_data = fetch_weather_data(lat, lon, datetime_str)

        if isinstance(weather_data, dict) and 'error' in weather_data:
            return jsonify({'success': False, 'error': weather_data['error'], 'fuel_load': fuel_load}), 500

        return jsonify({
            'success': True,
            'fuel_load': fuel_load,
            'fuel_load_year': fuel_year,
            'meteorology': weather_data,
            'request': {'lat': lat, 'lon': lon, 'datetime': datetime_str, 'year': year}
        })
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 400