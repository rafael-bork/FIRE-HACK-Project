# Models Notebooks

This folder contains Jupyter notebooks for fire Rate of Spread (ROS) prediction using the PT-FireSprd v2.1 dataset (Portuguese fire progression data).

## Notebooks

| Notebook | Description |
|----------|-------------|
| `Linear_model.ipynb` | Linear regression baseline with forward feature selection |
| `XGBoost_model_CV.ipynb` | XGBoost model with hyperparameter tuning and SHAP analysis |
| `Outlier_Analysis.ipynb` | Clustering and profiling of high-error predictions |

## Notebook Details

### Linear_model.ipynb
Linear model for ROS prediction.

**Pipeline:**
- Data loading and preprocessing (NaN filtering, categorical encoding)
- Log transformation of target variable
- Repeated K-Fold CV (5×4)
- Forward feature selection using MAE
- Feature importance via regression coefficients

**Key Results:** R² ≈ 0.52, MAE ≈ 470 m/h (linear scale)

---

### XGBoost_model_CV.ipynb
Primary prediction model using gradient boosting.

**Pipeline:**
- HalvingRandomSearchCV for hyperparameter optimization
- Repeated K-Fold CV (5×4) for robust evaluation
- SHAP-based feature importance and selection
- Final model trained on top 6 |SHAP| features

**Key Results:** R² ≈ 0.56 (test), MAE ≈ 457 m/h (linear scale)

**Output:** Serialized model saved to `../../Data/Models/model_xgboost.pkl`

---

### Outlier_Analysis.ipynb
Error analysis and diagnostics.

**Pipeline:**
- Identifies "bad predictions" (>35% error threshold)
- K-Means clustering of high-error observations
- Compares cluster profiles against low-error baseline
- Generates actionable recommendations

**Key Outputs:** Cluster profiles, error distribution plots, improvement recommendations

## Data Requirements

Notebooks expect the following data structure:
```
../../Data/
├── Processed/
│   └── PT-FireSprd_v2.1/
│       └── L2_FireBehavior/
│           └── PT-FireProg_v2.1_L2_model.shp
└── Models/
    └── PT_FireProg_model_SHAP_xgboost.shp  (for Outlier_Analysis.ipynb)
```

## Execution Order

1. `Linear_model.ipynb` or `XGBoost_model_CV.ipynb` in order to create model.
2. `Outlier_Analysis.ipynb` — Analyze prediction failures (requires XGBoost/Linear outputs).

## Environment

- Python 3.11+
- Key dependencies: `xgboost`, `shap`, `scikit-learn`, `geopandas`, `pandas`, `numpy`, `matplotlib`