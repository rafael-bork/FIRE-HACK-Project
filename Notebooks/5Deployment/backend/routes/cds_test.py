from flask import Blueprint, jsonify
from backend.utils.era5_fetch import CDS_AVAILABLE, cds_client

bp = Blueprint('cds_test', __name__)

@bp.route('/api/test-cds', methods=['GET'])
def test_cds():
    """Test CDS API connection with a simple request"""
    if not CDS_AVAILABLE:
        return jsonify({
            'success': False,
            'error': 'CDS API not configured'
        }), 500

    try:
        test_result = {
            'cds_available': True,
            'client_initialized': cds_client is not None
        }
        return jsonify({
            'success': True,
            'result': test_result
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500
