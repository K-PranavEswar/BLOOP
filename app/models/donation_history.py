"""
Donation history model.
"""
from datetime import datetime
from app.extensions import db


class DonationHistory(db.Model):
    __tablename__ = 'donation_history'

    id = db.Column(db.Integer, primary_key=True)
    donor_id = db.Column(db.Integer, db.ForeignKey('donors.id'), nullable=False)
    donation_date = db.Column(db.DateTime, default=datetime.utcnow)
    blood_group = db.Column(db.String(5), nullable=False)
    units_donated = db.Column(db.Integer, default=1)
    camp_id = db.Column(db.Integer, db.ForeignKey('donation_camps.id'), nullable=True)
    location = db.Column(db.String(200), nullable=True)
    notes = db.Column(db.Text, nullable=True)

    camp = db.relationship('DonationCamp', backref='donations_collected')

    def __repr__(self):
        return f'<DonationHistory donor={self.donor_id} date={self.donation_date}>'
