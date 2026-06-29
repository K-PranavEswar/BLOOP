from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, BooleanField, SelectField, IntegerField
from wtforms.validators import DataRequired, Email, EqualTo, Length, Optional, ValidationError

from app.utils.helpers import BLOOD_GROUPS, INDIAN_STATES

class LoginForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired()])
    password = PasswordField('Password', validators=[DataRequired()])
    remember_me = BooleanField('Remember Me')

class RegisterForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired(), Length(min=3, max=80)])
    full_name = StringField('Full Name', validators=[DataRequired(), Length(max=150)])
    email = StringField('Email', validators=[Optional(), Email(), Length(max=150)])
    phone = StringField('Phone', validators=[Optional(), Length(max=20)])
    password = PasswordField('Password', validators=[DataRequired(), Length(min=8)])
    confirm_password = PasswordField('Confirm Password', validators=[DataRequired(), EqualTo('password')])
    blood_group = SelectField('Blood Group', choices=[('', 'Select Blood Group')] + [(bg, bg) for bg in BLOOD_GROUPS], validators=[Optional()])
    gender = SelectField('Gender', choices=[('', 'Select Gender'), ('Male', 'Male'), ('Female', 'Female'), ('Other', 'Other')], validators=[Optional()])
    age = IntegerField('Age', validators=[Optional()])
    district = StringField('District', validators=[Optional(), Length(max=100)])
    state = SelectField('State', choices=[('', 'Select State')] + [(s, s) for s in INDIAN_STATES], validators=[Optional()])
    register_as_staff = BooleanField('Register as Staff')

    def validate(self, extra_validators=None):
        initial_validation = super(RegisterForm, self).validate()
        if not initial_validation:
            return False
        if not self.email.data and not self.phone.data:
            self.email.errors.append('Either email or phone is required.')
            self.phone.errors.append('Either email or phone is required.')
            return False
        return True

class OTPForm(FlaskForm):
    otp_code = StringField('OTP Code', validators=[DataRequired(), Length(min=4, max=6)])

class ForgotPasswordForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired()])

class ResetPasswordForm(FlaskForm):
    password = PasswordField('New Password', validators=[DataRequired(), Length(min=8)])
    confirm_password = PasswordField('Confirm Password', validators=[DataRequired(), EqualTo('password')])
