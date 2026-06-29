"""
Role-based access control decorators.
"""
from functools import wraps
from flask import abort, flash, redirect, url_for
from flask_login import current_user, login_required


def role_required(*roles):
    """
    Decorator that requires the current user to have one of the specified roles.
    Usage: @role_required('admin') or @role_required('admin', 'staff')
    """
    def decorator(f):
        @wraps(f)
        @login_required
        def decorated_function(*args, **kwargs):
            if current_user.role not in roles:
                abort(403)
            return f(*args, **kwargs)
        return decorated_function
    return decorator


def admin_required(f):
    """Shortcut decorator for admin-only routes."""
    @wraps(f)
    @login_required
    def decorated_function(*args, **kwargs):
        if current_user.role != 'admin':
            abort(403)
        return f(*args, **kwargs)
    return decorated_function


def staff_required(f):
    """Shortcut decorator for staff-only routes."""
    @wraps(f)
    @login_required
    def decorated_function(*args, **kwargs):
        if current_user.role != 'staff':
            abort(403)
        return f(*args, **kwargs)
    return decorated_function


def verified_required(f):
    """Decorator that requires the user to be verified."""
    @wraps(f)
    @login_required
    def decorated_function(*args, **kwargs):
        if not current_user.is_verified:
            flash('Please verify your account first.', 'warning')
            return redirect(url_for('auth.verify_otp'))
        return f(*args, **kwargs)
    return decorated_function
