from flask import Blueprint, jsonify
from backend.utils.era5_fetch import CDS_AVAILABLE, get_cds_client

bp = Blueprint('cds_test', __name__)

@bp.route('/api/test-cds', methods=['GET'])
def test_cds():
    """Test CDS API connection with a simple request"""
    if not CDS_AVAILABLE:
        return jsonify({
            'success': False,
            'error': 'CDS API not installed. Install with: pip install cdsapi'
        }), 500

    try:
        # Try to initialize the CDS client
        client = get_cds_client()
        test_result = {
            'cds_available': True,
            'client_initialized': client is not None,
            'message': 'CDS API client initialized successfully'
        }
        return jsonify({
            'success': True,
            'result': test_result
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'CDS API client initialization failed: {str(e)}',
            'hint': 'Make sure ~/.cdsapirc is configured with your credentials'
        }), 500
