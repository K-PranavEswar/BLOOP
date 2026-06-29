"""
Prediction history model.
"""
from datetime import datetime
from app.extensions import db


class PredictionHistory(db.Model):
    __tablename__ = 'prediction_history'

    id = db.Column(db.Integer, primary_key=True)
    model_type = db.Column(db.String(30), nullable=False)  # LightGBM, Prophet
    blood_type = db.Column(db.String(5), nullable=False)
    prediction_date = db.Column(db.DateTime, nullable=False)
    predicted_demand = db.Column(db.Integer, nullable=False)
    actual_demand = db.Column(db.Integer, nullable=True)
    lower_bound = db.Column(db.Integer, nullable=True)
    upper_bound = db.Column(db.Integer, nullable=True)
    confidence = db.Column(db.Float, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f'<PredictionHistory {self.model_type} {self.blood_type} {self.prediction_date}>'
