import pandas as pd
import numpy as np
import os
import joblib

# Try importing Prophet, and set up a fallback if it fails
try:
    from prophet import Prophet
    PROPHET_AVAILABLE = True
    print("Meta Prophet is available and will be used.")
except Exception as e:
    PROPHET_AVAILABLE = False
    print(f"Meta Prophet is NOT available or failed to import ({str(e)}). A scikit-learn LinearRegression fallback will be used.")

class FallbackModel:
    """
    A simple time-series fallback model using scikit-learn's LinearRegression
    to predict future values based on trend, weekly, and yearly seasonality.
    """
    def __init__(self, blood_group):
        from sklearn.linear_model import LinearRegression
        self.blood_group = blood_group
        self.model = LinearRegression()
        
    def fit(self, df):
        # df has columns 'ds' and 'y'
        df = df.copy()
        df['ds'] = pd.to_datetime(df['ds'])
        
        # Feature engineering for linear model
        df['trend'] = (df['ds'] - df['ds'].min()).dt.days
        df['day_of_week'] = df['ds'].dt.dayofweek
        df['month'] = df['ds'].dt.month
        
        # One-hot encode day of week and month
        X = pd.get_dummies(df[['trend', 'day_of_week', 'month']], columns=['day_of_week', 'month'])
        self.feature_columns = X.columns
        self.min_date = df['ds'].min()
        
        self.model.fit(X, df['y'])
        
    def predict(self, future_df):
        future_df = future_df.copy()
        future_df['ds'] = pd.to_datetime(future_df['ds'])
        future_df['trend'] = (future_df['ds'] - self.min_date).dt.days
        future_df['day_of_week'] = future_df['ds'].dt.dayofweek
        future_df['month'] = future_df['ds'].dt.month
        
        X = pd.get_dummies(future_df[['trend', 'day_of_week', 'month']], columns=['day_of_week', 'month'])
        
        # Align columns
        for col in self.feature_columns:
            if col not in X.columns:
                X[col] = 0
        X = X[self.feature_columns]
        
        preds = self.model.predict(X)
        future_df['yhat'] = np.clip(preds, 0, None)
        return future_df

def train_prophet_models(data_path="dataset/blood_bank_data.csv", model_dir="models"):
    os.makedirs(model_dir, exist_ok=True)
    
    print(f"Loading raw data from {data_path}...")
    df = pd.read_csv(data_path)
    df["date"] = pd.to_datetime(df["date"])
    
    # Train split: train on data before 2026-05-01
    split_date = pd.to_datetime("2026-05-01")
    train_raw = df[df["date"] < split_date].copy()
    
    blood_groups = ["O_pos", "A_pos", "B_pos", "AB_pos", "O_neg", "A_neg", "B_neg", "AB_neg"]
    models = {}
    
    for bt in blood_groups:
        bt_name = bt.replace("_pos", "+").replace("_neg", "-")
        print(f"Training Prophet model for blood type: {bt_name}...")
        
        # Prepare data for Prophet: needs columns 'ds' and 'y'
        train_bt = train_raw[["date", f"demand_{bt}"]].rename(columns={"date": "ds", f"demand_{bt}": "y"})
        
        if PROPHET_AVAILABLE:
            try:
                # Initialize Prophet model
                model = Prophet(
                    yearly_seasonality=True,
                    weekly_seasonality=True,
                    daily_seasonality=False,
                    interval_width=0.95  # 95% uncertainty intervals
                )
                
                # Fit model
                model.fit(train_bt)
                models[bt_name] = model
            except Exception as ex:
                print(f"Prophet training failed for {bt_name} ({str(ex)}). Falling back to LinearRegression.")
                model = FallbackModel(bt_name)
                model.fit(train_bt)
                models[bt_name] = model
        else:
            model = FallbackModel(bt_name)
            model.fit(train_bt)
            models[bt_name] = model
            
    # Save model dict
    model_path = os.path.join(model_dir, "prophet_models.joblib")
    joblib.dump({
        "models": models,
        "is_prophet": PROPHET_AVAILABLE
    }, model_path)
    print(f"Prophet/Fallback models saved successfully to {model_path}")
    return models

if __name__ == "__main__":
    train_prophet_models()
