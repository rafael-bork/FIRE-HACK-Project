from flask import Flask, render_template, request, jsonify, Response
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
import json
import time
import threading
import uuid

app = Flask(__name__)
CORS(app)  

prediction_progress = {}


def send_sse_event(event_type, data):
    """Format a Server-Sent Event message."""
    return f"event: {event_type}\ndata: {json.dumps(data)}\n\n"


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/api/predict-grid-sse', methods=['GET'])
def predict_grid_sse():
    """
    SSE endpoint for grid prediction with real-time progress updates.
    Query params: datetime, model, f_start, duration_p
    """
    # Get parameters from query string
    datetime_str = request.args.get('datetime')
    model_type = request.args.get('model', 'complex')
    mins_since_fire_start = int(request.args.get('f_start', 0))
    duration = int(request.args.get('duration_p', 1))
    
    def generate():
        try:
            # --- Validation ---
            yield send_sse_event('progress', {
                'stage': 'validating',
                'message': 'Validating inputs...',
                'detail': 'Checking parameters'
            })
            
            if not datetime_str:
                yield send_sse_event('error', {'message': 'Missing datetime parameter'})
                return
            
            if duration > 24:
                yield send_sse_event('error', {'message': 'Duration cannot exceed 24 hours.'})
                return
            
            # Parse and round start time
            start_time = pd.to_datetime(datetime_str)
            
            # Date constraints
            MIN_DATE = pd.Timestamp('2015-01-01')
            three_months_ago = pd.Timestamp.now() - pd.DateOffset(months=3)
            
            if not (MIN_DATE <= start_time <= three_months_ago):
                yield send_sse_event('error', {
                    'message': f'Date must be between January 1st, 2015 and {three_months_ago.date()}.'
                })
                return
            
            start_time = start_time.round('30min')
            
            # --- Check Master Table ---
            yield send_sse_event('progress', {
                'stage': 'checking_cache',
                'message': 'Checking cache...',
                'detail': 'Looking for existing data'
            })
            
            master_file = "Data/Master_Table.nc"
            ds_master = None
            
            if os.path.exists(master_file):
                with xr.open_dataset(master_file) as ds:
                    ds_master = ds.load()
            
            # Check if data exists
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
                        
                        if not df_slice[cols_to_check].notna().any().any():
                            valid = False
                            break
                    except KeyError:
                        valid = False
                        break
                
                data_exists = valid
            
            # --- Fetch or Calculate Data ---
            if data_exists:
                yield send_sse_event('progress', {
                    'stage': 'loading_cache',
                    'message': 'Loading cached data...',
                    'detail': 'Data found in Master Table'
                })
                
                model_inputs = ds_master.sel(
                    s_time=start_time,
                    duration_hours=slice(1, duration),
                    fstart=mins_since_fire_start
                ).to_dataframe().reset_index()
            else:
                # Need to calculate new data - this is where the main work happens
                yield send_sse_event('progress', {
                    'stage': 'fetching_era5_sl',
                    'message': 'Fetching ERA5_SL...',
                    'detail': 'Surface level weather data'
                })
                
                # Small delay to allow frontend to render (the actual fetch happens in calculate_and_append_master)
                time.sleep(0.1)
                
                yield send_sse_event('progress', {
                    'stage': 'fetching_era5_fwi',
                    'message': 'Fetching ERA5 Data...',
                    'detail': 'This may take up to 1 minute'
                })
                
                # Call the calculation function
                # Note: Ideally, Model_Prediction would accept a callback for progress updates
                Model_Prediction.calculate_and_append_master(start_time, duration, mins_since_fire_start)
                
                yield send_sse_event('progress', {
                    'stage': 'processing',
                    'message': 'Processing grid...',
                    'detail': 'Computing predictions'
                })
                
                # Load the newly calculated data
                with xr.open_dataset(master_file) as ds:
                    ds_master = ds.load()
                    model_inputs = ds_master.sel(
                        s_time=start_time,
                        duration_hours=slice(1, duration),
                        fstart=mins_since_fire_start
                    ).to_dataframe().reset_index()
            
            # --- Clean and Filter Data ---
            yield send_sse_event('progress', {
                'stage': 'filtering',
                'message': 'Filtering data...',
                'detail': 'Applying Portugal mask'
            })
            
            model_inputs = model_inputs.dropna(subset=cols_to_check, how='all')
            
            # Filter to Portugal cells
            portugal_cells = gpd.read_file('backend/utils/Data/Portugal_cells.gpkg')
            portugal_cells = portugal_cells.to_crs('EPSG:4326')
            
            centroids = portugal_cells.geometry.centroid
            valid_coords = set(zip(
                centroids.y.round(1),
                centroids.x.round(1)
            ))
            
            mask = [
                (round(lat, 1), round(lon, 1)) in valid_coords
                for lat, lon in zip(model_inputs['latitude'], model_inputs['longitude'])
            ]
            model_inputs = model_inputs[mask]
            
            # --- Build Response ---
            yield send_sse_event('progress', {
                'stage': 'building_response',
                'message': 'Building response...',
                'detail': 'Organizing predictions'
            })
            
            pred_col = 'linear_pred' if model_type == 'complex' else 'linear_pred'
            input_var_cols = ['fuel_load', 'pct_3_8', 'pct_8p', 'wv100_kh', 'FWI_12h']
            
            predictions_by_duration = {}
            total_cells = 0
            successful_cells = 0
            
            unique_durations = sorted(model_inputs['duration_hours'].unique())
            
            for dur in unique_durations:
                dur_int = int(dur)
                df_dur = model_inputs[model_inputs['duration_hours'] == dur]
                predictions_by_duration[dur_int] = []
                
                for _, row in df_dur.iterrows():
                    total_cells += 1
                    pred_value = row.get(pred_col)
                    if pd.notna(pred_value):
                        displacement = float(pred_value) * dur_int
                        
                        pred_entry = {
                            'lat': float(row['latitude']),
                            'lon': float(row['longitude']),
                            'ros': float(pred_value),
                            'displacement': displacement,
                            'error_estimate': float(pred_value * 0.1),
                            'input_vars': {}
                        }
                        
                        for col in input_var_cols:
                            val = row.get(col)
                            pred_entry['input_vars'][col] = float(val) if pd.notna(val) else None
                        
                        predictions_by_duration[dur_int].append(pred_entry)
                        successful_cells += 1
            
            # Calculate increments
            increments_by_duration = {}
            ros_increments_by_duration = {}
            duration_list = sorted(predictions_by_duration.keys())
            
            for i, dur in enumerate(duration_list):
                if i == 0:
                    increments_by_duration[dur] = {
                        (p['lat'], p['lon']): p['displacement']
                        for p in predictions_by_duration[dur]
                    }
                    ros_increments_by_duration[dur] = {
                        (p['lat'], p['lon']): p['ros']
                        for p in predictions_by_duration[dur]
                    }
                else:
                    prev_dur = duration_list[i - 1]
                    prev_displacements = {
                        (p['lat'], p['lon']): p['displacement']
                        for p in predictions_by_duration[prev_dur]
                    }
                    prev_ros = {
                        (p['lat'], p['lon']): p['ros']
                        for p in predictions_by_duration[prev_dur]
                    }
                    increments_by_duration[dur] = {}
                    ros_increments_by_duration[dur] = {}
                    for p in predictions_by_duration[dur]:
                        key = (p['lat'], p['lon'])
                        prev_disp = prev_displacements.get(key, 0)
                        increments_by_duration[dur][key] = p['displacement'] - prev_disp
                        prev_ros_val = prev_ros.get(key, 0)
                        ros_increments_by_duration[dur][key] = p['ros'] - prev_ros_val
            
            for dur in predictions_by_duration:
                for p in predictions_by_duration[dur]:
                    key = (p['lat'], p['lon'])
                    p['increment'] = increments_by_duration[dur].get(key, p['displacement'])
                    p['ros_increment'] = ros_increments_by_duration[dur].get(key, p['ros'])
            
            # Generate TIFF outputs
            yield send_sse_event('progress', {
                'stage': 'generating_tiff',
                'message': 'Generating outputs...',
                'detail': 'Creating TIFF files'
            })
            
            df_slice = model_inputs.copy()
            if pred_col in df_slice.columns:
                df_slice['linear_pred_smoothed'] = df_slice[pred_col]
                _generate_tiff_outputs(df_slice, duration, input_var_cols)
            
            # --- Send Final Result ---
            yield send_sse_event('complete', {
                'success': True,
                'predictions_by_duration': predictions_by_duration,
                'durations': duration_list,
                'total_cells': total_cells,
                'successful_cells': successful_cells,
                'input_var_names': input_var_cols
            })
            
        except Exception as e:
            import traceback
            traceback.print_exc()
            yield send_sse_event('error', {'message': str(e)})
    
    return Response(
        generate(),
        mimetype='text/event-stream',
        headers={
            'Cache-Control': 'no-cache',
            'Connection': 'keep-alive',
            'X-Accel-Buffering': 'no'  # Disable nginx buffering
        }
    )


# Keep the original endpoint for backwards compatibility
@app.route('/api/predict-grid', methods=['POST'])
def predict_grid():
    """
    Original prediction endpoint (non-SSE).
    Kept for backwards compatibility.
    """
    try:
        data = request.get_json()
        datetime_str = data.get('datetime')
        model_type = data.get('model', 'complex')
        mins_since_fire_start = data.get('f_start', 0)
        duration = data.get('duration_p', 1)
        
        if duration > 24:
            return jsonify({
                'success': False,
                'error': 'Duration cannot exceed 24 hours.'
            }), 400
        
        start_time = pd.to_datetime(datetime_str)
        
        MIN_DATE = pd.Timestamp('2015-01-01')
        three_months_ago = pd.Timestamp.now() - pd.DateOffset(months=3)
        
        if not (MIN_DATE <= start_time <= three_months_ago):
            return jsonify({
                'success': False,
                'error': f'Date must be between January 1st, 2015 and 3 months prior to the present. ({three_months_ago.date()}).'
            }), 400
        
        start_time = start_time.round('30min')
        
        master_file = "Data/Master_Table.nc"
        ds_master = None
        
        if os.path.exists(master_file):
            with xr.open_dataset(master_file) as ds:
                ds_master = ds.load()
        
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
                    
                    if not df_slice[cols_to_check].notna().any().any():
                        valid = False
                        break
                except KeyError:
                    valid = False
                    break
            
            data_exists = valid
        
        if data_exists:
            model_inputs = ds_master.sel(
                s_time=start_time,
                duration_hours=slice(1, duration),
                fstart=mins_since_fire_start
            ).to_dataframe().reset_index()
        else:
            Model_Prediction.calculate_and_append_master(start_time, duration, mins_since_fire_start)
            
            with xr.open_dataset(master_file) as ds:
                ds_master = ds.load()
                model_inputs = ds_master.sel(
                    s_time=start_time,
                    duration_hours=slice(1, duration),
                    fstart=mins_since_fire_start
                ).to_dataframe().reset_index()
        
        model_inputs = model_inputs.dropna(subset=cols_to_check, how='all')
        
        portugal_cells = gpd.read_file('backend/utils/Data/Portugal_cells.gpkg')
        portugal_cells = portugal_cells.to_crs('EPSG:4326')
        
        centroids = portugal_cells.geometry.centroid
        valid_coords = set(zip(
            centroids.y.round(1),
            centroids.x.round(1)
        ))
        
        mask = [
            (round(lat, 1), round(lon, 1)) in valid_coords
            for lat, lon in zip(model_inputs['latitude'], model_inputs['longitude'])
        ]
        model_inputs = model_inputs[mask]
        
        pred_col = 'linear_pred' if model_type == 'complex' else 'linear_pred'
        input_var_cols = ['fuel_load', 'pct_3_8', 'pct_8p', 'wv100_kh', 'FWI_12h']
        
        predictions_by_duration = {}
        total_cells = 0
        successful_cells = 0
        
        unique_durations = sorted(model_inputs['duration_hours'].unique())
        
        for dur in unique_durations:
            dur_int = int(dur)
            df_dur = model_inputs[model_inputs['duration_hours'] == dur]
            predictions_by_duration[dur_int] = []
            
            for _, row in df_dur.iterrows():
                total_cells += 1
                pred_value = row.get(pred_col)
                if pd.notna(pred_value):
                    displacement = float(pred_value) * dur_int
                    
                    pred_entry = {
                        'lat': float(row['latitude']),
                        'lon': float(row['longitude']),
                        'ros': float(pred_value),
                        'displacement': displacement,
                        'error_estimate': float(pred_value * 0.1),
                        'input_vars': {}
                    }
                    
                    for col in input_var_cols:
                        val = row.get(col)
                        pred_entry['input_vars'][col] = float(val) if pd.notna(val) else None
                    
                    predictions_by_duration[dur_int].append(pred_entry)
                    successful_cells += 1
        
        increments_by_duration = {}
        ros_increments_by_duration = {}
        duration_list = sorted(predictions_by_duration.keys())
        
        for i, dur in enumerate(duration_list):
            if i == 0:
                increments_by_duration[dur] = {
                    (p['lat'], p['lon']): p['displacement']
                    for p in predictions_by_duration[dur]
                }
                ros_increments_by_duration[dur] = {
                    (p['lat'], p['lon']): p['ros']
                    for p in predictions_by_duration[dur]
                }
            else:
                prev_dur = duration_list[i - 1]
                prev_displacements = {
                    (p['lat'], p['lon']): p['displacement']
                    for p in predictions_by_duration[prev_dur]
                }
                prev_ros = {
                    (p['lat'], p['lon']): p['ros']
                    for p in predictions_by_duration[prev_dur]
                }
                increments_by_duration[dur] = {}
                ros_increments_by_duration[dur] = {}
                for p in predictions_by_duration[dur]:
                    key = (p['lat'], p['lon'])
                    prev_disp = prev_displacements.get(key, 0)
                    increments_by_duration[dur][key] = p['displacement'] - prev_disp
                    prev_ros_val = prev_ros.get(key, 0)
                    ros_increments_by_duration[dur][key] = p['ros'] - prev_ros_val
        
        for dur in predictions_by_duration:
            for p in predictions_by_duration[dur]:
                key = (p['lat'], p['lon'])
                p['increment'] = increments_by_duration[dur].get(key, p['displacement'])
                p['ros_increment'] = ros_increments_by_duration[dur].get(key, p['ros'])
        
        df_slice = model_inputs.copy()
        if pred_col in df_slice.columns:
            df_slice['linear_pred_smoothed'] = df_slice[pred_col]
            _generate_tiff_outputs(df_slice, duration, input_var_cols)
        
        return jsonify({
            'success': True,
            'predictions_by_duration': predictions_by_duration,
            'durations': duration_list,
            'total_cells': total_cells,
            'successful_cells': successful_cells,
            'input_var_names': input_var_cols
        })
        
    except Exception as e:
        print(f"Error in predict_grid: {str(e)}")
        import traceback
        traceback.print_exc()
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
        
        pixel_size_lat = (lat_vals.max() - lat_vals.min()) / (len(lat_vals) - 1)
        pixel_size_lon = (lon_vals.max() - lon_vals.min()) / (len(lon_vals) - 1)
        transform = from_origin(
            lon_vals.min() - pixel_size_lon / 2,
            lat_vals.max() + pixel_size_lat / 2,
            pixel_size_lon,
            pixel_size_lat
        )
        
        data_grid = np.full((len(lat_vals), len(lon_vals)), np.nan)
        
        for i, lat in enumerate(lat_vals):
            for j, lon in enumerate(lon_vals):
                val = df[(df['latitude'] == lat) & (df['longitude'] == lon)]['linear_pred_smoothed']
                if not val.empty:
                    data_grid[i, j] = val.values[0]
        
        data_grid_to_save = np.flipud(data_grid)
        
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
    app.run(host="0.0.0.0", port=5050, debug=True, threaded=True)