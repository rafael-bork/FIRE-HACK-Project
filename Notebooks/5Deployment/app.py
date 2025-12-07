from flask import Flask, render_template, request, jsonify
from flask_cors import CORS
from backend.utils import Model_Prediction, Create_inputs
import pandas as pd
import os
import xarray as xr
import rasterio
from rasterio.transform import from_origin
import matplotlib.pyplot as plt
import numpy as np
import geopandas as gpd

app = Flask(__name__)
CORS(app)  # Enable CORS for frontend communication


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/api/predict-grid', methods=['POST'])
def predict_grid():
    """
    Main prediction endpoint that processes the grid prediction request.
    Expects JSON with: datetime, model, f_start, duration_p
    """
    try:
        # Get data from request
        data = request.get_json()
        datetime_str = data.get('datetime')

        model_type = data.get('model', 'complex')

        mins_since_fire_start = data.get('f_start', 0)

        duration = data.get('duration_p', 1)
        
        # Parse and round start time
        start_time = pd.to_datetime(datetime_str)

        # constrangimento de datas:
        MIN_DATE = pd.Timestamp('2015-01-01')
        MAX_DATE = pd.Timestamp('2025-12-31')

        if not (MIN_DATE <= start_time <= MAX_DATE):
            return jsonify({
                'success': False,
                'error': 'Date must be between Janurary 1st of 2015 and 2 weeks before the present time.'
            }), 400


        start_time = start_time.round('30min')

        ######## inicio do notebook do rafa #########
        
        master_file = "Data/Master_Table.nc"
        ds_master = None

        # ------------------- Checar se Master_Table existe -------------------
        if os.path.exists(master_file):
            with xr.open_dataset(master_file) as ds:
                ds_master = ds.load()  # Carrega em memória e fecha o arquivos

        # ------------------- Verificar se já existem dados válidos para todas as durations -------------------
        data_exists = False
        cols_to_check = ['fuel_load', 'pct_3_8', 'pct_8p', 
                 'wv100_kh', 'FWI_12h', 'log_pred', 'linear_pred']

        if ds_master is not None:
            valid = True
            for dur in range(1, duration + 1):
                try:
                    df_slice = ds_master.sel(
                        s_time=start_time,
                        duration_hours=dur,
                        fstart=mins_since_fire_start
                    ).to_dataframe().reset_index()

                    # Se nenhuma coluna de interesse tiver valor válido, a duração não está pronta
                    if not df_slice[cols_to_check].notna().any().any():
                        valid = False
                        break  # não precisa checar as próximas durations

                except KeyError:
                    valid = False
                    break

            data_exists = valid

        # ------------------- Extrair ou calcular -------------------
        if data_exists:
            print("Dados já existentes no Master_Table. Extraindo...")
            # Extrair todas as durations de 1 até duration
            model_inputs = ds_master.sel(
                s_time=start_time,
                duration_hours=slice(1, duration),
                fstart=mins_since_fire_start
            ).to_dataframe().reset_index()
        else:
            print("Calculando novos dados e atualizando Master_Table...")
            # Chama a função do Model_Prediction.py
            Model_Prediction.calculate_and_append_master(start_time, duration, mins_since_fire_start)

            # Depois de atualizar o NetCDF, abrir a fatia recém-calculada
            with xr.open_dataset(master_file) as ds:
                ds_master = ds.load()
                model_inputs = ds_master.sel(
                    s_time=start_time,
                    duration_hours=slice(1, duration),
                    fstart=mins_since_fire_start
                ).to_dataframe().reset_index()

        # ------------------- Limpar model_inputs -------------------
        # Remover linhas onde **todas essas colunas** são NaN
        model_inputs = model_inputs.dropna(subset=cols_to_check, how='all')

        # ------------------- Filtrar apenas células de Portugal -------------------
        portugal_cells = gpd.read_file('backend/utils/Data/Portugal_cells.gpkg')
        
        # Reproject to WGS84 (EPSG:4326) to match model_inputs
        portugal_cells = portugal_cells.to_crs('EPSG:4326')
        
        # Get valid coordinates from Portugal cells centroids (0.1° grid)
        centroids = portugal_cells.geometry.centroid
        valid_coords = set(zip(
            centroids.y.round(1),
            centroids.x.round(1)
        ))
        
        # Filter model_inputs by matching coordinates
        mask = [
            (round(lat, 1), round(lon, 1)) in valid_coords
            for lat, lon in zip(model_inputs['latitude'], model_inputs['longitude'])
        ]
        model_inputs = model_inputs[mask]
        
        # Select prediction column based on model type
        pred_col = 'linear_pred' if model_type == 'complex' else 'linear_pred' # isto ta errado !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
        
        # Input variable columns to include in response
        input_var_cols = ['fuel_load', 'pct_3_8', 'pct_8p', 'wv100_kh', 'FWI_12h']
        
        # Prepare predictions for response
        predictions = []
        total_cells = len(model_inputs)
        successful_cells = 0
        
        for _, row in model_inputs.iterrows():
            pred_value = row.get(pred_col)
            if pd.notna(pred_value):
                pred_entry = {
                    'lat': float(row['latitude']),
                    'lon': float(row['longitude']),
                    'prediction': float(pred_value),
                    'error_estimate': float(pred_value * 0.1),  # Placeholder error estimate
                    'input_vars': {}
                }
                
                # Add input variables
                for col in input_var_cols:
                    val = row.get(col)
                    pred_entry['input_vars'][col] = float(val) if pd.notna(val) else None
                
                predictions.append(pred_entry)
                successful_cells += 1
        
        # Generate TIFF outputs
        df_slice = model_inputs.copy()
        if pred_col in df_slice.columns:
            df_slice['linear_pred_smoothed'] = df_slice[pred_col]
            _generate_tiff_outputs(df_slice, duration, input_var_cols)
        
        return jsonify({
            'success': True,
            'predictions': predictions,
            'total_cells': total_cells,
            'successful_cells': successful_cells,
            'input_var_names': input_var_cols
        })
        
    except Exception as e:
        print(f"Error in predict_grid: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


def _generate_tiff_outputs(df_slice, max_duration, input_var_cols):
    """
    Generate TIFF output files for predictions and input variables.
    """
    if df_slice.empty or 'linear_pred_smoothed' not in df_slice.columns:
        return
    
    os.makedirs('Data/Output', exist_ok=True)
    
    # Get unique durations
    if 'duration_hours' not in df_slice.columns:
        return
    
    vmin = df_slice['linear_pred_smoothed'].min()
    vmax = df_slice['linear_pred_smoothed'].max()
    
    for duration in df_slice['duration_hours'].unique():
        df = df_slice[df_slice['duration_hours'] == duration]
        
        lat_vals = np.sort(df['latitude'].unique())
        lon_vals = np.sort(df['longitude'].unique())
        
        if len(lat_vals) < 2 or len(lon_vals) < 2:
            continue
        
        # Create pixel size and transform (shared for all outputs)
        pixel_size_lat = (lat_vals.max() - lat_vals.min()) / (len(lat_vals) - 1)
        pixel_size_lon = (lon_vals.max() - lon_vals.min()) / (len(lon_vals) - 1)
        transform = from_origin(
            lon_vals.min() - pixel_size_lon / 2,
            lat_vals.max() + pixel_size_lat / 2,
            pixel_size_lon,
            pixel_size_lat
        )
        
        # --- Generate ROS prediction TIFF ---
        data_grid = np.full((len(lat_vals), len(lon_vals)), np.nan)
        
        for i, lat in enumerate(lat_vals):
            for j, lon in enumerate(lon_vals):
                val = df[(df['latitude'] == lat) & (df['longitude'] == lon)]['linear_pred_smoothed']
                if not val.empty:
                    data_grid[i, j] = val.values[0]
        
        # Flip vertically for TIFF
        data_grid_to_save = np.flipud(data_grid)
        
        # Save ROS TIFF
        output_filename = f'Data/Output/ros_linear_pred_duration_{int(duration)}.tif'
        with rasterio.open(
            output_filename,
            'w',
            driver='GTiff',
            height=data_grid_to_save.shape[0],
            width=data_grid_to_save.shape[1],
            count=1,
            dtype=data_grid_to_save.dtype,
            crs='EPSG:4326',
            transform=transform,
            nodata=np.nan
        ) as dst:
            dst.write(data_grid_to_save, 1)
        
        # Save displacement TIFF (ROS * duration)
        displacement_grid = np.flipud(data_grid * duration)
        output_filename_disp = f'Data/Output/ros_displacement_duration_{int(duration)}.tif'
        with rasterio.open(
            output_filename_disp,
            'w',
            driver='GTiff',
            height=displacement_grid.shape[0],
            width=displacement_grid.shape[1],
            count=1,
            dtype=displacement_grid.dtype,
            crs='EPSG:4326',
            transform=transform,
            nodata=np.nan
        ) as dst:
            dst.write(displacement_grid, 1)
        
        # --- Generate Input Variable TIFFs ---
        for var_col in input_var_cols:
            if var_col not in df.columns:
                continue
            
            var_grid = np.full((len(lat_vals), len(lon_vals)), np.nan)
            
            for i, lat in enumerate(lat_vals):
                for j, lon in enumerate(lon_vals):
                    val = df[(df['latitude'] == lat) & (df['longitude'] == lon)][var_col]
                    if not val.empty and pd.notna(val.values[0]):
                        var_grid[i, j] = val.values[0]
            
            var_grid_to_save = np.flipud(var_grid)
            
            output_filename_var = f'Data/Output/input_{var_col}_duration_{int(duration)}.tif'
            with rasterio.open(
                output_filename_var,
                'w',
                driver='GTiff',
                height=var_grid_to_save.shape[0],
                width=var_grid_to_save.shape[1],
                count=1,
                dtype=var_grid_to_save.dtype,
                crs='EPSG:4326',
                transform=transform,
                nodata=np.nan
            ) as dst:
                dst.write(var_grid_to_save, 1)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5050, debug=True)