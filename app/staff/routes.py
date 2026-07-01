import datetime
from flask import render_template, redirect, url_for, flash, request
from flask_login import current_user

from app.extensions import db
from app.staff import staff_bp
from app.models import BloodInventory, BloodRequest, Donor, DonationCamp, DonationHistory
from app.utils.decorators import staff_required
from app.utils.helpers import log_activity
from app.services.inventory_service import get_inventory_summary, update_stock
from app.services.prediction_service import get_forecast, get_metrics
from app.services.donor_service import register_donor, record_donation
from app.services.notification_service import create_notification
from app.services.ai_risk_engine import calculate_global_risk
from app.services.llm_service import generate_insights
from app.services.report_service import (
    export_inventory_csv, export_inventory_pdf,
    export_predictions_csv, export_predictions_pdf,
    export_comprehensive_csv, export_comprehensive_pdf,
)
import io
from flask import send_file

@staff_bp.before_request
@staff_required
def require_staff():
    pass

@staff_bp.route('/dashboard')
def dashboard():
    global_risk = calculate_global_risk()
    total_inventory = global_risk['global_stats']['total_current']
    
    pending_requests = BloodRequest.query.filter_by(status='pending').count()
    recent_requests = BloodRequest.query.filter_by(status='pending').order_by(BloodRequest.created_at.desc()).limit(5).all()
    upcoming_camps = DonationCamp.query.filter(DonationCamp.date > datetime.datetime.utcnow(), DonationCamp.status == 'planned').count()
    
    # AI Engine Data (Fetch latest from DB)
    from app.models.ai_analysis_log import AIAnalysisLog
    latest_log = AIAnalysisLog.query.order_by(AIAnalysisLog.created_at.desc()).first()
    
    advanced_alerts = []
    ai_insights = None
    if latest_log:
        advanced_alerts = latest_log.get_prediction_dict()
        ai_insights = latest_log.get_recommendation_dict()
        ai_insights['model_used'] = latest_log.model_used
        ai_insights['last_updated'] = latest_log.created_at
    
    return render_template('staff/dashboard.html', 
                          total_inventory=total_inventory,
                          global_risk=global_risk,
                          pending_requests_count=pending_requests,
                          recent_requests=recent_requests, upcoming_camps=upcoming_camps,
                          advanced_alerts=advanced_alerts, ai_insights=ai_insights)

@staff_bp.route('/inventory')
def inventory():
    items = BloodInventory.query.filter_by(component='Whole Blood').order_by(BloodInventory.blood_type).all()
    all_items = BloodInventory.query.order_by(BloodInventory.last_updated.desc()).limit(20).all()
    return render_template('staff/inventory.html', whole_blood=items, recent_transactions=all_items)

@staff_bp.route('/inventory/update', methods=['POST'])
def update_inventory():
    blood_type = request.form.get('blood_type')
    component = request.form.get('component', 'Whole Blood')
    units = int(request.form.get('units', 0))
    transaction_type = request.form.get('transaction_type')
    
    success, msg = update_stock(blood_type, component, units, transaction_type, current_user.id)
    if success:
        flash(msg, 'success')
    else:
        flash(msg, 'danger')
        
    return redirect(url_for('staff.inventory'))

@staff_bp.route('/blood-requests')
def blood_requests():
    status = request.args.get('status', 'all')
    query = BloodRequest.query
    if status != 'all':
        query = query.filter_by(status=status)
    requests = query.order_by(BloodRequest.created_at.desc()).all()
    return render_template('staff/blood_requests.html', requests=requests, current_filter=status)

@staff_bp.route('/blood-requests/<int:id>/approve', methods=['POST'])
def approve_request(id):
    req = BloodRequest.query.get_or_404(id)
    
    # Try to auto-issue stock for Whole Blood (assuming 1 unit = 1 unit)
    success, msg = update_stock(req.blood_group, 'Whole Blood', req.units_required, 'issue', current_user.id)
    
    if success:
        req.status = 'approved'
        req.approved_by = current_user.id
        db.session.commit()
        
        create_notification(req.user_id, 'Blood Request Approved', 
                           f'Your request for {req.units_required} units of {req.blood_group} has been approved.', 
                           'success')
        log_activity(current_user.id, f'Approved blood request #{req.id} and issued {req.units_required} units of {req.blood_group}')
        flash('Request approved and stock issued successfully.', 'success')
        
        # Trigger AI analysis in background
        from flask import current_app
        from app.services.llm_service import run_and_log_analysis_async
        try:
            app = current_app._get_current_object()
            run_and_log_analysis_async(app.app_context)
        except Exception as e:
            print(f"Failed to trigger AI analysis: {e}")
    else:
        flash(f'Cannot approve request: {msg}', 'danger')
        
    return redirect(url_for('staff.blood_requests'))

@staff_bp.route('/blood-requests/<int:id>/reject', methods=['POST'])
def reject_request(id):
    req = BloodRequest.query.get_or_404(id)
    req.status = 'rejected'
    db.session.commit()
    
    create_notification(req.user_id, 'Blood Request Rejected', 
                       f'Unfortunately, your request for {req.blood_group} could not be fulfilled at this time.', 
                       'danger')
    log_activity(current_user.id, f'Rejected blood request #{req.id}')
    flash('Request rejected.', 'info')
    return redirect(url_for('staff.blood_requests'))

@staff_bp.route('/blood-requests/<int:id>/complete', methods=['POST'])
def complete_request(id):
    req = BloodRequest.query.get_or_404(id)
    req.status = 'completed'
    db.session.commit()
    log_activity(current_user.id, f'Completed blood request #{req.id}')
    flash('Request marked as completed.', 'success')
    return redirect(url_for('staff.blood_requests'))

@staff_bp.route('/donors', methods=['GET', 'POST'])
def donors():
    if request.method == 'POST':
        full_name = request.form.get('full_name')
        blood_group = request.form.get('blood_group')
        phone = request.form.get('phone')
        email = request.form.get('email')
        weight = float(request.form.get('weight', 0))
        gender = request.form.get('gender')
        age = int(request.form.get('age', 0))
        district = request.form.get('district')
        
        donor = register_donor(None, full_name, blood_group, phone, email, weight, gender, age, district)
        log_activity(current_user.id, f'Registered walk-in donor: {donor.donor_id}')
        flash(f'Donor registered successfully. ID: {donor.donor_id}', 'success')
        return redirect(url_for('staff.donors'))
        
    search = request.args.get('search', '')
    if search:
        donor_list = Donor.query.filter(Donor.full_name.ilike(f"%{search}%") | Donor.donor_id.ilike(f"%{search}%")).all()
    else:
        donor_list = Donor.query.order_by(Donor.created_at.desc()).limit(50).all()
        
    return render_template('staff/donors.html', donors=donor_list, search=search)

@staff_bp.route('/donors/<int:id>')
def view_donor(id):
    donor = Donor.query.get_or_404(id)
    history = DonationHistory.query.filter_by(donor_id=donor.id).order_by(DonationHistory.donation_date.desc()).all()
    return render_template('staff/donor_detail.html', donor=donor, history=history)

@staff_bp.route('/donors/<int:id>/record-donation', methods=['POST'])
def record_donor_donation(id):
    units = int(request.form.get('units', 1))
    location = request.form.get('location', 'In-House')
    camp_id_str = request.form.get('camp_id')
    camp_id = int(camp_id_str) if camp_id_str else None
    
    donor = Donor.query.get_or_404(id)
    donation, msg = record_donation(donor.id, donor.blood_group, units, camp_id, location)
    
    if donation:
        # Also add to inventory
        update_stock(donor.blood_group, 'Whole Blood', units, 'receive', current_user.id)
        
        if camp_id:
            camp = DonationCamp.query.get(camp_id)
            if camp:
                camp.collected_units += units
                db.session.commit()
                
        flash('Donation recorded and inventory updated successfully.', 'success')
    else:
        flash(f'Error: {msg}', 'danger')
        
    return redirect(url_for('staff.donors'))

@staff_bp.route('/camps', methods=['GET'])
def camps():
    all_camps = DonationCamp.query.order_by(DonationCamp.date.desc()).all()
    return render_template('staff/camps.html', camps=all_camps)

@staff_bp.route('/camps/create', methods=['POST'])
def create_camp():
    name = request.form.get('name')
    location = request.form.get('location')
    date_str = request.form.get('date')
    target_blood_group = request.form.get('target_blood_group') or None
    target_units = int(request.form.get('target_units', 50))
    
    try:
        camp_date = datetime.datetime.strptime(date_str, '%Y-%m-%dT%H:%M')
    except ValueError:
        flash('Invalid date format.', 'danger')
        return redirect(url_for('staff.camps'))
        
    camp = DonationCamp(
        name=name, location=location, date=camp_date,
        target_blood_group=target_blood_group, target_units=target_units,
        created_by=current_user.id
    )
    db.session.add(camp)
    db.session.commit()
    
    log_activity(current_user.id, f'Created donation camp: {name}')
    flash('Donation camp created successfully.', 'success')
    return redirect(url_for('staff.camps'))

@staff_bp.route('/alerts')
def alerts():
    global_risk = calculate_global_risk()
    return render_template('staff/alerts.html', global_risk=global_risk)

@staff_bp.route('/api/ai-insight')
@staff_required
def api_ai_insight():
    from flask import jsonify
    from app.services.gemini_manager import GeminiManager
    import json
    
    global_risk = calculate_global_risk()
    
    if not global_risk.get('critical_group'):
        return jsonify({'html': "<p class='text-success'><i class='fas fa-check-circle me-2'></i>All blood groups are currently operating within safe margins. No emergency AI intervention required.</p>"})
        
    prompt = f"""
    You are an expert AI Health Assistant for a Blood Bank Management System (HemoPulse AI Pro).
    The system has mathematically calculated a critical blood shortage risk for: {global_risk['critical_group']['blood_group']}
    
    Details:
    - Current Stock: {global_risk['critical_group']['current_stock']}
    - Expected Donations: {global_risk['critical_group']['expected_donations']}
    - Pending Requests: {global_risk['critical_group']['pending_requests']}
    - Predicted 7-Day Demand: {global_risk['critical_group']['predicted_demand']}
    - Expected Remaining: {global_risk['critical_group']['expected_remaining']}
    - Depletion Days: {global_risk['critical_group']['depletion_days']}
    - Risk Level: {global_risk['critical_group']['risk_level']}
    
    Generate a highly urgent, human-readable recommendation (like a hospital clinical alert) explaining:
    1. The exact shortage situation.
    2. Recommended action (e.g. immediate donation drive, target units).
    
    Keep it strictly professional and concise. Use simple HTML formatting (e.g. <strong>, <ul>, <li>) for the dashboard. Do NOT wrap it in ```html markdown blocks. Just output raw HTML.
    """
    
    try:
        manager = GeminiManager()
        response = manager.generate_content(prompt)
        
        if not response:
            # Rule-based fallback if Gemini is blank
            cg = global_risk['critical_group']
            response = f"<p class='text-danger'><strong>AI Alert Fallback:</strong> {cg['blood_group']} is at {cg['risk_level']} risk! Stock will deplete in {cg['depletion_days']} days. Deficit is {abs(cg['expected_remaining'])} units.</p>"
            
        return jsonify({'html': response})
    except Exception as e:
        import traceback
        traceback.print_exc()
        cg = global_risk['critical_group']
        fallback = f"<p class='text-danger'><strong>Rule-Based AI Alert:</strong> {cg['blood_group']} is at {cg['risk_level']} risk! Stock will deplete in {cg['depletion_days']} days. Expected Remaining: {cg['expected_remaining']} units. Immediate action required.</p>"
        return jsonify({'html': fallback})

@staff_bp.route('/predictions')
def predictions():
    model_type = request.args.get('model', 'LightGBM')
    from app.services.prediction_service import get_chart_data, get_metrics
    chart_data = get_chart_data(model_type=model_type, past_days=14)
    metrics = get_metrics()
        
    return render_template('staff/predictions.html', model_type=model_type, 
                          chart_data=chart_data, metrics=metrics, 
                          blood_groups=['O+', 'O-', 'A+', 'A-', 'B+', 'B-', 'AB+', 'AB-'])

@staff_bp.route('/reports')
def reports():
    """Staff Reports landing page – renders the reports UI."""
    from app.services.ai_risk_engine import calculate_global_risk
    try:
        risk_data = calculate_global_risk()
        summary = risk_data.get('global_stats', {})
        critical_count = sum(
            1 for b in risk_data.get('blood_groups', [])
            if b['risk_level'] in ('CRITICAL', 'OUT OF STOCK')
        )
    except Exception:
        summary = {}
        critical_count = 0
    return render_template('staff/reports.html', summary=summary, critical_count=critical_count)


@staff_bp.route('/reports/inventory/csv')
def report_inventory_csv():
    """Generate and download the Inventory CSV report."""
    import logging
    log = logging.getLogger(__name__)
    try:
        generated_by = current_user.full_name if current_user.is_authenticated else 'Staff'
        data = export_inventory_csv(generated_by=generated_by)
        fname = datetime.datetime.now().strftime('Inventory_Report_%Y%m%d_%H%M%S.csv')
        log_activity(current_user.id, f'Downloaded Inventory CSV Report: {fname}')
        return send_file(
            io.BytesIO(data), mimetype='text/csv',
            as_attachment=True, download_name=fname
        )
    except Exception as e:
        log.exception('Inventory CSV generation failed')
        flash(f'Failed to generate Inventory CSV: {e}', 'danger')
        return redirect(url_for('staff.reports'))


@staff_bp.route('/reports/inventory/pdf')
def report_inventory_pdf():
    """Generate and download the Inventory PDF report."""
    import logging
    log = logging.getLogger(__name__)
    try:
        generated_by = current_user.full_name if current_user.is_authenticated else 'Staff'
        data = export_inventory_pdf(generated_by=generated_by)
        fname = datetime.datetime.now().strftime('Inventory_Report_%Y%m%d_%H%M%S.pdf')
        log_activity(current_user.id, f'Downloaded Inventory PDF Report: {fname}')
        return send_file(
            io.BytesIO(data), mimetype='application/pdf',
            as_attachment=True, download_name=fname
        )
    except Exception as e:
        log.exception('Inventory PDF generation failed')
        flash(f'Failed to generate Inventory PDF: {e}', 'danger')
        return redirect(url_for('staff.reports'))


@staff_bp.route('/reports/prediction/csv')
def report_prediction_csv():
    """Generate and download the AI Prediction CSV report."""
    import logging
    log = logging.getLogger(__name__)
    model_type = request.args.get('model', 'LightGBM')
    try:
        generated_by = current_user.full_name if current_user.is_authenticated else 'Staff'
        data = export_predictions_csv(model_type=model_type, generated_by=generated_by)
        fname = datetime.datetime.now().strftime('Prediction_Report_%Y%m%d_%H%M%S.csv')
        log_activity(current_user.id, f'Downloaded Prediction CSV Report ({model_type}): {fname}')
        return send_file(
            io.BytesIO(data), mimetype='text/csv',
            as_attachment=True, download_name=fname
        )
    except Exception as e:
        log.exception('Prediction CSV generation failed')
        flash(f'Failed to generate Prediction CSV: {e}', 'danger')
        return redirect(url_for('staff.reports'))


@staff_bp.route('/reports/prediction/pdf')
def report_prediction_pdf():
    """Generate and download the AI Prediction PDF report."""
    import logging
    log = logging.getLogger(__name__)
    model_type = request.args.get('model', 'LightGBM')
    try:
        generated_by = current_user.full_name if current_user.is_authenticated else 'Staff'
        data = export_predictions_pdf(model_type=model_type, generated_by=generated_by)
        fname = datetime.datetime.now().strftime('Prediction_Report_%Y%m%d_%H%M%S.pdf')
        log_activity(current_user.id, f'Downloaded Prediction PDF Report ({model_type}): {fname}')
        return send_file(
            io.BytesIO(data), mimetype='application/pdf',
            as_attachment=True, download_name=fname
        )
    except Exception as e:
        log.exception('Prediction PDF generation failed')
        flash(f'Failed to generate Prediction PDF: {e}', 'danger')
        return redirect(url_for('staff.reports'))


@staff_bp.route('/reports/master/csv')
def report_master_csv():
    """Generate and download the Comprehensive Master CSV report."""
    import logging
    log = logging.getLogger(__name__)
    try:
        generated_by = current_user.full_name if current_user.is_authenticated else 'Staff'
        data = export_comprehensive_csv(generated_by=generated_by)
        fname = datetime.datetime.now().strftime('Master_Report_%Y%m%d_%H%M%S.csv')
        log_activity(current_user.id, f'Downloaded Master CSV Report: {fname}')
        return send_file(
            io.BytesIO(data), mimetype='text/csv',
            as_attachment=True, download_name=fname
        )
    except Exception as e:
        log.exception('Master CSV generation failed')
        flash(f'Failed to generate Master CSV: {e}', 'danger')
        return redirect(url_for('staff.reports'))


@staff_bp.route('/reports/master/pdf')
def report_master_pdf():
    """Generate and download the Comprehensive Master PDF report."""
    import logging
    log = logging.getLogger(__name__)
    try:
        generated_by = current_user.full_name if current_user.is_authenticated else 'Staff'
        data = export_comprehensive_pdf(generated_by=generated_by)
        fname = datetime.datetime.now().strftime('Master_Report_%Y%m%d_%H%M%S.pdf')
        log_activity(current_user.id, f'Downloaded Master PDF Report: {fname}')
        return send_file(
            io.BytesIO(data), mimetype='application/pdf',
            as_attachment=True, download_name=fname
        )
    except Exception as e:
        log.exception('Master PDF generation failed')
        flash(f'Failed to generate Master PDF: {e}', 'danger')
        return redirect(url_for('staff.reports'))


# ── Legacy export route (kept for backward compatibility) ────────────────────
@staff_bp.route('/export/<type>/<format>')
def export(type, format):
    """Legacy export endpoint – proxies to new named routes."""
    if type == 'comprehensive':
        if format == 'csv':
            return redirect(url_for('staff.report_master_csv'))
        elif format == 'pdf':
            return redirect(url_for('staff.report_master_pdf'))
    flash('Invalid export request.', 'danger')
    return redirect(url_for('staff.reports'))

@staff_bp.route('/emergency')
def emergency():
    urgent_requests = BloodRequest.query.filter(
        BloodRequest.status == 'pending',
        BloodRequest.priority.in_(['urgent', 'critical'])
    ).order_by(BloodRequest.created_at.desc()).all()
    return render_template('staff/emergency.html', requests=urgent_requests)
