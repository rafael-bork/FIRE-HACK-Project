# 🌦️ CDS API (ERA5) Integration Guide

This guide explains how to use the CDS API (Climate Data Store) for accessing ERA5 historical reanalysis weather data in your Fire ROS prediction system.

## 📋 Overview

### What is CDS API?

The Climate Data Store (CDS) API provides access to ERA5 reanalysis data from the European Centre for Medium-Range Weather Forecasts (ECMWF). ERA5 is a comprehensive reanalysis dataset covering weather conditions from 1940 to near-present.

### When to Use Each API?

| API | Data Type | Latency | Best For | Cost |
|-----|-----------|---------|----------|------|
| **Open-Meteo** | Real-time forecast | Instant | Current conditions, predictions | Free |
| **CDS API (ERA5)** | Historical reanalysis | ~5 days delay | Historical fire analysis, model training | Free |

**Key Difference:**
- **Open-Meteo**: "What is the weather RIGHT NOW?" ⏰
- **CDS API**: "What was the weather on August 15, 2023 at 14:00?" 📅

---

## 🔧 Setup CDS API

### Step 1: Create Free CDS Account

1. Go to: https://cds.climate.copernicus.eu/
2. Click "Register" and create an account
3. Log in to your account

### Step 2: Get API Credentials

1. Go to: https://cds.climate.copernicus.eu/api-how-to
2. Copy your **UID** and **API key**

### Step 3: Configure API Credentials

Create a file `~/.cdsapirc` with your credentials:

**Linux/Mac:**
```bash
cat > ~/.cdsapirc << EOF
url: https://cds.climate.copernicus.eu/api/v2
key: YOUR_UID:YOUR_API_KEY
EOF
```

**Windows:**
Create file `C:\Users\YourUsername\.cdsapirc`:
```
url: https://cds.climate.copernicus.eu/api/v2
key: YOUR_UID:YOUR_API_KEY
```

Replace `YOUR_UID:YOUR_API_KEY` with your actual credentials (e.g., `12345:abcdef12-3456-7890-abcd-ef1234567890`)

### Step 4: Install Python Package

```bash
pip install cdsapi
```

### Step 5: Verify Installation

```bash
python app.py
```

Look for:
```
✅ CDS API client initialized
```

If you see this, CDS API is ready!

---

## 📊 Available ERA5 Variables

### Variables in Current Implementation:

From **ERA5 Land** dataset:

| Variable | Description | Unit |
|----------|-------------|------|
| `2m_temperature` | Temperature at 2 meters | °C |
| `2m_dewpoint_temperature` | Dewpoint temperature | °C |
| `10m_u_component_of_wind` | U-component of wind (E-W) | m/s |
| `10m_v_component_of_wind` | V-component of wind (N-S) | m/s |
| `surface_pressure` | Surface pressure | hPa |

**Derived:**
- `wind_speed`: Calculated from u/v components (km/h)
- `wind_direction`: Calculated from u/v components (degrees)
- `relative_humidity`: Calculated from temp + dewpoint (%)

### Additional Variables (From Your Extraction Notebook):

From **ERA5 Single Levels**:
- `100m_u_component_of_wind`, `100m_v_component_of_wind`
- `total_cloud_cover`, `high_cloud_cover`, `low_cloud_cover`, `medium_cloud_cover`
- `cloud_base_height`
- `boundary_layer_height`
- `volumetric_soil_water_layer_1` through `_4`

From **ERA5 Pressure Levels** (950, 850, 700, 500, 300 hPa):
- `geopotential`
- `relative_humidity`
- `temperature`
- `u_component_of_wind`, `v_component_of_wind`
- `vertical_velocity`

---

## 🚀 Usage Examples

### 1. Real-Time Data (Open-Meteo) - Default

When a user clicks on the map without specifying a datetime:

```javascript
// Frontend request
const response = await fetch('http://localhost:5000/api/location-data', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({
        lat: 39.5,
        lon: -8.0
    })
});
```

**Result:** Current weather conditions from Open-Meteo

### 2. Historical Data (CDS API)

To query historical fire event weather:

```javascript
// Frontend request for historical data
const response = await fetch('http://localhost:5000/api/location-data', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({
        lat: 39.5,
        lon: -8.0,
        api: 'cds',
        datetime: '2023-08-15 14:00'  // ISO format: YYYY-MM-DD HH:MM
    })
});
```

**Result:** ERA5 reanalysis data for that specific date/time

### 3. Python Direct Usage

```python
from app import fetch_weather_data_cds

# Get weather for a historical fire event
weather = fetch_weather_data_cds(
    lat=39.5,
    lon=-8.0,
    datetime_str='2023-08-15 14:00'
)

print(weather)
```

Output:
```python
{
    'temperature': 28.5,
    'humidity': 32.1,
    'wind_speed': 18.2,  # km/h
    'wind_direction': 270.5,  # degrees
    'pressure': 1013.2,  # hPa
    'source': 'ERA5',
    'datetime': '2023-08-15T14:00:00',
    'note': 'Cloud cover and solar radiation not available in ERA5 Land'
}
```

---

## 💾 Caching

ERA5 data is **automatically cached** to avoid repeated API calls:

**Cache Location:**
```
Data/Interim/Meteorological_data/ERA5_cache/
```

**Cache Format:**
```
ERA5_20230815_14_39.50_-8.00.nc
     ^        ^  ^     ^
     Date     Hour Lat  Lon
```

**Benefits:**
- ✅ Faster subsequent queries
- ✅ Reduces API usage
- ✅ Works offline for previously queried data

---

## 🔀 Switching Default API

### Option 1: Environment Variable

```bash
# Use CDS API by default
export WEATHER_API=cds
python app.py
```

### Option 2: Edit `app.py`

```python
# Line 42 in app.py
WEATHER_API = os.getenv('WEATHER_API', 'cds')  # Change 'openmeteo' to 'cds'
```

---

## ⚠️ Limitations & Considerations

### 1. Data Availability Delay

ERA5 has a ~5 day delay. For recent dates:
```
Today: Nov 26, 2024
Available until: Nov 21, 2024
```

The backend automatically falls back to Open-Meteo for recent dates.

### 2. API Rate Limits

**CDS API Free Tier:**
- ~100,000 requests/day
- Queued processing (can take 1-10 minutes)

**Open-Meteo:**
- 10,000 requests/day
- Instant response

### 3. Missing Variables in ERA5 Land

Variables **NOT available** in current implementation:
- ❌ Cloud cover (requires ERA5 Single Levels)
- ❌ Solar radiation (requires ERA5 Single Levels)
- ❌ 100m wind (requires ERA5 Single Levels)

To add these, you need to make a second CDS API request to `reanalysis-era5-single-levels`.

### 4. Spatial Resolution

| Dataset | Resolution |
|---------|-----------|
| Open-Meteo | ~11 km (0.1°) |
| ERA5 Land | ~9 km (0.1°) |
| ERA5 | ~31 km (0.28°) |

---

## 🔧 Adding More ERA5 Variables

To fetch cloud cover and solar radiation, add this to `app.py`:

```python
# In fetch_weather_data_cds function, after ERA5 Land request:

# ERA5 Single Levels request (cloud cover, radiation)
request_sl = {
    "product_type": ["reanalysis"],
    "variable": [
        "total_cloud_cover",
        "surface_solar_radiation_downwards"
    ],
    "year": str(target_dt.year),
    "month": f"{target_dt.month:02d}",
    "day": [f"{target_dt.day:02d}"],
    "time": [f"{target_dt.hour:02d}:00"],
    "data_format": "netcdf",
    "download_format": "unarchived",
    "area": area
}

cache_file_sl = cache_file.with_name(cache_file.stem + '_SL.nc')
cds_client.retrieve("reanalysis-era5-single-levels", request_sl, str(cache_file_sl))

ds_sl = xr.open_dataset(cache_file_sl)
ds_point_sl = ds_sl.sel(latitude=lat, longitude=lon, method='nearest')

result['cloud_cover'] = float(ds_point_sl['tcc'].values) * 100  # fraction to %
result['solar_radiation'] = float(ds_point_sl['ssrd'].values) / 3600  # J/m² to W/m²
```

---

## 📈 Use Cases

### 1. Historical Fire Analysis

Analyze weather conditions during past fire events:

```python
fire_events = [
    {'date': '2017-06-17 15:00', 'lat': 39.8, 'lon': -8.1, 'name': 'Pedrógão Grande'},
    {'date': '2017-10-15 13:00', 'lat': 40.2, 'lon': -8.4, 'name': 'Lousã'},
]

for event in fire_events:
    weather = fetch_weather_data_cds(
        lat=event['lat'],
        lon=event['lon'],
        datetime_str=event['date']
    )
    print(f"{event['name']}: Wind={weather['wind_speed']} km/h, Temp={weather['temperature']}°C")
```

### 2. Model Training

Generate training datasets with actual historical weather:

```python
import pandas as pd

# Load fire progression data
fire_data = pd.read_csv('fire_events.csv')

# Add ERA5 weather for each event
for idx, row in fire_data.iterrows():
    weather = fetch_weather_data_cds(
        lat=row['lat'],
        lon=row['lon'],
        datetime_str=row['datetime']
    )
    fire_data.loc[idx, 'wind_speed'] = weather['wind_speed']
    fire_data.loc[idx, 'temperature'] = weather['temperature']
    fire_data.loc[idx, 'humidity'] = weather['humidity']

fire_data.to_csv('fire_events_with_ERA5_weather.csv')
```

### 3. Validation

Compare model predictions against actual historical conditions:

```python
# Predict using historical weather
prediction = model.predict(historical_weather_data)

# Compare with actual fire spread
accuracy = compare_with_actual(prediction, actual_ros)
```

---

## 🐛 Troubleshooting

### Error: "CDS API not available"

**Solution:**
1. Check `~/.cdsapirc` exists and contains correct credentials
2. Verify API key at https://cds.climate.copernicus.eu/user
3. Test connection:
```python
import cdsapi
client = cdsapi.Client()
print("✅ CDS API connected!")
```

### Error: "Request too recent"

ERA5 has ~5 day delay. For recent dates, the system automatically uses Open-Meteo.

### Error: "Request taking too long"

CDS API queues requests. First-time downloads can take 5-10 minutes. Subsequent requests use cache and are instant.

### Cache Taking Too Much Space

Clear old cache files:
```bash
# Linux/Mac
rm Data/Interim/Meteorological_data/ERA5_cache/*.nc

# Windows
del Data\Interim\Meteorological_data\ERA5_cache\*.nc
```

---

## 📚 Additional Resources

- **CDS API Documentation**: https://cds.climate.copernicus.eu/api-how-to
- **ERA5 Documentation**: https://confluence.ecmwf.int/display/CKB/ERA5
- **ERA5 Land vs ERA5**: https://confluence.ecmwf.int/display/CKB/ERA5-Land
- **Your Extraction Notebook**: `Notebooks/1Extraction/CDS_API_Download.ipynb`

---

## ✅ Summary

| Feature | Status |
|---------|--------|
| Open-Meteo (Real-time) | ✅ Always available |
| CDS API (Historical) | ✅ Available with setup |
| Auto-caching | ✅ Enabled |
| Fallback for recent dates | ✅ Automatic |
| Cloud cover from ERA5 | ⚠️ Requires additional code |

**Default behavior:** Open-Meteo for real-time, CDS API optional for historical analysis.
