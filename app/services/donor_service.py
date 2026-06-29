"""
Donor service – donor registration, QR codes, eligibility.
"""
import os
import qrcode
from io import BytesIO
from datetime import datetime, timedelta
from flask import current_app
from app.extensions import db
from app.models.donor import Donor
from app.models.donation_history import DonationHistory
from app.utils.helpers import generate_donor_id


def register_donor(user_id=None, full_name='', blood_group='', phone=None, email=None,
                   weight=None, gender=None, age=None, district=None):
    """Register a new blood donor."""
    donor_id = generate_donor_id()
    while Donor.query.filter_by(donor_id=donor_id).first():
        donor_id = generate_donor_id()

    donor = Donor(
        user_id=user_id,
        donor_id=donor_id,
        full_name=full_name,
        blood_group=blood_group,
        phone=phone,
        email=email,
        weight=weight,
        gender=gender,
        age=age,
        district=district,
        eligibility_status='eligible',
        health_status='healthy'
    )
    db.session.add(donor)
    db.session.commit()

    # Generate QR code
    generate_qr_code(donor)
    return donor


def generate_qr_code(donor):
    """Generate a QR code for the donor card."""
    qr_data = f"HemoPulse Donor Card\nID: {donor.donor_id}\nName: {donor.full_name}\nBlood Group: {donor.blood_group}\nRegistered: {donor.created_at.strftime('%Y-%m-%d')}"

    qr = qrcode.QRCode(version=1, box_size=10, border=4)
    qr.add_data(qr_data)
    qr.make(fit=True)
    img = qr.make_image(fill_color='#dc2626', back_color='white')

    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    qr_dir = os.path.join(base_dir, 'static', 'uploads', 'qr_codes')
    os.makedirs(qr_dir, exist_ok=True)
    qr_filename = f'donor_{donor.donor_id}.png'
    qr_path = os.path.join(qr_dir, qr_filename)
    img.save(qr_path)

    donor.qr_code_path = f'uploads/qr_codes/{qr_filename}'
    db.session.commit()
    return donor.qr_code_path


def record_donation(donor_id, blood_group, units=1, camp_id=None, location=None):
    """Record a blood donation and update donor eligibility."""
    donor = Donor.query.get(donor_id)
    if not donor:
        return None, 'Donor not found.'

    donation = DonationHistory(
        donor_id=donor.id,
        blood_group=blood_group,
        units_donated=units,
        camp_id=camp_id,
        location=location,
        donation_date=datetime.utcnow()
    )
    db.session.add(donation)

    donor.last_donation_date = datetime.utcnow()
    donor.update_eligibility()
    db.session.commit()

    return donation, 'Donation recorded successfully.'


def check_eligibility(donor_id):
    """Check if a donor is eligible to donate."""
    donor = Donor.query.get(donor_id)
    if not donor:
        return False, 'Donor not found.'

    donor.update_eligibility()
    db.session.commit()

    if donor.health_status != 'healthy':
        return False, f'Donor health status: {donor.health_status}'

    if donor.eligibility_status != 'eligible':
        days_left = (donor.next_eligible_date - datetime.utcnow()).days if donor.next_eligible_date else 0
        return False, f'Not eligible. {days_left} days until next eligible date.'

    return True, 'Donor is eligible to donate.'


def get_donation_history(donor_id):
    """Get donation history for a donor."""
    return DonationHistory.query.filter_by(donor_id=donor_id) \
        .order_by(DonationHistory.donation_date.desc()).all()
