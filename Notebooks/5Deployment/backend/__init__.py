"""
Flask Backend for Fire ROS Prediction System
Provides API endpoints for model prediction and data fetching
"""

from flask import Flask
from flask_cors import CORS
from backend.utils.era5_fetch import CDS_AVAILABLE
from backend.models.loader import MODELS
from backend.config import MODEL_DIR, RASTER_DIR, ERA5_CACHE_DIR

def create_app():
    """Application factory pattern"""
    app = Flask(__name__, static_folder='..', static_url_path='')
    CORS(app)

    # Print startup information
    print("\n" + "="*60)
    print("🔥 Fire ROS Historical Analysis API Server")
    print("="*60)

    print(f"\nConfiguration:")
    print(f"   Models loaded: {list(MODELS.keys()) if MODELS else 'None'}")
    print(f"   Model directory: {MODEL_DIR} {'✓' if MODEL_DIR.exists() else '✗'}")
    print(f"   Raster directory: {RASTER_DIR} {'✓' if RASTER_DIR.exists() else '✗'}")
    print(f"   ERA5 cache: {ERA5_CACHE_DIR} {'✓' if ERA5_CACHE_DIR.exists() else '✗'}")

    print(f"\nCDS API Status:")
    if CDS_AVAILABLE:
        print(f"   ✓ CDS API configured and ready")
        print(f"   Data source: ERA5 Historical Reanalysis")
    else:
        print(f"   ✗ CDS API NOT CONFIGURED")
        print(f"\n   Setup Instructions:")
        print(f"   1. Register: https://cds.climate.copernicus.eu/")
        print(f"   2. Get API key from your profile")
        print(f"   3. Create ~/.cdsapirc with:")
        print(f"      url: https://cds.climate.copernicus.eu/api")
        print(f"      key: YOUR_UID:YOUR_API_KEY")

    # Register blueprints
    from backend.routes.base import bp as base_bp
    from backend.routes.location import bp as location_bp
    from backend.routes.predict import bp as predict_bp
    from backend.routes.raster import bp as raster_bp
    from backend.routes.cds_test import bp as cds_test_bp

    app.register_blueprint(base_bp)
    app.register_blueprint(location_bp)
    app.register_blueprint(predict_bp)
    app.register_blueprint(raster_bp)
    app.register_blueprint(cds_test_bp)

    print(f"\nEndpoints:")
    print(f"   GET  /api/status          - Check API status")
    print(f"   GET  /api/models          - List available models")
    print(f"   GET  /api/test-cds        - Test CDS connection")
    print(f"   POST /api/location-data   - Fetch weather + fuel data")
    print(f"   POST /api/predict         - Run prediction model")

    print(f"\nExample request:")
    print(f'   curl -X POST http://localhost:5050/api/location-data \\')
    print(f'     -H "Content-Type: application/json" \\')
    print(f'     -d \'{{"lat": 39.5, "lon": -8.0, "datetime": "2023-08-15 14:00"}}\'')

    print("\n" + "="*60)
    print(f"Server ready on http://localhost:5050")
    print("="*60 + "\n")

    return app
