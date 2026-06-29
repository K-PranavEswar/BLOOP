from datetime import datetime, timedelta
from flask import render_template, redirect, url_for, flash, request, session
from flask_login import login_user, logout_user, current_user

from app.extensions import db, bcrypt
from app.auth import auth_bp
from app.auth.forms import LoginForm, RegisterForm, OTPForm, ForgotPasswordForm, ResetPasswordForm
from app.models import User, StaffRequest, OTPVerification, Notification
from app.utils.helpers import generate_otp, validate_password_strength, log_activity
from app.services.email_service import send_otp_email
from app.services.sms_service import send_otp_sms

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
        
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(username=form.username.data).first()
        
        if user:
            # Check account lock
            if user.is_account_locked():
                flash(f'Account locked due to multiple failed attempts. Try again after {user.locked_until.strftime("%H:%M")}', 'danger')
                return render_template('auth/login.html', form=form)
                
            # Check password
            if bcrypt.check_password_hash(user.password_hash, form.password.data):
                if not user.is_verified:
                    session['pending_verification_user_id'] = user.id
                    flash('Please verify your account first.', 'warning')
                    _send_otp_to_user(user, 'verification')
                    return redirect(url_for('auth.verify_otp'))
                    
                if not user.is_active:
                    flash('Your account has been suspended. Please contact support.', 'danger')
                    return render_template('auth/login.html', form=form)
                    
                # Success
                user.failed_login_attempts = 0
                user.locked_until = None
                db.session.commit()
                
                # Check pending staff request
                if user.role == 'public' and user.staff_request and user.staff_request.status == 'pending':
                    flash('Your staff registration is pending approval by an admin.', 'info')
                
                login_user(user, remember=form.remember_me.data)
                log_activity(user.id, 'User login', ip_address=request.remote_addr)
                
                next_page = request.args.get('next')
                if not next_page or not next_page.startswith('/'):
                    if user.role == 'admin':
                        next_page = url_for('admin.dashboard')
                    elif user.role == 'staff':
                        next_page = url_for('staff.dashboard')
                    else:
                        next_page = url_for('public.dashboard')
                return redirect(next_page)
            else:
                user.failed_login_attempts += 1
                if user.failed_login_attempts >= 5:
                    user.locked_until = datetime.utcnow() + timedelta(minutes=15)
                db.session.commit()
                
        flash('Invalid username or password.', 'danger')
        
    return render_template('auth/login.html', form=form)

@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
        
    form = RegisterForm()
    if form.validate_on_submit():
        if User.query.filter_by(username=form.username.data).first():
            flash('Username already exists. Please choose a different one.', 'danger')
            return render_template('auth/register.html', form=form)
            
        if form.email.data and User.query.filter_by(email=form.email.data).first():
            flash('Email already registered.', 'danger')
            return render_template('auth/register.html', form=form)
            
        if form.phone.data and User.query.filter_by(phone=form.phone.data).first():
            flash('Phone number already registered.', 'danger')
            return render_template('auth/register.html', form=form)
            
        is_valid, msg = validate_password_strength(form.password.data)
        if not is_valid:
            flash(msg, 'danger')
            return render_template('auth/register.html', form=form)
            
        hashed_password = bcrypt.generate_password_hash(form.password.data).decode('utf-8')
        
        user = User(
            username=form.username.data,
            full_name=form.full_name.data,
            email=form.email.data or None,
            phone=form.phone.data or None,
            password_hash=hashed_password,
            blood_group=form.blood_group.data or None,
            gender=form.gender.data or None,
            age=form.age.data or None,
            district=form.district.data or None,
            state=form.state.data or None,
            is_verified=False
        )
        db.session.add(user)
        db.session.commit()
        
        if form.register_as_staff.data:
            staff_req = StaffRequest(user_id=user.id)
            db.session.add(staff_req)
            db.session.commit()
            
        _send_otp_to_user(user, 'verification')
        session['pending_verification_user_id'] = user.id
        flash('Registration successful! Please verify your account with the OTP sent to you.', 'success')
        return redirect(url_for('auth.verify_otp'))
        
    return render_template('auth/register.html', form=form)

@auth_bp.route('/verify-otp', methods=['GET', 'POST'])
def verify_otp():
    if current_user.is_authenticated and current_user.is_verified:
        return redirect(url_for('index'))
        
    user_id = session.get('pending_verification_user_id')
    if not user_id and current_user.is_authenticated:
        user_id = current_user.id
        
    if not user_id:
        flash('Session expired. Please log in again.', 'warning')
        return redirect(url_for('auth.login'))
        
    user = User.query.get(user_id)
    if not user:
        return redirect(url_for('auth.login'))
        
    form = OTPForm()
    if form.validate_on_submit():
        otp_record = OTPVerification.query.filter_by(
            user_id=user.id, 
            otp_code=form.otp_code.data,
            is_used=False
        ).order_by(OTPVerification.created_at.desc()).first()
        
        if otp_record and otp_record.is_valid:
            otp_record.is_used = True
            
            if otp_record.otp_type == 'verification':
                user.is_verified = True
                
                notif = Notification(
                    user_id=user.id,
                    title='Welcome to HemoPulse AI Pro',
                    message='Your account has been successfully verified.',
                    type='success'
                )
                db.session.add(notif)
                db.session.commit()
                
                log_activity(user.id, 'Account verified')
                flash('Account verified successfully! You can now log in.', 'success')
                
                # Automatically login after verification if not logged in
                if not current_user.is_authenticated:
                    login_user(user)
                    session.pop('pending_verification_user_id', None)
                    return redirect(url_for('index'))
                    
                session.pop('pending_verification_user_id', None)
                return redirect(url_for('index'))
                
            elif otp_record.otp_type == 'password_reset':
                db.session.commit()
                session['reset_password_user_id'] = user.id
                return redirect(url_for('auth.reset_password'))
                
        flash('Invalid or expired OTP.', 'danger')
        
    return render_template('auth/verify_otp.html', form=form, user=user)

@auth_bp.route('/resend-otp')
def resend_otp():
    user_id = session.get('pending_verification_user_id')
    if not user_id and current_user.is_authenticated:
        user_id = current_user.id
        
    if not user_id:
        flash('Session expired.', 'warning')
        return redirect(url_for('auth.login'))
        
    user = User.query.get(user_id)
    if user:
        otp_type = request.args.get('type', 'verification')
        _send_otp_to_user(user, otp_type)
        flash('A new OTP has been sent.', 'info')
        
    return redirect(url_for('auth.verify_otp'))

@auth_bp.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
        
    form = ForgotPasswordForm()
    if form.validate_on_submit():
        user = User.query.filter_by(username=form.username.data).first()
        if user:
            _send_otp_to_user(user, 'password_reset')
            session['pending_verification_user_id'] = user.id
            flash('If the account exists, an OTP has been sent for password reset.', 'info')
            return redirect(url_for('auth.verify_otp'))
        else:
            # Don't reveal account existence
            flash('If the account exists, an OTP has been sent for password reset.', 'info')
            
    return render_template('auth/forgot_password.html', form=form)

@auth_bp.route('/reset-password', methods=['GET', 'POST'])
def reset_password():
    user_id = session.get('reset_password_user_id')
    if not user_id:
        flash('Unauthorized access.', 'danger')
        return redirect(url_for('auth.login'))
        
    user = User.query.get(user_id)
    if not user:
        return redirect(url_for('auth.login'))
        
    form = ResetPasswordForm()
    if form.validate_on_submit():
        is_valid, msg = validate_password_strength(form.password.data)
        if not is_valid:
            flash(msg, 'danger')
            return render_template('auth/reset_password.html', form=form)
            
        user.password_hash = bcrypt.generate_password_hash(form.password.data).decode('utf-8')
        user.failed_login_attempts = 0
        user.locked_until = None
        db.session.commit()
        
        log_activity(user.id, 'Password reset')
        session.pop('reset_password_user_id', None)
        session.pop('pending_verification_user_id', None)
        
        flash('Password reset successfully. You can now log in.', 'success')
        return redirect(url_for('auth.login'))
        
    return render_template('auth/reset_password.html', form=form)

@auth_bp.route('/logout')
def logout():
    if current_user.is_authenticated:
        log_activity(current_user.id, 'User logout', ip_address=request.remote_addr)
        logout_user()
    session.clear()
    flash('You have been logged out.', 'info')
    return redirect(url_for('auth.login'))

def _send_otp_to_user(user, purpose):
    """Generate and send OTP with debug."""

    otp_code = generate_otp(4)
    expires_at = datetime.utcnow() + timedelta(minutes=5)

    otp_record = OTPVerification(
        user_id=user.id,
        otp_code=otp_code,
        otp_type=purpose,
        expires_at=expires_at
    )

    db.session.add(otp_record)
    db.session.commit()

    print("=" * 60)
    print("SEND OTP FUNCTION CALLED")
    print("User ID :", user.id)
    print("Username:", user.username)
    print("Email   :", user.email)
    print("Phone   :", user.phone)
    print("OTP     :", otp_code)
    print("=" * 60)

    if user.email:
        try:
            result = send_otp_email(user.email, otp_code, purpose)
            print("EMAIL RESULT :", result)
        except Exception as e:
            import traceback
            traceback.print_exc()

    elif user.phone:
        print("Sending SMS...")
        send_otp_sms(user.phone, otp_code)
