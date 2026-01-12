# NCDF_Consolidation_1.py
import os
import xarray as xr

# ------------------------
# Função segura para Single Levels (SL)
# ------------------------
def compute_and_save_SL(ds_SL, out_path, chunk_sizes={"valid_time":100, "latitude":20, "longitude":20}, compress_level=4):
    """
    Computa o dataset Dask de Single Levels, carrega na memória, e salva um único NetCDF.
    Seguro para Windows: evita PermissionError.
    
    Parameters
    ----------
    ds_SL : xarray.Dataset
        Dataset Dask de Single Levels.
    out_path : str
        Caminho do NetCDF final.
    chunk_sizes : dict
        Tamanho dos chunks para Dask.
    compress_level : int
        Nível de compressão zlib (1-9).
    """
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    print("🔹 Computando Single Levels...")

    # Aplicar chunking Dask
    ds_SL = ds_SL.chunk(chunk_sizes)

    # Forçar cálculo e carregar na memória
    ds_loaded = ds_SL.load()  # Dask executa aqui

    # Encoding com compressão
    encoding = {
        var: {
            'zlib': True,
            'complevel': compress_level,
            'chunksizes': tuple(chunk_sizes.values())
        } for var in ds_loaded.data_vars
    }

    # Encoding coordenadas
    encoding['valid_time'] = {'dtype': 'int64'}
    encoding['latitude'] = {'dtype': 'float32'}
    encoding['longitude'] = {'dtype': 'float32'}

    # Salvar NetCDF de forma segura com `with`
    with xr.Dataset(ds_loaded) as ds_final:
        ds_final.to_netcdf(out_path, encoding=encoding)

    print(f"✅ NetCDF Single Levels guardado em {out_path}")


# ------------------------
# Função para Pressure Levels (PL)
# ------------------------
def compute_and_save_PL(ds_PL, out_path, chunk_sizes={"valid_time":100, "latitude":20, "longitude":20, "pressure_level":5}, compress=False):
    """
    Salva o dataset de Pressure Levels em NetCDF, acelerando a escrita com chunking.
    
    Parameters
    ----------
    ds_PL : xarray.Dataset
        Dataset Dask de Pressure Levels.
    out_path : str
        Caminho do NetCDF final.
    chunk_sizes : dict
        Tamanho dos chunks para Dask.
    compress : bool
        Se True, aplica compressão zlib; False = mais rápido.
    """
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    print("🔹 Computando e salvando Pressure Levels...")

    # Aplicar chunking
    ds_PL = ds_PL.chunk(chunk_sizes)

    # Encoding
    encoding = {
        var: {
            "zlib": compress,
            "chunksizes": tuple(chunk_sizes.values())
        } for var in ds_PL.data_vars
    }

    # Salvar NetCDF
    with xr.Dataset(ds_PL) as ds_final:
        ds_final.to_netcdf(out_path, encoding=encoding)

    print(f"✅ NetCDF Pressure Levels guardado em {out_path}")
