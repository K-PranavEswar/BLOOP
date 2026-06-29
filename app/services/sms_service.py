"""
SMS service placeholder for phone-based OTP.
Replace with Twilio/MSG91 integration in production.
"""


def send_otp_sms(phone_number, otp_code):
    """
    Send OTP via SMS.
    Currently a placeholder that logs to console.
    Replace with real SMS API (Twilio, MSG91, etc.) for production.
    """
    print(f"[SMS PLACEHOLDER] Sending OTP to {phone_number}: {otp_code}")
    print(f"[DEV OTP] Code for {phone_number}: {otp_code}")
    # In production, integrate with SMS gateway:
    # from twilio.rest import Client
    # client = Client(TWILIO_SID, TWILIO_AUTH_TOKEN)
    # client.messages.create(body=f"Your HemoPulse OTP: {otp_code}", from_=TWILIO_PHONE, to=phone_number)
    return True
