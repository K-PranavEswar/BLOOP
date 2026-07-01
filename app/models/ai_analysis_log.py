from app.extensions import db
from datetime import datetime
import json

class AIAnalysisLog(db.Model):
    __tablename__ = 'ai_analysis_logs'
    
    id = db.Column(db.Integer, primary_key=True)
    blood_group = db.Column(db.String(5), nullable=True) # None for global
    risk_level = db.Column(db.String(20), nullable=False)
    
    # Store the python calculated raw JSON string
    prediction_data = db.Column(db.Text, nullable=False)
    
    # Store the Gemini/Rule-based structured output JSON string
    recommendation_data = db.Column(db.Text, nullable=False)
    
    model_used = db.Column(db.String(50), nullable=False)
    confidence = db.Column(db.Integer, nullable=False)
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def get_prediction_dict(self):
        try:
            return json.loads(self.prediction_data)
        except:
            return {}
            
    def get_recommendation_dict(self):
        try:
            return json.loads(self.recommendation_data)
        except:
            return {}
