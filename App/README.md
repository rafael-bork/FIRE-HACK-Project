# Wildfire Rate of Spread Prediction Web Application

## Overview

This repository contains a web-based application developed to predict Wildfire Rate of Spread (ROS) across mainland Portugal.  
The application integrates machine learning models, meteorological data, and geospatial information to provide spatially explicit fire spread predictions at a 0.1° × 0.1° resolution.

The platform was developed within the scope of the FIRE-HACK project, using the PT-FireSprd v3.0 database and two fire behavior models:
- A Complex Model based on XGBoost (higher accuracy)
- A Linear Regression Model (simpler and more interpretable)

The application is designed for researchers, analysts, and operational fire management teams, enabling interactive exploration and scenario-based predictions.

---

## Application Architecture

The system follows a client–server architecture:

- Frontend: Single-page web interface (HTML, CSS, JavaScript)
- Backend: Flask API (Python)
- Data Sources:
  - Copernicus Climate Data Store (ERA5, ERA5-Land, Fire Weather Indices)
  - Static geographic datasets (fuel load, terrain, fire history)
- Models:
  - XGBoost Regressor
  - Linear Regression (OLS)

---

## Frontend

The frontend is implemented as a single-page application (`index.html`) and provides an interactive and intuitive interface for running predictions and visualizing results.

### Key Features

- Model selection (XGBoost or Linear Regression)
- Input controls for:
  - Fire date and time
  - Prediction duration (hours)
  - Time since fire ignition
- Interactive map of Portugal with:
  - Color-coded grid visualization of predicted ROS
  - Multiple base maps (default, satellite, terrain)
- Timeline control for temporal evolution of predictions
- Toggle between:
  - Incremental values
  - Cumulative values
- Visualization of additional layers:
  - Distance traveled
  - Meteorological and geographic input variables
- Clickable grid cells showing:
  - Local ROS value
  - Input variable values
  - Distance traveled
- Dynamic charts:
  - Rate of Spread vs Time
  - Distance vs Time
- CSV export of inputs and predictions

---

## Backend

The backend is built with Flask and orchestrates the complete prediction pipeline, from data acquisition to model inference and result delivery.

### Backend Workflow

1. User submits a prediction request via the frontend
2. Backend validates inputs (date, duration, ignition time)
3. Cache check:
   - If results already exist, they are returned immediately
   - Otherwise, the full pipeline is executed
4. Meteorological data is retrieved and processed
5. Geographic variables are merged
6. Machine learning models generate predictions
7. Results are saved and returned as GeoTIFF layers for visualization

---

## Backend Modules

| Script | Description |
|------|------------|
| `app.py` | Main Flask server coordinating the full pipeline |
| `CDS_API.py` | Handles communication with the Copernicus Climate Data Store API, including caching |
| `Meteo_vars.py` | Computes derived meteorological variables (e.g., wind speed, VPD, HDW) |
| `Meteo_dataset.py` | Builds the complete meteorological dataset for the requested time window |
| `Create_inputs.py` | Merges meteorological data with static geographic variables |
| `Model_Prediction.py` | Loads trained models, performs predictions |

---

## Models

### Complex Model (XGBoost)

- Captures nonlinear relationships between environmental variables
- Optimized using cross-validation and hyperparameter tuning
- Prioritized for higher predictive accuracy

### Linear Model (OLS Regression)

- Provides a transparent and interpretable equation for ROS
- Uses standardized features and log-transformed target variable
- Suitable for analytical interpretation and rapid estimation

Both models operate in log-transformed ROS space and return predictions converted back to linear scale.

The models are in the following data structure
```text
├── Data/
│   ├── Models/   
│       ├── model_xgboost.pkl    
│       ├── model_linear_ffs.pkl        
│
├── App/
│   ├── app.py/                   
│   ├── README.md

---

## Output

The application generates:
- Spatially explicit ROS predictions (GeoTIFF)
- Temporal evolution of fire spread
- Statistical summaries of predicted values
- Exportable datasets for external analysis

---

## Limitations

- Predictions are limited to continental Portugal
- Fire date must be between January 1, 2015 and three months before the present
- Assumes the fire remains within a single 0.1° grid cell during the selected duration
- For real-time or future predictions, the Copernicus CDS API must be replaced with a forecasting-capable weather API