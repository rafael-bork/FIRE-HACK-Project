import pandas as pd
from backend.models.loader import MODELS
from backend.config import LINEAR_VARIABLES, COMPLEX_VARIABLES

# TODO: import weather vars .nc file here

def run_prediction(model_name, variables):
    if model_name not in MODELS:
        return {"success": False, "error": f'Model "{model_name}" not found'}

    model = MODELS[model_name]
    expected_vars = LINEAR_VARIABLES if model_name == 'linear' else COMPLEX_VARIABLES

    feature_values = []
    missing_vars = []

    for var in expected_vars:
        if var not in variables:
            missing_vars.append(var)
        else:
            feature_values.append(float(variables[var]))

    if missing_vars:
        return {"success": False, "error": f"Missing variables: {missing_vars}"}

    X = pd.DataFrame([feature_values], columns=expected_vars)
    prediction = model.predict(X)[0]
    error_estimate = abs(prediction * 0.15) # TODO: mega aldrabado, fix this.

    return {
        "success": True,
        "prediction": float(prediction),
        "unit": "m/min",
        "error_estimate": float(error_estimate),
        "model_used": model_name
    }