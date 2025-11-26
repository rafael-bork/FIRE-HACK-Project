from flask import Flask
from flask_cors import CORS

# Create Flask app
app = Flask(__name__, static_folder='.', static_url_path='')
CORS(app)

# Register routes
from backend.routes import base, predict, location, raster, cds_test

app.register_blueprint(base.bp)
app.register_blueprint(predict.bp)
app.register_blueprint(location.bp)
app.register_blueprint(raster.bp)
app.register_blueprint(cds_test.bp)