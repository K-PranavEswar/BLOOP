import io
from flask import render_template, redirect, url_for, flash, request, send_file
from flask_login import current_user
from sqlalchemy import or_

from app.extensions import db
from app.admin import admin_bp
from app.models import User, StaffRequest, BloodInventory, DonationCamp, ActivityLog
from app.utils.decorators import admin_required
from app.utils.helpers import log_activity
from app.services.inventory_service import update_stock
from app.services.prediction_service import get_forecast, get_metrics
from app.services.report_service import export_inventory_csv, export_predictions_csv, export_inventory_pdf, export_predictions_pdf
from app.services.ai_risk_engine import calculate_global_risk
from app.services.llm_service import generate_insights
from app.services.notification_service import create_notification

@admin_bp.before_request
@admin_required
def require_admin():
    pass

@admin_bp.route('/dashboard')
def dashboard():
    total_users = User.query.count()
    total_staff = User.query.filter_by(role='staff').count()
    pending_staff = StaffRequest.query.filter_by(status='pending').count()
    
    # Needs BloodRequest model, let's import it here to avoid circular imports if any
    from app.models import BloodRequest
    blood_requests_count = BloodRequest.query.count()
    camp_count = DonationCamp.query.count()
    
    global_risk = calculate_global_risk()
    total_inventory = global_risk['global_stats']['total_current']
    forecast_df = get_forecast()
    
    # Data for charts
    inventory_items = BloodInventory.query.filter_by(component='Whole Blood').all()
    inv_labels = [i.blood_type for i in inventory_items]
    inv_data = [i.current_units for i in inventory_items]
    inv_safety = [i.safety_stock for i in inventory_items]
    
    # AI Engine Data (Fetch latest from DB)
    from app.models.ai_analysis_log import AIAnalysisLog
    latest_log = AIAnalysisLog.query.order_by(AIAnalysisLog.created_at.desc()).first()
    
    advanced_alerts = []
    ai_insights = None
    if latest_log:
        advanced_alerts = latest_log.get_prediction_dict()
        ai_insights = latest_log.get_recommendation_dict()
        # Ensure we pass the scores at top level if needed, or template reads them
        ai_insights['model_used'] = latest_log.model_used
        ai_insights['last_updated'] = latest_log.created_at
    
    req_status_counts = {
        'pending': BloodRequest.query.filter_by(status='pending').count(),
        'approved': BloodRequest.query.filter_by(status='approved').count(),
        'rejected': BloodRequest.query.filter_by(status='rejected').count(),
        'completed': BloodRequest.query.filter_by(status='completed').count()
    }
    
    return render_template('admin/dashboard.html', 
                          total_users=total_users, total_staff=total_staff, 
                          pending_staff=pending_staff, total_inventory=total_inventory,
                          blood_requests_count=blood_requests_count,
                          camp_count=camp_count, global_risk=global_risk,
                          recent_logs=ActivityLog.query.order_by(ActivityLog.created_at.desc()).limit(5).all(),
                          forecast_df=forecast_df,
                          advanced_alerts=advanced_alerts, ai_insights=ai_insights,
                          recent_pending_staff=StaffRequest.query.filter_by(status='pending').order_by(StaffRequest.requested_at.desc()).limit(5).all(),
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
        
    if user.username.lower() == 'admin' or user.role == 'superadmin':
        flash('Cannot delete the default admin account.', 'danger')
        return redirect(url_for('admin.users'))
        
    username = user.username
    
    try:
        from app.models.otp import OTPVerification
        from app.models.notification import Notification
        from app.models.online_session import OnlineSession
        from app.models.activity_log import ActivityLog
        from app.models.staff_request import StaffRequest
        from app.models.donor import Donor
        from app.models.blood_request import BloodRequest
        from app.models.donation_camp import DonationCamp
        
        # 1. Nullify references where the user acted upon other records (nullable columns)
        BloodRequest.query.filter_by(approved_by=user.id).update({'approved_by': None})
        StaffRequest.query.filter_by(reviewed_by=user.id).update({'reviewed_by': None})
        DonationCamp.query.filter_by(created_by=user.id).update({'created_by': None})
        
        # 2. Delete child records where user is the primary owner
        OTPVerification.query.filter_by(user_id=user.id).delete()
        Notification.query.filter_by(user_id=user.id).delete()
        OnlineSession.query.filter_by(user_id=user.id).delete()
        ActivityLog.query.filter_by(user_id=user.id).delete()
        StaffRequest.query.filter_by(user_id=user.id).delete()
        Donor.query.filter_by(user_id=user.id).delete()
        BloodRequest.query.filter_by(user_id=user.id).delete()
        
        # 3. Finally delete the user
        db.session.delete(user)
        db.session.commit()
        
        log_activity(current_user.id, f'Deleted user: {username} and all associated records.')
        flash(f'User {username} successfully deleted.', 'success')
        
    except Exception as e:
        db.session.rollback()
        import traceback
        traceback.print_exc()
        flash(f'Could not delete user. Related records block deletion: {str(e)}', 'danger')
        
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
@admin_required
def predictions():
    model_type = request.args.get('model', 'LightGBM')
    from app.services.prediction_service import get_chart_data, get_metrics
    from app.services.ai_risk_engine import calculate_global_risk
    
    chart_data = get_chart_data(model_type=model_type, past_days=14)
    metrics = get_metrics()
    global_risk = calculate_global_risk(model_type=model_type)
        
    return render_template('admin/predictions.html', model_type=model_type, 
                          chart_data=chart_data, metrics=metrics,
                          global_risk=global_risk, dashboard_metrics=global_risk,
                          blood_groups=['O+', 'O-', 'A+', 'A-', 'B+', 'B-', 'AB+', 'AB-'])

@admin_bp.route('/api/ai-insight')
@admin_required
def api_ai_insight():
    from flask import jsonify
    from app.services.gemini_manager import GeminiManager
    import json
    import traceback
    from app.services.ai_risk_engine import calculate_global_risk
    
    global_risk = calculate_global_risk()
    
    prompt = f"""
    You are an expert AI Health Assistant for a Blood Bank Management System (HemoPulse AI Pro).
    The system has mathematically calculated the following live data for the next 7 days:
    
    Global Stats: {json.dumps(global_risk['global_stats'], indent=2)}
    Critical Group Info: {json.dumps(global_risk['critical_group'], indent=2)}
    Camp Recommendations: {json.dumps(global_risk['camp_recommendations'], indent=2)}
    
    Generate a concise recommendation explaining:
    1. Which blood groups are at risk
    2. Why
    3. What action should be taken
    4. Expected impact if no action is taken
    
    Keep it strictly professional and concise. Use simple HTML formatting (e.g. <strong>, <ul>, <li>) to structure the output so it can be directly injected into a dashboard panel. Do NOT wrap it in ```html markdown blocks. Just output raw HTML.
    """
    
    try:
        manager = GeminiManager()
        response = manager.generate_content(prompt)
        
        if not response:
            response = "<p class='text-danger'>AI processing is temporarily unavailable. Please rely on the mathematical predictions.</p>"
            
        return jsonify({'html': response})
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'html': f"<p class='text-danger'>AI Error: {str(e)}</p>"})

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

@admin_bp.route('/api/live-users')
@admin_required
def api_live_users():
    from datetime import datetime, timedelta
    from flask import jsonify
    from app.models.online_session import OnlineSession
    
    # Online users are those active within the last 5 minutes
    threshold = datetime.utcnow() - timedelta(minutes=5)
    
    # Cleanup expired sessions globally to keep DB clean
    OnlineSession.query.filter(OnlineSession.last_active < threshold).delete()
    db.session.commit()
    
    # Fetch active sessions ordered by most recently active
    active_sessions = OnlineSession.query.order_by(OnlineSession.last_active.desc()).all()
    
    # Group by user to find "Number of Active Sessions" and latest activity
    user_map = {}
    for sess in active_sessions:
        uid = sess.user_id
        if uid not in user_map:
            user_map[uid] = {
                'user': sess.user,
                'sessions': 1,
                'last_active': sess.last_active,
                'login_time': sess.login_time,
                'user_agent': sess.user_agent,
                'ip_address': sess.ip_address
            }
        else:
            user_map[uid]['sessions'] += 1
            # keep the most recent last_active (already sorted descending, so first one is most recent)
            
    users_data = []
    for uid, data in user_map.items():
        u = data['user']
        diff = datetime.utcnow() - data['last_active']
        
        if diff.total_seconds() <= 30:
            last_active_str = "Active Now"
        else:
            mins = int(diff.total_seconds() / 60)
            last_active_str = f"Last Active {mins} mins ago" if mins > 0 else "Last Active <1 min ago"
            
        # Parse user agent for browser
        browser = "Unknown"
        ua = data['user_agent'].lower()
        if 'edg/' in ua or 'edge/' in ua: browser = "Edge"
        elif 'chrome/' in ua: browser = "Chrome"
        elif 'firefox/' in ua: browser = "Firefox"
        elif 'safari/' in ua and 'chrome' not in ua: browser = "Safari"
            
        users_data.append({
            'id': u.id,
            'username': u.username,
            'role': u.role,
            'avatar': u.profile_photo or None,
            'last_active_str': last_active_str,
            'login_time': data['login_time'].strftime('%I:%M %p'),
            'browser': browser,
            'active_sessions': data['sessions']
        })
        
    return jsonify({
        'total': len(users_data),
        'users': users_data
    })
