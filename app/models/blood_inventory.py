"""
Blood inventory model – tracks stock levels for each blood type and component.
"""
from datetime import datetime
from app.extensions import db


class BloodInventory(db.Model):
    __tablename__ = 'blood_inventory'

    id = db.Column(db.Integer, primary_key=True)
    blood_type = db.Column(db.String(5), nullable=False)  # O+, O-, A+, A-, B+, B-, AB+, AB-
    component = db.Column(db.String(30), default='Whole Blood')  # Whole Blood, Platelets, Plasma
    current_units = db.Column(db.Integer, default=0)
    max_capacity = db.Column(db.Integer, default=200)
    safety_stock = db.Column(db.Integer, default=20)
    last_updated = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    @property
    def fill_percentage(self):
        if self.max_capacity <= 0:
            return 0
        return min(100, int((self.current_units / self.max_capacity) * 100))

    @property
    def status(self):
        if self.current_units < self.safety_stock:
            return 'CRITICAL'
        elif self.current_units < self.safety_stock * 1.5:
            return 'LOW'
        return 'OK'

    def __repr__(self):
        return f'<BloodInventory {self.blood_type} {self.component}: {self.current_units} units>'
