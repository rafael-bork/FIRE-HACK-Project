from flask import Blueprint, jsonify, send_from_directory
from backend.models.loader import MODELS
from backend.config import LINEAR_VARIABLES, COMPLEX_VARIABLES
from backend.config import RASTER_DIR, ERA5_CACHE_DIR
from backend.utils.era5_fetch import CDS_AVAILABLE

bp = Blueprint('base', __name__)

@bp.route('/')
def index():
    return send_from_directory('.', 'index.html')

@bp.route('/api/status', methods=['GET'])
def api_status():
    return jsonify({
        'success': True,
        'models': list(MODELS.keys()),
        'cds_api_available': CDS_AVAILABLE,
        'features': {
            'raster_data': RASTER_DIR.exists(),
            'historical_weather': CDS_AVAILABLE,
            'model_prediction': len(MODELS) > 0
        },
        'cache_directory': str(ERA5_CACHE_DIR),
        'note': 'Historical fire analysis using ERA5 reanalysis data'
    })

@bp.route('/api/models', methods=['GET'])
def list_models():
    return jsonify({
        'models': list(MODELS.keys()),
        'model_variables': {
            'linear': LINEAR_VARIABLES,
            'complex': COMPLEX_VARIABLES
        }
    })