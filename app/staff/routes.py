import datetime
from flask import render_template, redirect, url_for, flash, request
from flask_login import current_user

from app.extensions import db
from app.staff import staff_bp
from app.models import BloodInventory, BloodRequest, Donor, DonationCamp, DonationHistory
from app.utils.decorators import staff_required
from app.utils.helpers import log_activity
from app.services.inventory_service import get_inventory_summary, update_stock, get_low_stock_alerts
from app.services.prediction_service import get_shortage_alerts, get_camp_recommendations, get_forecast, get_metrics
from app.services.donor_service import register_donor, record_donation
from app.services.notification_service import create_notification

@staff_bp.before_request
@staff_required
def require_staff():
    pass

@staff_bp.route('/dashboard')
def dashboard():
    inventory_summary = get_inventory_summary()
    low_stock = get_low_stock_alerts()
    critical_alerts, warning_alerts = get_shortage_alerts()
    pending_requests = BloodRequest.query.filter_by(status='pending').count()
    recent_requests = BloodRequest.query.filter_by(status='pending').order_by(BloodRequest.created_at.desc()).limit(5).all()
    upcoming_camps = DonationCamp.query.filter(DonationCamp.date > datetime.datetime.utcnow(), DonationCamp.status == 'planned').count()
    
    total_inventory = sum(item['current_units'] for item in inventory_summary)
    
    return render_template('staff/dashboard.html', 
                          inventory_summary=inventory_summary, total_inventory=total_inventory,
                          low_stock=low_stock, critical_alerts=critical_alerts,
                          pending_requests_count=pending_requests,
                          recent_requests=recent_requests, upcoming_camps=upcoming_camps)

@staff_bp.route('/inventory')
def inventory():
    items = BloodInventory.query.filter_by(component='Whole Blood').order_by(BloodInventory.blood_type).all()
    all_items = BloodInventory.query.order_by(BloodInventory.last_updated.desc()).limit(20).all() # Just to show some log
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
    low_stock = get_low_stock_alerts()
    critical_alerts, warning_alerts = get_shortage_alerts()
    camp_recommendations = get_camp_recommendations()
    
    return render_template('staff/alerts.html', 
                          low_stock=low_stock, 
                          critical_alerts=critical_alerts, 
                          warning_alerts=warning_alerts,
                          camp_recommendations=camp_recommendations)

@staff_bp.route('/predictions')
def predictions():
    model_type = request.args.get('model', 'LightGBM')
    forecast_df = get_forecast(model_type=model_type)
    metrics = get_metrics()
    
    chart_data = {}
    if not forecast_df.empty:
        for bt in forecast_df['blood_type'].unique():
            bt_data = forecast_df[forecast_df['blood_type'] == bt].sort_values('date')
            dates = [d.strftime('%Y-%m-%d') for d in bt_data['date']]
            demands = bt_data['predicted_demand'].tolist()
            chart_data[bt] = {'dates': dates, 'demands': demands}
            
    return render_template('staff/predictions.html', model_type=model_type, 
                          chart_data=chart_data, metrics=metrics,
                          blood_groups=list(chart_data.keys()))

@staff_bp.route('/reports')
def reports():
    return render_template('staff/reports.html')

@staff_bp.route('/emergency')
def emergency():
    urgent_requests = BloodRequest.query.filter(
        BloodRequest.status == 'pending',
        BloodRequest.priority.in_(['urgent', 'critical'])
    ).order_by(BloodRequest.created_at.desc()).all()
    return render_template('staff/emergency.html', requests=urgent_requests)
