"""
OTP verification model.
"""
from datetime import datetime, timedelta
from app.extensions import db


class OTPVerification(db.Model):
    __tablename__ = 'otp_verification'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    otp_code = db.Column(db.String(6), nullable=False)
    otp_type = db.Column(db.String(20), nullable=False)  # email, phone, password_reset
    expires_at = db.Column(db.DateTime, nullable=False)
    is_used = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship('User', backref='otps')

    @property
    def is_expired(self):
        return datetime.utcnow() > self.expires_at

    @property
    def is_valid(self):
        return not self.is_used and not self.is_expired

    def __repr__(self):
        return f'<OTP user_id={self.user_id} type={self.otp_type}>'
