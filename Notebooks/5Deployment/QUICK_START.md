# 🚀 Quick Start Guide

Get your Fire ROS prediction system up and running in 5 minutes!

## 📋 Prerequisites

- Python 3.11+
- GDAL library installed
- Trained models in `Data/Models/`

## ⚡ Quick Setup

### Step 1: Install Dependencies

```bash
cd Notebooks/5Deployment/
pip install -r requirements.txt
```

### Step 2: Convert Your NetCDF Data (if needed)

```bash
python convert_netcdf_to_cog.py
```

**Important:** Edit the script first to point to your NetCDF directory!

### Step 3: Start the Server

**Linux/Mac:**
```bash
chmod +x start_server.sh
./start_server.sh
```

**Windows:**
```batch
start_server.bat
```

**Or manually:**
```bash
python app.py
```

### Step 4: Open the Interface

Open your browser and go to:
```
http://localhost:5000
```

## 🎯 Usage

1. **Click on the map** to select a location
   - Topography data (elevation, slope) will load automatically
   - Weather data will be fetched from Open-Meteo API

2. **Fill in the fire model variables**
   - Use the manual input form
   - Or upload a CSV with all variables

3. **Select your model**
   - Linear Model (5 variables)
   - Complex Model (20 variables)

4. **Click "Run Model Prediction"**
   - Get Rate of Spread prediction in m/min
   - See estimated error

## 📊 Data Format Summary

### ✅ Recommended: Cloud-Optimized GeoTIFF (COG)

**Why?**
- ✅ Web browser compatible
- ✅ Efficient streaming (tiled access)
- ✅ Smaller than standard GeoTIFF
- ✅ Works with Leaflet + GeoTIFF.js

**How?**
```python
python convert_netcdf_to_cog.py
```

### Resolution: 0.1°

**Why 0.1 degrees?**
- Good balance between detail and file size
- ~11 km resolution at equator
- Suitable for regional fire prediction
- Fast loading on web browsers

**Trade-offs:**

| Resolution | File Size | Load Time | Use Case |
|-----------|-----------|-----------|----------|
| 0.01° | Very Large | Slow | Local, high-detail |
| **0.1°** | **Medium** | **Fast** | **Regional (BEST)** |
| 0.5° | Small | Very Fast | Continental |

## 🏗️ Architecture Summary

```
HTML/JavaScript (Frontend)
        ↓
    Flask API (Backend)
        ↓
    ┌────┴────┐
    ↓         ↓
Models      Rasters
(.pkl)      (.tif)
```

## 🔌 Connecting HTML to Python

### The Problem:
- HTML runs in browser (JavaScript)
- Python runs on server
- They can't directly communicate!

### The Solution: REST API

**1. Python (Flask) exposes endpoints:**
```python
@app.route('/api/predict', methods=['POST'])
def predict_ros():
    data = request.get_json()
    prediction = model.predict(data['variables'])
    return jsonify({'prediction': prediction})
```

**2. JavaScript calls those endpoints:**
```javascript
const response = await fetch('http://localhost:5000/api/predict', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({variables: {...}})
});
const result = await response.json();
```

**3. Data flows back and forth as JSON**

## 🛠️ API Requests Explained

### Example: Weather Data Request

**JavaScript (Frontend):**
```javascript
async function getWeatherData(lat, lon) {
    const response = await fetch('http://localhost:5000/api/location-data', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({lat: 39.5, lon: -8.0})
    });

    const data = await response.json();
    console.log(data.meteorology.wind_speed); // 15.2 km/h
}
```

**Python (Backend):**
```python
@app.route('/api/location-data', methods=['POST'])
def get_location_data():
    data = request.get_json()  # {lat: 39.5, lon: -8.0}

    # Call weather API
    weather = fetch_weather_data(data['lat'], data['lon'])

    # Return as JSON
    return jsonify({
        'success': True,
        'meteorology': weather
    })
```

**Flow:**
```
Browser → HTTP POST → Flask → Weather API
                              → Process
                              → Return JSON
Browser ← JSON Response ←───────┘
```

## 📁 File Overview

| File | Purpose |
|------|---------|
| `app.py` | Flask backend (Python API) |
| `index.html` | Main web interface |
| `convert_netcdf_to_cog.py` | Data conversion script |
| `map_overlay_example.html` | Example: Display rasters on map |
| `requirements.txt` | Python dependencies |
| `README.md` | Full documentation |
| `QUICK_START.md` | This file! |

## 🐛 Common Issues

### ❌ "Cannot fetch data" errors

**Check:**
1. Is Flask running? (`python app.py`)
2. Is the URL correct? (`http://localhost:5000/api`)
3. Are CORS headers enabled? (already in `app.py`)

### ❌ "Model not found" errors

**Solution:**
```bash
# Make sure models exist
ls ../../Data/Models/Linear.pkl

# If not, train models first using notebooks in 4Models/
```

### ❌ "GDAL not found" errors

**Solution:**
```bash
# Ubuntu/Debian
sudo apt-get install gdal-bin python3-gdal

# macOS
brew install gdal

# Windows - use conda
conda install -c conda-forge gdal
```

## 🚀 Next Steps

1. ✅ Get basic system running
2. ⬜ Convert all your NetCDF files
3. ⬜ Add more trained models (XGBoost, RFR)
4. ⬜ Customize the interface colors/branding
5. ⬜ Deploy to cloud (Heroku, AWS, Google Cloud)
6. ⬜ Add authentication if needed
7. ⬜ Enable batch CSV processing

## 💡 Tips

- **Start simple:** Get the linear model working first
- **Test locally:** Use `localhost` before deploying
- **Check browser console:** Press F12 to see JavaScript errors
- **Check Flask logs:** Terminal shows API requests
- **Use small rasters:** Test with small files first

## 📚 More Info

- Full documentation: See `README.md`
- API endpoints: See `app.py` comments
- Raster visualization: See `map_overlay_example.html`

---

**Ready?** Run `python app.py` and open http://localhost:5000 🔥
