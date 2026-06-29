import io
from flask import render_template, redirect, url_for, flash, request, send_file
from flask_login import current_user
from sqlalchemy import or_

from app.extensions import db
from app.admin import admin_bp
from app.models import User, StaffRequest, BloodInventory, DonationCamp, ActivityLog
from app.utils.decorators import admin_required
from app.utils.helpers import log_activity
from app.services.inventory_service import get_total_stock, get_low_stock_alerts, update_stock
from app.services.prediction_service import get_forecast, get_metrics, get_shortage_alerts
from app.services.notification_service import create_notification
from app.services.report_service import export_inventory_csv, export_inventory_pdf, export_predictions_csv, export_predictions_pdf

@admin_bp.before_request
@admin_required
def require_admin():
    pass

@admin_bp.route('/dashboard')
def dashboard():
    total_users = User.query.count()
    total_staff = User.query.filter_by(role='staff').count()
    pending_staff = StaffRequest.query.filter_by(status='pending').count()
    total_inventory = get_total_stock()
    
    # Needs BloodRequest model, let's import it here to avoid circular imports if any
    from app.models import BloodRequest
    total_requests = BloodRequest.query.count()
    total_camps = DonationCamp.query.count()
    
    low_stock = get_low_stock_alerts()
    critical_alerts, warning_alerts = get_shortage_alerts()
    
    recent_logs = ActivityLog.query.order_by(ActivityLog.created_at.desc()).limit(10).all()
    
    # Pending staff for quick widget
    recent_pending_staff = StaffRequest.query.filter_by(status='pending').order_by(StaffRequest.requested_at.desc()).limit(5).all()
    
    # Data for charts
    inventory_items = BloodInventory.query.filter_by(component='Whole Blood').all()
    inv_labels = [i.blood_type for i in inventory_items]
    inv_data = [i.current_units for i in inventory_items]
    inv_safety = [i.safety_stock for i in inventory_items]
    
    req_status_counts = {
        'pending': BloodRequest.query.filter_by(status='pending').count(),
        'approved': BloodRequest.query.filter_by(status='approved').count(),
        'rejected': BloodRequest.query.filter_by(status='rejected').count(),
        'completed': BloodRequest.query.filter_by(status='completed').count()
    }
    
    return render_template('admin/dashboard.html', 
                          total_users=total_users, total_staff=total_staff,
                          pending_staff=pending_staff, total_inventory=total_inventory,
                          total_requests=total_requests, total_camps=total_camps,
                          low_stock=low_stock, critical_alerts=critical_alerts,
                          recent_logs=recent_logs, recent_pending_staff=recent_pending_staff,
                          inv_labels=inv_labels, inv_data=inv_data, inv_safety=inv_safety,
                          req_status_counts=req_status_counts)

@admin_bp.route('/users')
def users():
    search = request.args.get('search', '')
    query = User.query
    if search:
        search_term = f"%{search}%"
        query = query.filter(or_(User.username.ilike(search_term), 
                                 User.full_name.ilike(search_term),
                                 User.email.ilike(search_term)))
    users = query.order_by(User.created_at.desc()).all()
    return render_template('admin/users.html', users=users, search=search)

@admin_bp.route('/user/<int:id>/toggle', methods=['POST'])
def toggle_user(id):
    user = User.query.get_or_404(id)
    if user.id == current_user.id:
        flash('Cannot toggle your own status.', 'warning')
        return redirect(url_for('admin.users'))
        
    user.is_active = not user.is_active
    db.session.commit()
    status = 'activated' if user.is_active else 'deactivated'
    log_activity(current_user.id, f'{status.capitalize()} user: {user.username}')
    flash(f'User {user.username} successfully {status}.', 'success')
    return redirect(url_for('admin.users'))

@admin_bp.route('/user/<int:id>/delete', methods=['POST'])
def delete_user(id):
    user = User.query.get_or_404(id)
    if user.id == current_user.id:
        flash('Cannot delete your own account.', 'danger')
        return redirect(url_for('admin.users'))
        
    username = user.username
    db.session.delete(user)
    db.session.commit()
    log_activity(current_user.id, f'Deleted user: {username}')
    flash(f'User {username} successfully deleted.', 'success')
    return redirect(url_for('admin.users'))

@admin_bp.route('/staff-requests')
def staff_requests():
    pending = StaffRequest.query.filter_by(status='pending').order_by(StaffRequest.requested_at.desc()).all()
    approved = StaffRequest.query.filter_by(status='approved').order_by(StaffRequest.reviewed_at.desc()).limit(20).all()
    rejected = StaffRequest.query.filter_by(status='rejected').order_by(StaffRequest.reviewed_at.desc()).limit(20).all()
    return render_template('admin/staff_requests.html', pending=pending, approved=approved, rejected=rejected)

@admin_bp.route('/approve-staff/<int:id>', methods=['POST'])
def approve_staff(id):
    req = StaffRequest.query.get_or_404(id)
    req.status = 'approved'
    req.reviewed_by = current_user.id
    req.reviewed_at = db.func.now()
    
    req.user.role = 'staff'
    db.session.commit()
    
    create_notification(req.user.id, 'Staff Request Approved', 'Your account has been upgraded to Staff.', 'success')
    log_activity(current_user.id, f'Approved staff request for user {req.user.username}')
    flash(f'Approved staff request for {req.user.full_name}.', 'success')
    return redirect(url_for('admin.staff_requests'))

@admin_bp.route('/reject-staff/<int:id>', methods=['POST'])
def reject_staff(id):
    req = StaffRequest.query.get_or_404(id)
    req.status = 'rejected'
    req.reviewed_by = current_user.id
    req.reviewed_at = db.func.now()
    db.session.commit()
    
    create_notification(req.user.id, 'Staff Request Rejected', 'Your staff request was not approved.', 'danger')
    log_activity(current_user.id, f'Rejected staff request for user {req.user.username}')
    flash(f'Rejected staff request for {req.user.full_name}.', 'info')
    return redirect(url_for('admin.staff_requests'))

@admin_bp.route('/inventory')
def inventory():
    items = BloodInventory.query.filter_by(component='Whole Blood').order_by(BloodInventory.blood_type).all()
    all_items = BloodInventory.query.order_by(BloodInventory.blood_type, BloodInventory.component).all()
    return render_template('admin/inventory.html', whole_blood=items, all_items=all_items)

@admin_bp.route('/inventory/update', methods=['POST'])
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
        
    return redirect(url_for('admin.inventory'))

@admin_bp.route('/camps')
def camps():
    all_camps = DonationCamp.query.order_by(DonationCamp.date.desc()).all()
    return render_template('admin/camps.html', camps=all_camps)

@admin_bp.route('/camps/create', methods=['POST'])
def create_camp():
    import datetime
    name = request.form.get('name')
    location = request.form.get('location')
    date_str = request.form.get('date')
    target_blood_group = request.form.get('target_blood_group') or None
    target_units = int(request.form.get('target_units', 50))
    
    try:
        camp_date = datetime.datetime.strptime(date_str, '%Y-%m-%dT%H:%M')
    except ValueError:
        flash('Invalid date format.', 'danger')
        return redirect(url_for('admin.camps'))
        
    camp = DonationCamp(
        name=name, location=location, date=camp_date,
        target_blood_group=target_blood_group, target_units=target_units,
        created_by=current_user.id
    )
    db.session.add(camp)
    db.session.commit()
    
    log_activity(current_user.id, f'Created donation camp: {name}')
    flash('Donation camp created successfully.', 'success')
    return redirect(url_for('admin.camps'))

@admin_bp.route('/camps/<int:id>/update-status', methods=['POST'])
def update_camp_status(id):
    camp = DonationCamp.query.get_or_404(id)
    new_status = request.form.get('status')
    if new_status in ['planned', 'active', 'completed', 'cancelled']:
        camp.status = new_status
        db.session.commit()
        log_activity(current_user.id, f'Updated camp {camp.name} status to {new_status}')
        flash('Camp status updated.', 'success')
    return redirect(url_for('admin.camps'))

@admin_bp.route('/predictions')
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
            
    return render_template('admin/predictions.html', model_type=model_type, 
                          chart_data=chart_data, metrics=metrics,
                          blood_groups=list(chart_data.keys()))

@admin_bp.route('/audit-logs')
def audit_logs():
    page = request.args.get('page', 1, type=int)
    search = request.args.get('search', '')
    
    query = ActivityLog.query.join(User, isouter=True)
    if search:
        query = query.filter(or_(ActivityLog.action.ilike(f"%{search}%"),
                                 User.username.ilike(f"%{search}%")))
                                 
    pagination = query.order_by(ActivityLog.created_at.desc()).paginate(page=page, per_page=20)
    return render_template('admin/audit_logs.html', pagination=pagination, search=search)

@admin_bp.route('/export/<type>/<format>')
def export(type, format):
    if type == 'inventory':
        if format == 'csv':
            csv_data = export_inventory_csv()
            return send_file(io.BytesIO(csv_data.encode('utf-8')), mimetype='text/csv', as_attachment=True, download_name='inventory_report.csv')
        elif format == 'pdf':
            pdf_data = export_inventory_pdf()
            return send_file(io.BytesIO(pdf_data), mimetype='application/pdf', as_attachment=True, download_name='inventory_report.pdf')
    elif type == 'predictions':
        model_type = request.args.get('model', 'LightGBM')
        if format == 'csv':
            csv_data = export_predictions_csv(model_type)
            return send_file(io.BytesIO(csv_data.encode('utf-8')), mimetype='text/csv', as_attachment=True, download_name=f'predictions_{model_type}.csv')
        elif format == 'pdf':
            pdf_data = export_predictions_pdf(model_type)
            return send_file(io.BytesIO(pdf_data), mimetype='application/pdf', as_attachment=True, download_name=f'predictions_{model_type}.pdf')
            
    flash('Invalid export request.', 'danger')
    return redirect(url_for('admin.dashboard'))
