# 🔥 Fire ROS Prediction System - Deployment Guide

Complete deployment guide for the Fire Rate of Spread (ROS) prediction web application.

## 📋 Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [Data Preparation](#data-preparation)
3. [Backend Setup](#backend-setup)
4. [Frontend Configuration](#frontend-configuration)
5. [Deployment Options](#deployment-options)
6. [Troubleshooting](#troubleshooting)

---

## 🏗️ Architecture Overview

```
┌─────────────────┐
│  Frontend (HTML)│
│   Leaflet Map   │◄───┐
│   User Inputs   │    │
└─────────────────┘    │
         │             │
         │ HTTP        │ JSON
         │ Requests    │ Response
         ▼             │
┌─────────────────┐    │
│  Flask Backend  │────┘
│   (Python API)  │
└─────────────────┘
         │
         ├──► Models (Linear, XGBoost, RFR)
         ├──► Raster Data (COG files)
         └──► Weather APIs:
              - Open-Meteo (real-time)
              - CDS API / ERA5 (historical)
```

### Components:

- **Frontend**: HTML/CSS/JavaScript with Leaflet for maps
- **Backend**: Flask REST API serving predictions
- **Data Layer**: Cloud-Optimized GeoTIFFs for topography
- **External APIs**:
  - Open-Meteo (real-time weather, default)
  - CDS API / ERA5 (historical reanalysis, optional)

---

## 📊 Data Preparation

### 1️⃣ Convert NetCDF to Cloud-Optimized GeoTIFF

NetCDF files are not browser-compatible. Convert them to COG format:

```python
python convert_netcdf_to_cog.py
```

This script:
- Resamples rasters to **0.1° resolution**
- Converts to **Cloud-Optimized GeoTIFF (COG)**
- Adds internal tiling for efficient web streaming
- Compresses with DEFLATE for smaller file sizes

#### Why COG?

| Format | Browser Support | Streaming | File Size | Use Case |
|--------|----------------|-----------|-----------|----------|
| NetCDF | ❌ No | ❌ No | Medium | Scientific data storage |
| GeoTIFF | ⚠️ Partial | ❌ No | Large | Desktop GIS |
| **COG** | ✅ Yes | ✅ Yes | Medium | **Web maps (BEST)** |
| PNG Tiles | ✅ Yes | ✅ Yes | Large | Pre-rendered basemaps |

#### What to Convert:

```
Data/raw_netcdf/
├── elevation.nc      → web_rasters/elevation.tif
├── slope.nc          → web_rasters/slope.tif
├── aspect.nc         → web_rasters/aspect.tif
├── fuel_load.nc      → web_rasters/fuel_load.tif
└── vegetation.nc     → web_rasters/vegetation.tif
```

#### Manual Conversion (if needed):

```bash
# Using GDAL command line
gdal_translate -of COG \
  -co COMPRESS=DEFLATE \
  -co BLOCKSIZE=512 \
  input.nc output.tif

# Resample to 0.1° using gdalwarp
gdalwarp -tr 0.1 0.1 \
  -r bilinear \
  input.tif resampled.tif
```

---

## 🐍 Backend Setup

### Installation

```bash
cd Notebooks/5Deployment/

# Install Python dependencies
pip install -r requirements.txt

# Verify GDAL installation (required for COG)
python -c "from osgeo import gdal; print(gdal.__version__)"
```

### Directory Structure

```
5Deployment/
├── app.py                      # Flask backend
├── index.html                  # Frontend interface
├── convert_netcdf_to_cog.py   # Data conversion script
├── requirements.txt            # Python dependencies
└── README.md                   # This file

../../Data/
├── Models/
│   ├── Linear.pkl              # Trained models
│   ├── XGBoost.pkl
│   └── RFR.pkl
└── web_rasters/                # COG files for web
    ├── elevation.tif
    ├── slope.tif
    └── aspect.tif
```

### Running the Backend

```bash
python app.py
```

Expected output:
```
🔥 Starting Fire ROS Prediction API Server...
   Models loaded: ['linear']
   Raster directory: ../../Data/web_rasters
   Server running on http://localhost:5000
   API docs: http://localhost:5000/api/models
```

### API Endpoints

#### 1. Get Location Data
```http
POST /api/location-data
Content-Type: application/json

{
  "lat": 39.5,
  "lon": -8.0,
  "api": "openmeteo",  // optional: "openmeteo" (default) or "cds"
  "datetime": "2023-08-15 14:00"  // optional: for historical CDS queries
}
```

**Response:**
```json
{
  "success": true,
  "topography": {
    "elevation": 1240,
    "slope": 12.5,
    "aspect": 180
  },
  "meteorology": {
    "temperature": 25.3,
    "humidity": 32,
    "wind_speed": 15.2,
    "wind_direction": 270,
    "cloud_cover": 45,
    "solar_radiation": 800
  },
  "api_used": "openmeteo"
}
```

**For historical weather (CDS API):**
```json
{
  "lat": 39.5,
  "lon": -8.0,
  "api": "cds",
  "datetime": "2023-08-15 14:00"
}
```

See `CDS_API_GUIDE.md` for setup instructions.

#### 2. Run Prediction
```http
POST /api/predict
Content-Type: application/json

{
  "model": "linear",
  "variables": {
    "wind_speed_midflame": 5.2,
    "wind_direction": 270,
    "slope": 12,
    "1h_fuel_moisture": 8,
    "fuel_load": 1.5
  }
}
```

**Response:**
```json
{
  "success": true,
  "prediction": 8.45,
  "unit": "m/min",
  "error_estimate": 1.27,
  "model_used": "linear"
}
```

#### 3. Get Raster Value
```http
GET /api/raster/slope/value?lat=39.5&lon=-8.0
```

---

## 🌐 Frontend Configuration

### Update API URL

In `index.html` line 253, update the API base URL:

```javascript
// For local development
const API_BASE_URL = 'http://localhost:5000/api';

// For production deployment
const API_BASE_URL = 'https://your-domain.com/api';
```

### Opening the Interface

```bash
# Option 1: Flask serves it
python app.py
# Open http://localhost:5000

# Option 2: Direct file (for development)
# Open index.html in browser (Chrome/Firefox)
```

### Testing the Interface

1. **Click on the map** → Should fetch topography & weather data
2. **Fill in variables** → Input fire model parameters
3. **Select model type** → Choose Linear or Complex model
4. **Click "Run Model Prediction"** → Get ROS prediction

---

## 🚀 Deployment Options

### Option 1: Local Development (Current Setup)

```bash
python app.py
```
- ✅ Quick setup
- ✅ Good for testing
- ❌ Not accessible from internet

### Option 2: Production Server (Recommended)

#### Using Gunicorn (Linux/Mac):

```bash
pip install gunicorn

gunicorn -w 4 -b 0.0.0.0:5000 app:app
```

#### Using Waitress (Windows):

```bash
pip install waitress

waitress-serve --host=0.0.0.0 --port=5000 app:app
```

### Option 3: Cloud Deployment

#### **A. Heroku**

```bash
# Create Procfile
echo "web: gunicorn app:app" > Procfile

# Deploy
git init
heroku create your-fire-app
git push heroku main
```

#### **B. Google Cloud Run**

```dockerfile
# Dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
CMD ["gunicorn", "-b", "0.0.0.0:8080", "app:app"]
```

```bash
gcloud run deploy fire-ros --source .
```

#### **C. AWS EC2**

1. Launch Ubuntu instance
2. Install Python & dependencies
3. Configure nginx reverse proxy
4. Set up SSL with Let's Encrypt

### Option 4: Docker Container

```dockerfile
# Dockerfile
FROM python:3.11-slim

# Install GDAL
RUN apt-get update && apt-get install -y \
    gdal-bin \
    libgdal-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 5000

CMD ["python", "app.py"]
```

```bash
docker build -t fire-ros .
docker run -p 5000:5000 fire-ros
```

---

## 🔧 Troubleshooting

### ❌ CORS Errors

**Problem:** Browser blocks requests from file:// to http://localhost

**Solution:**
```python
# In app.py, ensure CORS is enabled
from flask_cors import CORS
CORS(app)
```

### ❌ GDAL Not Found

**Problem:** `ImportError: No module named 'osgeo'`

**Solution:**
```bash
# Ubuntu/Debian
sudo apt-get install gdal-bin python3-gdal

# macOS
brew install gdal
pip install gdal

# Windows
# Use conda instead
conda install -c conda-forge gdal
```

### ❌ Model File Not Found

**Problem:** `FileNotFoundError: Linear.pkl`

**Solution:** Update paths in `app.py`:
```python
MODEL_DIR = Path('../../Data/Models')  # Adjust to your structure
```

### ❌ Raster Returns None

**Problem:** Coordinates outside raster bounds

**Solution:**
1. Check raster extent with:
```python
import rasterio
with rasterio.open('slope.tif') as src:
    print(src.bounds)  # (min_lon, min_lat, max_lon, max_lat)
```
2. Ensure clicked coordinates are within bounds

### ❌ Weather API Fails

**Problem:** Open-Meteo rate limiting

**Solution:**
- Free tier: 10,000 requests/day
- Implement caching (already done in `app.py`)
- Consider upgrading for production

---

## 📦 Data Format Recommendations

### For Your Use Case:

1. **Topography Data (Elevation, Slope, Aspect)**
   - Format: **Cloud-Optimized GeoTIFF**
   - Resolution: **0.1° (~11km)**
   - Why: Static data, efficient streaming

2. **Weather Data (Temperature, Wind, Humidity)**
   - Format: **API calls to Open-Meteo**
   - Why: Real-time, changes frequently

3. **Fuel Data (Vegetation, Fuel Load)**
   - Format: **Cloud-Optimized GeoTIFF**
   - Resolution: **0.1°**
   - Why: Semi-static, updated seasonally

4. **Fire Risk Output (Model Predictions)**
   - Format: **Generated on-the-fly**
   - Or: **Pre-computed GeoTIFF** (if running batch predictions)

### Storage Comparison:

| Data Type | NetCDF (original) | GeoTIFF | COG | Verdict |
|-----------|------------------|---------|-----|---------|
| Size | 50 MB | 100 MB | 60 MB | **COG wins** |
| Load time | ❌ Server-only | 🐢 Full download | ✅ Partial | **COG wins** |
| Browser support | ❌ No | ⚠️ Yes | ✅ Yes | **COG wins** |

---

## 🎯 Next Steps

1. ✅ Convert NetCDF files to COG
2. ✅ Test Flask backend locally
3. ✅ Verify map interface works
4. ⬜ Add more trained models (XGBoost, RFR)
5. ⬜ Deploy to cloud platform
6. ⬜ Set up SSL certificate
7. ⬜ Implement user authentication (if needed)
8. ⬜ Add batch prediction mode (upload CSV)

---

## 📚 Additional Resources

- **Flask Documentation**: https://flask.palletsprojects.com/
- **Leaflet Mapping**: https://leafletjs.com/
- **Open-Meteo API**: https://open-meteo.com/
- **GDAL COG Driver**: https://gdal.org/drivers/raster/cog.html
- **GeoTIFF.js** (alternative for client-side rendering): https://geotiffjs.github.io/

---

**Questions?** Check the [Troubleshooting](#troubleshooting) section or open an issue.
