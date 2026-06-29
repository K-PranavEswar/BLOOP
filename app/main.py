import streamlit as st
import pandas as pd
import numpy as np
import os
import sys

# Add root directory to python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Set page configuration
st.set_page_config(
    page_title="HemoPulse | AI Blood Bank Predictor",
    page_icon="🩸",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom premium styling
def inject_custom_css():
    st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;600;700&display=swap');
    
    /* Global Styles */
    html, body, [data-testid="stAppViewContainer"] {
        font-family: 'Outfit', sans-serif !important;
        background-color: #0c0d14 !important;
        color: #f1f3f9 !important;
    }
    
    /* Sidebar styling */
    [data-testid="stSidebar"] {
        background-color: #11121b !important;
        border-right: 1px solid #1f2235 !important;
    }
    
    /* Headers */
    h1, h2, h3, h4, h5, h6 {
        font-family: 'Outfit', sans-serif !important;
        font-weight: 600 !important;
        letter-spacing: -0.02em !important;
        color: #ffffff !important;
    }
    
    /* Custom Card Style */
    .metric-card {
        background-color: #171926;
        border: 1px solid #23273b;
        border-radius: 16px;
        padding: 24px;
        box-shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.3);
        transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
        margin-bottom: 20px;
    }
    
    .metric-card:hover {
        transform: translateY(-4px);
        border-color: #e53e3e;
        box-shadow: 0 12px 40px 0 rgba(229, 62, 62, 0.15);
    }
    
    .metric-header {
        font-size: 14px;
        font-weight: 500;
        color: #a0aec0;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        margin-bottom: 8px;
    }
    
    .metric-value {
        font-size: 36px;
        font-weight: 700;
        color: #ffffff;
        line-height: 1;
        margin-bottom: 8px;
    }
    
    .metric-delta {
        font-size: 14px;
        font-weight: 500;
        display: flex;
        align-items: center;
    }
    
    .delta-up { color: #48bb78; }
    .delta-down { color: #f56565; }
    
    /* Liquid Bottle Visuals */
    .liquid-container {
        position: relative;
        width: 100px;
        height: 140px;
        border: 4px solid #4a5568;
        border-radius: 12px 12px 30px 30px;
        overflow: hidden;
        margin: 10px auto;
        background-color: #1a202c;
        box-shadow: inset 0 0 20px rgba(0,0,0,0.5);
    }
    
    .liquid-level {
        position: absolute;
        bottom: 0;
        left: 0;
        width: 100%;
        transition: height 1s ease-out;
        background: linear-gradient(180deg, #ff3b30 0%, #a8201a 100%);
        box-shadow: 0 -5px 15px rgba(255, 59, 48, 0.4);
    }
    
    .liquid-wave {
        position: absolute;
        top: -10px;
        left: 0;
        width: 200%;
        height: 20px;
        background: rgba(255, 255, 255, 0.1);
        border-radius: 40%;
        animation: wave 4s infinite linear;
    }
    
    @keyframes wave {
        0% { transform: translateX(0) rotate(0deg); }
        100% { transform: translateX(-50%) rotate(360deg); }
    }
    
    /* Alert styles */
    .emergency-alert {
        background: linear-gradient(135deg, rgba(229, 62, 62, 0.2) 0%, rgba(229, 62, 62, 0.05) 100%);
        border: 1px solid #e53e3e;
        border-radius: 12px;
        padding: 16px 20px;
        margin-bottom: 16px;
        box-shadow: 0 0 20px rgba(229, 62, 62, 0.1);
    }
    
    /* Custom buttons and sliders styling */
    div.stButton > button {
        background: linear-gradient(135deg, #e53e3e 0%, #b83280 100%) !important;
        color: white !important;
        border: none !important;
        border-radius: 8px !important;
        padding: 8px 20px !important;
        font-weight: 600 !important;
        transition: all 0.2s !important;
        box-shadow: 0 4px 14px rgba(229, 62, 62, 0.3) !important;
    }
    
    div.stButton > button:hover {
        transform: translateY(-1px) !important;
        box-shadow: 0 6px 20px rgba(229, 62, 62, 0.4) !important;
    }
    
    /* Info banners */
    .pulse-container {
        border-left: 4px solid #3182ce;
        background-color: #171926;
        padding: 12px 20px;
        border-radius: 0 12px 12px 0;
        margin-bottom: 16px;
    }
    </style>
    """, unsafe_allow_html=True)

# Main Application Entry
def main():
    inject_custom_css()
    
    # -------------------- Load Data --------------------
    data_file = "dataset/blood_bank_data.csv"
    inventory_file = "dataset/inventory.csv"
    
    if not os.path.exists(data_file) or not os.path.exists(inventory_file):
        st.warning("⚠️ Datasets not detected. Initializing synthetic data generation...")
        try:
            from dataset.synthetic_data_generator import generate_synthetic_data
            generate_synthetic_data()
        except Exception as e:
            st.error(f"Failed to generate synthetic data: {str(e)}")
            return
            
    df = pd.read_csv(data_file)
    df["date"] = pd.to_datetime(df["date"])
    
    inventory_df = pd.read_csv(inventory_file)
    
    # -------------------- Session State --------------------
    if "current_date" not in st.session_state:
        st.session_state.current_date = df["date"].max()
        
    if "safety_stock_factor" not in st.session_state:
        st.session_state.safety_stock_factor = 5.0
        
    if "forecast_model" not in st.session_state:
        st.session_state.forecast_model = "LightGBM"
        
    # -------------------- Sidebar Controls --------------------
    st.sidebar.markdown(
        "<div style='text-align: center; padding: 10px;'>"
        "<h1 style='color: #ff3b30; margin: 0; font-size: 28px;'>HemoPulse AI</h1>"
        "<p style='color: #a0aec0; font-size: 13px;'>Predictive Blood Logistics Engine</p>"
        "</div>", 
        unsafe_allow_html=True
    )
    
    st.sidebar.markdown("---")
    
    # Page selector
    page = st.sidebar.radio(
        "Navigation",
        ["🏠 Dashboard Overview", "🩸 Inventory Status", "📈 Demand Forecast", "🚨 Emergency Alerts & Camps"]
    )
    
    st.sidebar.markdown("---")
    st.sidebar.subheader("🎛️ Parameters Config")
    
    # Date slider (allows user to step back in time to simulate past forecasting)
    available_dates = df["date"].sort_values().unique()
    # Let's restrict selection to dates that allow at least 7 days of validation/prediction
    min_sel_date = pd.to_datetime(available_dates[14])
    max_sel_date = pd.to_datetime(available_dates[-1])
    
    selected_date = st.sidebar.date_input(
        "Simulation Base Date",
        value=st.session_state.current_date,
        min_value=min_sel_date,
        max_value=max_sel_date
    )
    st.session_state.current_date = pd.to_datetime(selected_date)
    
    # Safety stock slider
    st.session_state.safety_stock_factor = st.sidebar.slider(
        "Safety Stock (Days of Demand)",
        min_value=2.0,
        max_value=10.0,
        value=st.session_state.safety_stock_factor,
        step=0.5
    )
    
    # Forecasting model selection
    st.session_state.forecast_model = st.sidebar.selectbox(
        "Forecasting Algorithm",
        ["LightGBM", "Prophet"]
    )
    
    st.sidebar.markdown("---")
    
    # Sidebar stats summary
    st.sidebar.markdown(
        f"<div style='background-color: #171926; padding: 15px; border-radius: 8px; border: 1px solid #23273b;'>"
        f"<p style='color: #a0aec0; margin: 0; font-size: 12px;'>SYSTEM STATUS</p>"
        f"<p style='color: #48bb78; margin: 0; font-size: 14px; font-weight: bold;'>● Online & Operational</p>"
        f"<p style='color: #a0aec0; margin: 5px 0 0 0; font-size: 11px;'>Base Date: {st.session_state.current_date.strftime('%Y-%m-%d')}</p>"
        f"</div>",
        unsafe_allow_html=True
    )
    
    # -------------------- Load Pages --------------------
    # Load corresponding page script
    if page == "🏠 Dashboard Overview":
        from app.dashboard import render_dashboard
        render_dashboard(df, inventory_df)
    elif page == "🩸 Inventory Status":
        from app.inventory import render_inventory
        render_inventory(df, inventory_df)
    elif page == "📈 Demand Forecast":
        from app.prediction import render_prediction
        render_prediction(df, inventory_df)
    elif page == "🚨 Emergency Alerts & Camps":
        from app.alerts import render_alerts
        render_alerts(df, inventory_df)

if __name__ == "__main__":
    main()
