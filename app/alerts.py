import streamlit as st
import pandas as pd
import numpy as np
import os
import sys

def render_alerts(df, inventory_df):
    current_date = st.session_state.current_date
    safety_stock_factor = st.session_state.safety_stock_factor
    selected_model = st.session_state.forecast_model
    
    st.title("🚨 Emergency Alerts & Logistics Planner")
    st.markdown("Automated shortage detection and targeted donation camp coordinator driven by AI forecasting.")
    
    # -------------------- Load Forecast --------------------
    from src.forecast import forecast_next_7_days
    
    lgb_path = "models/lightgbm_model.joblib"
    prophet_path = "models/prophet_models.joblib"
    
    if not os.path.exists(lgb_path) or not os.path.exists(prophet_path):
        st.warning("⚠️ ML models are not trained yet. Please visit the 'Demand Forecast' page to train models and generate alerts.")
        return
        
    try:
        fc_df = forecast_next_7_days(current_date=current_date)
    except Exception as e:
        st.error(f"Error generating forecast: {str(e)}")
        return
        
    if fc_df.empty:
        st.error("No predictions found. Please run model training.")
        return
        
    fc_subset = fc_df[fc_df["model"] == selected_model].copy()
    
    # Load historical average daily demand to determine dynamic safety thresholds
    hist_df = df[df["date"] <= current_date].copy()
    blood_types = ["O_pos", "A_pos", "B_pos", "AB_pos", "O_neg", "A_neg", "B_neg", "AB_neg"]
    
    avg_demands = {}
    for bt in blood_types:
        bt_display = bt.replace("_pos", "+").replace("_neg", "-")
        avg_demands[bt_display] = hist_df[f"demand_{bt}"].mean()
        
    # -------------------- Process Shortages and Depletion Days --------------------
    critical_alerts = []
    warning_alerts = []
    camp_recommendations = []
    
    # Pre-defined locations for camps
    locations = [
        "District Community Hall",
        "State Science College Campus",
        "Metro Central Shopping Mall",
        "City General Hospital Plaza",
        "Red Cross Youth HQ",
        "Industrial Zone Welfare Club"
    ]
    
    for idx, row in inventory_df.iterrows():
        bt = row["blood_type"]
        curr_stock = row["current_stock"]
        
        # Calculate dynamic safety threshold
        s_stock = int(round(avg_demands.get(bt, 10.0) * safety_stock_factor))
        
        # Get forecast for this blood type
        bt_fc = fc_subset[fc_subset["blood_type"] == bt].sort_values("date")
        
        if len(bt_fc) > 0:
            # 1. Check for immediate exhaustion
            cumulative_demand = 0
            depletion_day = None
            depletion_date = None
            
            for day_idx, fc_row in enumerate(bt_fc.itertuples()):
                cumulative_demand += fc_row.predicted_demand
                if cumulative_demand > curr_stock and depletion_day is None:
                    depletion_day = day_idx + 1  # 1-indexed (in how many days)
                    depletion_date = pd.to_datetime(fc_row.date)
            
            total_7day_demand = cumulative_demand
            
            # 2. Categorize Alerts
            if depletion_day is not None:
                # Stock will deplete within the next 7 days
                deficit = total_7day_demand - curr_stock
                critical_alerts.append({
                    "blood_type": bt,
                    "current_stock": curr_stock,
                    "predicted_demand": total_7day_demand,
                    "depletion_day": depletion_day,
                    "depletion_date": depletion_date,
                    "deficit": deficit
                })
                
                # Create Camp Recommendation
                # Target camp date is 2 days before depletion (to allow testing/processing time), clamped to at least tomorrow
                camp_days_away = max(1, depletion_day - 2)
                camp_date = current_date + pd.Timedelta(days=camp_days_away)
                
                # Pick location deterministically based on blood type hash
                loc_idx = hash(bt) % len(locations)
                camp_loc = locations[loc_idx]
                
                # Yield required is the 7-day deficit + 25% safety margin
                required_yield = int(round(deficit * 1.25))
                
                priority = "CRITICAL" if depletion_day <= 3 else "HIGH"
                
                camp_recommendations.append({
                    "blood_type": bt,
                    "camp_date": camp_date,
                    "location": camp_loc,
                    "required_yield": required_yield,
                    "priority": priority,
                    "reason": f"Stock depletion predicted in {depletion_day} days (on {depletion_date.strftime('%b %d')})."
                })
                
            elif curr_stock < s_stock:
                # Stock is below safety stock threshold (but won't fully deplete in 7 days)
                deficit = s_stock - curr_stock
                warning_alerts.append({
                    "blood_type": bt,
                    "current_stock": curr_stock,
                    "safety_stock": s_stock,
                    "deficit": deficit
                })
                
                # Suggest medium-priority camp
                camp_date = current_date + pd.Timedelta(days=4)
                loc_idx = hash(bt) % len(locations)
                camp_loc = locations[loc_idx]
                required_yield = int(round(deficit * 1.1))
                
                camp_recommendations.append({
                    "blood_type": bt,
                    "camp_date": camp_date,
                    "location": camp_loc,
                    "required_yield": required_yield,
                    "priority": "MEDIUM",
                    "reason": f"Warehouse stock ({curr_stock} units) is below safety limit ({s_stock} units)."
                })

    # -------------------- Render Active Alerts --------------------
    st.subheader("⚠️ Active Shortage Alerts")
    
    if not critical_alerts and not warning_alerts:
        st.markdown(
            "<div style='background-color: rgba(72, 187, 120, 0.15); border: 1px solid #48bb78; border-radius: 12px; padding: 20px; text-align: center;'>"
            "<h3 style='color: #48bb78; margin: 0;'>✓ Stock Security Level: Optimal</h3>"
            "<p style='color: #a0aec0; margin: 5px 0 0 0;'>AI forecasts show warehouse stock levels are sufficient to cover predicted demand for all blood groups over the next 7 days.</p>"
            "</div>",
            unsafe_allow_html=True
        )
    else:
        # Display Critical Alerts first
        for alert in critical_alerts:
            st.markdown(
                f"<div class='emergency-alert'>"
                f"<h4 style='color: #f56565; margin: 0 0 5px 0;'>🚨 CRITICAL STOCK EXHAUSTION: Blood Group {alert['blood_type']}</h4>"
                f"<p style='color: #e2e8f0; margin: 0; font-size: 14px;'>"
                f"Warehouse stock of <b>{alert['current_stock']} units</b> is predicted to exhaust in <b>{alert['depletion_day']} days</b> "
                f"(on {alert['depletion_date'].strftime('%A, %B %d')}) due to expected surges in demand.<br/>"
                f"Predicted 7-day demand is <b>{alert['predicted_demand']} units</b>. Deficit: <span style='color: #f56565; font-weight: bold;'>{alert['deficit']} units</span>."
                f"</p>"
                f"</div>",
                unsafe_allow_html=True
            )
            
        # Display Warning Alerts
        for alert in warning_alerts:
            st.markdown(
                f"<div class='emergency-alert' style='background: linear-gradient(135deg, rgba(236, 201, 75, 0.1) 0%, rgba(236, 201, 75, 0.02) 100%); border-color: #ecc94b;'>"
                f"<h4 style='color: #ecc94b; margin: 0 0 5px 0;'>⚠️ SAFETY LEVEL WARNING: Blood Group {alert['blood_type']}</h4>"
                f"<p style='color: #e2e8f0; margin: 0; font-size: 14px;'>"
                f"Current stock of <b>{alert['current_stock']} units</b> has fallen below the safety stock threshold "
                f"of <b>{alert['safety_stock']} units</b>.<br/>"
                f"Deficit to safety baseline: <span style='color: #ecc94b; font-weight: bold;'>{alert['deficit']} units</span>."
                f"</p>"
                f"</div>",
                unsafe_allow_html=True
            )

    st.markdown("---")
    
    # -------------------- Campaign Logistics Planner --------------------
    st.subheader("📅 Targeted Donation Camps Scheduler")
    st.markdown("AI-recommended locations and target donation yields to proactively resolve predicted blood shortages.")
    
    if not camp_recommendations:
        st.info("No donation camps required. Warehouse stockpiles are secure.")
    else:
        # Sort recommendations by priority: CRITICAL first, then HIGH, then MEDIUM
        priority_map = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2}
        camp_recommendations.sort(key=lambda x: priority_map.get(x["priority"], 3))
        
        # Display recommendations in a nice grid
        rec_cols = st.columns(2)
        for idx, camp in enumerate(camp_recommendations):
            col_idx = idx % 2
            
            p_color = "#f56565" if camp["priority"] == "CRITICAL" else ("#ed8936" if camp["priority"] == "HIGH" else "#ecc94b")
            p_bg = "rgba(245, 101, 101, 0.15)" if camp["priority"] == "CRITICAL" else ("rgba(237, 137, 54, 0.1)" if camp["priority"] == "HIGH" else "rgba(236, 201, 75, 0.1)")
            
            with rec_cols[col_idx]:
                st.markdown(
                    f"<div class='metric-card' style='border-left: 5px solid {p_color};'>"
                    f"  <div style='display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px;'>"
                    f"    <span style='background-color: {p_bg}; color: {p_color}; padding: 4px 8px; border-radius: 4px; font-size: 11px; font-weight: bold; text-transform: uppercase;'>{camp['priority']} PRIORITY</span>"
                    f"    <span style='color: #a0aec0; font-size: 13px;'>📅 Camp Date: <b>{camp['camp_date'].strftime('%b %d, %Y')}</b></span>"
                    f"  </div>"
                    f"  <h3 style='margin: 0 0 8px 0; font-size: 20px;'>Target Group: Blood Type <span style='color:#ff3b30;'>{camp['blood_type']}</span></h3>"
                    f"  <p style='color: #cbd5e0; font-size: 13px; margin: 0 0 16px 0;'><b>Reason:</b> {camp['reason']}</p>"
                    f"  <div style='background-color: rgba(255,255,255,0.03); padding: 12px; border-radius: 8px; border: 1px solid rgba(255,255,255,0.05); margin-bottom: 16px;'>"
                    f"    <p style='margin: 0; font-size: 13px; color: #a0aec0;'>RECOMMENDED LOCATION</p>"
                    f"    <p style='margin: 2px 0 8px 0; font-size: 15px; font-weight: 600; color: #ffffff;'>📍 {camp['location']}</p>"
                    f"    <p style='margin: 0; font-size: 13px; color: #a0aec0;'>REQUIRED DONATION YIELD</p>"
                    f"    <p style='margin: 2px 0 0 0; font-size: 18px; font-weight: bold; color: #ff3b30;'>🎯 {camp['required_yield']} Units</p>"
                    f"  </div>"
                    f"</div>",
                    unsafe_allow_html=True
                )
                
                # Interactive button inside streamlit to trigger simulation of camp completion
                if st.button(f"📅 Launch & Dispatch Alerts for {camp['blood_type']} Camp", key=f"btn_camp_{idx}"):
                    # Simulate completing the camp and adding units to inventory
                    bt_key = camp["blood_type"]
                    units_added = camp["required_yield"]
                    
                    idx_inv = inventory_df[inventory_df["blood_type"] == bt_key].index
                    if len(idx_inv) > 0:
                        current_val = inventory_df.loc[idx_inv[0], "current_stock"]
                        max_cap = inventory_df.loc[idx_inv[0], "max_capacity"]
                        new_val = min(max_cap, current_val + units_added)
                        inventory_df.loc[idx_inv[0], "current_stock"] = new_val
                        inventory_df.to_csv("dataset/inventory.csv", index=False)
                        st.success(f"🎉 Camp organized successfully! Added +{units_added} units to {bt_key} inventory.")
                        st.rerun()
                        
        st.write("")
