import os
import datetime
from flask import render_template, redirect, url_for, flash, request, current_app
from flask_login import current_user, login_required
from werkzeug.utils import secure_filename

from app.extensions import db, bcrypt
from app.public import public_bp
from app.models import BloodInventory, BloodRequest, Donor, DonationCamp, Notification, DonationHistory, User
from app.utils.decorators import verified_required
from app.utils.helpers import log_activity, save_uploaded_file, validate_password_strength
from app.services.donor_service import register_donor
from app.services.inventory_service import get_all_inventory
from app.services.notification_service import mark_all_read, mark_as_read, notify_staff
from app.services.prediction_service import get_forecast, get_metrics

@public_bp.before_request
@login_required
@verified_required
def require_auth():
    pass

@public_bp.route('/dashboard')
def dashboard():
    my_requests_count = BloodRequest.query.filter_by(user_id=current_user.id).count()
    my_recent_requests = BloodRequest.query.filter_by(user_id=current_user.id).order_by(BloodRequest.created_at.desc()).limit(5).all()
    
    total_stock = db.session.query(db.func.sum(BloodInventory.current_units)).scalar() or 0
    upcoming_camps = DonationCamp.query.filter(DonationCamp.date > datetime.datetime.utcnow(), DonationCamp.status == 'planned').count()
    
    donor = Donor.query.filter_by(user_id=current_user.id).first()
    
    # Quick inventory overview
    inventory = BloodInventory.query.filter_by(component='Whole Blood').all()
    
    return render_template('public/dashboard.html', 
                          my_requests_count=my_requests_count,
                          my_recent_requests=my_recent_requests,
                          total_stock=total_stock,
                          upcoming_camps=upcoming_camps,
                          donor=donor,
                          inventory=inventory)

@public_bp.route('/blood-availability')
def blood_availability():
    search = request.args.get('search', '').upper()
    inventory = get_all_inventory()
    
    if search:
        inventory = [i for i in inventory if search in i.blood_type]
        
    # Group by component
    whole_blood = [i for i in inventory if i.component == 'Whole Blood']
    platelets = [i for i in inventory if i.component == 'Platelets']
    plasma = [i for i in inventory if i.component == 'Plasma']
    
    return render_template('public/blood_availability.html', 
                          whole_blood=whole_blood, platelets=platelets, plasma=plasma, search=search)

@public_bp.route('/blood-request', methods=['GET', 'POST'])
def blood_request():
    if request.method == 'POST':
        patient_name = request.form.get('patient_name')
        hospital_name = request.form.get('hospital_name')
        blood_group = request.form.get('blood_group')
        units_required = int(request.form.get('units_required', 1))
        priority = request.form.get('priority', 'normal')
        emergency_level = request.form.get('emergency_level')
        
        cert_file = request.files.get('doctor_certificate')
        cert_filename = None
        
        if cert_file and cert_file.filename != '':
            folder = os.path.join(current_app.root_path, 'static', 'uploads', 'certificates')
            os.makedirs(folder, exist_ok=True)
            cert_filename = save_uploaded_file(cert_file, folder)
            
        req = BloodRequest(
            user_id=current_user.id,
            patient_name=patient_name,
            hospital_name=hospital_name,
            blood_group=blood_group,
            units_required=units_required,
            priority=priority,
            emergency_level=emergency_level,
            doctor_certificate=cert_filename
        )
        db.session.add(req)
        db.session.commit()
        
        # Notify staff
        notify_staff('New Blood Request', f'New {priority} request for {units_required} units of {blood_group}.', 'warning' if priority in ['urgent', 'critical'] else 'info')
        
        log_activity(current_user.id, f'Submitted blood request for {units_required} units of {blood_group}')
        flash('Blood request submitted successfully. We will process it shortly.', 'success')
        return redirect(url_for('public.my_requests'))
        
    return render_template('public/blood_request.html')

@public_bp.route('/my-requests')
def my_requests():
    requests = BloodRequest.query.filter_by(user_id=current_user.id).order_by(BloodRequest.created_at.desc()).all()
    return render_template('public/my_requests.html', requests=requests)

@public_bp.route('/register-donor', methods=['GET', 'POST'])
def register_donor_route():
    donor = Donor.query.filter_by(user_id=current_user.id).first()
    
    if request.method == 'POST':
        if donor:
            flash('You are already registered as a donor.', 'info')
            return redirect(url_for('public.register_donor_route'))
            
        weight = float(request.form.get('weight', 0))
        health_status = request.form.get('health_status')
        
        new_donor = register_donor(
            user_id=current_user.id,
            full_name=current_user.full_name,
            blood_group=current_user.blood_group,
            phone=current_user.phone,
            email=current_user.email,
            weight=weight,
            gender=current_user.gender,
            age=current_user.age,
            district=current_user.district
        )
        
        # Additional info
        new_donor.health_status = health_status
        db.session.commit()
        
        log_activity(current_user.id, f'Registered as donor: {new_donor.donor_id}')
        flash('Successfully registered as a donor! Thank you for your pledge.', 'success')
        return redirect(url_for('public.register_donor_route'))
        
    return render_template('public/register_donor.html', donor=donor)

@public_bp.route('/donation-camps')
def donation_camps():
    camps = DonationCamp.query.filter(DonationCamp.status.in_(['planned', 'active'])).order_by(DonationCamp.date).all()
    return render_template('public/donation_camps.html', camps=camps)

@public_bp.route('/notifications')
def notifications():
    notifs = Notification.query.filter_by(user_id=current_user.id).order_by(Notification.created_at.desc()).all()
    return render_template('public/notifications.html', notifications=notifs)

@public_bp.route('/notifications/<int:id>/read', methods=['POST'])
def read_notification(id):
    mark_as_read(id, current_user.id)
    return redirect(request.referrer or url_for('public.notifications'))

@public_bp.route('/notifications/mark-all-read')
def read_all_notifications():
    mark_all_read(current_user.id)
    flash('All notifications marked as read.', 'success')
    return redirect(url_for('public.notifications'))

@public_bp.route('/predictions')
def predictions():
    model_type = request.args.get('model', 'LightGBM')
    forecast_df = get_forecast(model_type=model_type)
    
    chart_data = {}
    if not forecast_df.empty:
        for bt in forecast_df['blood_type'].unique():
            bt_data = forecast_df[forecast_df['blood_type'] == bt].sort_values('date')
            dates = [d.strftime('%Y-%m-%d') for d in bt_data['date']]
            demands = bt_data['predicted_demand'].tolist()
            chart_data[bt] = {'dates': dates, 'demands': demands}
            
    return render_template('public/predictions.html', model_type=model_type, chart_data=chart_data)

@public_bp.route('/profile', methods=['GET', 'POST'])
def profile():
    if request.method == 'POST':
        full_name = request.form.get('full_name')
        phone = request.form.get('phone')
        blood_group = request.form.get('blood_group')
        gender = request.form.get('gender')
        age = request.form.get('age')
        district = request.form.get('district')
        state = request.form.get('state')
        
        # Profile Photo
        photo_file = request.files.get('profile_photo')
        if photo_file and photo_file.filename != '':
            folder = os.path.join(current_app.root_path, 'static', 'uploads', 'profile_photos')
            os.makedirs(folder, exist_ok=True)
            filename = save_uploaded_file(photo_file, folder)
            current_user.profile_photo = filename
            
        current_user.full_name = full_name
        current_user.phone = phone
        current_user.blood_group = blood_group
        current_user.gender = gender
        if age:
            current_user.age = int(age)
        current_user.district = district
        current_user.state = state
        
        db.session.commit()
        log_activity(current_user.id, 'Updated profile')
        flash('Profile updated successfully.', 'success')
        return redirect(url_for('public.profile'))
        
    return render_template('public/profile.html')

@public_bp.route('/change-password', methods=['GET', 'POST'])
def change_password():
    if request.method == 'POST':
        current_pwd = request.form.get('current_password')
        new_pwd = request.form.get('new_password')
        confirm_pwd = request.form.get('confirm_password')
        
        if not bcrypt.check_password_hash(current_user.password_hash, current_pwd):
            flash('Current password is incorrect.', 'danger')
            return redirect(url_for('public.change_password'))
            
        if new_pwd != confirm_pwd:
            flash('New passwords do not match.', 'danger')
            return redirect(url_for('public.change_password'))
            
        is_valid, msg = validate_password_strength(new_pwd)
        if not is_valid:
            flash(msg, 'danger')
            return redirect(url_for('public.change_password'))
            
        current_user.password_hash = bcrypt.generate_password_hash(new_pwd).decode('utf-8')
        db.session.commit()
        
        log_activity(current_user.id, 'Changed password')
        flash('Password changed successfully.', 'success')
        return redirect(url_for('public.profile'))
        
    return render_template('public/change_password.html')

@public_bp.route('/donation-history')
def donation_history():
    donor = Donor.query.filter_by(user_id=current_user.id).first()
    history = []
    if donor:
        history = DonationHistory.query.filter_by(donor_id=donor.id).order_by(DonationHistory.donation_date.desc()).all()
    return render_template('public/donation_history.html', donor=donor, history=history)
