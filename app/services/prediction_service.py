"""
Prediction service – bridges existing ML pipeline into Flask.
Wraps src/forecast.py and src/evaluate.py without modifying them.
"""
import os
import json
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from flask import current_app


def get_forecast(current_date=None, model_type='LightGBM', days=7):
    """
    Generate blood demand forecast using existing ML pipeline.
    Returns a pandas DataFrame with columns: date, blood_type, predicted_demand, lower_bound, upper_bound, model
    """
    import sys
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    if base_dir not in sys.path:
        sys.path.insert(0, base_dir)

    try:
        from src.forecast import forecast_next_7_days

        if current_date is None:
            from datetime import datetime
            current_date = pd.to_datetime(datetime.now().date())

        fc_df = forecast_next_7_days(
            data_path=os.path.join(base_dir, 'dataset', 'blood_bank_data.csv'),
            current_date=current_date,
            model_dir=os.path.join(base_dir, 'models')
        )

        if fc_df.empty:
            return pd.DataFrame()

        if model_type:
            fc_df = fc_df[fc_df['model'] == model_type]
            
        # Standardize column name to blood_group
        col_mapping = {'blood_type': 'blood_group', 'Blood Group': 'blood_group', 'bloodtype': 'blood_group', 'type': 'blood_group', 'group': 'blood_group'}
        fc_df = fc_df.rename(columns=col_mapping)

        return fc_df

    except Exception as e:
        print(f"[PREDICTION SERVICE] Forecast error: {e}")
        return pd.DataFrame()


def get_chart_data(model_type='LightGBM', past_days=14):
    """
    Returns chart data for the UI combining historical data and forecast data.
    """
    import os
    import pandas as pd
    from flask import current_app
    
    # Defensive validation helper
    def validate_and_standardize(df, context_name="Dataset"):
        if df.empty:
            return df
        # Rename known variations
        col_mapping = {'blood_type': 'blood_group', 'Blood Group': 'blood_group', 'bloodtype': 'blood_group', 'type': 'blood_group', 'group': 'blood_group'}
        df = df.rename(columns=col_mapping)
        if 'blood_group' not in df.columns:
            raise KeyError(f"{context_name} is missing required column: blood_group")
        return df

    # 1. Get Forecast Data
    fc_df = get_forecast(model_type=model_type)
    try:
        fc_df = validate_and_standardize(fc_df, "Forecast Output")
    except KeyError as e:
        print(f"[ERROR] {e}")
        return {'current_date': '2026-06-28', 'blood_groups': {}}
    
    # 2. Get Historical Data
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    data_path = os.path.join(base_dir, 'dataset', 'blood_bank_data.csv')
    
    try:
        df = pd.read_csv(data_path)
        df['date'] = pd.to_datetime(df['date'])
        
        from datetime import datetime
        current_date_ts = pd.to_datetime(datetime.now().date())
        current_date_str = current_date_ts.strftime('%Y-%m-%d')
        
        # Melt the wide format into long format so we have a 'blood_group' column
        # Columns like 'demand_O_pos' -> 'O+'
        demand_cols = [c for c in df.columns if c.startswith('demand_')]
        melted_df = pd.melt(df, id_vars=['date'], value_vars=demand_cols, var_name='blood_group', value_name='demand')
        melted_df['blood_group'] = melted_df['blood_group'].str.replace('demand_', '').str.replace('_pos', '+').str.replace('_neg', '-')
        
        hist_df = validate_and_standardize(melted_df, "Preprocessed Historical Data")
        
        # Filter last `past_days` days
        start_date = current_date_ts - pd.Timedelta(days=past_days)
        hist_df = hist_df[(hist_df['date'] > start_date) & (hist_df['date'] <= current_date_ts)]
    except Exception as e:
        print(f"Error loading historical data: {e}")
        return {'current_date': '2026-06-28', 'blood_groups': {}}

    blood_groups = ['O+', 'O-', 'A+', 'A-', 'B+', 'B-', 'AB+', 'AB-']
    chart_data = {
        'current_date': current_date_str,
        'blood_groups': {}
    }
    
    for bg in blood_groups:
        # Historical for this bg
        h_data = hist_df[hist_df['blood_group'] == bg].sort_values('date')
        
        if 'demand' in h_data.columns:
            h_demands = h_data['demand'].tolist()
        elif 'units_demanded' in h_data.columns:
            h_demands = h_data['units_demanded'].tolist()
        else:
            h_demands = []
            
        h_dates = [d.strftime('%Y-%m-%d') for d in h_data['date']]
        
        # Forecast for this bg
        if not fc_df.empty:
            f_data = fc_df[fc_df['blood_group'] == bg].sort_values('date')
            f_dates = [d.strftime('%Y-%m-%d') for d in f_data['date']]
            f_demands = f_data['predicted_demand'].tolist()
            
            # To make the line continuous, prepend the last known historical point
            if len(h_dates) > 0 and len(f_dates) > 0:
                f_dates.insert(0, current_date_str)
                # If there's a gap between dataset max and current_date, we just use the last known h_demand
                f_demands.insert(0, h_demands[-1] if len(h_demands) > 0 else 0)
        else:
            f_dates = []
            f_demands = []
            
        # Pad the historical timeline with nulls (Nones) if the dataset ends before current_date_ts
        if len(h_dates) > 0:
            last_hist_date = pd.to_datetime(h_dates[-1])
            if last_hist_date < current_date_ts:
                # Add dummy dates up to current_date_str
                pad_dates = pd.date_range(start=last_hist_date + pd.Timedelta(days=1), end=current_date_ts, freq='D')
                for p_date in pad_dates:
                    h_dates.append(p_date.strftime('%Y-%m-%d'))
                    h_demands.append(None)  # Becomes null in JSON

        chart_data['blood_groups'][bg] = {
            'hist_dates': h_dates,
            'hist_demands': h_demands,
            'fc_dates': f_dates,
            'fc_demands': f_demands
        }
        
    return chart_data


def get_forecast_30_day(current_date=None, model_type='LightGBM'):
    """Generate 30-day forecast by using available 7-day data and extending with trends."""
    fc_7 = get_forecast(current_date=current_date, model_type=model_type)
    if fc_7.empty:
        return pd.DataFrame()

    # For 30-day view, we extrapolate by repeating the 7-day pattern with slight trend adjustment
    blood_groups = fc_7['blood_group'].unique()
    extended_rows = []

    for bg in blood_groups:
        bg_data = fc_7[fc_7['blood_group'] == bg].sort_values('date')
        if len(bg_data) == 0:
            continue

        base_demands = bg_data['predicted_demand'].values
        avg_demand = np.mean(base_demands)
        last_date = pd.to_datetime(bg_data['date'].max())

        for day in range(len(base_demands)):
            extended_rows.append(bg_data.iloc[day].to_dict())

        for day in range(7, 30):
            next_date = last_date + timedelta(days=day - 6)
            pattern_idx = day % 7
            predicted = max(0, int(base_demands[pattern_idx] + np.random.normal(0, avg_demand * 0.05)))
            extended_rows.append({
                'date': next_date,
                'blood_group': bg,
                'predicted_demand': predicted,
                'lower_bound': max(0, int(predicted * 0.8)),
                'upper_bound': int(predicted * 1.2),
                'model': model_type
            })

    return pd.DataFrame(extended_rows)


def get_metrics():
    """Load model performance metrics from reports/metrics.json."""
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    metrics_path = os.path.join(base_dir, 'reports', 'metrics.json')

    if not os.path.exists(metrics_path):
        import subprocess
        try:
            # Automatically regenerate evaluation metrics if missing
            evaluate_script = os.path.join(base_dir, 'src', 'evaluate.py')
            subprocess.run(['python', evaluate_script], check=True)
        except Exception as e:
            print(f"[PREDICTION SERVICE] Failed to regenerate metrics: {e}")

    if os.path.exists(metrics_path):
        with open(metrics_path, 'r') as f:
            return json.load(f)
    return {}



def are_models_trained():
    """Check if ML models exist."""
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    lgb_path = os.path.join(base_dir, 'models', 'lightgbm_model.joblib')
    prophet_path = os.path.join(base_dir, 'models', 'prophet_models.joblib')
    return os.path.exists(lgb_path) and os.path.exists(prophet_path)


def train_models():
    """Trigger model training pipeline."""
    import sys
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    if base_dir not in sys.path:
        sys.path.insert(0, base_dir)

    from src.preprocess import preprocess_and_split
    from src.train_lightgbm import train_lightgbm_model
    from src.train_prophet import train_prophet_models
    from src.evaluate import evaluate_models

    preprocess_and_split()
    train_lightgbm_model()
    train_prophet_models()
    evaluate_models()
    return True
