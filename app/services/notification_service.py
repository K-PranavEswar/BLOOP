"""
Notification service for creating and managing in-app notifications.
"""
from app.extensions import db
from app.models.notification import Notification


def create_notification(user_id, title, message, notif_type='info', link=None):
    """Create a new notification for a user."""
    notif = Notification(
        user_id=user_id,
        title=title,
        message=message,
        type=notif_type,
        link=link
    )
    db.session.add(notif)
    db.session.commit()
    return notif


def get_unread_count(user_id):
    """Get count of unread notifications for a user."""
    return Notification.query.filter_by(user_id=user_id, is_read=False).count()


def get_notifications(user_id, limit=20):
    """Get recent notifications for a user."""
    return Notification.query.filter_by(user_id=user_id) \
        .order_by(Notification.created_at.desc()) \
        .limit(limit).all()


def mark_as_read(notification_id, user_id):
    """Mark a notification as read."""
    notif = Notification.query.filter_by(id=notification_id, user_id=user_id).first()
    if notif:
        notif.is_read = True
        db.session.commit()
    return notif


def mark_all_read(user_id):
    """Mark all notifications as read for a user."""
    Notification.query.filter_by(user_id=user_id, is_read=False) \
        .update({'is_read': True})
    db.session.commit()


def notify_admins(title, message, notif_type='info', link=None):
    """Send notification to all admin users."""
    from app.models.user import User
    admins = User.query.filter_by(role='admin').all()
    for admin in admins:
        create_notification(admin.id, title, message, notif_type, link)


def notify_staff(title, message, notif_type='info', link=None):
    """Send notification to all active staff."""
    from app.models.user import User
    staff_members = User.query.filter_by(role='staff', is_active=True).all()
    for staff in staff_members:
        create_notification(staff.id, title, message, notif_type, link)
