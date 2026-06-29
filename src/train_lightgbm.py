import pandas as pd
import numpy as np
import lightgbm as lgb
import os
import joblib

def train_lightgbm_model(train_path="dataset/train_features.csv", model_dir="models"):
    os.makedirs(model_dir, exist_ok=True)
    
    print(f"Loading training features from {train_path}...")
    train_df = pd.read_csv(train_path)
    
    # Target column
    target = "demand"
    
    # Identify feature columns
    # We exclude date, demand (target), and any other helper columns
    exclude_cols = ["date", "demand"]
    features = [col for col in train_df.columns if col not in exclude_cols]
    
    # Treat blood_type as categorical
    train_df["blood_type"] = train_df["blood_type"].astype("category")
    
    X_train = train_df[features]
    y_train = train_df[target]
    
    print(f"Training LightGBM model with {X_train.shape[1]} features and {X_train.shape[0]} rows...")
    print(f"Features: {features}")
    
    # Initialize and train LightGBM regressor
    # Using reasonable default parameters for time-series forecasting
    model = lgb.LGBMRegressor(
        objective="regression",
        n_estimators=150,
        learning_rate=0.05,
        num_leaves=31,
        random_state=42,
        importance_type="gain",
        verbose=-1
    )
    
    model.fit(X_train, y_train)
    
    # Save the model and the features list
    model_path = os.path.join(model_dir, "lightgbm_model.joblib")
    model_data = {
        "model": model,
        "features": features
    }
    joblib.dump(model_data, model_path)
    print(f"LightGBM model and metadata saved successfully to {model_path}")
    
    # Print feature importances
    importances = model.feature_importances_
    importance_df = pd.DataFrame({
        "feature": features,
        "importance": importances
    }).sort_values(by="importance", ascending=False)
    
    print("\nTop 10 Feature Importances:")
    print(importance_df.head(10).to_string(index=False))
    
    return model

if __name__ == "__main__":
    train_lightgbm_model()
