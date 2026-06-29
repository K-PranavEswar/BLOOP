"""
Report service – CSV and PDF export.
"""
import io
import csv
from datetime import datetime
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

from app.models.blood_inventory import BloodInventory
from app.services.prediction_service import get_forecast, get_metrics


def export_inventory_csv():
    """Export blood inventory as CSV string."""
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['Blood Type', 'Component', 'Current Units', 'Max Capacity', 'Safety Stock', 'Status', 'Fill %'])

    items = BloodInventory.query.order_by(BloodInventory.blood_type).all()
    for item in items:
        writer.writerow([
            item.blood_type, item.component, item.current_units,
            item.max_capacity, item.safety_stock, item.status, f'{item.fill_percentage}%'
        ])

    return output.getvalue()


def export_predictions_csv(model_type='LightGBM'):
    """Export prediction forecast as CSV string."""
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['Date', 'Blood Type', 'Predicted Demand', 'Lower Bound', 'Upper Bound', 'Model'])

    fc_df = get_forecast(model_type=model_type)
    if not fc_df.empty:
        for _, row in fc_df.iterrows():
            writer.writerow([
                row['date'], row['blood_type'], row['predicted_demand'],
                row['lower_bound'], row['upper_bound'], row['model']
            ])

    return output.getvalue()


def export_inventory_pdf():
    """Export blood inventory as PDF bytes."""
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=landscape(A4), topMargin=0.5*inch, bottomMargin=0.5*inch)
    elements = []
    styles = getSampleStyleSheet()

    # Title
    title_style = ParagraphStyle('CustomTitle', parent=styles['Title'], fontSize=18, textColor=colors.HexColor('#dc2626'))
    elements.append(Paragraph('🩸 HemoPulse AI – Blood Inventory Report', title_style))
    elements.append(Spacer(1, 12))
    elements.append(Paragraph(f'Generated: {datetime.utcnow().strftime("%B %d, %Y %I:%M %p")}', styles['Normal']))
    elements.append(Spacer(1, 24))

    # Table data
    data = [['Blood Type', 'Component', 'Current Units', 'Max Capacity', 'Safety Stock', 'Status', 'Fill %']]
    items = BloodInventory.query.order_by(BloodInventory.blood_type).all()
    for item in items:
        data.append([
            item.blood_type, item.component, str(item.current_units),
            str(item.max_capacity), str(item.safety_stock), item.status, f'{item.fill_percentage}%'
        ])

    table = Table(data, repeatRows=1)
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#dc2626')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 10),
        ('FONTSIZE', (0, 1), (-1, -1), 9),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#f8f9fa')),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#dee2e6')),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f1f3f5')]),
    ]))
    elements.append(table)
    doc.build(elements)
    buffer.seek(0)
    return buffer.getvalue()


def export_predictions_pdf(model_type='LightGBM'):
    """Export prediction forecast as PDF bytes."""
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=landscape(A4), topMargin=0.5*inch, bottomMargin=0.5*inch)
    elements = []
    styles = getSampleStyleSheet()

    title_style = ParagraphStyle('CustomTitle', parent=styles['Title'], fontSize=18, textColor=colors.HexColor('#dc2626'))
    elements.append(Paragraph(f'🩸 HemoPulse AI – {model_type} Forecast Report', title_style))
    elements.append(Spacer(1, 12))
    elements.append(Paragraph(f'Generated: {datetime.utcnow().strftime("%B %d, %Y %I:%M %p")}', styles['Normal']))
    elements.append(Spacer(1, 24))

    # Metrics
    metrics = get_metrics()
    if metrics:
        model_key = 'lightgbm' if model_type == 'LightGBM' else 'prophet'
        m = metrics.get(model_key, {})
        overall = m.get('overall', {})
        if overall:
            elements.append(Paragraph(
                f"Overall MAE: {overall.get('mae', 'N/A'):.3f} | Overall RMSE: {overall.get('rmse', 'N/A'):.3f}",
                styles['Normal']))
            elements.append(Spacer(1, 16))

    # Forecast table
    data = [['Date', 'Blood Type', 'Predicted Demand', 'Lower Bound', 'Upper Bound']]
    fc_df = get_forecast(model_type=model_type)
    if not fc_df.empty:
        for _, row in fc_df.iterrows():
            date_str = row['date'].strftime('%Y-%m-%d') if hasattr(row['date'], 'strftime') else str(row['date'])[:10]
            data.append([date_str, row['blood_type'], str(row['predicted_demand']),
                        str(row['lower_bound']), str(row['upper_bound'])])

    table = Table(data, repeatRows=1)
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#dc2626')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 10),
        ('FONTSIZE', (0, 1), (-1, -1), 9),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#dee2e6')),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f1f3f5')]),
    ]))
    elements.append(table)
    doc.build(elements)
    buffer.seek(0)
    return buffer.getvalue()
