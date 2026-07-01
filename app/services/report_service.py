"""
Report Service – Production-grade CSV and PDF report generation.
Uses only real data from SQLAlchemy models + AI Risk Engine.

Sections:
  1. Inventory Report  (CSV + PDF)
  2. AI Prediction Report (CSV + PDF)
  3. Comprehensive Master Report  (CSV + PDF)
"""
import io
import logging
from datetime import datetime
from typing import Optional

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import (
    SimpleDocTemplate, Table, TableStyle, Paragraph,
    Spacer, HRFlowable, PageBreak, KeepTogether
)
from reportlab.platypus.flowables import HRFlowable

from app.models.blood_inventory import BloodInventory
from app.models.blood_request import BloodRequest
from app.models.donor import Donor
from app.models.donation_camp import DonationCamp
from app.models.donation_history import DonationHistory
from app.models.activity_log import ActivityLog
from app.models.ai_analysis_log import AIAnalysisLog
from app.services.prediction_service import get_forecast, get_metrics
from app.services.ai_risk_engine import calculate_global_risk

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
#  Design Tokens
# ─────────────────────────────────────────────────────────────────────────────
C_RED       = colors.HexColor('#dc2626')
C_DARK_RED  = colors.HexColor('#991b1b')
C_BLUE      = colors.HexColor('#2563eb')
C_GREEN     = colors.HexColor('#16a34a')
C_ORANGE    = colors.HexColor('#ea580c')
C_PURPLE    = colors.HexColor('#7c3aed')
C_DARK      = colors.HexColor('#1e293b')
C_GREY      = colors.HexColor('#64748b')
C_LIGHT     = colors.HexColor('#f8fafc')
C_ALT_ROW   = colors.HexColor('#f1f5f9')
C_BORDER    = colors.HexColor('#cbd5e1')

# Risk colours
RISK_COLOR = {
    'OUT OF STOCK': colors.HexColor('#111827'),
    'CRITICAL':     C_RED,
    'HIGH RISK':    C_ORANGE,
    'LOW':          colors.HexColor('#0284c7'),
    'SAFE':         C_GREEN,
    'CRITICAL\n':   C_RED,  # guard for whitespace
}

def _risk_cell_color(risk: str):
    return RISK_COLOR.get(risk.strip(), C_GREY)


# ─────────────────────────────────────────────────────────────────────────────
#  Style helpers
# ─────────────────────────────────────────────────────────────────────────────
def _build_styles():
    base = getSampleStyleSheet()
    title = ParagraphStyle(
        'HPTitle', parent=base['Title'],
        fontSize=22, textColor=C_RED, spaceAfter=6, leading=26
    )
    subtitle = ParagraphStyle(
        'HPSubtitle', parent=base['Normal'],
        fontSize=11, textColor=C_GREY, spaceAfter=4
    )
    section = ParagraphStyle(
        'HPSection', parent=base['Heading2'],
        fontSize=13, textColor=C_DARK, spaceBefore=18, spaceAfter=8,
        borderPad=4, borderColor=C_BORDER, borderWidth=0, leading=16
    )
    body = ParagraphStyle(
        'HPBody', parent=base['Normal'],
        fontSize=9, textColor=C_DARK, leading=13
    )
    footer_s = ParagraphStyle(
        'HPFooter', parent=base['Normal'],
        fontSize=8, textColor=C_GREY, alignment=1
    )
    bold_body = ParagraphStyle(
        'HPBoldBody', parent=base['Normal'],
        fontSize=9, textColor=C_DARK, leading=13, fontName='Helvetica-Bold'
    )
    kv_key = ParagraphStyle(
        'HPKVKey', parent=base['Normal'],
        fontSize=9, textColor=C_GREY, leading=13
    )
    return {
        'title': title, 'subtitle': subtitle, 'section': section,
        'body': body, 'footer': footer_s, 'bold_body': bold_body,
        'kv_key': kv_key,
    }


def _table_style(header_color=C_RED, alternate=True):
    cmds = [
        ('BACKGROUND', (0, 0), (-1, 0), header_color),
        ('TEXTCOLOR',  (0, 0), (-1, 0), colors.white),
        ('FONTNAME',   (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE',   (0, 0), (-1, 0), 9),
        ('FONTSIZE',   (0, 1), (-1, -1), 8),
        ('ALIGN',      (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN',     (0, 0), (-1, -1), 'MIDDLE'),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
        ('TOPPADDING',    (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 1), (-1, -1), 5),
        ('GRID',       (0, 0), (-1, -1), 0.4, C_BORDER),
    ]
    if alternate:
        cmds.append(('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, C_ALT_ROW]))
    return TableStyle(cmds)


def _header_block(elements, styles, title_text: str, generated_by: str = 'Staff Member', model_type: str = ''):
    now = datetime.now().strftime('%B %d, %Y  %I:%M %p')
    elements.append(Paragraph('HEMOPULSE AI PRO', styles['title']))
    subtitle = f'{title_text}'
    if model_type:
        subtitle += f' &nbsp;•&nbsp; Model: {model_type}'
    elements.append(Paragraph(subtitle, styles['subtitle']))
    elements.append(Paragraph(f'Generated: {now}  &nbsp;|&nbsp;  Generated by: {generated_by}', styles['kv_key']))
    elements.append(HRFlowable(width='100%', thickness=1.5, color=C_RED, spaceAfter=12, spaceBefore=8))


def _footer_note(elements, styles):
    elements.append(Spacer(1, 24))
    elements.append(HRFlowable(width='100%', thickness=0.5, color=C_BORDER, spaceBefore=8, spaceAfter=6))
    elements.append(Paragraph(
        'CONFIDENTIAL – Generated by HemoPulse AI Pro | AI-Based Blood Bank Management System',
        styles['footer']
    ))


# ─────────────────────────────────────────────────────────────────────────────
#  1. INVENTORY REPORT
# ─────────────────────────────────────────────────────────────────────────────

def export_inventory_csv(generated_by: str = 'Staff Member') -> bytes:
    """CSV: Blood inventory enriched with AI risk data."""
    import csv
    output = io.StringIO()
    writer = csv.writer(output)

    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    writer.writerow(['HemoPulse AI Pro – Blood Inventory Report'])
    writer.writerow([f'Generated: {now}', f'Generated By: {generated_by}'])
    writer.writerow([])

    writer.writerow([
        'Blood Group', 'Component', 'Current Stock', 'Max Capacity',
        'Safety Stock', 'Status', 'Fill %', 'Last Updated',
        'AI Risk Level', 'AI Risk Score (%)', 'Expected Remaining (7d)',
        'Predicted Weekly Demand', 'Recommended Collection'
    ])

    # Fetch global AI risk once
    try:
        risk_data = calculate_global_risk()
        risk_map = {bg['blood_group']: bg for bg in risk_data.get('blood_groups', [])}
    except Exception as e:
        logger.warning(f'[report_service] AI risk calculation failed: {e}')
        risk_map = {}

    items = BloodInventory.query.order_by(BloodInventory.blood_type, BloodInventory.component).all()
    for item in items:
        ai = risk_map.get(item.blood_type, {})
        expected_rem = ai.get('expected_remaining', 'N/A')
        pred_demand  = ai.get('predicted_demand', 'N/A')
        risk_level   = ai.get('risk_level', 'UNKNOWN')
        risk_score   = ai.get('risk_score', 'N/A')
        # Recommended collection = max(0, safety_stock - expected_remaining)
        try:
            rec_col = max(0, item.safety_stock - int(expected_rem))
        except (TypeError, ValueError):
            rec_col = 'N/A'

        last_updated = item.last_updated.strftime('%Y-%m-%d %H:%M') if item.last_updated else 'N/A'
        writer.writerow([
            item.blood_type, item.component, item.current_units,
            item.max_capacity, item.safety_stock, risk_level,
            f'{item.fill_percentage}%', last_updated,
            risk_level, risk_score, expected_rem, pred_demand, rec_col
        ])

    if not items:
        writer.writerow(['No records available'])

    return output.getvalue().encode('utf-8')


def export_inventory_pdf(generated_by: str = 'Staff Member') -> bytes:
    """PDF: Professional blood inventory report with colour-coded risk rows."""
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=landscape(A4),
        topMargin=0.5 * inch, bottomMargin=0.5 * inch,
        leftMargin=0.5 * inch, rightMargin=0.5 * inch
    )
    elements = []
    styles = _build_styles()

    _header_block(elements, styles, 'Blood Inventory Report', generated_by)

    # ── Fetch data ──────────────────────────────────────────────────────────
    try:
        risk_data = calculate_global_risk()
        risk_map = {bg['blood_group']: bg for bg in risk_data.get('blood_groups', [])}
        global_stats = risk_data.get('global_stats', {})
    except Exception as e:
        logger.warning(f'[report_service] AI risk: {e}')
        risk_map, global_stats = {}, {}

    items = BloodInventory.query.order_by(BloodInventory.blood_type, BloodInventory.component).all()

    # ── Executive stats ─────────────────────────────────────────────────────
    elements.append(Paragraph('Inventory Summary', styles['section']))
    whole_blood_items = [i for i in items if i.component == 'Whole Blood']
    critical_groups = [i for i in whole_blood_items if risk_map.get(i.blood_type, {}).get('risk_level') == 'CRITICAL']
    safe_groups     = [i for i in whole_blood_items if risk_map.get(i.blood_type, {}).get('risk_level') == 'HEALTHY']

    summary_data = [
        ['Total Blood Types Tracked', str(len(whole_blood_items))],
        ['Total Current Stock (All Components)', str(sum(i.current_units for i in items))],
        ['Critical Blood Groups', str(len(critical_groups))],
        ['Safe Blood Groups', str(len(safe_groups))],
        ['Predicted 7-Day Consumption', str(global_stats.get('total_consumed', 'N/A'))],
        ['Expected Remaining (7d)', str(global_stats.get('total_remaining', 'N/A'))],
    ]
    summary_table = Table(summary_data, colWidths=[3 * inch, 2 * inch])
    summary_table.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('TEXTCOLOR', (0, 0), (0, -1), C_GREY),
        ('TEXTCOLOR', (1, 0), (1, -1), C_DARK),
        ('ALIGN', (1, 0), (1, -1), 'LEFT'),
        ('ROWBACKGROUNDS', (0, 0), (-1, -1), [colors.white, C_ALT_ROW]),
        ('GRID', (0, 0), (-1, -1), 0.3, C_BORDER),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
    ]))
    elements.append(summary_table)
    elements.append(Spacer(1, 14))

    # ── Critical groups callout ──────────────────────────────────────────────
    if critical_groups:
        elements.append(Paragraph(f'⚠ Critical Blood Groups: {", ".join(i.blood_type for i in critical_groups)}', styles['bold_body']))
        elements.append(Spacer(1, 8))

    # ── Main inventory table ─────────────────────────────────────────────────
    elements.append(Paragraph('Full Inventory Table', styles['section']))
    headers = [
        'Blood Group', 'Component', 'Current\nStock', 'Max\nCapacity',
        'Safety\nStock', 'Fill %', 'Status',
        'AI Risk\nLevel', 'AI Risk\nScore', 'Expected\nRemaining',
        'Predicted\nDemand', 'Rec. Collect'
    ]
    col_w = [0.7, 1.0, 0.75, 0.75, 0.75, 0.6, 0.75, 0.85, 0.75, 0.85, 0.85, 0.85]
    col_w = [w * inch for w in col_w]

    table_data = [headers]
    row_colors = []  # (row_idx, color)

    for i, item in enumerate(items, start=1):
        ai = risk_map.get(item.blood_type, {})
        expected_rem = ai.get('expected_remaining', 'N/A')
        pred_demand  = ai.get('predicted_demand', 'N/A')
        risk_level   = ai.get('risk_level', 'UNKNOWN')
        risk_score   = f"{ai.get('risk_score', 'N/A')}%"
        try:
            rec_col = str(max(0, item.safety_stock - int(expected_rem)))
        except (TypeError, ValueError):
            rec_col = 'N/A'
        last_updated = item.last_updated.strftime('%m/%d') if item.last_updated else '-'

        table_data.append([
            item.blood_type, item.component, str(item.current_units),
            str(item.max_capacity), str(item.safety_stock),
            f"{ai.get('fill_pct', 0)}%", ai.get('risk_level', 'UNKNOWN'),
            risk_level, risk_score, str(expected_rem), str(pred_demand), rec_col
        ])

        # Color critical rows
        if risk_level in ('OUT OF STOCK', 'CRITICAL'):
            row_colors.append((i, colors.HexColor('#fee2e2')))
        elif risk_level == 'HIGH RISK':
            row_colors.append((i, colors.HexColor('#ffedd5')))

    if not items:
        table_data.append(['No records available'] + [''] * (len(headers) - 1))

    inv_table = Table(table_data, colWidths=col_w, repeatRows=1)
    style_cmds = _table_style(header_color=C_RED)
    for row_idx, bg in row_colors:
        style_cmds.add('BACKGROUND', (0, row_idx), (-1, row_idx), bg)
    inv_table.setStyle(style_cmds)
    elements.append(inv_table)

    _footer_note(elements, styles)
    doc.build(elements)
    buffer.seek(0)
    return buffer.getvalue()


# ─────────────────────────────────────────────────────────────────────────────
#  2. AI PREDICTION REPORT
# ─────────────────────────────────────────────────────────────────────────────

def export_predictions_csv(model_type: str = 'LightGBM', generated_by: str = 'Staff Member') -> bytes:
    """CSV: AI prediction report with risk metrics per blood group."""
    import csv
    output = io.StringIO()
    writer = csv.writer(output)

    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    writer.writerow(['HemoPulse AI Pro – AI Prediction Report'])
    writer.writerow([f'Generated: {now}', f'Model: {model_type}', f'Generated By: {generated_by}'])
    writer.writerow([])

    # ── Per-blood-group summary from AI risk engine ──────────────────────────
    writer.writerow(['=== AI RISK SUMMARY (Per Blood Group) ==='])
    writer.writerow([
        'Blood Group', 'Current Stock', 'Predicted Demand (7d)',
        'Expected Remaining', 'Days Until Depletion',
        'AI Risk Score (%)', 'Risk Level', 'Priority Rank',
        'Collection Target', 'Model Used'
    ])

    try:
        risk_data = calculate_global_risk(model_type=model_type)
        blood_groups = risk_data.get('blood_groups', [])
    except Exception as e:
        logger.warning(f'[report_service] AI risk: {e}')
        blood_groups = []

    for bg in blood_groups:
        safety   = bg.get('safety_stock', 0)
        expected = bg.get('expected_remaining', 0)
        try:
            col_target = max(0, safety - int(expected))
        except (TypeError, ValueError):
            col_target = 'N/A'

        writer.writerow([
            bg['blood_group'],
            bg['current_stock'],
            bg['predicted_demand'],
            bg['expected_remaining'],
            bg['depletion_days'],
            bg['risk_score'],
            bg['risk_level'],
            bg['priority'],
            col_target,
            model_type
        ])

    if not blood_groups:
        writer.writerow(['No records available'])

    writer.writerow([])
    writer.writerow(['=== 7-DAY DAILY FORECAST ==='])
    writer.writerow(['Date', 'Blood Group', 'Predicted Demand', 'Lower Bound', 'Upper Bound', 'Model'])

    try:
        fc_df = get_forecast(model_type=model_type)
        if not fc_df.empty:
            for _, row in fc_df.sort_values(['blood_group', 'date']).iterrows():
                d = row['date']
                date_str = d.strftime('%Y-%m-%d') if hasattr(d, 'strftime') else str(d)[:10]
                writer.writerow([
                    date_str, row['blood_group'], row['predicted_demand'],
                    row['lower_bound'], row['upper_bound'], row['model']
                ])
        else:
            writer.writerow(['No forecast data available'])
    except Exception as e:
        writer.writerow([f'Forecast error: {e}'])

    writer.writerow([])
    writer.writerow(['=== MODEL PERFORMANCE METRICS ==='])
    writer.writerow(['Model', 'Blood Group', 'MAE', 'RMSE'])
    try:
        metrics = get_metrics()
        model_key = 'lightgbm' if model_type == 'LightGBM' else 'prophet'
        m = metrics.get(model_key, {})
        overall = m.get('overall', {})
        writer.writerow([model_type, 'Overall', f"{overall.get('mae', 'N/A'):.3f}" if isinstance(overall.get('mae'), float) else 'N/A',
                         f"{overall.get('rmse', 'N/A'):.3f}" if isinstance(overall.get('rmse'), float) else 'N/A'])
        for bg_key, bg_val in m.items():
            if bg_key != 'overall' and isinstance(bg_val, dict):
                mae_v = bg_val.get('mae', 'N/A')
                rmse_v = bg_val.get('rmse', 'N/A')
                writer.writerow([model_type, bg_key,
                                  f'{mae_v:.3f}' if isinstance(mae_v, float) else 'N/A',
                                  f'{rmse_v:.3f}' if isinstance(rmse_v, float) else 'N/A'])
    except Exception as e:
        writer.writerow([f'Metrics error: {e}'])

    return output.getvalue().encode('utf-8')


def export_predictions_pdf(model_type: str = 'LightGBM', generated_by: str = 'Staff Member') -> bytes:
    """PDF: Professional AI prediction report."""
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=landscape(A4),
        topMargin=0.5 * inch, bottomMargin=0.5 * inch,
        leftMargin=0.5 * inch, rightMargin=0.5 * inch
    )
    elements = []
    styles = _build_styles()

    _header_block(elements, styles, 'AI Demand Prediction Report', generated_by, model_type)

    # ── Fetch all data ───────────────────────────────────────────────────────
    try:
        risk_data    = calculate_global_risk(model_type=model_type)
        blood_groups = risk_data.get('blood_groups', [])
        global_stats = risk_data.get('global_stats', {})
        camp_recs    = risk_data.get('camp_recommendations', [])
    except Exception as e:
        logger.warning(f'[report_service] AI risk: {e}')
        blood_groups, global_stats, camp_recs = [], {}, []

    try:
        fc_df = get_forecast(model_type=model_type)
    except Exception as e:
        logger.warning(f'[report_service] Forecast: {e}')
        fc_df = None

    try:
        metrics = get_metrics()
    except Exception as e:
        metrics = {}

    # ── Executive Summary ────────────────────────────────────────────────────
    elements.append(Paragraph('Executive Summary', styles['section']))
    critical = [b for b in blood_groups if b['risk_level'] in ('CRITICAL', 'OUT OF STOCK')]
    high     = [b for b in blood_groups if b['risk_level'] == 'HIGH RISK']
    safe     = [b for b in blood_groups if b['risk_level'] == 'SAFE']

    summary_data = [
        ['Total Blood Groups Assessed', str(len(blood_groups))],
        ['Critical / Out-of-Stock', str(len(critical))],
        ['High Risk',               str(len(high))],
        ['Safe',                    str(len(safe))],
        ['Total Current Stock',     str(global_stats.get('total_current', 'N/A'))],
        ['Total 7-Day Consumption', str(global_stats.get('total_consumed', 'N/A'))],
        ['Total Expected Remaining',str(global_stats.get('total_remaining', 'N/A'))],
        ['Forecast Model Used',     model_type],
    ]
    s_table = Table(summary_data, colWidths=[3 * inch, 2.5 * inch])
    s_table.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('TEXTCOLOR', (0, 0), (0, -1), C_GREY),
        ('ALIGN', (1, 0), (1, -1), 'LEFT'),
        ('ROWBACKGROUNDS', (0, 0), (-1, -1), [colors.white, C_ALT_ROW]),
        ('GRID', (0, 0), (-1, -1), 0.3, C_BORDER),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
    ]))
    elements.append(s_table)
    elements.append(Spacer(1, 14))

    if critical:
        elements.append(Paragraph(
            f'⚠ Critical Alert: {", ".join(b["blood_group"] for b in critical)} – Immediate action required!',
            styles['bold_body']
        ))
        elements.append(Spacer(1, 8))

    # ── Risk Forecast Table (per blood group) ────────────────────────────────
    elements.append(Paragraph('Blood Group Risk Analysis', styles['section']))
    headers = [
        'Blood\nGroup', 'Current\nStock', 'Predicted\nDemand (7d)',
        'Expected\nRemaining', 'Depletion\nDays', 'Risk\nScore',
        'Risk Level', 'Priority', 'Collection\nTarget'
    ]
    col_w = [0.8, 0.8, 1.0, 1.0, 0.8, 0.75, 1.0, 0.7, 1.0]
    col_w = [w * inch for w in col_w]

    fg_table_data = [headers]
    risk_row_colors = []

    for i, bg in enumerate(blood_groups, start=1):
        safety   = bg.get('safety_stock', 0)
        expected = bg.get('expected_remaining', 0)
        try:
            col_target = str(max(0, safety - int(expected)))
        except (TypeError, ValueError):
            col_target = 'N/A'

        fg_table_data.append([
            bg['blood_group'],
            str(bg['current_stock']),
            str(bg['predicted_demand']),
            str(bg['expected_remaining']),
            str(bg['depletion_days']),
            f"{bg['risk_score']}%",
            bg['risk_level'],
            str(bg['priority']),
            col_target
        ])

        rl = bg['risk_level']
        if rl in ('OUT OF STOCK', 'CRITICAL'):
            risk_row_colors.append((i, colors.HexColor('#fee2e2')))
        elif rl == 'HIGH RISK':
            risk_row_colors.append((i, colors.HexColor('#ffedd5')))

    if not blood_groups:
        fg_table_data.append(['No data'] + [''] * (len(headers) - 1))

    risk_table = Table(fg_table_data, colWidths=col_w, repeatRows=1)
    rs_style = _table_style(header_color=C_BLUE)
    for row_idx, bg_color in risk_row_colors:
        rs_style.add('BACKGROUND', (0, row_idx), (-1, row_idx), bg_color)
        rs_style.add('FONTNAME', (0, row_idx), (-1, row_idx), 'Helvetica-Bold')
    risk_table.setStyle(rs_style)
    elements.append(risk_table)
    elements.append(Spacer(1, 14))

    # ── Daily Forecast Table ─────────────────────────────────────────────────
    elements.append(PageBreak())
    _header_block(elements, styles, 'AI Demand Prediction Report – Daily Forecast', generated_by, model_type)
    elements.append(Paragraph('7-Day Daily Demand Forecast', styles['section']))

    fc_headers = ['Date', 'Blood Group', 'Predicted Demand', 'Lower Bound', 'Upper Bound']
    fc_col_w = [1.2, 1.0, 1.2, 1.2, 1.2]
    fc_col_w = [w * inch for w in fc_col_w]
    fc_data = [fc_headers]

    if fc_df is not None and not fc_df.empty:
        for _, row in fc_df.sort_values(['blood_group', 'date']).iterrows():
            d = row['date']
            date_str = d.strftime('%Y-%m-%d') if hasattr(d, 'strftime') else str(d)[:10]
            fc_data.append([
                date_str, row['blood_group'],
                str(int(row['predicted_demand'])),
                str(int(row['lower_bound'])),
                str(int(row['upper_bound']))
            ])
    else:
        fc_data.append(['No forecast data available'] + [''] * (len(fc_headers) - 1))

    fc_table = Table(fc_data, colWidths=fc_col_w, repeatRows=1)
    fc_table.setStyle(_table_style(header_color=C_BLUE))
    elements.append(fc_table)
    elements.append(Spacer(1, 14))

    # ── Camp Recommendations ─────────────────────────────────────────────────
    if camp_recs:
        elements.append(Paragraph('Suggested Donation Camps', styles['section']))
        camp_headers = ['Blood Type', 'Priority', 'Required Yield', 'Target Donors', 'Suggested Date', 'Location', 'Reason']
        camp_col_w = [0.8, 0.8, 0.9, 0.9, 1.0, 1.8, 2.0]
        camp_col_w = [w * inch for w in camp_col_w]
        camp_data = [camp_headers]
        for c in camp_recs:
            camp_data.append([
                c.get('blood_type', ''), c.get('priority', ''),
                str(c.get('required_yield', '')), str(c.get('target_donors', '')),
                c['camp_date'].strftime('%Y-%m-%d') if hasattr(c.get('camp_date'), 'strftime') else str(c.get('camp_date', '')),
                c.get('location', ''), c.get('reason', '')
            ])
        camp_table = Table(camp_data, colWidths=camp_col_w, repeatRows=1)
        camp_table.setStyle(_table_style(header_color=C_ORANGE))
        elements.append(camp_table)
        elements.append(Spacer(1, 14))

    # ── Model Performance ────────────────────────────────────────────────────
    elements.append(Paragraph('AI Model Performance', styles['section']))
    model_key = 'lightgbm' if model_type == 'LightGBM' else 'prophet'
    m = metrics.get(model_key, {}) if metrics else {}
    overall = m.get('overall', {})

    perf_data = [['Metric', 'Overall', 'Note']]
    if overall:
        mae  = overall.get('mae', None)
        rmse = overall.get('rmse', None)
        perf_data.append(['MAE',  f'{mae:.3f}'  if isinstance(mae, float) else 'N/A', 'Mean Absolute Error'])
        perf_data.append(['RMSE', f'{rmse:.3f}' if isinstance(rmse, float) else 'N/A', 'Root Mean Square Error'])
    else:
        perf_data.append(['N/A', 'N/A', 'Metrics file not generated yet. Run model evaluation.'])

    perf_table = Table(perf_data, colWidths=[1.5 * inch, 1.5 * inch, 4 * inch])
    perf_table.setStyle(_table_style(header_color=C_PURPLE))
    elements.append(perf_table)

    # ── Gemini AI Recommendation ─────────────────────────────────────────────
    elements.append(Spacer(1, 14))
    elements.append(Paragraph('Gemini AI Recommendation', styles['section']))
    try:
        latest_log = AIAnalysisLog.query.order_by(AIAnalysisLog.created_at.desc()).first()
        if latest_log:
            rec = latest_log.get_recommendation_dict()
            summary = rec.get('situation_summary', '')
            actions = rec.get('emergency_recommendations', '')
            if summary:
                elements.append(Paragraph(f'<b>Situation:</b> {summary}', styles['body']))
            if actions:
                elements.append(Paragraph(f'<b>Recommended Actions:</b> {actions}', styles['body']))
            elements.append(Paragraph(
                f'<i>Last AI analysis run: {latest_log.created_at.strftime("%Y-%m-%d %H:%M")}, Model: {latest_log.model_used}</i>',
                styles['kv_key']
            ))
        else:
            elements.append(Paragraph('No Gemini AI analysis has been run yet. Trigger analysis from the dashboard.', styles['body']))
    except Exception as e:
        elements.append(Paragraph(f'AI recommendation unavailable: {e}', styles['body']))

    _footer_note(elements, styles)
    doc.build(elements)
    buffer.seek(0)
    return buffer.getvalue()


# ─────────────────────────────────────────────────────────────────────────────
#  3. COMPREHENSIVE MASTER REPORT
# ─────────────────────────────────────────────────────────────────────────────

def export_comprehensive_csv(generated_by: str = 'Staff Member') -> bytes:
    """CSV: Multi-section comprehensive master report."""
    import csv
    output = io.StringIO()
    writer = csv.writer(output)
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    writer.writerow(['HemoPulse AI Pro – Comprehensive Master Report'])
    writer.writerow([f'Generated: {now}', f'Generated By: {generated_by}'])
    writer.writerow([])

    # ── 1. Inventory ─────────────────────────────────────────────────────────
    writer.writerow(['=== SECTION 1: BLOOD INVENTORY ==='])
    writer.writerow([
        'Blood Group', 'Component', 'Current Stock', 'Max Capacity',
        'Safety Stock', 'Status', 'Fill %', 'Last Updated',
        'AI Risk Level', 'Expected Remaining', 'Predicted Demand'
    ])
    try:
        risk_data = calculate_global_risk()
        risk_map  = {bg['blood_group']: bg for bg in risk_data.get('blood_groups', [])}
    except Exception:
        risk_map = {}

    items = BloodInventory.query.order_by(BloodInventory.blood_type, BloodInventory.component).all()
    for item in items:
        ai = risk_map.get(item.blood_type, {})
        writer.writerow([
            item.blood_type, item.component, item.current_units, item.max_capacity,
            item.safety_stock, ai.get('risk_level', 'UNKNOWN'), f"{ai.get('fill_pct', 0)}%",
            item.last_updated.strftime('%Y-%m-%d %H:%M') if item.last_updated else 'N/A',
            ai.get('risk_level', 'UNKNOWN'), ai.get('expected_remaining', 'N/A'), ai.get('predicted_demand', 'N/A')
        ])
    if not items:
        writer.writerow(['No records available'])

    writer.writerow([])

    # ── 2. Pending Blood Requests ────────────────────────────────────────────
    writer.writerow(['=== SECTION 2: PENDING BLOOD REQUESTS ==='])
    writer.writerow(['ID', 'Patient Name', 'Hospital', 'Blood Group', 'Units', 'Priority', 'Status', 'Date'])
    reqs = BloodRequest.query.filter_by(status='pending').order_by(BloodRequest.created_at.desc()).all()
    for r in reqs:
        writer.writerow([
            r.id, r.patient_name, r.hospital_name, r.blood_group,
            r.units_required, r.priority, r.status, r.created_at.strftime('%Y-%m-%d %H:%M')
        ])
    if not reqs:
        writer.writerow(['No pending requests'])
    writer.writerow([])

    # ── 3. Emergency Requests ────────────────────────────────────────────────
    writer.writerow(['=== SECTION 3: EMERGENCY / URGENT REQUESTS ==='])
    writer.writerow(['ID', 'Patient Name', 'Hospital', 'Blood Group', 'Units', 'Priority', 'Status', 'Date'])
    emerg = BloodRequest.query.filter(
        BloodRequest.priority.in_(['urgent', 'critical'])
    ).order_by(BloodRequest.created_at.desc()).limit(50).all()
    for r in emerg:
        writer.writerow([
            r.id, r.patient_name, r.hospital_name, r.blood_group,
            r.units_required, r.priority, r.status, r.created_at.strftime('%Y-%m-%d %H:%M')
        ])
    if not emerg:
        writer.writerow(['No emergency requests'])
    writer.writerow([])

    # ── 4. Recent Donors ─────────────────────────────────────────────────────
    writer.writerow(['=== SECTION 4: RECENT DONORS ==='])
    writer.writerow(['Donor ID', 'Full Name', 'Blood Group', 'Phone', 'Gender', 'Age', 'Eligibility', 'Last Donation', 'Registered'])
    donors = Donor.query.order_by(Donor.created_at.desc()).limit(100).all()
    for d in donors:
        writer.writerow([
            d.donor_id, d.full_name, d.blood_group, d.phone or 'N/A',
            d.gender or 'N/A', d.age or 'N/A', d.eligibility_status,
            d.last_donation_date.strftime('%Y-%m-%d') if d.last_donation_date else 'Never',
            d.created_at.strftime('%Y-%m-%d')
        ])
    if not donors:
        writer.writerow(['No donors registered'])
    writer.writerow([])

    # ── 5. Donation Camps ────────────────────────────────────────────────────
    writer.writerow(['=== SECTION 5: DONATION CAMPS ==='])
    writer.writerow(['Name', 'Location', 'Date', 'Target Blood Group', 'Target Units', 'Collected', 'Progress %', 'Status', 'Priority'])
    camps = DonationCamp.query.order_by(DonationCamp.date.desc()).limit(50).all()
    for c in camps:
        writer.writerow([
            c.name, c.location, c.date.strftime('%Y-%m-%d %H:%M'),
            c.target_blood_group or 'All', c.target_units, c.collected_units,
            f'{c.progress_percentage}%', c.status, c.priority
        ])
    if not camps:
        writer.writerow(['No camps scheduled'])
    writer.writerow([])

    # ── 6. Prediction Results ────────────────────────────────────────────────
    writer.writerow(['=== SECTION 6: AI PREDICTION RESULTS ==='])
    writer.writerow(['Blood Group', 'Predicted Demand (7d)', 'Expected Remaining', 'Risk Level', 'Risk Score', 'Depletion Days', 'Priority'])
    for bg in risk_map.values():
        writer.writerow([
            bg['blood_group'], bg['predicted_demand'], bg['expected_remaining'],
            bg['risk_level'], f"{bg['risk_score']}%", bg['depletion_days'], bg['priority']
        ])
    if not risk_map:
        writer.writerow(['No AI prediction data available'])
    writer.writerow([])

    # ── 7. Critical AI Alerts ────────────────────────────────────────────────
    writer.writerow(['=== SECTION 7: CRITICAL AI ALERTS ==='])
    writer.writerow(['Blood Group', 'Risk Level', 'Expected Remaining', 'Days Until Depletion'])
    critical_groups = [bg for bg in risk_map.values() if bg['risk_level'] in ('CRITICAL', 'OUT OF STOCK')]
    for bg in critical_groups:
        writer.writerow([bg['blood_group'], bg['risk_level'], bg['expected_remaining'], bg['depletion_days']])
    if not critical_groups:
        writer.writerow(['No critical alerts at this time'])
    writer.writerow([])

    # ── 8. Gemini Recommendation ─────────────────────────────────────────────
    writer.writerow(['=== SECTION 8: GEMINI AI RECOMMENDATION ==='])
    try:
        latest_log = AIAnalysisLog.query.order_by(AIAnalysisLog.created_at.desc()).first()
        if latest_log:
            rec = latest_log.get_recommendation_dict()
            writer.writerow(['Blood Group', latest_log.blood_group or 'Global'])
            writer.writerow(['Risk Level', latest_log.risk_level])
            writer.writerow(['Situation Summary', rec.get('situation_summary', 'N/A')])
            writer.writerow(['Emergency Recommendation', rec.get('emergency_recommendations', 'N/A')])
            writer.writerow(['Donation Campaign Suggestions', rec.get('donation_campaign_suggestions', 'N/A')])
            writer.writerow(['Last Updated', latest_log.created_at.strftime('%Y-%m-%d %H:%M')])
        else:
            writer.writerow(['No Gemini AI analysis run yet'])
    except Exception as e:
        writer.writerow([f'Error: {e}'])
    writer.writerow([])

    # ── 9. Audit Logs ────────────────────────────────────────────────────────
    writer.writerow(['=== SECTION 9: RECENT AUDIT LOGS ==='])
    writer.writerow(['ID', 'User', 'Action', 'Description', 'Timestamp'])
    logs = ActivityLog.query.order_by(ActivityLog.created_at.desc()).limit(100).all()
    for log in logs:
        username = log.user.username if log.user else 'System'
        writer.writerow([
            log.id, username, log.action,
            log.description or '', log.created_at.strftime('%Y-%m-%d %H:%M')
        ])
    if not logs:
        writer.writerow(['No audit log entries'])

    return output.getvalue().encode('utf-8')


def export_comprehensive_pdf(generated_by: str = 'Staff Member') -> bytes:
    """PDF: Full multi-page comprehensive master report."""
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=landscape(A4),
        topMargin=0.5 * inch, bottomMargin=0.55 * inch,
        leftMargin=0.5 * inch, rightMargin=0.5 * inch
    )
    elements = []
    styles = _build_styles()
    now = datetime.now()
    now_str = now.strftime('%B %d, %Y  %I:%M %p')

    # Pre-fetch all data once
    try:
        risk_data    = calculate_global_risk()
        blood_groups = risk_data.get('blood_groups', [])
        global_stats = risk_data.get('global_stats', {})
        camp_recs    = risk_data.get('camp_recommendations', [])
        risk_map     = {bg['blood_group']: bg for bg in blood_groups}
    except Exception as e:
        logger.warning(f'[report_service] Risk engine: {e}')
        blood_groups, global_stats, camp_recs, risk_map = [], {}, [], {}

    inv_items  = BloodInventory.query.order_by(BloodInventory.blood_type, BloodInventory.component).all()
    blood_reqs = BloodRequest.query.order_by(BloodRequest.created_at.desc()).limit(50).all()
    emerg_reqs = BloodRequest.query.filter(
        BloodRequest.priority.in_(['urgent', 'critical'])
    ).order_by(BloodRequest.created_at.desc()).limit(30).all()
    donors     = Donor.query.order_by(Donor.created_at.desc()).limit(50).all()
    camps      = DonationCamp.query.order_by(DonationCamp.date.desc()).limit(20).all()
    audit_logs = ActivityLog.query.order_by(ActivityLog.created_at.desc()).limit(50).all()

    try:
        latest_ai_log = AIAnalysisLog.query.order_by(AIAnalysisLog.created_at.desc()).first()
    except Exception:
        latest_ai_log = None

    try:
        metrics   = get_metrics()
    except Exception:
        metrics = {}

    # ══════════════════════════════════════════════════════════════
    #  PAGE 1 – Cover / Executive Summary
    # ══════════════════════════════════════════════════════════════
    _header_block(elements, styles, 'Comprehensive Master Report', generated_by)

    critical_cnt = sum(1 for b in blood_groups if b['risk_level'] in ('CRITICAL', 'OUT OF STOCK'))
    safe_cnt     = sum(1 for b in blood_groups if b['risk_level'] == 'SAFE')
    pending_cnt  = BloodRequest.query.filter_by(status='pending').count()
    total_donors = Donor.query.count()

    exec_data = [
        ['Executive Summary', ''],
        ['Report Date',              now_str],
        ['Generated By',            generated_by],
        ['Total Blood Types Tracked', str(len(blood_groups))],
        ['Critical / Out-of-Stock Groups', str(critical_cnt)],
        ['Safe Groups',              str(safe_cnt)],
        ['Total Current Stock',      str(global_stats.get('total_current', 'N/A'))],
        ['Predicted 7-Day Demand',   str(global_stats.get('total_consumed', 'N/A'))],
        ['Expected Remaining (7d)',  str(global_stats.get('total_remaining', 'N/A'))],
        ['Pending Blood Requests',   str(pending_cnt)],
        ['Total Registered Donors',  str(total_donors)],
        ['Scheduled Donation Camps', str(DonationCamp.query.filter_by(status='planned').count())],
    ]
    exec_table = Table(exec_data, colWidths=[3.5 * inch, 5 * inch])
    exec_table.setStyle(TableStyle([
        ('SPAN',        (0, 0), (-1, 0)),
        ('BACKGROUND',  (0, 0), (-1, 0), C_RED),
        ('TEXTCOLOR',   (0, 0), (-1, 0), colors.white),
        ('FONTNAME',    (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE',    (0, 0), (-1, 0), 11),
        ('ALIGN',       (0, 0), (-1, 0), 'CENTER'),
        ('FONTNAME',    (0, 1), (0, -1), 'Helvetica-Bold'),
        ('FONTSIZE',    (0, 1), (-1, -1), 9),
        ('TEXTCOLOR',   (0, 1), (0, -1), C_GREY),
        ('TEXTCOLOR',   (1, 1), (1, -1), C_DARK),
        ('ALIGN',       (1, 1), (1, -1), 'LEFT'),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, C_ALT_ROW]),
        ('GRID',        (0, 0), (-1, -1), 0.3, C_BORDER),
        ('TOPPADDING',  (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING',(0, 0), (-1, -1), 5),
    ]))
    elements.append(exec_table)

    if critical_cnt > 0:
        crit_names = ', '.join(b['blood_group'] for b in blood_groups if b['risk_level'] in ('CRITICAL', 'OUT OF STOCK'))
        elements.append(Spacer(1, 12))
        elements.append(Paragraph(
            f'⚠ CRITICAL ALERT: {crit_names} blood groups are at critical risk and require immediate intervention.',
            styles['bold_body']
        ))

    # ══════════════════════════════════════════════════════════════
    #  PAGE 2 – Inventory Analysis
    # ══════════════════════════════════════════════════════════════
    elements.append(PageBreak())
    _header_block(elements, styles, 'Inventory Analysis', generated_by)
    elements.append(Paragraph('Blood Inventory Status', styles['section']))

    inv_headers = [
        'Blood\nGroup', 'Component', 'Current\nStock', 'Max\nCapacity',
        'Safety\nStock', 'Fill %', 'Status', 'AI Risk', 'Expected\nRemaining', 'Rec. Collect'
    ]
    inv_col_w = [0.7, 1.0, 0.8, 0.8, 0.75, 0.6, 0.7, 0.85, 0.85, 0.85]
    inv_col_w = [w * inch for w in inv_col_w]
    inv_data_rows = [inv_headers]
    inv_row_colors = []

    for i, item in enumerate(inv_items, start=1):
        ai = risk_map.get(item.blood_type, {})
        expected = ai.get('expected_remaining', 'N/A')
        try:
            rec = str(max(0, item.safety_stock - int(expected)))
        except (TypeError, ValueError):
            rec = 'N/A'
        risk_level = ai.get('risk_level', 'UNKNOWN')
        inv_data_rows.append([
            item.blood_type, item.component, str(item.current_units),
            str(item.max_capacity), str(item.safety_stock),
            f"{ai.get('fill_pct', 0)}%", ai.get('risk_level', 'UNKNOWN'),
            risk_level, str(expected), rec
        ])
        if risk_level in ('OUT OF STOCK', 'CRITICAL'):
            inv_row_colors.append((i, colors.HexColor('#fee2e2')))
        elif risk_level == 'HIGH RISK':
            inv_row_colors.append((i, colors.HexColor('#ffedd5')))

    if not inv_items:
        inv_data_rows.append(['No records available'] + [''] * (len(inv_headers) - 1))

    inv_table = Table(inv_data_rows, colWidths=inv_col_w, repeatRows=1)
    inv_style = _table_style(header_color=C_RED)
    for row_idx, row_color in inv_row_colors:
        inv_style.add('BACKGROUND', (0, row_idx), (-1, row_idx), row_color)
    inv_table.setStyle(inv_style)
    elements.append(inv_table)

    # ══════════════════════════════════════════════════════════════
    #  PAGE 3 – Blood Requests
    # ══════════════════════════════════════════════════════════════
    elements.append(PageBreak())
    _header_block(elements, styles, 'Blood Request Analysis', generated_by)
    elements.append(Paragraph('All Blood Requests (Recent 50)', styles['section']))

    br_headers = ['ID', 'Patient', 'Hospital', 'Blood\nGroup', 'Units', 'Priority', 'Status', 'Date']
    br_col_w   = [0.4, 1.8, 2.0, 0.7, 0.5, 0.75, 0.75, 1.0]
    br_col_w   = [w * inch for w in br_col_w]
    br_data    = [br_headers]

    for r in blood_reqs:
        br_data.append([
            str(r.id), r.patient_name[:22], r.hospital_name[:26],
            r.blood_group, str(r.units_required), r.priority,
            r.status, r.created_at.strftime('%Y-%m-%d')
        ])
    if not blood_reqs:
        br_data.append(['No records available'] + [''] * (len(br_headers) - 1))

    br_table = Table(br_data, colWidths=br_col_w, repeatRows=1)
    br_style = _table_style(header_color=C_GREEN)
    # Color pending rows
    for i, r in enumerate(blood_reqs, start=1):
        if r.status == 'pending' and r.priority in ('urgent', 'critical'):
            br_style.add('BACKGROUND', (0, i), (-1, i), colors.HexColor('#fee2e2'))
    br_table.setStyle(br_style)
    elements.append(br_table)

    # ══════════════════════════════════════════════════════════════
    #  PAGE 4 – Emergency Queue
    # ══════════════════════════════════════════════════════════════
    elements.append(PageBreak())
    _header_block(elements, styles, 'Emergency Request Queue', generated_by)
    elements.append(Paragraph('Urgent & Critical Blood Requests', styles['section']))

    em_headers = ['ID', 'Patient', 'Hospital', 'Blood\nGroup', 'Units', 'Priority', 'Status', 'Date']
    em_col_w   = [0.4, 1.8, 2.0, 0.7, 0.5, 0.75, 0.75, 1.0]
    em_col_w   = [w * inch for w in em_col_w]
    em_data    = [em_headers]

    for r in emerg_reqs:
        em_data.append([
            str(r.id), r.patient_name[:22], r.hospital_name[:26],
            r.blood_group, str(r.units_required), r.priority,
            r.status, r.created_at.strftime('%Y-%m-%d')
        ])
    if not emerg_reqs:
        em_data.append(['No emergency requests'] + [''] * (len(em_headers) - 1))

    em_table = Table(em_data, colWidths=em_col_w, repeatRows=1)
    em_style = _table_style(header_color=C_DARK_RED)
    for i, r in enumerate(emerg_reqs, start=1):
        if r.priority == 'critical':
            em_style.add('BACKGROUND', (0, i), (-1, i), colors.HexColor('#fee2e2'))
            em_style.add('FONTNAME', (0, i), (-1, i), 'Helvetica-Bold')
    em_table.setStyle(em_style)
    elements.append(em_table)

    # ══════════════════════════════════════════════════════════════
    #  PAGE 5 – Donor Statistics
    # ══════════════════════════════════════════════════════════════
    elements.append(PageBreak())
    _header_block(elements, styles, 'Donor Statistics', generated_by)
    elements.append(Paragraph('Registered Donors (Recent 50)', styles['section']))

    dn_headers = ['Donor ID', 'Full Name', 'Blood\nGroup', 'Gender', 'Age', 'Eligibility', 'Last Donation', 'Registered']
    dn_col_w   = [1.0, 2.0, 0.7, 0.65, 0.5, 0.9, 1.1, 1.0]
    dn_col_w   = [w * inch for w in dn_col_w]
    dn_data    = [dn_headers]

    for d in donors:
        dn_data.append([
            d.donor_id, d.full_name[:26], d.blood_group,
            d.gender or '-', str(d.age or '-'), d.eligibility_status,
            d.last_donation_date.strftime('%Y-%m-%d') if d.last_donation_date else 'Never',
            d.created_at.strftime('%Y-%m-%d')
        ])
    if not donors:
        dn_data.append(['No donors registered'] + [''] * (len(dn_headers) - 1))

    dn_table = Table(dn_data, colWidths=dn_col_w, repeatRows=1)
    dn_table.setStyle(_table_style(header_color=C_PURPLE))
    elements.append(dn_table)

    elements.append(Spacer(1, 14))
    elements.append(Paragraph('Donation Camps', styles['section']))

    cp_headers = ['Name', 'Location', 'Date', 'Target\nGroup', 'Target\nUnits', 'Collected', 'Progress', 'Status']
    cp_col_w   = [1.8, 2.0, 1.0, 0.7, 0.7, 0.7, 0.7, 0.8]
    cp_col_w   = [w * inch for w in cp_col_w]
    cp_data    = [cp_headers]

    for c in camps:
        cp_data.append([
            c.name[:24], c.location[:26], c.date.strftime('%Y-%m-%d'),
            c.target_blood_group or 'All', str(c.target_units),
            str(c.collected_units), f'{c.progress_percentage}%', c.status
        ])
    if not camps:
        cp_data.append(['No camps' ] + [''] * (len(cp_headers) - 1))

    cp_table = Table(cp_data, colWidths=cp_col_w, repeatRows=1)
    cp_table.setStyle(_table_style(header_color=C_GREEN))
    elements.append(cp_table)

    # ══════════════════════════════════════════════════════════════
    #  PAGE 6 – AI Prediction
    # ══════════════════════════════════════════════════════════════
    elements.append(PageBreak())
    _header_block(elements, styles, 'AI Prediction Analysis', generated_by)
    elements.append(Paragraph('Blood Group Risk Analysis (7-Day Outlook)', styles['section']))

    pred_headers = [
        'Blood\nGroup', 'Current\nStock', 'Predicted\nDemand', 'Expected\nRemaining',
        'Depletion\nDays', 'Risk Score', 'Risk Level', 'Priority', 'Collection\nTarget'
    ]
    pred_col_w = [0.8, 0.8, 0.9, 0.95, 0.85, 0.8, 0.95, 0.65, 0.9]
    pred_col_w = [w * inch for w in pred_col_w]
    pred_data  = [pred_headers]
    pred_row_colors = []

    for i, bg in enumerate(blood_groups, start=1):
        safety   = bg.get('safety_stock', 0)
        expected = bg.get('expected_remaining', 0)
        try:
            col_target = str(max(0, safety - int(expected)))
        except (TypeError, ValueError):
            col_target = 'N/A'
        pred_data.append([
            bg['blood_group'], str(bg['current_stock']), str(bg['predicted_demand']),
            str(bg['expected_remaining']), str(bg['depletion_days']),
            f"{bg['risk_score']}%", bg['risk_level'], str(bg['priority']), col_target
        ])
        rl = bg['risk_level']
        if rl in ('OUT OF STOCK', 'CRITICAL'):
            pred_row_colors.append((i, colors.HexColor('#fee2e2')))
        elif rl == 'HIGH RISK':
            pred_row_colors.append((i, colors.HexColor('#ffedd5')))

    if not blood_groups:
        pred_data.append(['No prediction data'] + [''] * (len(pred_headers) - 1))

    pred_table = Table(pred_data, colWidths=pred_col_w, repeatRows=1)
    pd_style = _table_style(header_color=C_BLUE)
    for row_idx, row_color in pred_row_colors:
        pd_style.add('BACKGROUND', (0, row_idx), (-1, row_idx), row_color)
        pd_style.add('FONTNAME', (0, row_idx), (-1, row_idx), 'Helvetica-Bold')
    pred_table.setStyle(pd_style)
    elements.append(pred_table)

    # Model performance
    elements.append(Spacer(1, 14))
    elements.append(Paragraph('AI Model Performance (LightGBM)', styles['section']))
    m_lgb = metrics.get('lightgbm', {}) if metrics else {}
    ov = m_lgb.get('overall', {})
    mae  = ov.get('mae', None)
    rmse = ov.get('rmse', None)
    perf_data = [['Metric', 'Value', 'Description']]
    perf_data.append(['MAE',  f'{mae:.3f}'  if isinstance(mae, float)  else 'N/A', 'Mean Absolute Error (lower is better)'])
    perf_data.append(['RMSE', f'{rmse:.3f}' if isinstance(rmse, float) else 'N/A', 'Root Mean Square Error (lower is better)'])
    perf_t = Table(perf_data, colWidths=[1.5 * inch, 1.5 * inch, 5 * inch])
    perf_t.setStyle(_table_style(header_color=C_PURPLE))
    elements.append(perf_t)

    # ══════════════════════════════════════════════════════════════
    #  PAGE 7 – Critical AI Alerts
    # ══════════════════════════════════════════════════════════════
    elements.append(PageBreak())
    _header_block(elements, styles, 'Critical AI Alerts', generated_by)
    elements.append(Paragraph('High-Priority Blood Shortage Alerts', styles['section']))

    critical_groups = [b for b in blood_groups if b['risk_level'] in ('CRITICAL', 'OUT OF STOCK', 'HIGH RISK')]
    if critical_groups:
        al_headers = ['Blood Group', 'Risk Level', 'Current Stock', 'Expected Remaining', 'Days Until Depletion', 'Collection Target', 'Reason']
        al_col_w   = [0.9, 0.9, 0.9, 1.0, 1.0, 1.0, 3.1]
        al_col_w   = [w * inch for w in al_col_w]
        al_data    = [al_headers]

        for bg in critical_groups:
            safety   = bg.get('safety_stock', 0)
            expected = bg.get('expected_remaining', 0)
            try:
                col_target = str(max(0, safety - int(expected)))
            except (TypeError, ValueError):
                col_target = 'N/A'
            rl = bg['risk_level']
            reason = f"AI risk score {bg['risk_score']}%. Depletion in {bg['depletion_days']} days."
            al_data.append([
                bg['blood_group'], rl, str(bg['current_stock']),
                str(expected), str(bg['depletion_days']), col_target, reason
            ])

        al_table = Table(al_data, colWidths=al_col_w, repeatRows=1)
        al_style = _table_style(header_color=C_DARK_RED)
        for i, bg in enumerate(critical_groups, start=1):
            if bg['risk_level'] in ('OUT OF STOCK', 'CRITICAL'):
                al_style.add('BACKGROUND', (0, i), (-1, i), colors.HexColor('#fee2e2'))
                al_style.add('FONTNAME', (0, i), (-1, i), 'Helvetica-Bold')
        al_table.setStyle(al_style)
        elements.append(al_table)
    else:
        elements.append(Paragraph('✓ No critical alerts at this time. All blood groups are within acceptable levels.', styles['body']))

    # ── Camp Recommendations ─────────────────────────────────────
    if camp_recs:
        elements.append(Spacer(1, 14))
        elements.append(Paragraph('Recommended Donation Camps', styles['section']))
        cr_headers = ['Blood Type', 'Priority', 'Required Yield', 'Target Donors', 'Suggested Date', 'Location']
        cr_col_w   = [0.8, 0.8, 1.0, 1.0, 1.0, 4.2]
        cr_col_w   = [w * inch for w in cr_col_w]
        cr_data    = [cr_headers]
        for c in camp_recs:
            cr_data.append([
                c.get('blood_type', ''), c.get('priority', ''),
                str(c.get('required_yield', '')), str(c.get('target_donors', '')),
                c['camp_date'].strftime('%Y-%m-%d') if hasattr(c.get('camp_date'), 'strftime') else '',
                c.get('location', '')
            ])
        cr_table = Table(cr_data, colWidths=cr_col_w, repeatRows=1)
        cr_table.setStyle(_table_style(header_color=C_ORANGE))
        elements.append(cr_table)

    # ══════════════════════════════════════════════════════════════
    #  PAGE 8 – Gemini AI Recommendation
    # ══════════════════════════════════════════════════════════════
    elements.append(PageBreak())
    _header_block(elements, styles, 'Gemini AI Recommendation', generated_by)
    elements.append(Paragraph('AI-Generated Clinical Logistics Recommendation', styles['section']))

    if latest_ai_log:
        rec = latest_ai_log.get_recommendation_dict()
        elements.append(Paragraph(f'<b>Risk Level:</b> {latest_ai_log.risk_level}', styles['body']))
        elements.append(Paragraph(f'<b>Blood Group Focus:</b> {latest_ai_log.blood_group or "Global"}', styles['body']))
        elements.append(Paragraph(f'<b>Model Used:</b> {latest_ai_log.model_used}', styles['body']))
        elements.append(Paragraph(f'<b>Generated:</b> {latest_ai_log.created_at.strftime("%Y-%m-%d %H:%M")}', styles['body']))
        elements.append(Spacer(1, 10))

        for field_key, field_label in [
            ('situation_summary', 'Situation Summary'),
            ('emergency_recommendations', 'Emergency Recommendations'),
            ('donation_campaign_suggestions', 'Donation Campaign Suggestions'),
            ('hospital_coordination_suggestions', 'Hospital Coordination'),
        ]:
            val = rec.get(field_key, '')
            if val:
                elements.append(Paragraph(f'<b>{field_label}</b>', styles['bold_body']))
                elements.append(Paragraph(str(val), styles['body']))
                elements.append(Spacer(1, 8))
    else:
        elements.append(Paragraph(
            'No Gemini AI analysis has been run yet. Navigate to the Admin Dashboard or Staff Alerts to trigger AI analysis.',
            styles['body']
        ))

    # ── Recent Audit Logs ────────────────────────────────────────
    elements.append(Spacer(1, 14))
    elements.append(Paragraph('Recent Audit Logs (Last 50)', styles['section']))

    lg_headers = ['ID', 'User', 'Action', 'Timestamp']
    lg_col_w   = [0.5, 1.5, 5.5, 1.3]
    lg_col_w   = [w * inch for w in lg_col_w]
    lg_data    = [lg_headers]

    for log in audit_logs:
        username = log.user.username if log.user else 'System'
        action_desc = log.action
        if log.description:
            action_desc += f' – {log.description[:60]}'
        lg_data.append([
            str(log.id), username, action_desc[:80], log.created_at.strftime('%Y-%m-%d %H:%M')
        ])
    if not audit_logs:
        lg_data.append(['No logs'] + [''] * (len(lg_headers) - 1))

    lg_table = Table(lg_data, colWidths=lg_col_w, repeatRows=1)
    lg_table.setStyle(_table_style(header_color=C_DARK))
    elements.append(lg_table)

    # ══════════════════════════════════════════════════════════════
    #  PAGE 9 – Conclusion
    # ══════════════════════════════════════════════════════════════
    elements.append(PageBreak())
    _header_block(elements, styles, 'Conclusion & Recommendations', generated_by)
    elements.append(Paragraph('Overall Hospital Blood Bank Status', styles['section']))

    # Inventory health score
    total_inv     = sum(i.current_units for i in inv_items)
    total_max     = sum(i.max_capacity for i in inv_items) or 1
    health_score  = round((total_inv / total_max) * 100, 1)
    overall_status = 'CRITICAL' if critical_cnt > 0 else ('LOW' if len([b for b in blood_groups if b['risk_level'] in ('HIGH RISK', 'LOW')]) > 0 else 'GOOD')

    conc_data = [
        ['Overall System Status',        overall_status],
        ['Inventory Health Score',        f'{health_score}%'],
        ['Total Blood Units Available',   str(global_stats.get('total_current', 'N/A'))],
        ['Predicted Weekly Demand',       str(global_stats.get('total_consumed', 'N/A'))],
        ['Expected Remaining After 7d',   str(global_stats.get('total_remaining', 'N/A'))],
        ['Critical Groups Requiring Action', str(critical_cnt)],
        ['Recommended Collection Camps',  str(len(camp_recs))],
    ]
    conc_table = Table(conc_data, colWidths=[3.5 * inch, 3 * inch])
    conc_style = TableStyle([
        ('FONTNAME',   (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTSIZE',   (0, 0), (-1, -1), 10),
        ('TEXTCOLOR',  (0, 0), (0, -1), C_GREY),
        ('ALIGN',      (1, 0), (1, -1), 'LEFT'),
        ('ROWBACKGROUNDS', (0, 0), (-1, -1), [colors.white, C_ALT_ROW]),
        ('GRID',       (0, 0), (-1, -1), 0.3, C_BORDER),
        ('TOPPADDING', (0, 0), (-1, -1), 7),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 7),
    ])
    # Highlight status
    status_color_map = {'CRITICAL': colors.HexColor('#fee2e2'), 'LOW': colors.HexColor('#ffedd5'), 'GOOD': colors.HexColor('#dcfce7')}
    status_text_color_map = {'CRITICAL': C_RED, 'LOW': C_ORANGE, 'GOOD': C_GREEN}
    conc_style.add('BACKGROUND', (1, 0), (1, 0), status_color_map.get(overall_status, C_ALT_ROW))
    conc_style.add('TEXTCOLOR',  (1, 0), (1, 0), status_text_color_map.get(overall_status, C_DARK))
    conc_style.add('FONTNAME',   (1, 0), (1, 0), 'Helvetica-Bold')
    conc_table.setStyle(conc_style)
    elements.append(conc_table)

    # Final recommendation paragraphs
    elements.append(Spacer(1, 16))
    if critical_cnt > 0:
        crit_names = ', '.join(b['blood_group'] for b in blood_groups if b['risk_level'] in ('CRITICAL', 'OUT OF STOCK'))
        elements.append(Paragraph(
            f'<b>IMMEDIATE ACTION REQUIRED:</b> {crit_names} blood groups have been identified as critically low. '
            f'Organize emergency donation drives and coordinate with affiliated hospitals to source emergency supply within 24-48 hours.',
            styles['body']
        ))
    else:
        elements.append(Paragraph(
            'The blood bank inventory is currently within acceptable operational levels. '
            'Continue scheduled donation camps and monitor daily forecast updates to maintain adequate stock.',
            styles['body']
        ))

    elements.append(Spacer(1, 12))
    elements.append(Paragraph(
        'This report was auto-generated by HemoPulse AI Pro using LightGBM and Prophet forecasting models. '
        'All risk calculations are based on current inventory levels, 7-day demand forecasts, pending blood requests, '
        'and expected incoming donations. Consult qualified medical professionals before making clinical decisions.',
        styles['kv_key']
    ))

    _footer_note(elements, styles)
    doc.build(elements)
    buffer.seek(0)
    return buffer.getvalue()


# ─────────────────────────────────────────────────────────────────────────────
#  Backward-compatibility aliases (do NOT remove – used by admin/routes.py)
# ─────────────────────────────────────────────────────────────────────────────
def export_inventory_csv_legacy():
    """Alias for admin reports route."""
    return export_inventory_csv().decode('utf-8')

def export_predictions_csv_legacy(model_type='LightGBM'):
    """Alias for admin reports route."""
    return export_predictions_csv(model_type).decode('utf-8')

def export_inventory_pdf_legacy():
    """Alias for admin reports route."""
    return export_inventory_pdf()

def export_predictions_pdf_legacy(model_type='LightGBM'):
    """Alias for admin reports route."""
    return export_predictions_pdf(model_type)
