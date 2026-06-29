"""
HemoPulse AI Pro – Flask Application Factory.
"""
import os
from flask import Flask, redirect, url_for, render_template
from flask_login import current_user

from config import config_by_name


def create_app(config_name=None):
    """Create and configure the Flask application."""
    if config_name is None:
        config_name = os.environ.get('FLASK_ENV', 'development')

    app = Flask(__name__,
                template_folder='templates',
                static_folder='static')

    app.config.from_object(config_by_name.get(config_name, config_by_name['default']))

    # Ensure required directories exist
    os.makedirs(app.config.get('UPLOAD_FOLDER', 'app/static/uploads'), exist_ok=True)
    os.makedirs(os.path.join(app.config.get('UPLOAD_FOLDER', 'app/static/uploads'), 'profile_photos'), exist_ok=True)
    os.makedirs(os.path.join(app.config.get('UPLOAD_FOLDER', 'app/static/uploads'), 'certificates'), exist_ok=True)
    os.makedirs(os.path.join(app.config.get('UPLOAD_FOLDER', 'app/static/uploads'), 'qr_codes'), exist_ok=True)

    # Initialize extensions
    from app.extensions import db, login_manager, bcrypt, mail, csrf
    db.init_app(app)
    login_manager.init_app(app)
    bcrypt.init_app(app)
    mail.init_app(app)
    csrf.init_app(app)

    # User loader for Flask-Login
    from app.models.user import User

    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))

    # Register blueprints
    from app.auth import auth_bp
    from app.admin import admin_bp
    from app.staff import staff_bp
    from app.public import public_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(admin_bp, url_prefix='/admin')
    app.register_blueprint(staff_bp, url_prefix='/staff')
    app.register_blueprint(public_bp)

    # Context processor for templates
    @app.context_processor
    def inject_globals():
        notif_count = 0
        notifications = []
        if current_user.is_authenticated:
            from app.services.notification_service import get_unread_count, get_notifications
            notif_count = get_unread_count(current_user.id)
            notifications = get_notifications(current_user.id, limit=5)
        return dict(
            notif_count=notif_count,
            recent_notifications=notifications,
            app_name='HemoPulse AI Pro'
        )

    # Root route
    @app.route('/')
    def index():
        if current_user.is_authenticated:
            if current_user.role == 'admin':
                return redirect(url_for('admin.dashboard'))
            elif current_user.role == 'staff':
                return redirect(url_for('staff.dashboard'))
            else:
                return redirect(url_for('public.dashboard'))
        return render_template('landing.html')

    # Error handlers
    @app.errorhandler(403)
    def forbidden(e):
        return render_template('errors/403.html'), 403

    @app.errorhandler(404)
    def not_found(e):
        return render_template('errors/404.html'), 404

    @app.errorhandler(500)
    def server_error(e):
        return render_template('errors/500.html'), 500

    # Create tables and seed data on first run
    with app.app_context():
        db.create_all()
        _seed_initial_data(db, bcrypt)

    return app


def _seed_initial_data(db, bcrypt):
    """Seed default admin and inventory on first run."""
    from app.models.user import User
    from app.services.inventory_service import seed_inventory_from_csv

    # Seed admin account if none exists
    admin = User.query.filter_by(role='admin').first()
    if not admin:
        admin = User(
            username='admin',
            full_name='System Administrator',
            email='admin@hemopulse.com',
            password_hash=bcrypt.generate_password_hash('Admin@1234').decode('utf-8'),
            role='admin',
            is_active=True,
            is_verified=True,
            blood_group='O+',
            gender='Other',
            age=30,
            state='Delhi',
            district='New Delhi'
        )
        db.session.add(admin)
        db.session.commit()
        print("[SEED] Default admin created: admin / Admin@1234")

    # Seed inventory from CSV
    seed_inventory_from_csv()
