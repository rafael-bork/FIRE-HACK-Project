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

    rename_dict = {
        'duration_hours': 'duration_p',
        'pct_8p': '8_ny_fir_p',
        'pct_3_8': '3_8y_fir_p',
        'fstart': 'f_start',
        'FWI_12h': 'FWI_12h_av'
    }

    X = model_inputs.drop(columns=['latitude', 'longitude', 's_time']).rename(columns=rename_dict)
    missing_cols = set(model.get_booster().feature_names) - set(X.columns)
    if missing_cols:
        raise ValueError(f"Faltando colunas: {missing_cols}")
    X = X[model.get_booster().feature_names]

    # Fazer previsões
    predictions = model.predict(X)

    model_inputs['log_pred'] = predictions # log scale
    model_inputs['linear_pred'] = np.exp(predictions) - 1 # linear scale

    model_inputs = model_inputs.sort_values(by=["duration_hours", "latitude", "longitude"])

    # ------------------- Error Estimation -------------------
    with open(r'../../Data/Models/model_xgboost_error.pkl', 'rb') as f:
        import sklearn
        error_model = pickle.load(f)

    # Predict error based on linear ROS
    # Reshape if needed (polynomial models typically expect 2D input)
    linear_ros = model_inputs['linear_pred'].values.reshape(-1, 1)
    model_inputs['error_estimate'] = error_model.predict(linear_ros)


    # ------------------- Linear Model Predictions -------------------
    model_inputs = Create_inputs.Compile_data(duration, mins_since_fire_start, start_time)
    with open(r'../../Data/Models/model_linear_ffs.pkl', 'rb') as f:
        linear_model = pickle.load(f)

    rename_dict = {
        'duration_hours': 'duration_p',
        'pct_8p': '8_ny_fir_p',
        'pct_3_8': '3_8y_fir_p',
        'fstart': 'f_start',
        'FWI_12h': 'FWI_12h_av'
    }

    # Prepare features for linear model (adjust rename_dict if needed)
    X_linear = model_inputs.drop(columns=['latitude', 'longitude', 's_time']).rename(columns=rename_dict)

    # Check feature names - linear models from sklearn have feature_names_in_
    if hasattr(linear_model, 'feature_names_in_'):
        missing_cols_linear = set(linear_model.feature_names_in_) - set(X_linear.columns)
        if missing_cols_linear:
            raise ValueError(f"Linear model missing columns: {missing_cols_linear}")
        X_linear = X_linear[linear_model.feature_names_in_]

    linear_predictions = linear_model.predict(X_linear)
    model_inputs['log_pred_linear'] = linear_predictions
    model_inputs['linear_pred_linear'] = np.exp(linear_predictions) - 1

    # ------------------- Transformar em xarray -------------------
    df = model_inputs.copy()
    times = np.sort(df['s_time'].unique())
    lats = np.sort(df['latitude'].unique())
    lons = np.sort(df['longitude'].unique())
    durations = np.sort(df['duration_hours'].unique())
    fstarts = np.sort(df['fstart'].unique())

    dims = ('s_time', 'latitude', 'longitude', 'duration_hours', 'fstart')
    variables = ['fuel_load', 'pct_3_8', 'pct_8p', 'wv100_kh',
                  'FWI_12h', 'log_pred', 'linear_pred', 'error_estimate']

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
            ds_new[var][t_idx, lat_idx, lon_idx, dur_idx, fstart_idx] = row[var]


    # ------------------- Atualizar ou criar Master_Table -------------------
    if os.path.exists(master_file):
        with xr.open_dataset(master_file) as ds_master:
            ds_master = ds_master.sortby('s_time')
            ds_new = ds_new.sortby('s_time')

            # Concatenar todos os timestamps
            ds_combined = xr.concat([ds_master, ds_new], dim='s_time')
            ds_combined = ds_combined.sortby('s_time')

        # Salvar o dataset combinado
        ds_combined.to_netcdf(master_file)
        print("Master_Table atualizado:", master_file)
    else:
        # Salvar o novo dataset
        ds_new.to_netcdf(master_file)
        print("Master_Table criado:", master_file)
