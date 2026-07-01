import pandas as pd
import numpy as np
import os
import sys

# Add src to python path if needed
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from feature_engineering import build_features_for_lightgbm

def preprocess_and_split(data_path="dataset/blood_bank_data.csv", output_dir="dataset"):
    print(f"Loading raw data from {data_path}...")
    df = pd.read_csv(data_path)
    df["date"] = pd.to_datetime(df["date"])
    
    blood_groups = ["O_pos", "A_pos", "B_pos", "AB_pos", "O_neg", "A_neg", "B_neg", "AB_neg"]
    
    # 1. Feature engineering for LightGBM
    print("Building features for LightGBM...")
    pivoted_df = build_features_for_lightgbm(df, blood_groups)
    
    # Time-series split: Train until 2026-04-30, Test/Validation from 2026-05-01 onwards
    split_date = pd.to_datetime("2026-05-01")
    
    train_df = pivoted_df[pivoted_df["date"] < split_date].copy()
    test_df = pivoted_df[pivoted_df["date"] >= split_date].copy()
    
    train_path = os.path.join(output_dir, "train_features.csv")
    test_path = os.path.join(output_dir, "test_features.csv")
    
    train_df.to_csv(train_path, index=False)
    test_df.to_csv(test_path, index=False)
    
    print(f"Preprocessed train data saved to {train_path} (Shape: {train_df.shape})")
    print(f"Preprocessed test data saved to {test_path} (Shape: {test_df.shape})")
    
    return train_df, test_df

if __name__ == "__main__":
    preprocess_and_split()
