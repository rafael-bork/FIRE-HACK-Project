@echo off
REM Fire ROS Prediction Server Startup Script (Windows)

echo.
echo 🔥 Fire ROS Prediction System
echo ================================
echo.

REM Check if virtual environment exists
if not exist "venv\" (
    echo 📦 Creating virtual environment...
    python -m venv venv
)

REM Activate virtual environment
echo 🔧 Activating virtual environment...
call venv\Scripts\activate.bat

REM Install dependencies
echo 📥 Installing dependencies...
pip install -r requirements.txt -q

REM Check if models exist
if not exist "..\..\Data\Models\Linear.pkl" (
    echo ⚠️  WARNING: Linear.pkl model not found!
    echo    Please train models first using notebooks in 4Models/
)

REM Check if raster directory exists
if not exist "..\..\Data\web_rasters\" (
    echo 📂 Creating web_rasters directory...
    mkdir ..\..\Data\web_rasters
    echo ⚠️  Please convert NetCDF files using convert_netcdf_to_cog.py
)

echo.
echo ✅ Setup complete!
echo.
echo 🚀 Starting Flask server...
echo    Access the application at: http://localhost:5000
echo    Press Ctrl+C to stop the server
echo.

REM Start Flask app
python app.py

pause
