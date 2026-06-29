# 🩸 HemoPulse AI: Blood Bank Demand & Critical Shortage Predictor

An AI-powered predictive logistics engine that forecasts daily blood group consumption 7 days in advance. Designed for public hospitals and blood bank managers, HemoPulse AI flags automated shortage warnings and recommends targeted donation camp logistics to proactively prevent blood reserves exhaustion.

---

## 🚀 Key Features

* **AI-Driven Demand Forecasting**: Combines Meta Prophet (for robust univariate trend/seasonality extraction) and LightGBM (for categorical cross-blood-type relationships) to forecast daily unit consumption 7 days ahead.
* **Liquid Blood Reserve Visualizations**: High-fidelity dashboard visualizing current stockpile capacities with dynamic CSS-animated liquid blood bottles.
* **Smart Alert & Depletion System**: Predicts the exact day of stock depletion based on incoming demand forecasts and raises warning alerts.
* **Targeted Donation Camp Planner**: Dynamically suggests optimal camp dates, venues, priority levels, and target donation yields to proactively resolve upcoming deficits.
* **Interactive Logistics Simulation**: Simulate incoming donations or outbound hospital issues in real-time, and launch recommended donation camps to replenish inventory.

---

## 🛠️ Tech Stack

* **Language**: Python
* **Data Processing**: Pandas, NumPy
* **Machine Learning**: LightGBM, Meta Prophet, Scikit-learn
* **Data Visualization**: Plotly, Streamlit
* **Model Persistency**: Joblib

---

## 📁 Directory Structure

```text
├── app/
│   ├── app.py          # Main Streamlit driver, layouts, and custom HSL CSS styling
│   ├── dashboard.py    # Overview landing page with admissions trends & KPIs
│   ├── inventory.py    # Stock management, liquid visuals, and manual adjustments
│   ├── prediction.py   # Forecast plotter with confidence intervals & csv export
│   └── alerts.py       # Shortage warning & targeted camp scheduler
├── dataset/
│   ├── synthetic_data_generator.py # Simulates historical admissions & consumption
│   ├── blood_bank_data.csv         # Generated historical time-series log
│   └── inventory.csv               # Live warehouse inventory tracker
├── models/
│   ├── lightgbm_model.joblib       # Trained LightGBM regressor
│   └── prophet_models.joblib       # Trained Meta Prophet models dictionary
├── reports/
│   └── metrics.json                # Performance validation metrics (MAE / RMSE)
├── src/
│   ├── feature_engineering.py      # Lags, rolling statistics, and temporal features
│   ├── preprocess.py               # Preprocessing pipelines & train-test splitters
│   ├── train_lightgbm.py           # LightGBM training script
│   ├── train_prophet.py            # Meta Prophet training script (with sklearn fallback)
│   ├── forecast.py                 # Multi-model prediction coordinator
│   └── evaluate.py                 # Model validation & error logging
└── requirements.txt                # Python dependencies
```

---

## ⚙️ Installation & Setup

### 1. Install Dependencies
Ensure you have Python 3.9+ installed. Install the required libraries using pip:

```bash
python -m pip install -r requirements.txt
```

### 2. Generate Synthetic Historical Data & Warehouse Status
Generate 5 years of daily public hospital admissions mapping accidents, surgeries, dengue outbreaks, and corresponding blood type demand:

```bash
python dataset/synthetic_data_generator.py
```

### 3. Run Preprocessing & Model Training
Preprocess the time-series features, train both LightGBM and Meta Prophet, and evaluate performance on the validation set:

```bash
# 1. Feature engineer and split data
python src/preprocess.py

# 2. Train LightGBM model
python src/train_lightgbm.py

# 3. Train Meta Prophet models (with sklearn fallback)
python src/train_prophet.py

# 4. Generate evaluation reports
python src/evaluate.py
```

### 4. Run the Streamlit Dashboard
Launch the interactive web-based logistics dashboard:

```bash
python -m streamlit run app/app.py
```

Open your browser and navigate to **`http://localhost:8501`**.

---

## 📊 How the Forecasting Model Works

The models utilize historical hospital indices to forecast the demand:
1. **Hospital Admissions**: Standard daily load with weekend drop-offs.
2. **Accident Trauma Cases**: Spikes on Friday/Saturday nights, leading to disproportionate spikes in universal blood type (`O-` and `O+`).
3. **Elective Surgeries**: Scheduled weekday cases demanding typed whole blood.
4. **Dengue Outbreak Seasons**: Heavy summer/monsoon seasonal spikes (July–October) increasing platelet support demand.

### Performance Validation (MAE/RMSE on Holdout Set)

| Blood Group | LightGBM MAE | LightGBM RMSE | Prophet MAE | Prophet RMSE |
| :--- | :---: | :---: | :---: | :---: |
| **O+** | 1.34 | 1.81 | 1.22 | 1.69 |
| **A+** | 1.32 | 1.67 | 1.25 | 1.61 |
| **B+** | 0.62 | 0.81 | 0.62 | 0.80 |
| **O-** | 0.84 | 1.30 | 0.75 | 1.21 |
| **Overall** | **0.76** | **1.10** | **0.71** | **1.05** |

---

## 🔄 User Flow Summary

1. **Monitor System Status**: Check the landing page for total inventory status, predicted shortages, and hospital admissions trends.
2. **Audit Stock Reserves**: Navigate to **Inventory Status** to see liquid indicators representing bottle capacities. Log mock donations or hospital distributions to test the warning systems.
3. **Evaluate Forecasts**: Head to **Demand Forecast** to view the interactive 7-day predicted charts, toggle confidence bounds, inspect metrics comparison, and export CSV forecasts.
4. **Schedule Campaigns**: Review **Emergency Alerts** for depletion days and launch suggested donation camps. Completing a camp will automatically add the target yield to the warehouse inventory.
5. **Simulate Scenarios**: Use the sidebar to step back in time (Simulation Base Date) or adjust safety thresholds (Safety Stock Slider) to see how the logistics system responds.
