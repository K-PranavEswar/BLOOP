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
from app.services.inventory_service import get_all_inventory
from app.services.ai_risk_engine import calculate_global_risk
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
    search = request.args.get('search', '')
    global_risk = calculate_global_risk()
    
    blood_groups = global_risk['blood_groups']
    
    if search:
        search = search.upper().replace('POS', '+').replace('NEG', '-')
        blood_groups = [bg for bg in blood_groups if search in bg['blood_group']]
        
    return render_template('public/blood_availability.html', 
                          blood_groups=blood_groups,
                          search=search)

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
    from app.services.prediction_service import get_chart_data
    chart_data = get_chart_data(model_type=model_type, past_days=14)
            
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
        address = request.form.get('address')
        
        # Phone Validation
        if phone and len(phone) < 10:
            flash('Phone number must be at least 10 digits.', 'danger')
            return redirect(url_for('public.profile'))
        
        # Profile Photo
        photo_file = request.files.get('profile_photo')
        if photo_file and photo_file.filename != '':
            # Validate format
            allowed_extensions = {'png', 'jpg', 'jpeg'}
            if '.' not in photo_file.filename or photo_file.filename.rsplit('.', 1)[1].lower() not in allowed_extensions:
                flash('Invalid image format. Only JPG, JPEG, and PNG are allowed.', 'danger')
                return redirect(url_for('public.profile'))
                
            # Validate size (Max 2MB)
            photo_file.seek(0, os.SEEK_END)
            size = photo_file.tell()
            photo_file.seek(0)
            if size > 2 * 1024 * 1024:
                flash('File too large. Maximum size is 2 MB.', 'danger')
                return redirect(url_for('public.profile'))
                
            try:
                ext = photo_file.filename.rsplit('.', 1)[1].lower()
                timestamp = datetime.datetime.utcnow().strftime('%Y%m%d_%H%M%S')
                filename = f"user_{current_user.id}_{timestamp}.{ext}"
                
                folder = os.path.join(current_app.root_path, 'static', 'uploads', 'profile_photos')
                os.makedirs(folder, exist_ok=True)
                filepath = os.path.join(folder, filename)
                
                # Delete old photo if exists
                if current_user.profile_photo:
                    # current_user.profile_photo might be just filename or full relative path depending on old code
                    # Let's handle both
                    old_file = current_user.profile_photo.split('/')[-1] if '/' in current_user.profile_photo else current_user.profile_photo
                    old_path = os.path.join(folder, old_file)
                    if os.path.exists(old_path):
                        try:
                            os.remove(old_path)
                        except Exception as e:
                            print(f"[WARNING] Could not delete old photo: {e}")
                
                photo_file.save(filepath)
                # Save only the filename to the database as requested
                current_user.profile_photo = filename
                
                print(f"[UPLOAD]\nUser: {current_user.username.upper()}\nImage Saved: {filename}")
                flash('Profile photo updated successfully.', 'success')
            except Exception as e:
                print(f"[ERROR] Upload failed: {e}")
                flash('Upload failed due to a server error.', 'danger')
                return redirect(url_for('public.profile'))
            
        current_user.full_name = full_name
        current_user.phone = phone
        current_user.blood_group = blood_group
        current_user.gender = gender
        if age:
            current_user.age = int(age)
        current_user.district = district
        current_user.state = state
        current_user.address = address
        
        db.session.commit()
        log_activity(current_user.id, 'Updated profile')
        flash('Profile updated successfully.', 'success')
        return redirect(url_for('public.profile'))
        
    from app.utils.helpers import INDIAN_STATES, BLOOD_GROUPS
    return render_template('public/profile.html', indian_states=INDIAN_STATES, blood_groups=BLOOD_GROUPS)

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
