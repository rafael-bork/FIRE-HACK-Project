import numpy as np
import xarray as xr
from scipy.interpolate import griddata
from multiprocessing import Pool, cpu_count

def interpolate_2d_array(data_array):
    """Interpolação 2D para um DataArray com dimensões (latitude, longitude)"""
    lon_grid, lat_grid = np.meshgrid(data_array.longitude, data_array.latitude)
    
    valid_mask = ~np.isnan(data_array.values)
    points_valid = np.column_stack([lat_grid[valid_mask], lon_grid[valid_mask]])
    values_valid = data_array.values[valid_mask]
    
    points_target = np.column_stack([lat_grid.ravel(), lon_grid.ravel()])
    
    if len(values_valid) > 3:
        interpolated = griddata(points_valid, values_valid, points_target, 
                               method='linear', fill_value=0)
    else:
        interpolated = np.zeros_like(data_array.values.ravel())
    
    return interpolated.reshape(data_array.shape)

# Função auxiliar para processar cada slice
def process_time_slice(args):
    var_data, i = args
    slice_2d = var_data.isel(valid_time=i)
    return interpolate_2d_array(slice_2d)

def interpolate_dataset(ds_FWI):
    print("Aplicando interpolação 2D com multiprocessamento...")
    
    data_vars_interp = {}
    
    for var in ds_FWI.data_vars:
        print(f"Processando {var}...")
        var_data = ds_FWI[var]
        
        # Preparar argumentos para Pool
        args_list = [(var_data, i) for i in range(len(var_data.valid_time))]
        
        with Pool(cpu_count()) as pool:
            interp_results = pool.map(process_time_slice, args_list)
        
        # Criar DataArray interpolado
        data_vars_interp[var] = xr.DataArray(
            np.array(interp_results),
            dims=['valid_time', 'latitude', 'longitude'],
            coords={
                'valid_time': ds_FWI.valid_time,
                'latitude': ds_FWI.latitude,
                'longitude': ds_FWI.longitude
            },
            name=var
        )
    
    ds_interp = xr.Dataset(data_vars_interp)
    # Substituir zeros por NaN para manter consistência com seu código original
    ds_interp = ds_interp.where(ds_interp != 0)
    
    print("Interpolação 2D concluída!")
    return ds_interp
