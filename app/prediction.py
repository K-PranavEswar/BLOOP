import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import json
import os
import sys

def render_prediction(df, inventory_df):
    current_date = st.session_state.current_date
    selected_model = st.session_state.forecast_model
    
    st.title("📈 7-Day Demand Forecasting")
    st.markdown("Visualize upcoming blood consumption trends, inspect forecast confidence intervals, and review performance reports.")
    
    blood_types = ["O_pos", "A_pos", "B_pos", "AB_pos", "O_neg", "A_neg", "B_neg", "AB_neg"]
    blood_types_display = [bt.replace("_pos", "+").replace("_neg", "-") for bt in blood_types]
    
    # -------------------- Load Predictions --------------------
    from src.forecast import forecast_next_7_days
    
    # Check if models exist. If not, prompt the user to train them.
    lgb_path = "models/lightgbm_model.joblib"
    prophet_path = "models/prophet_models.joblib"
    
    if not os.path.exists(lgb_path) or not os.path.exists(prophet_path):
        st.warning("⚠️ Predictive models have not been trained yet. Please run the model training script to generate forecasts.")
        
        # Add a run training button directly in the UI! This is extremely helpful and interactive.
        train_btn = st.button("🚀 Train Machine Learning Models Now")
        if train_btn:
            with st.spinner("Training LightGBM & Prophet/Fallback models... (This may take up to a minute)"):
                try:
                    # Run train_lightgbm
                    from src.train_lightgbm import train_lightgbm_model
                    from src.train_prophet import train_prophet_models
                    from src.evaluate import evaluate_models
                    from src.preprocess import preprocess_and_split
                    
                    preprocess_and_split()
                    train_lightgbm_model()
                    train_prophet_models()
                    evaluate_models()
                    
                    st.success("✓ Models trained and evaluated successfully!")
                    st.rerun()
                except Exception as ex:
                    st.error(f"Error during training: {str(ex)}")
            return
        return
        
    # Generate the forecast
    with st.spinner("Generating forecasts..."):
        try:
            fc_df = forecast_next_7_days(current_date=current_date)
        except Exception as e:
            st.error(f"Error generating forecast: {str(e)}")
            return
            
    if fc_df.empty:
        st.error("No forecast predictions could be generated. Check if the models are correctly trained.")
        return
        
    # Filter by chosen model (LightGBM or Prophet)
    fc_model_df = fc_df[fc_df["model"] == selected_model].copy()
    
    # -------------------- Selection Row --------------------
    st.subheader("📊 Forecast Settings")
    sel_col1, sel_col2 = st.columns([3, 1])
    
    with sel_col1:
        selected_bts = st.multiselect(
            "Select Blood Groups to Plot",
            options=blood_types_display,
            default=["O+", "O-", "A+", "B+"]
        )
        
    with sel_col2:
        show_uncertainty = st.checkbox("Show 90% Confidence Interval", value=True)
        
    if not selected_bts:
        st.warning("Please select at least one blood group to visualize.")
        return
        
    # -------------------- Forecast Visualizations --------------------
    st.subheader(f"📈 7-Day Forecast Trend ({selected_model})")
    
    # Plotly Line Chart
    fig = go.Figure()
    
    # If a single blood type is selected, show historical demand and confidence bounds
    if len(selected_bts) == 1:
        bt_sel = selected_bts[0]
        bt_col_name = bt_sel.replace("+", "_pos").replace("-", "_neg")
        
        # Historical slice (last 14 days)
        hist_subset = df[df["date"] <= current_date].tail(14).copy()
        
        # Forecast slice
        fc_subset = fc_model_df[fc_model_df["blood_type"] == bt_sel].sort_values("date")
        
        # Draw historical actual demand
        fig.add_trace(go.Scatter(
            x=hist_subset["date"],
            y=hist_subset[f"demand_{bt_col_name}"],
            name=f"Historical Demand ({bt_sel})",
            line=dict(color="rgba(255, 255, 255, 0.6)", width=2, dash='dot')
        ))
        
        # Draw forecast prediction
        fig.add_trace(go.Scatter(
            x=fc_subset["date"],
            y=fc_subset["predicted_demand"],
            name=f"Predicted Demand ({bt_sel})",
            line=dict(color="#ff3b30", width=3)
        ))
        
        # Draw uncertainty interval
        if show_uncertainty:
            fig.add_trace(go.Scatter(
                x=pd.concat([fc_subset["date"], fc_subset["date"].iloc[::-1]]),
                y=pd.concat([fc_subset["upper_bound"], fc_subset["lower_bound"].iloc[::-1]]),
                fill='toself',
                fillcolor='rgba(255, 59, 48, 0.15)',
                line=dict(color='rgba(255, 255, 255, 0)'),
                hoverinfo="skip",
                name="90% Confidence Interval"
            ))
            
    else:
        # Multiple blood types selected: show predictions only for clarity
        colors = ["#ff3b30", "#4299e1", "#48bb78", "#ecc94b", "#ed64a6", "#9f7aea", "#38b2ac", "#ed8936"]
        for idx, bt_sel in enumerate(selected_bts):
            fc_subset = fc_model_df[fc_model_df["blood_type"] == bt_sel].sort_values("date")
            color = colors[idx % len(colors)]
            
            fig.add_trace(go.Scatter(
                x=fc_subset["date"],
                y=fc_subset["predicted_demand"],
                name=f"Predicted {bt_sel}",
                line=dict(color=color, width=2.5)
            ))
            
            if show_uncertainty:
                fig.add_trace(go.Scatter(
                    x=pd.concat([fc_subset["date"], fc_subset["date"].iloc[::-1]]),
                    y=pd.concat([fc_subset["upper_bound"], fc_subset["lower_bound"].iloc[::-1]]),
                    fill='toself',
                    fillcolor=f"rgba{tuple(list(int(color.lstrip('#')[i:i+2], 16) for i in (0, 2, 4)) + [0.08])}",
                    line=dict(color='rgba(255, 255, 255, 0)'),
                    hoverinfo="skip",
                    showlegend=False
                ))
                
    fig.update_layout(
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        font=dict(color='#ffffff', family='Outfit'),
        margin=dict(l=0, r=0, t=10, b=0),
        xaxis=dict(gridcolor='#23273b', linecolor='#23273b'),
        yaxis=dict(gridcolor='#23273b', linecolor='#23273b')
    )
    st.plotly_chart(fig, use_container_width=True)

    # -------------------- Forecast Data Table --------------------
    st.markdown("---")
    col_t1, col_t2 = st.columns([5, 3])
    
    with col_t1:
        st.subheader("📋 Forecast Data Table")
        
        # Pivot the forecast table to show dates as index and blood groups as columns
        fc_filtered = fc_model_df[fc_model_df["blood_type"].isin(selected_bts)].copy()
        
        pivoted_fc = fc_filtered.pivot(index="date", columns="blood_type", values="predicted_demand")
        pivoted_fc.index = pd.to_datetime(pivoted_fc.index).strftime('%Y-%m-%d')
        pivoted_fc = pivoted_fc[selected_bts] # Keep user selected order
        
        st.dataframe(pivoted_fc, use_container_width=True)
        
        # Download button
        csv_data = pivoted_fc.to_csv()
        st.download_button(
            label="📥 Download Forecast as CSV",
            data=csv_data,
            file_name=f"hemopulse_forecast_{selected_model}_{current_date.strftime('%Y-%m-%d')}.csv",
            mime="text/csv"
        )
        
    # -------------------- Model Performance Metrics --------------------
    with col_t2:
        st.subheader("🎯 Model Performance Metrics (MAE / RMSE)")
        
        metrics_file = "reports/metrics.json"
        if os.path.exists(metrics_file):
            try:
                with open(metrics_file, "r") as f:
                    metrics = json.load(f)
                    
                lgb_m = metrics.get("lightgbm", {})
                prophet_m = metrics.get("prophet", {})
                
                # Build Comparison Table
                comparison_rows = []
                for bt_sel in selected_bts:
                    lgb_mae = lgb_m.get(bt_sel, {}).get("mae", np.nan)
                    lgb_rmse = lgb_m.get(bt_sel, {}).get("rmse", np.nan)
                    
                    prophet_mae = prophet_m.get(bt_sel, {}).get("mae", np.nan)
                    prophet_rmse = prophet_m.get(bt_sel, {}).get("rmse", np.nan)
                    
                    comparison_rows.append({
                        "Blood Group": bt_sel,
                        "LGBM MAE": f"{lgb_mae:.2f}" if not pd.isna(lgb_mae) else "N/A",
                        "LGBM RMSE": f"{lgb_rmse:.2f}" if not pd.isna(lgb_rmse) else "N/A",
                        "Prophet MAE": f"{prophet_mae:.2f}" if not pd.isna(prophet_mae) else "N/A",
                        "Prophet RMSE": f"{prophet_rmse:.2f}" if not pd.isna(prophet_rmse) else "N/A"
                    })
                    
                metrics_df = pd.DataFrame(comparison_rows)
                st.dataframe(metrics_df, use_container_width=True, hide_index=True)
                
                st.markdown(
                    "<div style='font-size: 11px; color: #a0aec0;'>"
                    "<i>Note: MAE (Mean Absolute Error) represents the average error in units. "
                    "RMSE (Root Mean Squared Error) penalizes larger forecast errors heavily. "
                    "Lower values indicate higher model accuracy.</i>"
                    "</div>",
                    unsafe_allow_html=True
                )
            except Exception as e:
                st.text("Failed to parse metrics file.")
        else:
            st.info("No metrics report available. Run model training to compute performance metrics.")
