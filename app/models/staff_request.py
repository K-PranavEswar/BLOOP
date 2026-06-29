"""
Staff registration request model.
"""
from datetime import datetime
from app.extensions import db


class StaffRequest(db.Model):
    __tablename__ = 'staff_requests'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    status = db.Column(db.String(20), default='pending')  # pending, approved, rejected, suspended
    requested_at = db.Column(db.DateTime, default=datetime.utcnow)
    reviewed_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    reviewed_at = db.Column(db.DateTime, nullable=True)
    notes = db.Column(db.Text, nullable=True)

    reviewer = db.relationship('User', foreign_keys=[reviewed_by], backref='reviewed_staff_requests')

    def __repr__(self):
        return f'<StaffRequest user_id={self.user_id} status={self.status}>'
