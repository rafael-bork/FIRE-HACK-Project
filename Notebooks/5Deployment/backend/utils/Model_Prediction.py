import xarray as xr
import numpy as np
import pandas as pd
import pickle
import os
from . import Create_inputs
import importlib
importlib.reload(Create_inputs)

def calculate_and_append_master(start_time, duration, mins_since_fire_start, master_file="Data/Master_Table.nc"):
    """
    Calcula novos dados com Create_inputs.Compile_data e XGBoost, 
    e adiciona ao Master_Table.nc.
    """

    # ------------------- Calcular dados -------------------
    model_inputs = Create_inputs.Compile_data(duration, mins_since_fire_start, start_time)

    model_inputs['fstart'] = mins_since_fire_start

    # ------------------- Previsões XGBoost -------------------
    with open(r'../../Data/Models/model_xgboost.pkl', 'rb') as f:
        model = pickle.load(f)

    rename_dict_xgb = {
        'duration_hours': 'duration_p',
        'pct_8p': '8_ny_fir_p',
        'pct_3_8': '3_8y_fir_p',
        'fstart': 'f_start',
        'FWI_12h': 'FWI_12h_av'
    }

    X = model_inputs.drop(columns=['latitude', 'longitude', 's_time']).rename(columns=rename_dict_xgb)
    missing_cols = set(model.get_booster().feature_names) - set(X.columns)
    if missing_cols:
        raise ValueError(f"XGBoost missing columns: {missing_cols}")
    X = X[model.get_booster().feature_names]

    # Fazer previsões
    predictions = model.predict(X)

    model_inputs['log_pred'] = predictions  # log scale
    model_inputs['linear_pred'] = np.exp(predictions) - 1  # linear scale

    model_inputs = model_inputs.sort_values(by=["duration_hours", "latitude", "longitude"])

    # ------------------- Error Estimation for XGBoost -------------------
    with open(r'../../Data/Models/model_xgboost_error.pkl', 'rb') as f:
        error_model_xgb = pickle.load(f)

    linear_ros = model_inputs['linear_pred'].values.reshape(-1, 1)
    model_inputs['error_estimate'] = error_model_xgb.predict(linear_ros)

    # ------------------- Linear Model Predictions -------------------
    with open(r'../../Data/Models/model_linear_ffs.pkl', 'rb') as f:
        linear_model = pickle.load(f)

    # Signed log transformation function: sign * ln(|var| + 1)
    def signed_log1p(x):
        return np.sign(x) * np.log(np.abs(x) + 1)

    # Create all required features for linear model
    model_inputs['duration_p'] = model_inputs['duration_hours'].values
    
    # Signed log-transformed versions: sign * ln(|var| + 1)
    if 'DC_12h' in model_inputs.columns:
        model_inputs['DC_12h_av_log'] = signed_log1p(model_inputs['DC_12h'].values)
    
    if 'pct_3_8' in model_inputs.columns:
        model_inputs['3_8y_fir_p_log'] = signed_log1p(model_inputs['pct_3_8'].values)
    
    if 'Cape' in model_inputs.columns:
        model_inputs['Cape_av_log'] = signed_log1p(model_inputs['Cape'].values)
    
    # Direct mappings (no transformation)
    if 'HDW' in model_inputs.columns:
        model_inputs['HDW_av'] = model_inputs['HDW'].values
    
    if 'wv_850' in model_inputs.columns:
        model_inputs['wv_850_av'] = model_inputs['wv_850'].values
    
    if 'gT_8_7' in model_inputs.columns:
        model_inputs['gT_8_7_av'] = model_inputs['gT_8_7'].values

    # Get the exact feature order from the model
    if hasattr(linear_model, 'feature_names_in_'):
        linear_features = list(linear_model.feature_names_in_)
    elif hasattr(linear_model, 'steps'):
        # It's a pipeline - get feature names from first step
        for name, step in linear_model.steps:
            if hasattr(step, 'feature_names_in_'):
                linear_features = list(step.feature_names_in_)
                break
    else:
        # Fallback to manual order
        linear_features = ['DC_12h_av_log', '3_8y_fir_p_log', 'HDW_av', 'Cape_av_log', 'wv_850_av', 'gT_8_7_av', 'duration_p']

    print(f"Linear model expected feature order: {linear_features}")
    
    # Check which features are available
    available_linear_features = [f for f in linear_features if f in model_inputs.columns]
    missing_linear_features = set(linear_features) - set(available_linear_features)
    
    if missing_linear_features:
        print(f"Warning: Linear model missing columns: {missing_linear_features}")
        model_inputs['log_pred_linear'] = np.nan
        model_inputs['linear_pred_linear'] = np.nan
    else:
        # Use the EXACT order from the model
        X_linear = model_inputs[linear_features].copy()
        X_linear = X_linear.fillna(0)
        
        linear_predictions = linear_model.predict(X_linear)
        model_inputs['log_pred_linear'] = linear_predictions
        model_inputs['linear_pred_linear'] = np.exp(linear_predictions) - 1

    # ------------------- Error Estimation for Linear model -------------------
    with open(r'../../Data/Models/model_linear_error.pkl', 'rb') as f:
        error_model_linear = pickle.load(f)

    # Use linear model's predictions, not XGBoost's
    linear_ros_linear = model_inputs['linear_pred_linear'].values.reshape(-1, 1)
    model_inputs['error_estimate_linear'] = error_model_linear.predict(linear_ros_linear)

    # ------------------- Transformar em xarray -------------------
    df = model_inputs.copy()
    times = np.sort(df['s_time'].unique())
    lats = np.sort(df['latitude'].unique())
    lons = np.sort(df['longitude'].unique())
    durations = np.sort(df['duration_hours'].unique())
    fstarts = np.sort(df['fstart'].unique())

    dims = ('s_time', 'latitude', 'longitude', 'duration_hours', 'fstart')
    
    # Updated variables list to include linear model predictions
    variables = ['fuel_load', 'pct_3_8', 'pct_8p', 
                 'FWI_12h', 'log_pred', 'linear_pred', 'error_estimate',
                 'log_pred_linear', 'linear_pred_linear', 'error_estimate_linear',
                 'DC_12h', 'Cape', 'HDW', 'wv_850', 'gT_8_7']
    
    ds_new = xr.Dataset()
    for var in variables:
        ds_new[var] = xr.DataArray(
            np.full((len(times), len(lats), len(lons), len(durations), len(fstarts)), np.nan),
            coords={
                's_time': times,
                'latitude': lats,
                'longitude': lons,
                'duration_hours': durations,
                'fstart': fstarts
            },
            dims=dims
        )

    for idx, row in df.iterrows():
        t_idx = np.where(times == row['s_time'])[0][0]
        lat_idx = np.where(lats == row['latitude'])[0][0]
        lon_idx = np.where(lons == row['longitude'])[0][0]
        dur_idx = np.where(durations == row['duration_hours'])[0][0]
        fstart_idx = np.where(fstarts == row['fstart'])[0][0]

        for var in variables:
            if var in row.index and pd.notna(row[var]):
                ds_new[var][t_idx, lat_idx, lon_idx, dur_idx, fstart_idx] = row[var]

    # ------------------- Atualizar ou criar Master_Table -------------------
    if os.path.exists(master_file):
        with xr.open_dataset(master_file) as ds_master:
            ds_master = ds_master.sortby('s_time')
            ds_new = ds_new.sortby('s_time')

            ds_combined = xr.concat([ds_master, ds_new], dim='s_time')
            ds_combined = ds_combined.sortby('s_time')

        ds_combined.to_netcdf(master_file)
        print("Master_Table atualizado:", master_file)
    else:
        ds_new.to_netcdf(master_file)
        print("Master_Table criado:", master_file)