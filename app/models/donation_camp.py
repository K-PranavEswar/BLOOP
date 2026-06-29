"""
Donation camp model.
"""
from datetime import datetime
from app.extensions import db


class DonationCamp(db.Model):
    __tablename__ = 'donation_camps'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    location = db.Column(db.String(300), nullable=False)
    date = db.Column(db.DateTime, nullable=False)
    target_blood_group = db.Column(db.String(5), nullable=True)  # NULL = all groups
    target_units = db.Column(db.Integer, default=50)
    collected_units = db.Column(db.Integer, default=0)
    priority = db.Column(db.String(20), default='MEDIUM')  # CRITICAL, HIGH, MEDIUM, LOW
    expected_success_rate = db.Column(db.Float, default=0.75)
    status = db.Column(db.String(20), default='planned')  # planned, active, completed, cancelled
    target_donors = db.Column(db.Integer, default=0)
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    creator = db.relationship('User', backref='created_camps')

    @property
    def progress_percentage(self):
        if self.target_units <= 0:
            return 0
        return min(100, int((self.collected_units / self.target_units) * 100))

    def __repr__(self):
        return f'<DonationCamp {self.name} on {self.date}>'
