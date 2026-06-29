"""
Blood request model – public users requesting blood.
"""
from datetime import datetime
from app.extensions import db


class BloodRequest(db.Model):
    __tablename__ = 'blood_requests'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    patient_name = db.Column(db.String(150), nullable=False)
    hospital_name = db.Column(db.String(200), nullable=False)
    blood_group = db.Column(db.String(5), nullable=False)
    units_required = db.Column(db.Integer, nullable=False, default=1)
    priority = db.Column(db.String(20), default='normal')  # normal, urgent, critical
    emergency_level = db.Column(db.String(20), nullable=True)
    doctor_certificate = db.Column(db.String(255), nullable=True)
    status = db.Column(db.String(20), default='pending')  # pending, approved, rejected, completed
    approved_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    notes = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    approver = db.relationship('User', foreign_keys=[approved_by])

    def __repr__(self):
        return f'<BloodRequest {self.blood_group} x{self.units_required} status={self.status}>'
