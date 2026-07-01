from datetime import datetime
from app.extensions import db

class OnlineSession(db.Model):
    __tablename__ = 'online_sessions'

    session_id = db.Column(db.String(36), primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    ip_address = db.Column(db.String(45), nullable=True)
    user_agent = db.Column(db.String(255), nullable=True)
    login_time = db.Column(db.DateTime, default=datetime.utcnow)
    last_active = db.Column(db.DateTime, default=datetime.utcnow, index=True)

    user = db.relationship('User', backref=db.backref('online_sessions', lazy=True, cascade="all, delete-orphan"))

    def __repr__(self):
        return f'<OnlineSession {self.session_id} User:{self.user_id}>'
