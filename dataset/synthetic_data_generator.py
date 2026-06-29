import pandas as pd
import numpy as np
import os

def generate_synthetic_data(output_dir="dataset"):
    os.makedirs(output_dir, exist_ok=True)
    
    # Set seed for reproducibility
    np.random.seed(42)
    
    # Date range: 5 years of daily data
    start_date = "2021-01-01"
    end_date = "2026-06-28"
    dates = pd.date_range(start=start_date, end=end_date, freq="D")
    n_days = len(dates)
    
    # 1. Hospital admissions
    # Base rate of admissions is 150 with a slow upward trend (growth) over time
    time_index = np.arange(n_days)
    trend = 150 + 0.005 * time_index
    
    # Weekly seasonality (lower on weekends)
    day_of_week = dates.dayofweek
    weekly_seasonality = np.zeros(n_days)
    weekly_seasonality[day_of_week == 5] = -35  # Saturday
    weekly_seasonality[day_of_week == 6] = -50  # Sunday
    weekly_seasonality[day_of_week < 5] = 15    # Weekdays
    
    # Random noise
    admissions_noise = np.random.normal(0, 12, n_days)
    admissions = np.round(trend + weekly_seasonality + admissions_noise).astype(int)
    admissions = np.clip(admissions, 50, None) # Min 50 admissions
    
    # 2. Accident cases
    # Base accident rate of 12, higher on weekends (Friday/Saturday/Sunday nights)
    accident_base = 12
    accident_weekly = np.zeros(n_days)
    accident_weekly[day_of_week == 4] = 6   # Friday
    accident_weekly[day_of_week == 5] = 10  # Saturday
    accident_weekly[day_of_week == 6] = 5   # Sunday
    
    # Holiday/random accident surges (poisson process)
    accident_surges = np.random.poisson(1.5, n_days)
    # Extra spikes on random holidays / events
    surge_days = np.random.choice([0, 1], size=n_days, p=[0.97, 0.03])
    accident_spikes = surge_days * np.random.randint(15, 35, n_days)
    
    accidents = np.round(accident_base + accident_weekly + accident_surges + accident_spikes).astype(int)
    accidents = np.clip(accidents, 2, None)
    
    # 3. Elective surgeries
    # Scheduled surgeries, base rate of 25. High on weekdays, almost zero on weekends
    surgery_weekly = np.zeros(n_days)
    surgery_weekly[day_of_week < 5] = 25
    surgery_weekly[day_of_week >= 5] = 2
    
    # Seasonal drops (e.g. December holidays or mid-summer)
    month = dates.month
    surgery_seasonal = np.zeros(n_days)
    surgery_seasonal[month == 12] = -5 # Holiday season
    surgery_seasonal[month == 5] = -3  # Summer dip
    
    surgery_noise = np.random.normal(0, 3, n_days)
    elective_surgeries = np.round(surgery_weekly + surgery_seasonal + surgery_noise).astype(int)
    elective_surgeries = np.clip(elective_surgeries, 0, None)
    
    # 4. Dengue cases
    # Highly seasonal: Peaks in July-October (monsoon)
    # Model as a Gaussian curve peaking around day 250 (Sept 7th) of each year
    dengue_cases = np.zeros(n_days)
    for year in np.unique(dates.year):
        year_mask = dates.year == year
        day_of_year = dates[year_mask].dayofyear
        # Peak around day 245 (late August/early September), standard deviation of 35 days
        dengue_peak = 35 * np.exp(-((day_of_year - 245) ** 2) / (2 * (30 ** 2)))
        dengue_noise = np.random.poisson(1.5, np.sum(year_mask))
        dengue_cases[year_mask] = np.round(dengue_peak + dengue_noise).astype(int)
        
    dengue_cases = np.clip(dengue_cases, 0, None)
    
    # Create the base DataFrame
    df = pd.DataFrame({
        "date": dates,
        "admissions": admissions,
        "accidents": accidents,
        "elective_surgeries": elective_surgeries,
        "dengue_cases": dengue_cases
    })
    
    # 5. Blood Group Demand Calculation
    # Standard population distribution
    prevalence = {
        "O_pos": 0.38,
        "A_pos": 0.34,
        "B_pos": 0.17,
        "AB_pos": 0.05,
        "O_neg": 0.03,
        "A_neg": 0.02,
        "B_neg": 0.01,
        "AB_neg": 0.005
    }
    
    # Emergency distribution (O-neg is universal, O-pos is also heavily used)
    emergency_prevalence = {
        "O_pos": 0.35,
        "A_pos": 0.18,
        "B_pos": 0.10,
        "AB_pos": 0.02,
        "O_neg": 0.30,  # Universal donor surge
        "A_neg": 0.03,
        "B_neg": 0.01,
        "AB_neg": 0.01
    }
    
    # We will generate daily demand for each blood type
    for bt in prevalence.keys():
        # Demand components:
        # - Routine admissions: base demand
        # - Accidents: heavy emergency usage (especially O- and O+)
        # - Elective surgeries: planned usage
        # - Dengue: platelet support (correlated with overall hospital blood demand)
        
        routine_factor = prevalence[bt] * (0.08 * df["admissions"])
        accident_factor = emergency_prevalence[bt] * (0.6 * df["accidents"])
        surgery_factor = prevalence[bt] * (0.5 * df["elective_surgeries"])
        dengue_factor = prevalence[bt] * (0.4 * df["dengue_cases"])
        
        # Base daily consumption + random variation (std relative to demand size)
        base_demand = routine_factor + accident_factor + surgery_factor + dengue_factor
        noise = np.random.normal(0, np.clip(0.12 * base_demand, 0.5, None), n_days)
        
        demand_col = np.round(base_demand + noise).astype(int)
        df[f"demand_{bt}"] = np.clip(demand_col, 0, None)
        
    # Save the synthetic admissions log
    data_path = os.path.join(output_dir, "blood_bank_data.csv")
    df.to_csv(data_path, index=False)
    print(f"Historical blood bank data saved to {data_path} (Shape: {df.shape})")
    
    # 6. Generate current warehouse inventory.csv
    # Calculate historical average daily demand to set realistic current stock levels
    inventory_data = []
    for bt in prevalence.keys():
        avg_demand = df[f"demand_{bt}"].mean()
        # Current stock is set to a randomized value between 3.5 and 7 days of supply
        current_stock = int(avg_demand * np.random.uniform(3.5, 7.0))
        safety_stock = int(avg_demand * 5.0)  # 5-day safety limit
        max_capacity = int(avg_demand * 12.0)  # 12-day storage limit
        
        inventory_data.append({
            "blood_type": bt.replace("_pos", "+").replace("_neg", "-"),
            "current_stock": current_stock,
            "safety_stock": safety_stock,
            "max_capacity": max_capacity
        })
        
    inventory_df = pd.DataFrame(inventory_data)
    inventory_path = os.path.join(output_dir, "inventory.csv")
    inventory_df.to_csv(inventory_path, index=False)
    print(f"Inventory status saved to {inventory_path}")
    
    return df, inventory_df

if __name__ == "__main__":
    generate_synthetic_data()
