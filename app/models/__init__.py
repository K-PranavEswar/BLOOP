"""
Models package – import all models for clean access.
"""
from app.models.user import User
from app.models.staff_request import StaffRequest
from app.models.blood_inventory import BloodInventory
from app.models.blood_request import BloodRequest
from app.models.donor import Donor
from app.models.donation_history import DonationHistory
from app.models.donation_camp import DonationCamp
from app.models.otp import OTPVerification
from app.models.notification import Notification
from app.models.prediction_history import PredictionHistory
from app.models.activity_log import ActivityLog
from app.models.ai_analysis_log import AIAnalysisLog
from app.models.online_session import OnlineSession

__all__ = [
    'User', 'StaffRequest', 'BloodInventory', 'BloodRequest',
    'Donor', 'DonationHistory', 'DonationCamp', 'OTPVerification',
    'Notification', 'PredictionHistory', 'ActivityLog', 'AIAnalysisLog',
    'OnlineSession'
]
