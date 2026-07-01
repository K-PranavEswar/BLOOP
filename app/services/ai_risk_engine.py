"""
AI Risk Engine – Single Source of Truth for all blood-bank status calculations.

Public API
──────────
calculate_inventory_status(current_stock, safety_stock,
                           predicted_7_day_demand, pending_requests=0, expected_donations=0)
    → dict with: status, color, badge_class, fill_pct, risk_score, risk_factors

calculate_global_risk(model_type='LightGBM')
    → full risk dictionary used by all pages

Every status label in the entire application MUST call one of these two
functions.  No other file may implement its own status logic.
"""
from datetime import datetime, timedelta
import pandas as pd
from app.models.blood_inventory import BloodInventory
from app.models.donation_camp import DonationCamp
from app.models.blood_request import BloodRequest
from app.services.prediction_service import get_forecast


# ─────────────────────────────────────────────────────────────────────────────
#  THE canonical status function — used by every page in the system
# ─────────────────────────────────────────────────────────────────────────────

def calculate_inventory_status(current_stock: int,
                                safety_stock: int,
                                predicted_7_day_demand: int,
                                pending_requests: int = 0,
                                expected_donations: int = 0) -> dict:
    """
    Advanced AI Decision Support Engine for Inventory Risk.
    
    Produces a 0-100 Risk Score based on:
    1. Supply-Demand Gap
    2. Safety Stock Breach
    3. Days to Depletion (Consumption Trend)
    """
    net_demand = predicted_7_day_demand + pending_requests
    net_supply = current_stock + expected_donations

    # 1. Supply-Demand Gap (Max 50 points)
    if net_demand == 0:
        gap_score = 0
    else:
        ratio = net_supply / net_demand
        if ratio >= 1.5:
            gap_score = 0
        elif ratio >= 1.0:
            gap_score = 20 * (1.5 - ratio) / 0.5
        else:
            gap_score = 20 + 30 * (1.0 - ratio)

    # 2. Safety Stock Breach (Max 30 points)
    if safety_stock == 0:
        safety_score = 0
    else:
        s_ratio = current_stock / safety_stock
        if s_ratio >= 1.5:
            safety_score = 0
        elif s_ratio >= 1.0:
            safety_score = 10 * (1.5 - s_ratio) / 0.5
        else:
            safety_score = 10 + 20 * (1.0 - s_ratio)

    # 3. Days to Depletion / Trend (Max 20 points)
    daily_consumption = net_demand / 7.0 if net_demand > 0 else 0
    if daily_consumption == 0:
        trend_score = 0
    else:
        dio = net_supply / daily_consumption
        if dio >= 7:
            trend_score = 0
        else:
            trend_score = 20 * (1.0 - dio / 7.0)

    # Overrides & Total Score Calculation
    if current_stock == 0:
        total_score = 100
    else:
        total_score = int(gap_score + safety_score + trend_score)
        
    risk_score = min(100, max(0, total_score))
    
    # Classification based on 0-100 score
    if risk_score <= 20:
        status = 'HEALTHY'
        color = 'success'
        badge_class = 'bg-success text-white'
    elif risk_score <= 40:
        status = 'LOW'
        color = 'info'
        badge_class = 'bg-info text-dark'
    elif risk_score <= 60:
        status = 'MODERATE'
        color = 'primary'
        badge_class = 'bg-primary text-white'
    elif risk_score <= 80:
        status = 'HIGH RISK'
        color = 'warning'
        badge_class = 'bg-warning text-dark'
    else:
        status = 'CRITICAL'
        color = 'danger'
        badge_class = 'bg-danger text-white'

    # Fill percentage for visual UI (0-100%)
    max_safe = max(safety_stock * 1.5, 1)
    fill_pct = min(100, max(0, int((current_stock / max_safe) * 100)))

    return {
        'status':      status,
        'color':       color,
        'badge_class': badge_class,
        'fill_pct':    fill_pct,
        'remaining':   net_supply - net_demand,
        'risk_score':  risk_score,
        'risk_factors': {
            'gap_score': round(gap_score, 1),
            'safety_score': round(safety_score, 1),
            'trend_score': round(trend_score, 1)
        }
    }


# ─────────────────────────────────────────────────────────────────────────────
#  Main engine
# ─────────────────────────────────────────────────────────────────────────────

def calculate_global_risk(model_type='LightGBM'):
    """
    Centralized Single Source of Truth for Blood Bank AI Risk.

    All pages (Admin Dashboard, Staff Dashboard, Inventory, Alerts, Public
    Availability, Reports) receive their status from THIS function.
    Internally calls calculate_inventory_status() for every blood group.
    """
    fc_df = get_forecast(model_type=model_type)

    # Only Whole Blood rows represent one record per blood group
    inventory_items = (
        BloodInventory.query
        .filter_by(component='Whole Blood')
        .order_by(BloodInventory.blood_type)
        .all()
    )

    metrics = {
        'blood_groups': [],
        'critical_group': None,
        'global_stats': {
            'total_current': 0,
            'total_consumed': 0,
            'total_remaining': 0,
        },
        'camp_recommendations': [],
    }

    now       = datetime.utcnow()
    next_week = now + timedelta(days=7)

    # Pre-fetch planned camps for the next 7 days (one DB call, not 8)
    upcoming_camps = DonationCamp.query.filter(
        DonationCamp.date >= now,
        DonationCamp.date <= next_week,
        DonationCamp.status == 'planned'
    ).all()

    for inv in inventory_items:
        bt          = inv.blood_type
        curr_stock  = inv.current_units
        safety      = inv.safety_stock

        # ── Predicted 7-day demand from ML model ─────────────────────────
        predicted_7day = 0
        bt_fc = pd.DataFrame()

        if not fc_df.empty:
            bt_fc = fc_df[fc_df['blood_group'] == bt].sort_values('date')
            if not bt_fc.empty:
                predicted_7day = int(bt_fc['predicted_demand'].sum())

        # ── Pending blood requests ───────────────────────────────────────
        pending_reqs  = BloodRequest.query.filter_by(blood_group=bt, status='pending').all()
        pending_units = sum(r.units_required for r in pending_reqs)

        # ── Expected donations from planned camps ────────────────────────
        expected_donations = 0
        for camp in upcoming_camps:
            if camp.target_blood_group == bt:
                expected_donations += int(camp.target_units * camp.expected_success_rate)
            elif not camp.target_blood_group:
                # General camp: distribute evenly across all 8 blood groups
                expected_donations += int((camp.target_units * camp.expected_success_rate) / 8)

        # ── Canonical status calculation (the ONLY place this happens) ───
        status_info = calculate_inventory_status(
            current_stock=curr_stock,
            safety_stock=safety,
            predicted_7_day_demand=predicted_7day,
            pending_requests=pending_units,
            expected_donations=expected_donations,
        )

        remaining   = status_info['remaining']
        risk        = status_info['status']
        color       = status_info['color']
        badge_class = status_info['badge_class']
        risk_score  = status_info['risk_score']

        # ── Depletion day calculation ────────────────────────────────────
        depletion_days = '> 7'
        if not bt_fc.empty:
            cumulative = 0
            temp_stock = curr_stock + expected_donations - pending_units
            for day_idx, fc_row in enumerate(bt_fc.itertuples()):
                cumulative += fc_row.predicted_demand
                if cumulative > temp_stock:
                    depletion_days = day_idx + 1
                    break
        elif remaining <= 0:
            depletion_days = 0

        metrics['blood_groups'].append({
            'blood_group':       bt,
            'current_stock':     curr_stock,
            'safety_stock':      safety,
            'predicted_demand':  predicted_7day,
            'expected_donations': expected_donations,
            'pending_requests':  pending_units,
            'expected_remaining': remaining,
            'depletion_days':    depletion_days,
            'risk_level':        risk,      # canonical status label
            'risk_score':        risk_score,
            'fill_pct':          status_info['fill_pct'],
            'color':             color,
            'badge_class':       badge_class,
            'priority':          0,
        })

        metrics['global_stats']['total_current']   += curr_stock
        metrics['global_stats']['total_consumed']   += predicted_7day
        metrics['global_stats']['total_remaining']  += remaining

    # ── Sort by priority (worst first) ──────────────────────────────────
    risk_weights = {
        'OUT OF STOCK': 1, 'CRITICAL': 2,
        'HIGH RISK': 3, 'MODERATE': 4, 'LOW': 5, 'HEALTHY': 6,
    }
    metrics['blood_groups'].sort(
        key=lambda x: (risk_weights.get(x['risk_level'], 7), -x['risk_score'])
    )
    for i, bg in enumerate(metrics['blood_groups']):
        bg['priority'] = i + 1

    if metrics['blood_groups']:
        metrics['critical_group'] = metrics['blood_groups'][0]

    # ── Camp recommendations for at-risk groups ──────────────────────────
    for bg in metrics['blood_groups']:
        if bg['risk_level'] in ('OUT OF STOCK', 'CRITICAL', 'HIGH RISK', 'MODERATE'):
            deficit = max(0, bg['safety_stock'] - bg['expected_remaining'])
            if bg['expected_remaining'] < 0:
                deficit += abs(bg['expected_remaining'])
            if deficit > 0:
                metrics['camp_recommendations'].append({
                    'blood_type':     bg['blood_group'],
                    'priority':       bg['risk_level'],
                    'required_yield': int(deficit),
                    'target_donors':  int(deficit / 0.8),
                    'reason': (
                        f"AI Risk Score {bg['risk_score']}%. "
                        f"Stock expected to deplete in {bg['depletion_days']} days."
                    ),
                    'camp_date': now + timedelta(days=1),
                    'location':  'City Center (High Traffic Area)',
                    'color':     bg['color'],
                })

    return metrics


# ─────────────────────────────────────────────────────────────────────────────
#  Convenience wrapper: compute status for a single BloodInventory ORM object.
#  Use this everywhere `item.status` used to be called directly.
# ─────────────────────────────────────────────────────────────────────────────

def get_item_status(inv_item,
                    predicted_7_day_demand: int = 0,
                    pending_requests: int = 0,
                    expected_donations: int = 0) -> dict:
    """
    Compute the canonical status for one BloodInventory row.

    Usage (replaces item.status):
        s = get_item_status(item)
        s['status']      → 'HEALTHY' | 'LOW' | 'MODERATE' | 'HIGH RISK' | 'CRITICAL' | 'OUT OF STOCK'
        s['badge_class'] → Bootstrap badge class string
        s['fill_pct']    → integer 0-100 for the liquid animation
    """
    return calculate_inventory_status(
        current_stock=inv_item.current_units,
        safety_stock=inv_item.safety_stock,
        predicted_7_day_demand=predicted_7_day_demand,
        pending_requests=pending_requests,
        expected_donations=expected_donations,
    )
