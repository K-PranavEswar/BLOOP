import pandas as pd
import numpy as np

def create_calendar_features(df, date_col="date"):
    """
    Extract calendar-based features from the date column.
    """
    df = df.copy()
    df[date_col] = pd.to_datetime(df[date_col])
    df["day_of_week"] = df[date_col].dt.dayofweek
    df["month"] = df[date_col].dt.month
    df["day_of_year"] = df[date_col].dt.dayofyear
    df["year"] = df[date_col].dt.year
    df["is_weekend"] = df["day_of_week"].isin([5, 6]).astype(int)
    return df

def create_lag_features(df, value_cols, lag_days, prefix=""):
    """
    Create lag features for specified columns.
    Since we predict 7 days in advance, lags must be >= 7.
    """
    df = df.copy()
    for col in value_cols:
        for lag in lag_days:
            df[f"{prefix}{col}_lag_{lag}"] = df[col].shift(lag)
    return df

def create_rolling_features(df, value_cols, windows, lag_shift=7, prefix=""):
    """
    Create rolling mean and std features for specified columns.
    Shift the window by lag_shift to ensure no data leakage for a 7-day forecast.
    """
    df = df.copy()
    for col in value_cols:
        # Shift the column first to prevent leakage of the most recent days
        shifted_col = df[col].shift(lag_shift)
        for window in windows:
            df[f"{prefix}{col}_roll_mean_{window}"] = shifted_col.rolling(window=window).mean()
            df[f"{prefix}{col}_roll_std_{window}"] = shifted_col.rolling(window=window).std()
    return df

def build_features_for_lightgbm(df, blood_groups):
    """
    Prepares a dataset optimized for LightGBM.
    We pivot the dataframe so that each row represents a single date and blood type.
    This allows us to train a single model for all blood types, leveraging shared patterns.
    """
    df = df.copy()
    df["date"] = pd.to_datetime(df["date"])
    
    # 1. Base calendar features
    df = create_calendar_features(df, "date")
    
    # 2. Lag and rolling features for external drivers (admissions, accidents, surgeries, dengue)
    external_cols = ["admissions", "accidents", "elective_surgeries", "dengue_cases"]
    # We can use lag 7, 8, 14, 21 for these drivers
    df = create_lag_features(df, external_cols, lag_days=[7, 8, 14], prefix="ext_")
    df = create_rolling_features(df, external_cols, windows=[7, 14], lag_shift=7, prefix="ext_")
    
    # 3. Pivot the blood demand data
    # Melt the dataframe so we have: date, external features, blood_group, demand
    melted_dfs = []
    for bt in blood_groups:
        bt_col = f"demand_{bt}"
        temp_df = df[["date", "day_of_week", "month", "day_of_year", "year", "is_weekend"] + 
                     [c for c in df.columns if c.startswith("ext_")] + [bt_col]].copy()
        temp_df = temp_df.rename(columns={bt_col: "demand"})
        temp_df["blood_group"] = bt.replace("_pos", "+").replace("_neg", "-")
        melted_dfs.append(temp_df)
        
    pivoted_df = pd.concat(melted_dfs, ignore_index=True)
    pivoted_df = pivoted_df.sort_values(by=["blood_group", "date"]).reset_index(drop=True)
    
    # 4. Now create demand-specific lag and rolling features for each blood type
    # Since the dataframe is sorted by blood_group and date, we can group by blood_group to shift/roll
    pivoted_df["demand_lag_7"] = pivoted_df.groupby("blood_group")["demand"].shift(7)
    pivoted_df["demand_lag_8"] = pivoted_df.groupby("blood_group")["demand"].shift(8)
    pivoted_df["demand_lag_9"] = pivoted_df.groupby("blood_group")["demand"].shift(9)
    pivoted_df["demand_lag_14"] = pivoted_df.groupby("blood_group")["demand"].shift(14)
    pivoted_df["demand_lag_21"] = pivoted_df.groupby("blood_group")["demand"].shift(21)
    
    # Rolling averages of demand (shifted by 7 to prevent leakage)
    # We use transform to apply rolling within each group
    grouped = pivoted_df.groupby("blood_group")["demand"]
    pivoted_df["demand_roll_mean_7"] = grouped.transform(lambda x: x.shift(7).rolling(7).mean())
    pivoted_df["demand_roll_std_7"] = grouped.transform(lambda x: x.shift(7).rolling(7).std())
    pivoted_df["demand_roll_mean_14"] = grouped.transform(lambda x: x.shift(7).rolling(14).mean())
    pivoted_df["demand_roll_std_14"] = grouped.transform(lambda x: x.shift(7).rolling(14).std())
    
    # Drop rows with NaN values (due to lags and rolling windows)
    pivoted_df = pivoted_df.dropna().reset_index(drop=True)
    
    return pivoted_df
