#!/bin/bash

# Fire ROS Prediction Server Startup Script

echo "🔥 Fire ROS Prediction System"
echo "================================"
echo ""

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "📦 Creating virtual environment..."
    python3 -m venv venv
fi

# Activate virtual environment
echo "🔧 Activating virtual environment..."
source venv/bin/activate

# Install dependencies
echo "📥 Installing dependencies..."
pip install -r requirements.txt -q

# Check if models exist
if [ ! -f "../../Data/Models/Linear.pkl" ]; then
    echo "⚠️  WARNING: Linear.pkl model not found!"
    echo "   Please train models first using notebooks in 4Models/"
fi

# Check if raster directory exists
if [ ! -d "../../Data/web_rasters" ]; then
    echo "📂 Creating web_rasters directory..."
    mkdir -p ../../Data/web_rasters
    echo "⚠️  Please convert NetCDF files using convert_netcdf_to_cog.py"
fi

echo ""
echo "✅ Setup complete!"
echo ""
echo "🚀 Starting Flask server..."
echo "   Access the application at: http://localhost:5000"
echo "   Press Ctrl+C to stop the server"
echo ""

# Start Flask app
python app.py
