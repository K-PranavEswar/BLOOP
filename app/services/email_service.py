"""
Email service for sending OTPs and notifications.
"""
from flask import current_app
from flask_mail import Message
from app.extensions import mail


def send_otp_email(to_email, otp_code, purpose='verification'):
    """Send OTP via email using Flask-Mail."""
    subject_map = {
        'verification': 'HemoPulse AI – Verify Your Account',
        'password_reset': 'HemoPulse AI – Password Reset OTP',
        'profile_update': 'HemoPulse AI – Confirm Profile Change'
    }
    subject = subject_map.get(purpose, 'HemoPulse AI – OTP Verification')

    html_body = f"""
    <div style="font-family: 'Segoe UI', Arial, sans-serif; max-width: 480px; margin: 0 auto;
                background: #1a1b2e; border-radius: 16px; overflow: hidden; border: 1px solid #2d2e4a;">
        <div style="background: linear-gradient(135deg, #dc2626 0%, #991b1b 100%); padding: 32px; text-align: center;">
            <h1 style="color: #fff; margin: 0; font-size: 24px;">🩸 HemoPulse AI</h1>
            <p style="color: rgba(255,255,255,0.8); margin: 8px 0 0; font-size: 13px;">
                Intelligent Blood Bank Management System</p>
        </div>
        <div style="padding: 32px; text-align: center;">
            <p style="color: #cbd5e1; font-size: 15px; margin: 0 0 24px;">
                Your one-time verification code is:</p>
            <div style="background: #0f1021; border: 2px solid #dc2626; border-radius: 12px;
                        padding: 20px; display: inline-block; min-width: 180px;">
                <span style="font-size: 36px; font-weight: 700; color: #ffffff; letter-spacing: 12px;">
                    {otp_code}</span>
            </div>
            <p style="color: #94a3b8; font-size: 13px; margin: 24px 0 0;">
                This code will expire in <strong style="color: #f87171;">5 minutes</strong>.</p>
            <p style="color: #64748b; font-size: 12px; margin: 16px 0 0;">
                If you didn't request this code, please ignore this email.</p>
        </div>
    </div>
    """

    try:
        msg = Message(subject=subject, recipients=[to_email], html=html_body)
        mail.send(msg)
        print(f"[EMAIL] OTP sent to {to_email}: {otp_code}")
        return True
    except Exception as e:
        print(f"[EMAIL FAILED] {e}")
        return False


def send_notification_email(to_email, subject, message):
    """Send a general notification email."""
    html_body = f"""
    <div style="font-family: 'Segoe UI', Arial, sans-serif; max-width: 480px; margin: 0 auto;
                background: #1a1b2e; border-radius: 16px; padding: 32px; border: 1px solid #2d2e4a;">
        <h2 style="color: #fff; margin: 0 0 16px;">🩸 HemoPulse AI</h2>
        <p style="color: #cbd5e1; font-size: 15px;">{message}</p>
        <hr style="border: 1px solid #2d2e4a; margin: 24px 0;">
        <p style="color: #64748b; font-size: 12px;">This is an automated message from HemoPulse AI Pro.</p>
    </div>
    """
    try:
        msg = Message(subject=subject, recipients=[to_email], html=html_body)
        mail.send(msg)
        return True
    except Exception as e:
        print(f"[EMAIL FAILED] {e}")
        return False
