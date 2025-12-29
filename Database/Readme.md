README – PT-FireSprd_v3.0
=============================================

1. Dataset Identification
-------------------------
Dataset name: PT-FireSprd_v3.0
Version: v3.0
Delivery date: 2025-12-31
Author / Organization: Akli Benali; Diogo Gomes; Rafael Oliveira; Xavier Loreto / Instituto Superior de Agronomia - Universidade de Lisboa
Project: FIRE-HACK

2. General Description
----------------------
This spatial database represents wildfire progression in spaciotemporal polygons for mainland Portugal, provided in ESRI Shapefile format.
The dataset was developed to support wildfire behavior analysis, spatial modeling, and decision-support applications.

3. Source Database
------------------
Original dataset: The Portuguese Large Wildfire Spread Database (PT-FireSprd_v2.0) 
Source: Akli Benali, Nuno Guiomar, Hugo Gonçalves, Bernardo Mota, Fábio Silva, Paulo M. Fernandes, Carlos Mota, Alexandre Penha, João Santos, José M.C. Pereira, Ana C.L. Sá, Bacciu, V., SALIS, M., Coskuner, K. A., & Valasek, L.
Original version/date: 2025

Known limitations of the original dataset include:
- No 2025 fire progression data
- Lack of associated environmental variables
- Inconsistencies across events

4. Database Improvement Process
-------------------------------

4.1 Types of Improvements Performed
The following improvements were applied to the original dataset:
- Enrichment of fire progression polygons with meteorological, topographic, fuel, and land-use variables
- Correction of localized geometric errors
- Removal or flagging of records with incomplete temporal information

4.2 Methodology
- Topographic variables were extracted using spatial averages (arithmetic, circular, and weighted) from raster datasets with resolutions between 50 m and 100 m.
- Meteorological variables were derived from ERA5 reanalysis products and aggregated both spatially and temporally to each progression.
- Categorical variables (e.g. fuel model, land use) were assigned using spatial mode.
- Temporal fire variables were added (rate of spread lags, time since ignition).
- Data processing and quality control were performed using QGIS and Python-based workflows.

4.3 Remaining Limitations
- Uncertainties persist in some manually reconstructed fire progressions and their relationships, particularly in older events.
- Meteorological variables are based on reanalysis data and may not fully represent localized extreme conditions.
- Meteorological variables represent spatiotemporal averages, simplifying complex relationships.
- Some meteorological variables are calculated from atmospheric profiles, of which are based on few observations.
- The dataset is not intended to capture micro-scale fire behavior and environmental conditions.

5. Data Structure
-----------------
Delivered files:
- Atribute_Metadata.xlsx  (atribute metadata)
- fire_progressions.shp   (geometry)
- fire_progressions.shx   (spatial index)
- fire_progressions.dbf   (attribute table)
- fire_progressions.prj   (coordinate reference system)
- fire_progressions.cpg   (UTF-8 encoding)

6. Coordinate Reference System
------------------------------
WGS 84 / UTM zone 29N
EPSG:32629

7. Conditions of Use
-------------------
This dataset is made available under an open-access policy and may be used, shared, and adapted, provided that appropriate credit is given to the authors and source.
Use of the dataset must comply with the terms of the Creative Commons Attribution (CC BY) license or an equivalent open-data license.
The dataset is provided "as is" and without warranties of any kind. The authors and data providers shall not be held liable for any direct or indirect damages arising from the use of the data.