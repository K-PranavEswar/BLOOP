"""
Donor model – blood donor registration and eligibility tracking.
"""
from datetime import datetime, timedelta
from app.extensions import db


class Donor(db.Model):
    __tablename__ = 'donors'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    donor_id = db.Column(db.String(20), unique=True, nullable=False)  # HMP-DONOR-XXXXX
    full_name = db.Column(db.String(150), nullable=False)
    blood_group = db.Column(db.String(5), nullable=False)
    phone = db.Column(db.String(20), nullable=True)
    email = db.Column(db.String(150), nullable=True)
    last_donation_date = db.Column(db.DateTime, nullable=True)
    weight = db.Column(db.Float, nullable=True)
    health_status = db.Column(db.String(20), default='healthy')  # healthy, deferred, rejected
    eligibility_status = db.Column(db.String(20), default='eligible')  # eligible, not_eligible, pending
    next_eligible_date = db.Column(db.DateTime, nullable=True)
    qr_code_path = db.Column(db.String(255), nullable=True)
    gender = db.Column(db.String(10), nullable=True)
    age = db.Column(db.Integer, nullable=True)
    district = db.Column(db.String(100), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    donations = db.relationship('DonationHistory', backref='donor', lazy=True, order_by='DonationHistory.donation_date.desc()')

    def update_eligibility(self):
        """Update eligibility based on last donation date (56-day gap required)."""
        if self.last_donation_date:
            self.next_eligible_date = self.last_donation_date + timedelta(days=56)
            if datetime.utcnow() >= self.next_eligible_date:
                self.eligibility_status = 'eligible'
            else:
                self.eligibility_status = 'not_eligible'
        else:
            self.eligibility_status = 'eligible'
            self.next_eligible_date = None

    def __repr__(self):
        return f'<Donor {self.donor_id} {self.blood_group}>'
