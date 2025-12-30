# Fire Rate of Spread Prediction Models

## Description
This repository contains two machine learning models developed to predict the Rate of Spread (ROS) of wildfires in Portugal, based on the enriched PT-FireSprd v3.0 database. The models were developed as part of the FIRE-HACK project during a hackathon.

## Models Overview

### 1. Complex Model (XGBoost Regressor)
- Type: Regression
- Algorithm: XGBoost
- Objective: High-accuracy prediction of fire Rate of Spread (ROS)
- Performance:
  - R²: 0.5283 (log space)
  - MAE: 384.3 m/h (linear space)
  - RMSE: 728.3 m/h (linear space)
- Input Variables (7 features):
  1. `duration_p` - Duration associated with ROS
  2. `3_8y_fir_p` - Percentage of area burned between 3 and 8 years before
  3. `8_ny_fir_p` - Percentage of area burned more than 8 years before
  4. `sW_100_av` - Average soil water content between 28 and 100cm depth
  5. `f_start` - Time since the beginning of the wildfire (minutes)
  6. `HDW_av` - Average Hot Dry Windy index

### 2. Linear Model (Ordinary Least Squares)
- Type: Linear Regression
- Algorithm: OLS
- Objective: Interpretable prediction of fire Rate of Spread
- Performance:
  - R²: 0.422 (log space)
  - MAE: 500.0 m/h (linear space)
  - RMSE: 894.8 m/h (linear space)
- Input Variables (7 features):
  1. `duration_p` - Duration associated with ROS
  2. `3_8y_fir_p_log` - Log of percentage of area burned between 3 and 8 years before
  3. `HDW_av` - Average Hot Dry Windy index
  4. `wv_850_av` - Average Horizontal Wind Speed at 850 hPa
  5. `Cape_av_log` - Log of average convective available potential energy
  6. `gT_8_7_av` - Average Temperature Gradient between 700hPa and 500hPa
  7. `DC_12h_av_log` - Log of average Drought Code
- Equation :
  ```
  ln(ROS) = 6.2374 + 0.2240HDW_av + 0.1116wv_850_av - 0.4613duration_p 
            - 0.2202Cape_av_log - 0.1744gT_8_7_av + 0.17563_8y_fir_p_log 
            + 0.2365DC_12h_av_log
  ROS = 511.55 * (1.2513^HDW_av) * (1.1181^wv_850_av) 
      * (0.6305^duration_p) * Cape_av^(-0.2202) 
      * (0.8399^gT_8_7_av) * (3_8y_fir_p)^(0.1756) 
      * (DC_12h_av)^(0.2365)
  ```

## How to Use the Models

### Prerequisites
```bash
pip install pandas numpy scikit-learn xgboost joblib
```

### Loading and Using the Models

```python
import joblib
import pandas as pd
import numpy as np

# Load the models
xgboost_model = joblib.load('model_xgboost.pkl')
linear_model = joblib.load('model_linear_ffs.pkl')

# Prepare input data
# Note: The models expect log-transformed ROS as output

def safe_log(x):
    """Safe logarithm transformation: sign(x) * ln(|x| + 1)"""
    return np.sign(x) * np.log(np.abs(x) + 1)

# Example input data for XGBoost model
xgboost_features = ['duration_p', '8_ny_fir_p', 'sW_100_av', '3_8y_fir_p', 'f_start', 'HDW_av']
                    
input_data_xgb = pd.DataFrame({
    'duration_p': [1.5],
    '3_8y_fir_p': [10.1],
    '8_ny_fir_p': [59.1],
    'sW_100_av': [0.21],
    'f_start': [1593],
    'HDW_av': [27268]
})

# Example input data for Linear model
linear_features = ['HDW_av', 'wv_850_av', 'duration_p', 'Cape_av_log', 'gT_8_7_av',
        '3_8y_fir_p_log', 'DC_12h_av_log']

input_data_linear = pd.DataFrame({
    'duration_p': [1.5],                    
    '3_8y_fir_p_log': [safe_log(10.1)],     
    'HDW_av': [27268],                      
    'wv_850_av': [23.5],                    
    'Cape_av_log': [safe_log(92.3)],        
    'gT_8_7_av': [-7.46],                   
    'DC_12h_av_log': [safe_log(700.2)],    
})

# Make predictions (these will be in log space)
ros_log_xgb = xgboost_model.predict(input_data_xgb[xgboost_features])
ros_log_linear = linear_model.predict(input_data_linear[linear_features])

# Convert to linear scale
ros_linear_xgb = np.exp(ros_log_xgb)
ros_linear_linear = np.exp(ros_log_linear)

print(f"XGBoost prediction: {ros_linear_xgb[0]:.1f} m/h")
print(f"Linear model prediction: {ros_linear_linear[0]:.1f} m/h")
```

## Model Performance Details

### Complex Model (XGBoost)
- Best Hyperparameters:
  - max_depth: 7
  - learning_rate: 0.117
  - reg_lambda: 3.787
  - reg_alpha: 1.956
- Training Method: Nested cross-validation (5 splits, 4 repeats)
- Feature Selection: SHAP-based importance with elbow method
- Notes: Model tends to underpredict extreme ROS values (>1500 m/h)

### Linear Model (OLS)
- Preprocessing: Median imputation, z-score normalization
- Feature Selection: Forward selection with MAE minimization
- Interpretation: Coefficients represent marginal effects on log(ROS)
- Limitations: Assumes linear relationships; less accurate for extreme values

## Limitations
1. Dataset Size: Models trained on only 1,173 fire progressions
2. Extreme Values: Both models struggle with ROS > 1500 m/h
3. Geographic Scope: Trained specifically on Portuguese wildfires
4. Temporal Scope: Data from 2015-2025 Portuguese fires only
