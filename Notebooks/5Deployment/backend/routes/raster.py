from flask import Blueprint, request, jsonify
from backend.config import RASTER_DIR
from backend.utils.raster import get_raster_value_at_point

bp = Blueprint('raster', __name__)

@bp.route('/api/raster/<raster_name>/value', methods=['GET'])
def get_raster_value(raster_name):
    try:
        lat = float(request.args.get('lat'))
        lon = float(request.args.get('lon'))
        raster_path = RASTER_DIR / f'{raster_name}.tif'
        if not raster_path.exists():
            return jsonify({'success': False, 'error': f'Raster "{raster_name}" not found'}), 404

        value = get_raster_value_at_point(raster_path, lon, lat)
        return jsonify({'success': True, 'value': value, 'raster