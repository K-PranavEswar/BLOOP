import streamlit as st
import pandas as pd
import numpy as np

def render_inventory(df, inventory_df):
    current_date = st.session_state.current_date
    safety_stock_factor = st.session_state.safety_stock_factor
    
    st.title("🩸 Warehouse Inventory Status")
    st.markdown("Real-time monitoring of blood group stockpiles, safety margins, and maximum warehouse capacities.")
    
    # -------------------- Load and Calculate Dynamic Thresholds --------------------
    hist_df = df[df["date"] <= current_date].copy()
    
    # Get average daily demands for recalculating safety stock dynamically
    blood_types = ["O_pos", "A_pos", "B_pos", "AB_pos", "O_neg", "A_neg", "B_neg", "AB_neg"]
    
    avg_demands = {}
    for bt in blood_types:
        bt_display = bt.replace("_pos", "+").replace("_neg", "-")
        avg_demands[bt_display] = hist_df[f"demand_{bt}"].mean()
        
    # Let's enrich the inventory DataFrame with the updated safety stock
    enriched_inventory = []
    
    for idx, row in inventory_df.iterrows():
        bt = row["blood_type"]
        curr_stock = row["current_stock"]
        max_cap = row["max_capacity"]
        
        # Dynamic safety stock based on sidebar configuration
        s_stock = int(round(avg_demands.get(bt, 10.0) * safety_stock_factor))
        
        # Calculate percentage filled
        fill_percent = min(100, int((curr_stock / max_cap) * 100)) if max_cap > 0 else 0
        
        enriched_inventory.append({
            "blood_type": bt,
            "current_stock": curr_stock,
            "safety_stock": s_stock,
            "max_capacity": max_cap,
            "fill_percent": fill_percent,
            "status": "CRITICAL" if curr_stock < s_stock else ("LOW" if curr_stock < s_stock * 1.5 else "OK")
        })
        
    # -------------------- Grid of Liquid Bottles --------------------
    st.subheader("🧪 Stock levels (Capacity Utilization)")
    
    # Render 4 columns in 2 rows
    cols = st.columns(4)
    for i, item in enumerate(enriched_inventory):
        col_idx = i % 4
        with cols[col_idx]:
            # Highlight border if critical
            border_color = "#e53e3e" if item["status"] == "CRITICAL" else ("#ecc94b" if item["status"] == "LOW" else "#23273b")
            status_text = "🚨 Critical" if item["status"] == "CRITICAL" else ("⚡ Low Stock" if item["status"] == "LOW" else "✓ Optimal")
            status_color = "#e53e3e" if item["status"] == "CRITICAL" else ("#ecc94b" if item["status"] == "LOW" else "#48bb78")
            
            st.markdown(
                f"<div class='metric-card' style='border-color: {border_color}; text-align: center;'>"
                f"<h3 style='margin: 0; font-size: 24px; color: #ffffff;'>Blood Type {item['blood_type']}</h3>"
                f"<span style='color: {status_color}; font-size: 13px; font-weight: 600;'>{status_text}</span>"
                f"<div class='liquid-container'>"
                f"  <div class='liquid-level' style='height: {item['fill_percent']}%;'>"
                f"    <div class='liquid-wave'></div>"
                f"  </div>"
                f"</div>"
                f"<div style='font-size: 18px; font-weight: bold; margin-top: 10px; color: #ffffff;'>{item['current_stock']} Units</div>"
                f"<div style='color: #a0aec0; font-size: 11px; margin-top: 4px;'>"
                f"  Safety Stock: <b>{item['safety_stock']}</b><br/>"
                f"  Max Capacity: <b>{item['max_capacity']}</b> ({item['fill_percent']}% filled)"
                f"</div>"
                f"</div>",
                unsafe_allow_html=True
            )
            
        # Add a spacing row between columns
        if i == 3:
            st.write("")

    st.markdown("---")
    
    # -------------------- Interactive Inventory Editor --------------------
    col_table, col_form = st.columns([5, 3])
    
    with col_table:
        st.subheader("📋 Inventory Audit Log")
        
        # Render a clean table of inventory status
        table_data = []
        for item in enriched_inventory:
            status_label = "🔴 Critical Shortage" if item["status"] == "CRITICAL" else ("🟡 Low Stock" if item["status"] == "LOW" else "🟢 Adequate")
            table_data.append({
                "Blood Type": item["blood_type"],
                "Current Stock": item["current_stock"],
                "Safety Stock Threshold": item["safety_stock"],
                "Maximum Storage Capacity": item["max_capacity"],
                "Capacity Utilization": f"{item['fill_percent']}%",
                "Status": status_label
            })
            
        inventory_table_df = pd.DataFrame(table_data)
        st.dataframe(inventory_table_df, use_container_width=True, hide_index=True)
        
    with col_form:
        st.subheader("📥 Log Shipment / Update Stock")
        with st.form("inventory_update_form"):
            selected_bt = st.selectbox("Select Blood Group", blood_types_display)
            transaction_type = st.radio("Transaction Type", ["Incoming Donation", "Outbound Issue"])
            units_amount = st.number_input("Units Count", min_value=1, max_value=200, value=20)
            
            submit_btn = st.form_submit_button("Submit Transaction")
            
            if submit_btn:
                # Find matching row in inventory_df and update current_stock
                idx = inventory_df[inventory_df["blood_type"] == selected_bt].index
                if len(idx) > 0:
                    current_val = inventory_df.loc[idx[0], "current_stock"]
                    max_cap = inventory_df.loc[idx[0], "max_capacity"]
                    
                    if transaction_type == "Incoming Donation":
                        new_val = min(max_cap, current_val + units_amount)
                        inventory_df.loc[idx[0], "current_stock"] = new_val
                        st.success(f"✓ Recorded donation of +{units_amount} units for {selected_bt}. Stock updated to {new_val}.")
                    else:
                        new_val = max(0, current_val - units_amount)
                        inventory_df.loc[idx[0], "current_stock"] = new_val
                        st.success(f"✓ Issued -{units_amount} units of {selected_bt}. Stock updated to {new_val}.")
                        
                    # Save changes back to file
                    inventory_df.to_csv("dataset/inventory.csv", index=False)
                    st.rerun()
                else:
                    st.error("Error updating inventory: Blood type not found.")
