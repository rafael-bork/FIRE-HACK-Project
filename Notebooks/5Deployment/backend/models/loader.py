import joblib
from backend.config import MODEL_DIR

MODELS = {}

def load_models():
    global MODELS
    try:
        if (MODEL_DIR / 'Linear.pkl').exists():
            MODELS['linear'] = joblib.load(MODEL_DIR / 'Linear.pkl')
        if (MODEL_DIR / 'XGBoost.pkl').exists():
            MODELS['xgboost'] = joblib.load(MODEL_DIR / 'XGBoost.pkl')
        print(f"Models loaded: {list(MODELS.keys())}")
    except Exception as e:
        print(f"Warning: Could not load some models: {e}")

load_models()