"""
Helper utilities.
"""
import os
import re
import random
import string
from datetime import datetime
from werkzeug.utils import secure_filename
from flask import current_app


def generate_otp(length=4):
    """Generate a random numeric OTP."""
    return ''.join(random.choices(string.digits, k=length))


def generate_donor_id():
    """Generate a unique donor ID like HMP-DONOR-XXXXX."""
    random_part = ''.join(random.choices(string.digits, k=5))
    return f'HMP-DONOR-{random_part}'


def validate_password_strength(password):
    """
    Validate password meets requirements:
    - Min 8 characters, uppercase, lowercase, number, special character
    Returns (is_valid, message)
    """
    if len(password) < 8:
        return False, 'Password must be at least 8 characters long.'
    if not re.search(r'[A-Z]', password):
        return False, 'Password must contain at least one uppercase letter.'
    if not re.search(r'[a-z]', password):
        return False, 'Password must contain at least one lowercase letter.'
    if not re.search(r'[0-9]', password):
        return False, 'Password must contain at least one number.'
    if not re.search(r'[!@#$%^&*(),.?":{}|<>]', password):
        return False, 'Password must contain at least one special character.'
    return True, 'Password is strong.'


def allowed_file(filename, allowed_extensions):
    """Check if a file extension is allowed."""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in allowed_extensions


def save_uploaded_file(file, subfolder='profile_photos'):
    """Save an uploaded file and return the relative path."""
    if not file or not file.filename:
        return None

    upload_dir = os.path.join(current_app.config['UPLOAD_FOLDER'], subfolder)
    os.makedirs(upload_dir, exist_ok=True)

    filename = secure_filename(file.filename)
    timestamp = datetime.utcnow().strftime('%Y%m%d%H%M%S')
    unique_filename = f'{timestamp}_{filename}'
    filepath = os.path.join(upload_dir, unique_filename)
    file.save(filepath)

    return f'uploads/{subfolder}/{unique_filename}'


def log_activity(user_id, action, description=None, ip_address=None):
    """Log an activity to the database."""
    from app.extensions import db
    from app.models.activity_log import ActivityLog

    log = ActivityLog(
        user_id=user_id,
        action=action,
        description=description,
        ip_address=ip_address
    )
    db.session.add(log)
    db.session.commit()


def format_datetime(dt):
    """Format datetime for display."""
    if dt is None:
        return 'N/A'
    return dt.strftime('%b %d, %Y %I:%M %p')


INDIAN_STATES = [
    'Andhra Pradesh', 'Arunachal Pradesh', 'Assam', 'Bihar', 'Chhattisgarh',
    'Goa', 'Gujarat', 'Haryana', 'Himachal Pradesh', 'Jharkhand', 'Karnataka',
    'Kerala', 'Madhya Pradesh', 'Maharashtra', 'Manipur', 'Meghalaya', 'Mizoram',
    'Nagaland', 'Odisha', 'Punjab', 'Rajasthan', 'Sikkim', 'Tamil Nadu',
    'Telangana', 'Tripura', 'Uttar Pradesh', 'Uttarakhand', 'West Bengal',
    'Delhi', 'Chandigarh', 'Puducherry', 'Jammu and Kashmir', 'Ladakh'
]

BLOOD_GROUPS = ['O+', 'O-', 'A+', 'A-', 'B+', 'B-', 'AB+', 'AB-']
