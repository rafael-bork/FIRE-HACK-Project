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
    with open(r'../../Data/Models/XGBoost.pkl', 'rb') as f:
        model = pickle.load(f)

    rename_dict = {
        'duration_hours': 'duration_p',
        'sW_100': 'sW_100_av',
        'pct_8p': '8_ny_fir_p',
        'pct_3_8': '3_8y_fir_p',
        'fuel_load': 'f_load_av',
        'fstart': 'f_start',
        'FWI_12h': 'FWI_12h_av',
        'wv100_kh': 'wv100_k_av',
        'rh_2m': 'rh_2m_av',
        'wdir_950': 'wdi_950_av'
    }

    X = model_inputs.drop(columns=['latitude', 'longitude', 's_time']).rename(columns=rename_dict)
    missing_cols = set(model.get_booster().feature_names) - set(X.columns)
    if missing_cols:
        raise ValueError(f"Faltando colunas: {missing_cols}")
    X = X[model.get_booster().feature_names]
    predictions = model.predict(X)
    model_inputs['predictions'] = predictions
    model_inputs['linear_pred'] = 10**(predictions / 5) - 1
    model_inputs = model_inputs.sort_values(by=["duration_hours", "latitude", "longitude"])

    # ------------------- Transformar em xarray -------------------
    df = model_inputs.copy()
    times = np.sort(df['s_time'].unique())
    lats = np.sort(df['latitude'].unique())
    lons = np.sort(df['longitude'].unique())
    durations = np.sort(df['duration_hours'].unique())
    fstarts = np.sort(df['fstart'].unique())

    dims = ('s_time', 'latitude', 'longitude', 'duration_hours', 'fstart')
    variables = ['fuel_load', 'pct_3_8', 'pct_8p', 'rh_2m', 'wv100_kh',
                 'wdir_950', 'FWI_12h', 'predictions', 'linear_pred']

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
