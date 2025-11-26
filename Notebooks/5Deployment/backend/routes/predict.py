from flask import Blueprint, request, jsonify
from backend.models.predict import run_prediction

bp = Blueprint('predict', __name__)

@bp.route('/api/predict', methods=['POST'])
def predict_ros():
    data = request.get_json()
    model_name = data.get('model', 'linear')
    variables = data.get('variables', {})
    return jsonify(run_prediction(model_name, variables))