import pandas as pd
import numpy as np
import os
import json
import joblib
import sys

# Add src to python path if needed
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def evaluate_models(test_path="dataset/test_features.csv", 
                    raw_data_path="dataset/blood_bank_data.csv",
                    model_dir="models", 
                    report_dir="reports"):
    os.makedirs(report_dir, exist_ok=True)
    
    print(f"Loading test features from {test_path}...")
    test_df = pd.read_csv(test_path)
    test_df["date"] = pd.to_datetime(test_df["date"])
    
    blood_groups = ["O_pos", "A_pos", "B_pos", "AB_pos", "O_neg", "A_neg", "B_neg", "AB_neg"]
    blood_groups_display = [bt.replace("_pos", "+").replace("_neg", "-") for bt in blood_groups]
    
    # 1. EVALUATE LIGHTGBM
    lgb_path = os.path.join(model_dir, "lightgbm_model.joblib")
    lgb_metrics = {}
    
    if os.path.exists(lgb_path):
        lgb_data = joblib.load(lgb_path)
        lgb_model = lgb_data["model"]
        features_list = lgb_data["features"]
        
        # Make a copy for evaluation
        lgb_eval_df = test_df.copy()
        lgb_eval_df["blood_group"] = lgb_eval_df["blood_group"].astype("category")
        
        X_test = lgb_eval_df[features_list]
        y_true = lgb_eval_df["demand"]
        y_pred = lgb_model.predict(X_test)
        lgb_eval_df["prediction"] = np.clip(y_pred, 0, None)
        
        # Overall metrics
        overall_mae = np.mean(np.abs(y_true - lgb_eval_df["prediction"]))
        overall_rmse = np.sqrt(np.mean((y_true - lgb_eval_df["prediction"]) ** 2))
        
        lgb_metrics["overall"] = {
            "mae": float(overall_mae),
            "rmse": float(overall_rmse)
        }
        
        # By blood type
        for bt_display in blood_groups_display:
            bt_subset = lgb_eval_df[lgb_eval_df["blood_group"] == bt_display]
            if len(bt_subset) > 0:
                y_t = bt_subset["demand"]
                y_p = bt_subset["prediction"]
                mae = np.mean(np.abs(y_t - y_p))
                rmse = np.sqrt(np.mean((y_t - y_p) ** 2))
                lgb_metrics[bt_display] = {
                    "mae": float(mae),
                    "rmse": float(rmse)
                }
    else:
        print("LightGBM model not found for evaluation.")
        
    # 2. EVALUATE PROPHET
    prophet_path = os.path.join(model_dir, "prophet_models.joblib")
    prophet_metrics = {}
    
    if os.path.exists(prophet_path):
        prophet_data = joblib.load(prophet_path)
        prophet_models = prophet_data["models"]
        
        # We need the raw historical demand for testing Prophet, as it operates on dates directly
        raw_df = pd.read_csv(raw_data_path)
        raw_df["date"] = pd.to_datetime(raw_df["date"])
        
        # Prophet test split matches the date range of test_df
        test_dates = test_df["date"].unique()
        test_start = pd.to_datetime(min(test_dates))
        test_end = pd.to_datetime(max(test_dates))
        
        prophet_eval_list = []
        
        for bt in blood_groups:
            bt_display = bt.replace("_pos", "+").replace("_neg", "-")
            if bt_display in prophet_models:
                model = prophet_models[bt_display]
                
                # Fetch actual test target
                test_subset = raw_df[(raw_df["date"] >= test_start) & (raw_df["date"] <= test_end)].copy()
                test_bt = test_subset[["date", f"demand_{bt}"]].rename(columns={"date": "ds", f"demand_{bt}": "y"})
                
                # Generate predictions
                future_df = pd.DataFrame({"ds": test_bt["ds"]})
                
                if prophet_data.get("is_prophet", False) and hasattr(model, "predict"):
                    forecast = model.predict(future_df)
                    pred_y = np.clip(forecast["yhat"].values, 0, None)
                else:
                    forecast = model.predict(future_df)
                    pred_y = forecast["yhat"].values
                    
                test_bt["prediction"] = pred_y
                test_bt["blood_group"] = bt_display
                prophet_eval_list.append(test_bt)
                
                # Compute metrics for this blood type
                mae = np.mean(np.abs(test_bt["y"] - test_bt["prediction"]))
                rmse = np.sqrt(np.mean((test_bt["y"] - test_bt["prediction"]) ** 2))
                prophet_metrics[bt_display] = {
                    "mae": float(mae),
                    "rmse": float(rmse)
                }
                
        if prophet_eval_list:
            all_prophet_eval = pd.concat(prophet_eval_list, ignore_index=True)
            overall_mae = np.mean(np.abs(all_prophet_eval["y"] - all_prophet_eval["prediction"]))
            overall_rmse = np.sqrt(np.mean((all_prophet_eval["y"] - all_prophet_eval["prediction"]) ** 2))
            prophet_metrics["overall"] = {
                "mae": float(overall_mae),
                "rmse": float(overall_rmse)
            }
    else:
        print("Prophet models not found for evaluation.")
        
    # Combine and save
    metrics_report = {
        "lightgbm": lgb_metrics,
        "prophet": prophet_metrics
    }
    
    report_path = os.path.join(report_dir, "metrics.json")
    with open(report_path, "w") as f:
        json.dump(metrics_report, f, indent=4)
        
    print(f"Metrics report saved successfully to {report_path}")
    return metrics_report

if __name__ == "__main__":
    evaluate_models()
