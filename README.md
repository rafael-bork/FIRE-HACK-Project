# FIRE-HACK: Wildfire Rate of Spread Prediction System

## Project Overview
This project was developed within the FIRE-HACK project with the objective of building an end-to-end system for predicting wildfire Rate of Spread (ROS) in continental Portugal. The work starts from the PT-FireSprd database and extends it with environmental and meteorological variables, applies exploratory data analysis and machine learning modeling, and culminates in the deployment of an interactive web-based prediction interface.

The system is designed to support both scientific analysis and operational decision-making by providing spatially explicit fire spread predictions under user-defined conditions.

---

## Objectives
The main objectives of this project are:
- To enrich the PT-FireSprd database with high-resolution meteorological, geographic, and fuel-related variables
- To explore and characterize the main physical drivers of wildfire spread
- To develop predictive machine learning models for fire Rate of Spread
- To provide an accessible interface for real-time and scenario-based fire spread prediction

---

## Data Sources

### PT-FireSprd Database
The Portuguese Large Wildfire Spread database (PT-FireSprd) contains reconstructed fire spread progressions for more than 155 large wildfires that occurred in Portugal between 2015 and 2025. The database includes detailed fire behavior descriptors such as Rate of Spread, Fire Growth Rate, Spread Direction, and Fireline Intensity.

For modeling purposes, the Level 2 (L2) database was used, providing individual fire progressions with sufficient temporal and spatial resolution.


### Meteorological and Geographic Data
The PT-FireSprd database was complemented with environmental variables derived from:
- ERA5 and ERA5-Land reanalysis datasets (Copernicus Climate Data Store)
- Fire Weather Index (FWI) products
- Topographic and land use datasets
- Fuel models and historical fire occurrence rasters
- Land Use shapefiles

Meteorological variables include temperature, relative humidity, wind speed and direction, geopotential at multiple atmospheric levels and also surface-level vapor pressure deficit, dead fuel moisture content, atmospheric stability indices (e.g., CAPE, CIN, Haines Index, Wind Recirculation, BLH, ...), and FWI indicators.

---

## Database Enhancement and Feature Engineering
A comprehensive set of environmental variables was spatially and temporally aggregated and added to each fire progression. Feature engineering steps included:
- Spatial calculations of raster-based variables over fire progression polygons
- Spacio-tTemporal aggregation of meteorological variables over progression duration and extent
- Selection of representative progressions when multiple fronts occurred simultaneously
- Log-transformation of the target variable (ROS) to address skewness

The final modeling dataset consists of approximately 1,170 fire progressions described by nearly 100 explanatory variables.

---

## Exploratory Data Analysis
Exploratory Data Analysis (EDA) was conducted to:
- Analyze variable distributions and variability
- Identify missing data and outliers
- Examine correlations between environmental drivers and ROS
- Justify transformations and modeling assumptions

To identify distinct wildfire propagation regimes and the dominant physical drivers associated with each regime, feature importance (Shapley Additive Explanations) values were computed for a XGBoost model. These explanations were further analyzed using:
- Dimensionality reduction (UMAP)
- Unsupervised clustering (HDBSCAN)

The EDA phase provided key insights into the dominant role of wind, atmospheric instability, fuel conditions, and drought in driving wildfire spread.

---

## Modeling

Two predictive models were developed to balance accuracy and interpretability:

### Complex Model
- Algorithm: XGBoost Regressor
- Capable of capturing non-linear relationships and interactions
- Hyperparameters optimized using cross-validation
- Designed for high-accuracy predictions in operational or research contexts

### Linear Model
- Algorithm: Ordinary Least Squares (OLS) Regression
- Includes standardized inputs and forward feature selection
- Provides transparent interpretation of variable contributions
- Suitable for rapid estimation and explanatory analysis

Both models were trained in log-transformed ROS space and evaluated using repeated cross-validation due to the limited dataset size.

---

## Application Deployment

### System Architecture
The prediction system follows a client–server architecture:
- **Backend:** Flask-based API responsible for data retrieval, preprocessing, model inference, and caching
- **Frontend:** Single-page web application built with HTML, CSS, and JavaScript

The backend dynamically retrieves meteorological data, assembles model inputs, executes predictions using the trained models, and serves geospatial outputs to the frontend.


### Prediction Interface
The web interface allows users to:
- Select the prediction model (Complex or Linear)
- Define fire date, time, duration, and time since ignition
- Visualize spatial predictions of fire Rate of Spread at 0.1° resolution across Portugal
- Explore temporal evolution using an interactive timeline
- Inspect grid-cell-level details and export results as CSV files

Predictions are displayed as interactive, color-coded maps with multiple visualization layers and summary statistics.

---

## Repository Structure
```text
├── Data/
│   ├── Raw/                      # Original datasets
│   ├── Interim/                  # Intermediary datasets
│   ├── Processed/                # Cleaned and feature-engineered data
│   ├── Data_Exploration/         # Data analysis and vizualization products
│   ├── Models/                   # Dataset with model outputs
│
├── Database/
│   ├── Attribute_Metadata.xlsx   # Database attribute metadata
│   ├── PT-FireSprd_v3.0.shp      # Database geometry
│   ├── PT-FireSprd_v3.0.shx      # Database spatial index
│   ├── PT-FireSprd_v3.0.dbf      # Database attribute table
│   ├── PT-FireSprd_v3.0.prj      # Database coordinate reference system
│   ├── PT-FireSprd_v3.0.cpg      # Database encoding
│   ├── README.md
│
├── Models/
│   ├── model_xgboost.pkl         # Trained complex model
│   ├── model_linear_ffs.pkl      # Trained linear model with forward feature selection
│   ├── README.md
│
├── Notebooks/
│   ├── 1Extraction.ipynb         # Meteorological data retrieval from API
│   ├── 2Transformation.ipynb     # Data processing
│   ├── 3Exploration.ipynb        # Exploratory Data Analysis
│   ├── 4Models.ipynb             # Model development and evaluation
│   ├── 5Deployement.ipynb        # Complete web application integration
│
├── Hackathon_Report.pdf
├── requirements.txt
└── README.md
