import numpy as np
from datetime import datetime
from backend.utils.era5_fetch import fetch_era5_single_levels, fetch_era5_pressure_levels, fetch_fire_weather_index, CDS_AVAILABLE, cds_client
from backend.utils.era5_extract import extract_value_at_point

def fetch_weather_data(lat, lon, datetime_str=None):
    if not CDS_AVAILABLE:
        return {"error": "CDS API not available"}

    target_dt = datetime.strptime(datetime_str, '%Y-%m-%d %H:%M')
    area = [lat + 0.5, lon - 0.5, lat - 0.5, lon + 0.5]

    ds_sl = fetch_era5_single_levels(lat, lon, target_dt, area)
    ds_pl = fetch_era5_pressure_levels(lat, lon, target_dt, area)
    ds_fwi = fetch_fire_weather_index(lat, lon, target_dt)

    u_100 = extract_value_at_point(ds_sl, 'u100', lat, lon) or 0
    v_100 = extract_value_at_point(ds_sl, 'v100', lat, lon) or 0
    cape = extract_value_at_point(ds_sl, 'cape', lat, lon) or 0
    swvl3 = extract_value_at_point(ds_sl, 'swvl3', lat, lon) or 0.2
    swvl4 = extract_value_at_point(ds_sl, 'swvl4', lat, lon) or 0.2

    wv100_k = np.sqrt(u_100**2 + v_100**2) * 3.6
    wv_850 = extract_value_at_point(ds_pl, 'q', lat, lon, pressure_level=850) or 0.005
    z_850 = extract_value_at_point(ds_pl, 'z', lat, lon, pressure_level=850) or 14000
    z_700 = extract_value_at_point(ds_pl, 'z', lat, lon, pressure_level=700) or 30000
    t_850 = extract_value_at_point(ds_pl, 't', lat, lon, pressure_level=850)
    t_850 = (t_850 - 273.15) if t_850 else 15
    t_700 = extract_value_at_point(ds_pl, 't', lat, lon, pressure_level=700)
    t_700 = (t_700 - 273.15) if t_700 else 5

    fwi = None
    if ds_fwi is not None:
        for fwi_var in ['fwi', 'fire_weather_index', 'FWI']:
            fwi = extract_value_at_point(ds_fwi, fwi_var, lat, lon)
            if fwi is not None:
                break
    if fwi is None:
        fwi = max(0, (t_850 - 10) * 2)

    sW_100_av = (swvl3 + swvl4) / 2
    gT_8_7_av = ((z_850 - z_700) / 9.81) / 1000

    result = {
        "sW_100_av": round(sW_100_av, 4),
        "FWI_12h_av": round(fwi, 2),
        "wv100_k_av": round(wv100_k, 2),
        "wv_850_av": round(wv_850 * 1000, 3),
        "Cape_av": round(cape, 1),
        "gT_8_7_av": round(gT_8_7_av, 3),
        "temperature_850": round(t_850, 1),
        "temperature_700": round(t_700, 1),
        "wind_100m_speed_kmh": round(wv100_k, 1),
        "wind_100m_u": round(u_100, 2),
        "wind_100m_v": round(v_100, 2),
        "soil_water_layer3": round(swvl3, 4),
        "soil_water_layer4": round(swvl4, 4),
        "source": "ERA5",
        "datetime": target_dt.isoformat(),
        "data_quality": "complete" if ds_fwi is not None else "partial_fwi_estimated"
    }

    ds_sl.close()
    ds_pl.close()
    if ds_fwi is not None:
        ds_fwi.close()

    return result