import pandas as pd
import numpy as np
import os
import joblib
import sys

# Add src to python path if needed
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from feature_engineering import create_calendar_features, create_lag_features, create_rolling_features

def forecast_next_7_days(data_path="dataset/blood_bank_data.csv", 
                         current_date=None, 
                         model_dir="models"):
    """
    Generates 7-day demand forecasts for all blood types using LightGBM and Prophet/Fallback models.
    """
    df = pd.read_csv(data_path)
    df["date"] = pd.to_datetime(df["date"])
    
    if current_date is None:
        current_date = df["date"].max()
    else:
        current_date = pd.to_datetime(current_date)
        
    print(f"Generating 7-day forecast starting after base date: {current_date.strftime('%Y-%m-%d')}...")
    
    blood_types = ["O_pos", "A_pos", "B_pos", "AB_pos", "O_neg", "A_neg", "B_neg", "AB_neg"]
    blood_types_display = [bt.replace("_pos", "+").replace("_neg", "-") for bt in blood_types]
    
    # Define future dates
    future_dates = pd.date_range(start=current_date + pd.Timedelta(days=1), periods=7, freq="D")
    
    # 1. GENERATE PROPHET FORECAST
    prophet_forecasts = []
    prophet_path = os.path.join(model_dir, "prophet_models.joblib")
    
    if os.path.exists(prophet_path):
        prophet_data = joblib.load(prophet_path)
        prophet_models = prophet_data["models"]
        
        for bt_display in blood_types_display:
            if bt_display in prophet_models:
                model = prophet_models[bt_display]
                # Prepare future dataframe
                future_df = pd.DataFrame({"ds": future_dates})
                
                # Predict
                if prophet_data.get("is_prophet", False) and hasattr(model, "predict"):
                    forecast = model.predict(future_df)
                    pred_y = np.clip(forecast["yhat"].values, 0, None)
                    lower_y = np.clip(forecast.get("yhat_lower", forecast["yhat"] - 3).values, 0, None)
                    upper_y = np.clip(forecast.get("yhat_upper", forecast["yhat"] + 3).values, 0, None)
                else:
                    # Fallback model (sklearn LinearRegression)
                    forecast = model.predict(future_df)
                    pred_y = forecast["yhat"].values
                    # For fallback, use simple std proxy for uncertainty bounds
                    pred_y_clean = np.clip(pred_y, 0, None)
                    lower_y = np.clip(pred_y_clean - 0.15 * pred_y_clean - 2, 0, None)
                    upper_y = np.clip(pred_y_clean + 0.15 * pred_y_clean + 2, 0, None)
                
                for i, date in enumerate(future_dates):
                    prophet_forecasts.append({
                        "date": date,
                        "blood_type": bt_display,
                        "predicted_demand": np.round(pred_y[i]).astype(int),
                        "lower_bound": np.round(lower_y[i]).astype(int),
                        "upper_bound": np.round(upper_y[i]).astype(int),
                        "model": "Prophet"
                    })
    else:
        print("Prophet models not found. Skipping Prophet forecast.")
        
    # 2. GENERATE LIGHTGBM FORECAST
    lgb_forecasts = []
    lgb_path = os.path.join(model_dir, "lightgbm_model.joblib")
    
    if os.path.exists(lgb_path):
        lgb_data = joblib.load(lgb_path)
        lgb_model = lgb_data["model"]
        features_list = lgb_data["features"]
        
        # We need to construct the feature rows for each of the 7 future dates
        # Historical context up to current_date
        hist_df = df[df["date"] <= current_date].copy()
        
        # Build features for future dates
        # We create a dummy dataframe extending into the future to calculate lags and rolling stats
        future_dummy_rows = []
        for f_date in future_dates:
            future_dummy_rows.append({
                "date": f_date,
                "admissions": 0,  # Lags won't read this, they read historical values
                "accidents": 0,
                "elective_surgeries": 0,
                "dengue_cases": 0,
                **{f"demand_{bt}": 0 for bt in blood_types}
            })
            
        extended_df = pd.concat([hist_df, pd.DataFrame(future_dummy_rows)], ignore_index=True)
        extended_df = extended_df.sort_values("date").reset_index(drop=True)
        
        # Calculate external features on extended df
        extended_df = create_calendar_features(extended_df, "date")
        
        external_cols = ["admissions", "accidents", "elective_surgeries", "dengue_cases"]
        extended_df = create_lag_features(extended_df, external_cols, lag_days=[7, 8, 14], prefix="ext_")
        extended_df = create_rolling_features(extended_df, external_cols, windows=[7, 14], lag_shift=7, prefix="ext_")
        
        # Filter back down to future dates to construct inputs for each blood type
        future_extended = extended_df[extended_df["date"] > current_date].copy()
        
        for bt in blood_types:
            bt_display = bt.replace("_pos", "+").replace("_neg", "-")
            bt_col = f"demand_{bt}"
            
            # Construct lag demand features from history
            for f_idx, f_date in enumerate(future_dates):
                # For f_date, the lags are relative to f_date:
                # lag_7 of demand is the demand at (f_date - 7 days)
                feature_row = {}
                feature_row["blood_type"] = bt_display
                
                # Fetch calendar features from extended
                row_ext = future_extended[future_extended["date"] == f_date].iloc[0]
                feature_row["day_of_week"] = row_ext["day_of_week"]
                feature_row["month"] = row_ext["month"]
                feature_row["day_of_year"] = row_ext["day_of_year"]
                feature_row["year"] = row_ext["year"]
                feature_row["is_weekend"] = row_ext["is_weekend"]
                
                # Fetch external features
                for col in row_ext.index:
                    if col.startswith("ext_"):
                        feature_row[col] = row_ext[col]
                        
                # Fetch demand lags
                for lag in [7, 8, 9, 14, 21]:
                    lag_date = f_date - pd.Timedelta(days=lag)
                    hist_val = hist_df[hist_df["date"] == lag_date]
                    if len(hist_val) > 0:
                        feature_row[f"demand_lag_{lag}"] = hist_val.iloc[0][bt_col]
                    else:
                        # Fallback if history doesn't stretch back far enough
                        feature_row[f"demand_lag_{lag}"] = hist_df[bt_col].mean()
                        
                # Fetch demand rolling stats (shifted by 7 relative to f_date)
                # This means rolling of demand from f_date-7, f_date-8, ...
                roll_start_date = f_date - pd.Timedelta(days=7)
                # Filter history up to roll_start_date
                hist_up_to_roll = hist_df[hist_df["date"] <= roll_start_date].sort_values("date")
                
                # 7-day rolling ending at roll_start_date
                mean_7 = hist_up_to_roll[bt_col].tail(7).mean()
                std_7 = hist_up_to_roll[bt_col].tail(7).std()
                
                # 14-day rolling ending at roll_start_date
                mean_14 = hist_up_to_roll[bt_col].tail(14).mean()
                std_14 = hist_up_to_roll[bt_col].tail(14).std()
                
                feature_row["demand_roll_mean_7"] = mean_7 if not pd.isna(mean_7) else hist_df[bt_col].mean()
                feature_row["demand_roll_std_7"] = std_7 if not pd.isna(std_7) else 1.0
                feature_row["demand_roll_mean_14"] = mean_14 if not pd.isna(mean_14) else hist_df[bt_col].mean()
                feature_row["demand_roll_std_14"] = std_14 if not pd.isna(std_14) else 1.0
                
                # Convert feature_row to DataFrame
                feat_df = pd.DataFrame([feature_row])
                
                # Convert blood_type to category for LightGBM
                feat_df["blood_type"] = feat_df["blood_type"].astype("category")
                
                # Order columns to match training features list
                feat_df = feat_df[features_list]
                
                # Predict
                pred_val = lgb_model.predict(feat_df)[0]
                pred_val = max(0.0, pred_val)
                
                # Simple confidence interval based on rolling std
                std_val = feature_row["demand_roll_std_7"]
                lower_val = max(0.0, pred_val - 1.645 * std_val) # 90% confidence
                upper_val = pred_val + 1.645 * std_val
                
                lgb_forecasts.append({
                    "date": f_date,
                    "blood_type": bt_display,
                    "predicted_demand": int(round(pred_val)),
                    "lower_bound": int(round(lower_val)),
                    "upper_bound": int(round(upper_val)),
                    "model": "LightGBM"
                })
    else:
        print("LightGBM model not found. Skipping LightGBM forecast.")
        
    # Combine results
    all_forecasts = lgb_forecasts + prophet_forecasts
    if len(all_forecasts) == 0:
        return pd.DataFrame()
        
    return pd.DataFrame(all_forecasts)

if __name__ == "__main__":
    fc = forecast_next_7_days()
    if not fc.empty:
        print(f"Generated {len(fc)} forecast rows.")
        print(fc.head(10))
